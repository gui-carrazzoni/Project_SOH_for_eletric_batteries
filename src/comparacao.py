#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Confronto entre os dois esquemas de grupo: com e sem a tensao de corte.

    python comparacao.py
    python comparacao.py --sem-graficos

Le as duas arvores de esquema sob saida_nasa/cluster/ e escreve
saida_nasa/cluster/comparacao/. Roda depois de capacidade.py e modelos_area.py.

A pergunta e uma so: acrescentar a tensao de corte ao `test_condition` melhora
ou piora os grupos? Quatro medidas respondem, e nenhuma delas e opiniao.

**1. Grupos utilizaveis.** Um grupo com uma celula so nao tem dispersao interna
para medir — deixou de ser agrupamento e virou rotulo de instancia. E o defeito
que o projeto ja recusa em `battery_id`: nao existe para uma celula nova.

**2. Dispersao da taxa de fade dentro do grupo.** Um agrupamento se justifica se
as celulas dentro dele degradam no mesmo ritmo. Desvio menor e melhor — mas so
vale comparar entre grupos que tenham pelo menos duas celulas.

**3. Qualidade do ajuste do item 4.** Se o agrupamento separa regimes de verdade,
as series dentro do grupo deveriam ficar mais faceis de modelar.

**4. Concordancia do modelo vencedor.** Celulas de um mesmo regime deveriam
escolher a mesma familia de curva. Grupo que mistura vencedores esta reunindo
mecanismos de degradacao diferentes.

Dependencias: numpy, pandas, matplotlib
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# A raiz do projeto e a pasta acima de src/: e la que ficam
# cleaned_nasa_dataset/ e saida_nasa/.
RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "saida_nasa" / "cluster" / "comparacao"
ESQUEMAS = ["grupo_corrente_temperatura", "grupo_corrente_temperatura_corte"]
AREA_PADRAO = "energia"

PAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e3e2de"


def p(msg: str = "") -> None:
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "ascii"
        print(msg.encode(enc, "replace").decode(enc), flush=True)


def checar():
    faltando, mods = [], {}
    for nome in ("numpy", "pandas"):
        try:
            mods[nome] = __import__(nome)
        except ImportError:
            faltando.append(nome)
    if faltando:
        p("ERRO: faltam dependencias: " + ", ".join(faltando))
        sys.exit(1)
    for e in ESQUEMAS:
        if not (RAIZ / "saida_nasa" / "cluster" / e / "capacidade" /
                "resumo_por_grupo.csv").exists():
            p(f"ERRO: falta saida_nasa/cluster/{e}/capacidade/.")
            p("    Rode antes: python capacidade.py && python modelos_area.py")
            sys.exit(1)
    return mods


def ler(mods, esquema, area):
    pd = mods["pandas"]
    base = RAIZ / "saida_nasa" / "cluster" / esquema
    cap = pd.read_csv(base / "capacidade" / "resumo_por_grupo.csv")
    fade = pd.read_csv(base / "capacidade" / "fade_por_celula.csv")
    m = base / "modelos_area" / area
    aj = pd.read_csv(m / "ajustes.csv") if (m / "ajustes.csv").exists() else None
    venc = pd.read_csv(m / "vencedores.csv") if (m / "vencedores.csv").exists() else None
    return cap, fade, aj, venc


def medir(mods, esquema, area):
    np, pd = mods["numpy"], mods["pandas"]
    cap, fade, aj, venc = ler(mods, esquema, area)

    n = len(cap)
    unit = int((cap.celulas == 1).sum())
    uteis = cap[cap.celulas >= 2]

    r = {
        "esquema": esquema,
        "grupos": n,
        "grupos_com_1_celula": unit,
        "pct_com_1_celula": unit / n * 100 if n else float("nan"),
        "grupos_uteis": len(uteis),
        "descargas_no_menor_grupo": int(cap.descargas.min()) if n else 0,
        # So os grupos com 2+ celulas entram: onde ha uma celula so, o desvio
        # nao existe, e incluir NaN como se fosse zero premiaria a fragmentacao.
        "desvio_fade_mediano": float(uteis.taxa_desvio_pct_ciclo.median())
        if len(uteis) else float("nan"),
    }

    if venc is not None and len(venc):
        r["r2_mediano"] = float(venc.r2.median())
        r["series_ajustadas"] = int(len(venc))
        # Concordancia: fracao da maioria dentro de cada grupo com 2+ series.
        conc = []
        for g, b in venc.groupby("grupo"):
            if len(b) >= 2:
                conc.append(b.modelo.value_counts().iat[0] / len(b))
        r["concordancia_modelo"] = float(np.mean(conc)) if conc else float("nan")
        r["grupos_com_2_series"] = len(conc)
    return r


