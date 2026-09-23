#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Estudo da capacidade em cada ciclo, nos dois agrupamentos.

    python capacidade.py                # os dois esquemas de grupo
    python capacidade.py --sem-corte    # so o esquema sem a tensao de corte
    python capacidade.py --sem-graficos

Escreve, com os **mesmos nomes de arquivo** nas duas arvores — e o que torna a
comparacao direta:

    saida_nasa/cluster/grupo_corrente_temperatura/capacidade/
    saida_nasa/cluster/grupo_corrente_temperatura_corte/capacidade/

**Os dois esquemas de grupo.** O primeiro e o `test_condition` que o projeto ja
usa: corrente x temperatura ambiente. O segundo acrescenta a tensao de corte da
descarga, o terceiro eixo do protocolo — 2.0 a 2.7 V conforme a bateria, e
ausente de `test_condition`.

**O esquema com o corte esta aqui como demonstracao de que nao funciona**, e nao
como recomendacao. O agrupamento hierarquico de grupos.py mostrou celulas sob o mesmo
rotulo nominal se separando pelo corte, o que sugeria acrescentar esse eixo. Mas
a NASA da um corte diferente a cada bateria do mesmo README, entao
`condicao x corte` quase identifica a celula: 17 dos 29 grupos ficam com uma
unica bateria, e o agrupamento vira o `battery_id` que o projeto ja recusa por
ser rotulo de instancia.

E o efeito do corte que parecia justificar a divisao nao sobrevive ao exame. A
area na janela comum e integrada ate 2.7 V, igual para todas: **o corte nao pode
influir nela por construcao**. Ainda assim a correlacao entre corte e area
dentro da condicao fica em |r| ~ 0.40, com sinais que trocam de condicao para
condicao (+0.68 em 1 A / 4 C, -0.84 em 1 A / 44 C). Efeito fisico real nao troca
de sinal; isso e confundimento com a identidade da celula, que agrupar por corte
nao corrige — so ajusta ruido.

**A capacidade usada e a da janela comum.** `carga_Ah_comum` integra a corrente
ate 2.7 V, igual para todas as celulas; `carga_Ah` vai ate o corte de cada uma e
por isso nao se compara entre celulas de corte diferente. Ver curvas.py.

**O joelho** e localizado pela maior distancia vertical ate a corda que liga o
primeiro ao ultimo ciclo da serie. E o criterio mais simples que nao exige
escolher modelo antes de olhar o dado — e escolher o modelo e o item 4.

Dependencias: numpy, pandas, matplotlib
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# A raiz do projeto e a pasta acima de src/: e la que ficam
# cleaned_nasa_dataset/ e saida_nasa/.
RAIZ = Path(__file__).resolve().parent.parent
ENTRADA = RAIZ / "saida_nasa" / "curvas" / "features_curvas.csv"

PAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
       "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e3e2de"

CAPACIDADE = "carga_Ah_comum"   # a comparavel entre celulas
MIN_CICLOS = 8                  # abaixo disso nao ha serie para estudar
CICLOS_REF = 5                  # ciclos que definem a capacidade de inicio
FIM_DE_VIDA = 0.80              # limiar de 80% do artigo


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
        p("    python -m pip install -r requirements.txt")
        sys.exit(1)
    if not ENTRADA.exists():
        p(f"ERRO: {ENTRADA.relative_to(RAIZ)} nao existe.")
        p("    Rode antes: python curvas.py")
        sys.exit(1)
    return mods


def cortes():
    """A tensao de corte de cada bateria.

    Vem de correlacao_soh.PROTOCOLO, transcrita dos README de extra_infos/.
    Importar em vez de copiar mantem uma fonte so — e a transcricao foi
    validada de forma independente: a tensao minima que cada celula atinge sob
    carga bate com o corte declarado em todas as 34 (B0049 chega a 1.993 V com
    corte 2.0, B0051 a 2.492 V com corte 2.5).
    """
    from correlacao_soh import PROTOCOLO
    return {b: v for b, (_, v) in PROTOCOLO.items()}