def por_condicao(mods, area):
    """Dentro de cada condicao nominal, o que a divisao por corte fez.

    E a comparacao pareada: a mesma condicao, antes e depois de ser partida.
    Uma media geral esconderia que a divisao ajuda numas e atrapalha noutras.
    """
    np, pd = mods["numpy"], mods["pandas"]
    _c, fade_n, _a, venc_n = ler(mods, "grupo_corrente_temperatura", area)
    _c2, fade_p, _a2, venc_p = ler(mods, "grupo_corrente_temperatura_corte", area)

    # O grupo do protocolo comeca com o nome da condicao nominal: e assim que
    # capacidade.py monta o rotulo, entao o prefixo faz o pareamento.
    fade_p["condicao"] = fade_p.grupo.str.split(" / corte").str[0]

    linhas = []
    for cond, bn in fade_n.groupby("grupo"):
        bp = fade_p[fade_p.condicao == cond]
        if bp.empty:
            continue
        sub = bp.groupby("grupo").taxa_pct_por_ciclo
        # Desvio de cada subgrupo que ainda tem 2+ celulas.
        desvios = [g.std() for _, g in sub if g.notna().sum() >= 2]
        linhas.append({
            "condicao": cond,
            "celulas": int(bn.battery_id.nunique()),
            "desvio_nominal": float(bn.taxa_pct_por_ciclo.std()),
            "subgrupos": int(bp.grupo.nunique()),
            "subgrupos_com_1_celula": int((bp.groupby("grupo").battery_id
                                           .nunique() == 1).sum()),
            "desvio_protocolo_mediano": float(np.median(desvios)) if desvios else float("nan"),
        })
    t = pd.DataFrame(linhas)
    if len(t):
        t["melhorou"] = t.desvio_protocolo_mediano < t.desvio_nominal
    return t


def relatar(mods, tab, pc):
    pd = mods["pandas"]
    p("")
    p("  visao geral")
    p(f"    {'':<22} {'nominal':>12} {'protocolo':>12}")
    linhas = [
        ("grupos", "grupos", "{:.0f}"),
        ("com 1 celula so", "grupos_com_1_celula", "{:.0f}"),
        ("  (em %)", "pct_com_1_celula", "{:.0f}%"),
        ("grupos utilizaveis", "grupos_uteis", "{:.0f}"),
        ("desvio do fade", "desvio_fade_mediano", "{:.3f}"),
        ("R2 mediano", "r2_mediano", "{:.4f}"),
        ("concordancia do modelo", "concordancia_modelo", "{:.3f}"),
    ]
    d = tab.set_index("esquema")
    for rotulo, col, fmt in linhas:
        if col not in d.columns:
            continue
        vs = []
        for e in ESQUEMAS:
            v = d.at[e, col] if e in d.index else float("nan")
            vs.append(fmt.format(v) if v == v else "-")
        p(f"    {rotulo:<22} {vs[0]:>12} {vs[1]:>12}")

    if len(pc):
        p("")
        p("  pareado, condicao por condicao (desvio do fade dentro do grupo)")
        p(f"    {'condicao':<14} {'cel':>3} {'nominal':>8} {'subgr':>6} "
          f"{'unit':>5} {'protocolo':>10} {'':>4}")
        for r in pc.itertuples(index=False):
            dn = f"{r.desvio_nominal:.3f}" if r.desvio_nominal == r.desvio_nominal else "-"
            dp = (f"{r.desvio_protocolo_mediano:.3f}"
                  if r.desvio_protocolo_mediano == r.desvio_protocolo_mediano else "-")
            marca = "melhor" if r.melhorou else ("pior" if dp != "-" else "")
            p(f"    {r.condicao:<14} {r.celulas:>3} {dn:>8} {r.subgrupos:>6} "
              f"{r.subgrupos_com_1_celula:>5} {dp:>10} {marca:>7}")
        ok = int(pc.melhorou.sum())
        aval = int(pc.desvio_protocolo_mediano.notna().sum())
        p("")
        p(f"    a divisao por corte reduziu o desvio em {ok} das {aval} condicoes "
          f"em que pode ser avaliada")