def preparar(mods, sem_corte=False):
    np, pd = mods["numpy"], mods["pandas"]
    d = pd.read_csv(ENTRADA)
    d = d[d[CAPACIDADE].notna() & d.condicao.notna()].copy()

    # As descargas que nao alcancam o piso comum tem area truncada e nao se
    # comparam com as demais; ficam de fora em vez de entrar distorcidas.
    d = d[d.atingiu_piso.fillna(False).astype(bool)]

    c = cortes()
    d["corte_V"] = d.battery_id.map(c)
    d = d[d.corte_V.notna()]

    esquemas = {"grupo_corrente_temperatura": d.condicao}
    if not sem_corte:
        esquemas["grupo_corrente_temperatura_corte"] = (
            d.condicao + " / corte " + d.corte_V.map(lambda v: f"{v:.1f}V"))
    return d, esquemas


# ---------------------------------------------------------------------------
# metricas de fade
# ---------------------------------------------------------------------------
def joelho(np, x, y):
    """Ciclo do joelho: maior distancia vertical ate a corda inicio-fim.

    Devolve (ciclo, forca), onde forca e a distancia em fracao da capacidade
    inicial. Perto de zero significa que a queda e reta e nao ha joelho.
    """
    if len(x) < 4 or x[-1] == x[0]:
        return float("nan"), float("nan")
    corda = y[0] + (y[-1] - y[0]) * (x - x[0]) / (x[-1] - x[0])
    dist = corda - y                      # positivo = curva abaixo da corda
    k = int(np.argmax(np.abs(dist)))
    ref = y[0] if y[0] > 0 else 1.0
    return float(x[k]), float(dist[k] / ref)


def metricas_celula(np, bloco):
    """Uma bateria dentro de um grupo -> as metricas de fade daquela serie."""
    b = bloco.sort_values("ciclo_na_condicao")
    x = b.ciclo_na_condicao.to_numpy(float)
    y = b[CAPACIDADE].to_numpy(float)
    if len(x) < MIN_CICLOS:
        return None

    ini = float(np.median(y[:CICLOS_REF]))
    if not (ini > 0):
        return None

    # Taxa linear por minimos quadrados: a inclinacao da reta capacidade x ciclo.
    coef = np.polyfit(x, y, 1)
    r = float(np.corrcoef(x, y)[0, 1]) if len(x) > 2 else float("nan")

    # Ciclos ate 80%: primeira vez que a capacidade cruza o limiar, interpolada
    # entre os dois ciclos vizinhos. NaN quando a celula nunca chega la.
    alvo = ini * FIM_DE_VIDA
    abaixo = np.where(y <= alvo)[0]
    if len(abaixo) and abaixo[0] > 0:
        j = int(abaixo[0])
        f = (y[j - 1] - alvo) / (y[j - 1] - y[j]) if y[j - 1] != y[j] else 0.0
        ciclos_80 = float(x[j - 1] + f * (x[j] - x[j - 1]))
    elif len(abaixo):
        ciclos_80 = float(x[abaixo[0]])
    else:
        ciclos_80 = float("nan")

    xj, fj = joelho(np, x, y)
    return {
        "ciclos": len(x),
        "ciclo_max": float(x.max()),
        "Ah_inicial": ini,
        "Ah_final": float(np.median(y[-CICLOS_REF:])),
        "queda_total_pct": float((1 - np.median(y[-CICLOS_REF:]) / ini) * 100),
        "taxa_Ah_por_ciclo": float(coef[0]),
        "taxa_pct_por_ciclo": float(coef[0] / ini * 100),
        "r_capacidade_ciclo": r,
        "ciclos_ate_80pct": ciclos_80,
        "atingiu_80pct": bool(ciclos_80 == ciclos_80),
        "joelho_ciclo": xj,
        "joelho_forca": fj,
    }


def estudar(mods, d, rotulos, nome):
    np, pd = mods["numpy"], mods["pandas"]
    d = d.assign(grupo=rotulos)

    linhas = []
    for (grupo, bat), bloco in d.groupby(["grupo", "battery_id"]):
        m = metricas_celula(np, bloco)
        if m:
            linhas.append({"grupo": grupo, "battery_id": bat, **m})
    fade = pd.DataFrame(linhas)

    # Resumo por grupo. O desvio da taxa dentro do grupo e o numero que importa:
    # um agrupamento so se justifica se as celulas dentro dele degradarem de
    # forma parecida. Desvio menor = grupo mais coerente.
    resumo = fade.groupby("grupo").agg(
        celulas=("battery_id", "nunique"),
        descargas=("ciclos", "sum"),
        taxa_mediana_pct_ciclo=("taxa_pct_por_ciclo", "median"),
        taxa_desvio_pct_ciclo=("taxa_pct_por_ciclo", "std"),
        taxa_iqr_pct_ciclo=("taxa_pct_por_ciclo",
                            lambda s: s.quantile(.75) - s.quantile(.25)),
        queda_mediana_pct=("queda_total_pct", "median"),
        celulas_ate_80pct=("atingiu_80pct", "sum"),
        ciclos_ate_80_mediana=("ciclos_ate_80pct", "median"),
        joelho_forca_mediana=("joelho_forca", "median"),
    ).sort_values("descargas", ascending=False)

    # Validacao da integracao contra o campo Capacity da NASA, por grupo.
    v = d[d.Capacity.notna() & (d.Capacity > 0)].copy()
    v["erro_pct"] = (v[CAPACIDADE] - v.Capacity) / v.Capacity * 100
    v["erro_pct_ate_corte"] = (v.carga_Ah - v.Capacity) / v.Capacity * 100
    val = v.groupby("grupo").agg(
        descargas=("erro_pct", "size"),
        erro_janela_comum_pct=("erro_pct", "median"),
        erro_ate_o_corte_pct=("erro_pct_ate_corte", "median"),
        pior_5pct=("erro_pct", lambda s: (s.abs() > 5).mean() * 100),
    )
    return fade, resumo, val


def relatar(nome, resumo, val):
    p("")
    p(f"  {nome}: {len(resumo)} grupos")
    p(f"    {'grupo':<30} {'cel':>3} {'desc':>5} {'%/ciclo':>8} {'desvio':>7} {'ate 80%':>8}")
    for g, r in resumo.iterrows():
        n80 = (f"{r.ciclos_ate_80_mediana:.0f}"
               if r.ciclos_ate_80_mediana == r.ciclos_ate_80_mediana else "-")
        dv = (f"{r.taxa_desvio_pct_ciclo:.3f}"
              if r.taxa_desvio_pct_ciclo == r.taxa_desvio_pct_ciclo else "-")
        p(f"    {str(g):<30} {int(r.celulas):>3} {int(r.descargas):>5} "
          f"{r.taxa_mediana_pct_ciclo:>8.3f} {dv:>7} {n80:>8}")
    p("")
    p(f"    integracao contra o Capacity da NASA: "
      f"janela comum {val.erro_janela_comum_pct.median():+.2f}%, "
      f"ate o corte {val.erro_ate_o_corte_pct.median():+.2f}%")

    # O numero que decide entre os dois agrupamentos: quantos grupos ficaram com
    # uma celula so. Grupo unitario nao tem dispersao interna para medir, e o
    # agrupamento deixa de ser agrupamento.
    unit = int((resumo.celulas == 1).sum())
    p(f"    grupos com uma unica celula: {unit} de {len(resumo)}"
      f" ({unit / len(resumo) * 100:.0f}%)")


# ---------------------------------------------------------------------------
# graficos
# ---------------------------------------------------------------------------
def estilo(mods):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
        "font.size": 11, "text.color": INK, "axes.labelcolor": INK2,
        "xtick.color": INK2, "ytick.color": INK2, "axes.edgecolor": GRID,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 1.8,
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