def veredito(mods, tab, pc):
    """O veredito tem duas metades que apontam para lados diferentes.

    Nao ha como resolver isso com um numero so, e forcar um esconderia o que o
    dado tem de interessante: a divisao por corte funciona onde pode ser
    medida, e na metade das condicoes ela nao pode ser medida.
    """
    d = tab.set_index("esquema")
    unit = d.at["grupo_corrente_temperatura_corte", "pct_com_1_celula"]
    avaliaveis = int(pc.desvio_protocolo_mediano.notna().sum()) if len(pc) else 0
    ganhou = int(pc.melhorou.sum()) if len(pc) else 0

    p("")
    p("  veredito")
    p("    Contra a divisao por corte, o custo:")
    p(f"      {unit:.0f}% dos grupos ficam com uma celula so. A NASA atribui um corte")
    p("      diferente a cada bateria do mesmo README, entao condicao x corte quase")
    p("      identifica a celula e o agrupamento vira battery_id — rotulo de")
    p("      instancia, que nao existe para uma celula nova.")
    if avaliaveis:
        p("")
        p("    A favor, o beneficio onde ele pode ser medido:")
        p(f"      o desvio do fade caiu em {ganhou} das {avaliaveis} condicoes avaliaveis.")
        melhor = pc.dropna(subset=["desvio_protocolo_mediano"])
        if len(melhor):
            g = melhor.assign(
                ganho=melhor.desvio_nominal - melhor.desvio_protocolo_mediano
            ).sort_values("ganho", ascending=False).iloc[0]
            p(f"      O maior ganho e {g.condicao}: {g.desvio_nominal:.3f} -> "
              f"{g.desvio_protocolo_mediano:.3f}.")
        p(f"      Nas outras {len(pc) - avaliaveis} condicoes todo subgrupo ficou")
        p("      unitario e nao ha desvio interno para comparar.")

    tem_r2 = "r2_mediano" in d.columns
    r2n = d.at["grupo_corrente_temperatura", "r2_mediano"] if tem_r2 else float("nan")
    r2p = (d.at["grupo_corrente_temperatura_corte", "r2_mediano"] if tem_r2
           else float("nan"))
    if r2n == r2n and r2p == r2p:
        p("")
        p(f"    E o que nao muda: o R2 dos ajustes do item 4 fica em {r2n:.4f} contra")
        p(f"    {r2p:.4f}. Partir os grupos nao tornou as series mais faceis de modelar,")
        p("    porque o ajuste ja e por celula — o grupo nunca entrou na conta.")

    p("")
    p("    Recomendacao: grupo_corrente_temperatura (sem o corte), com a area")
    p("    na janela comum de 2.7 V.")
    p("    A janela comum nao depende do corte, entao o efeito que motivaria a")
    p("    divisao ja foi removido na origem; o que sobra correlacionado ao corte")
    p("    troca de sinal entre condicoes e e confundimento com a celula, nao")
    p("    fisica. Dividir por corte ajustaria esse ruido ao preco de perder o")
    p("    grupo. Fica registrado que, com mais celulas por corte, a divisao teria")
    p("    merito — e limitacao do dataset, nao da ideia.")


def estilo(mods):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
        "font.size": 11, "text.color": INK, "axes.labelcolor": INK2,
        "xtick.color": INK2, "ytick.color": INK2, "axes.edgecolor": GRID,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False,
        "legend.frameon": False, "figure.dpi": 200,
    })
    return plt


def titulo_figura(plt, fig, texto, sub):
    import textwrap
    linhas = textwrap.wrap(sub, width=int(fig.get_figwidth() * 13.5))
    alt = 0.1875 / fig.get_figheight()
    fig.suptitle(texto, fontsize=14, fontweight="bold", color=INK,
                 x=0.007, ha="left", y=0.99)
    topo = 0.99 - 2.1 * alt
    fig.text(0.007, topo, "\n".join(linhas), fontsize=10, color=INK2,
             ha="left", va="top", linespacing=1.35)
    fig.tight_layout(rect=[0, 0, 1, topo - len(linhas) * alt - 0.015])