def desenhar(mods, plt, d, rotulos, fade, resumo, saida, nome):
    np, pd = mods["numpy"], mods["pandas"]
    d = d.assign(grupo=rotulos)
    grupos = list(resumo.index)

    # 01 — capacidade por ciclo, um painel por grupo
    n = len(grupos)
    cols = min(4, n)
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(3.6 * cols, 2.9 * rows),
                             squeeze=False)
    for k, g in enumerate(grupos):
        ax = axes[k // cols][k % cols]
        bloco = d[d.grupo == g]
        for i, (bat, b) in enumerate(bloco.groupby("battery_id")):
            b = b.sort_values("ciclo_na_condicao")
            ax.plot(b.ciclo_na_condicao, b[CAPACIDADE],
                    color=PAL[i % len(PAL)], linewidth=1.4, alpha=0.9)
        ax.set_title(str(g), fontsize=8.5, color=INK2)
        ax.tick_params(labelsize=8)
    for k in range(n, rows * cols):
        axes[k // cols][k % cols].axis("off")
    fig.supxlabel("ciclo dentro do grupo", fontsize=10, color=INK2)
    fig.supylabel("capacidade na janela comum (Ah)", fontsize=10, color=INK2)
    titulo_figura(plt, fig, f"Capacidade por ciclo — {nome}",
                  "Uma linha por celula. Capacidade integrada ate o piso comum de 2.7 V, "
                  "a unica base que se compara entre celulas de corte diferente. "
                  "Um grupo coerente mostra trajetorias parecidas dentro do painel.")
    fig.savefig(saida / "01_capacidade_por_ciclo.png", bbox_inches="tight")
    plt.close(fig)
    p(f"  {nome}/01_capacidade_por_ciclo.png")

    # 02 — dispersao da taxa de fade dentro de cada grupo
    fig, ax = plt.subplots(figsize=(max(7, 0.42 * len(grupos) + 4), 5))
    dados = [fade[fade.grupo == g].taxa_pct_por_ciclo.dropna().to_numpy()
             for g in grupos]
    manter = [i for i, v in enumerate(dados) if len(v)]
    bp = ax.boxplot([dados[i] for i in manter], patch_artist=True,
                    medianprops=dict(color=INK, linewidth=1.6),
                    flierprops=dict(markersize=3, markerfacecolor=INK2,
                                    markeredgecolor="none"))
    for i, caixa in enumerate(bp["boxes"]):
        caixa.set_facecolor(PAL[i % len(PAL)])
        caixa.set_alpha(0.55)
        caixa.set_edgecolor(INK2)
    ax.set_xticks(range(1, len(manter) + 1),
                  [str(grupos[i]) for i in manter], rotation=40,
                  ha="right", fontsize=8)
    ax.axhline(0, color=INK2, linewidth=1, linestyle="--")
    ax.set_ylabel("taxa de fade (% da capacidade inicial por ciclo)")
    titulo_figura(plt, fig, f"Dispersao do fade dentro do grupo — {nome}",
                  "Cada ponto e uma celula. Caixa estreita significa que o grupo reune "
                  "celulas que degradam no mesmo ritmo — e o teste de se o agrupamento "
                  "esta separando o que deveria.")
    fig.savefig(saida / "02_taxa_de_fade.png", bbox_inches="tight")
    plt.close(fig)
    p(f"  {nome}/02_taxa_de_fade.png")


def rodar(mods, d, rotulos, nome, graficos):
    saida = RAIZ / "saida_nasa" / "cluster" / nome / "capacidade"
    saida.mkdir(parents=True, exist_ok=True)
    fade, resumo, val = estudar(mods, d, rotulos, nome)
    relatar(nome, resumo, val)
    fade.to_csv(saida / "fade_por_celula.csv", index=False)
    resumo.to_csv(saida / "resumo_por_grupo.csv")
    val.to_csv(saida / "validacao_integracao.csv")
    if graficos:
        desenhar(mods, estilo(mods), d, rotulos, fade, resumo, saida, nome)
    return fade, resumo


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--sem-corte", action="store_true")
    ap.add_argument("--sem-graficos", action="store_true")
    a = ap.parse_args()

    mods = checar()
    p("Capacidade em cada ciclo")
    p("=" * 60)
    d, esquemas = preparar(mods, a.sem_corte)
    p(f"  {len(d)} descargas com area na janela comum, "
      f"{d.battery_id.nunique()} baterias")

    for nome, rot in esquemas.items():
        rodar(mods, d, rot, nome, not a.sem_graficos)
    p("")
    p("  ok")


if __name__ == "__main__":
    main()