def desenhar(mods, plt, tab, pc):
    np = mods["numpy"]
    d = tab.set_index("esquema")

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))

    # Esquerda: grupos uteis contra grupos unitarios.
    ax = axes[0]
    x = np.arange(len(ESQUEMAS))
    uteis = [d.at[e, "grupos_uteis"] for e in ESQUEMAS]
    unit = [d.at[e, "grupos_com_1_celula"] for e in ESQUEMAS]
    ax.bar(x - 0.2, uteis, 0.4, color=PAL[0], label="com 2+ celulas")
    ax.bar(x + 0.2, unit, 0.4, color=PAL[1], label="com 1 celula so")
    for i in range(len(ESQUEMAS)):
        ax.text(i - 0.2, uteis[i], str(int(uteis[i])), ha="center",
                va="bottom", fontsize=10, color=INK)
        ax.text(i + 0.2, unit[i], str(int(unit[i])), ha="center",
                va="bottom", fontsize=10, color=INK)
    ax.set_xticks(x, ["nominal\n(corrente x temp)", "protocolo\n(+ corte)"],
                  fontsize=9.5)
    ax.set_ylabel("grupos")
    ax.legend(fontsize=9)
    ax.set_title("um grupo de uma celula so nao e um grupo",
                 fontsize=10.5, color=INK2)
    ax.grid(axis="x", visible=False)

    # Direita: desvio do fade pareado por condicao.
    ax = axes[1]
    if len(pc):
        q = pc.dropna(subset=["desvio_protocolo_mediano"])
        for i, r in enumerate(q.itertuples(index=False)):
            ax.plot([0, 1], [r.desvio_nominal, r.desvio_protocolo_mediano],
                    marker="o", markersize=5,
                    color=PAL[2] if r.melhorou else PAL[1], linewidth=1.6,
                    alpha=0.9)
            ax.annotate(r.condicao, (0, r.desvio_nominal), fontsize=7.5,
                        color=INK2, xytext=(-6, 0), textcoords="offset points",
                        ha="right", va="center")
        ax.set_xticks([0, 1], ["nominal", "+ corte"], fontsize=9.5)
        ax.set_xlim(-0.55, 1.25)
        ax.set_ylabel("desvio da taxa de fade no grupo (%/ciclo)")
        ax.set_title("verde = dividir ajudou, laranja = piorou",
                     fontsize=10.5, color=INK2)
        ax.grid(axis="x", visible=False)
    titulo_figura(plt, fig, "Qual agrupamento sustenta a comparacao",
                  "A esquerda o custo da fragmentacao, a direita o beneficio pareado "
                  "condicao a condicao. Dividir por corte so vale se o ganho de "
                  "coerencia superar a perda de celulas por grupo.")
    fig.savefig(SAIDA / "01_qual_agrupamento_ganha.png", bbox_inches="tight")
    plt.close(fig)
    p(f"  01_qual_agrupamento_ganha.png")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--area", default=AREA_PADRAO)
    ap.add_argument("--sem-graficos", action="store_true")
    a = ap.parse_args()

    mods = checar()
    pd = mods["pandas"]
    SAIDA.mkdir(parents=True, exist_ok=True)

    p("Nominal contra protocolo completo")
    p("=" * 60)
    tab = pd.DataFrame([medir(mods, e, a.area) for e in ESQUEMAS])
    pc = por_condicao(mods, a.area)

    relatar(mods, tab, pc)
    veredito(mods, tab, pc)

    tab.to_csv(SAIDA / "visao_geral.csv", index=False)
    pc.to_csv(SAIDA / "pareado_por_condicao.csv", index=False)
    p("")
    p(f"  {(SAIDA / 'visao_geral.csv').relative_to(RAIZ)}")
    p(f"  {(SAIDA / 'pareado_por_condicao.csv').relative_to(RAIZ)}")

    if not a.sem_graficos:
        desenhar(mods, estilo(mods), tab, pc)


if __name__ == "__main__":
    main()
