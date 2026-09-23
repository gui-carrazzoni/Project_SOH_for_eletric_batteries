#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analise descritiva da tabela analitica: um atributo numerico e um nominal.

    python descritiva.py                 # tabelas + graficos
    python descritiva.py --sem-graficos   # so as tabelas

Le saida_nasa/correlacao/tabela_modelagem.csv (tabela integrada, 2.794 descargas)
e saida_nasa/preprocessado/dados_modelagem.csv (apos a limpeza, 2.719) e escreve
em saida_nasa/descritiva/.

**Atributo numerico: SOH.** E a variavel-alvo — a razao entre a capacidade medida
na descarga e a capacidade de referencia da celula naquela condicao. Descrever o
SOH e descrever o que o projeto vai prever, e a comparacao com a `capacity` bruta
mostra por que a normalizacao existe: a capacidade e bimodal porque mistura
protocolos, o SOH nao.

**Atributo nominal: test_condition.** Das tres colunas nominais do dicionario,
`charge_type` e constante nas 34 celulas (variancia zero, nada a descrever) e
`discharge_type` explica 8,6% da variancia do SOH. A condicao de ensaio
(corrente x temperatura ambiente) explica 16,0%, e e o eixo em torno do qual o
alvo e definido: o SOH e normalizado *dentro* da condicao justamente porque a
capacidade nao e comparavel entre elas.

Dependencias: numpy, pandas, matplotlib
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# A raiz do projeto e a pasta acima de src/: e la que ficam
# cleaned_nasa_dataset/ e saida_nasa/.
RAIZ = Path(__file__).resolve().parent.parent
BRUTA = RAIZ / "saida_nasa" / "correlacao" / "tabela_modelagem.csv"
LIMPA = RAIZ / "saida_nasa" / "preprocessado" / "dados_modelagem.csv"
SAIDA = RAIZ / "saida_nasa" / "descritiva"

# Paleta categorica validada para daltonismo (modo claro), slots 1..8 em ordem fixa
PAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
       "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e3e2de"

ALVO = "SOH"
NOMINAL = "test_condition"


def virg(v, casas=1):
    """Numero com virgula decimal, como manda a norma brasileira."""
    return f"{v:.{casas}f}".replace(".", ",")


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
    return mods


def carregar(mods):
    pd = mods["pandas"]
    for f in (BRUTA, LIMPA):
        if not f.exists():
            p(f"ERRO: falta {f.relative_to(RAIZ)}")
            p("    rode antes: python correlacao_soh.py && python limpeza.py")
            sys.exit(1)
    bruta = pd.read_csv(BRUTA)
    d = pd.read_csv(LIMPA)
    # A capacidade bruta ficou de fora da tabela limpa (e vazamento para o SOH),
    # mas serve a descricao: e ela que mostra por que o alvo precisa ser relativo.
    chave = ["battery_id", "filename"]
    d = d.merge(bruta[chave + ["capacity"]], on=chave, how="left")
    return bruta, d


def resumo_numerico(mods, s):
    """Tendencia central, dispersao e forma de uma serie numerica."""
    np = mods["numpy"]
    x = s.dropna().to_numpy(float)
    n, m, dp = len(x), x.mean(), x.std(ddof=1)
    q1, q2, q3 = np.percentile(x, [25, 50, 75])
    z = (x - m) / dp
    return {
        "n": n,
        "media": m,
        "mediana": q2,
        "desvio_padrao": dp,
        "coef_variacao_pct": 100 * dp / m,
        "minimo": x.min(),
        "q1": q1,
        "q3": q3,
        "maximo": x.max(),
        "amplitude_interquartil": q3 - q1,
        "assimetria": (z ** 3).mean() * n * n / ((n - 1) * (n - 2)),
        "curtose_excesso": float(mods["pandas"].Series(x).kurtosis()),
    }


def eta_quadrado(mods, d, nominal, alvo):
    """Fracao da variancia do alvo explicada pelo atributo nominal."""
    g = d.groupby(nominal)[alvo]
    media = d[alvo].mean()
    entre = (g.count() * (g.mean() - media) ** 2).sum()
    return entre / ((d[alvo] - media) ** 2).sum()


def tabelas(mods, bruta, d):
    pd = mods["pandas"]
    SAIDA.mkdir(parents=True, exist_ok=True)

    est = pd.DataFrame([
        dict(atributo="SOH (%)", **resumo_numerico(mods, d[ALVO])),
        dict(atributo="capacity (Ah)", **resumo_numerico(mods, d["capacity"])),
    ])
    est.to_csv(SAIDA / "estatisticas_numericas.csv", index=False)

    g = d.groupby(NOMINAL)
    freq = pd.DataFrame({
        "descargas": g.size(),
        "frequencia_relativa_pct": 100 * g.size() / len(d),
        "celulas": g.battery_id.nunique(),
        "soh_mediana": g[ALVO].median(),
        "soh_q1": g[ALVO].quantile(0.25),
        "soh_q3": g[ALVO].quantile(0.75),
        "soh_minimo": g[ALVO].min(),
        "capacidade_mediana_Ah": g.capacity.median(),
        # Duas leituras da mesma relacao: agrupando as celulas da condicao, e
        # dentro de cada celula. A divergencia entre as duas e o assunto da figura 3.
        "corr_soh_ciclo": g.apply(lambda x: x[["cycle", ALVO]].corr().iloc[0, 1]),
        "corr_soh_ciclo_intracelula": g.apply(
            lambda x: x.groupby("battery_id").apply(
                lambda c: c[["cycle", ALVO]].corr().iloc[0, 1]).median()),
    }).sort_values("descargas", ascending=False)
    freq.index.name = "condicao_de_ensaio"
    freq.to_csv(SAIDA / "frequencias_condicao.csv")

    por_grupo = d.groupby(["battery_id", NOMINAL]).apply(
        lambda x: x[["cycle", ALVO]].corr().iloc[0, 1])
    p("")
    p(f"SOH x ciclo: r agrupado {d[['cycle', ALVO]].corr().iloc[0, 1]:+.2f}"
      f"   mediana dos {len(por_grupo)} grupos celula x condicao {por_grupo.median():+.2f}"
      f"   negativo em {(por_grupo < 0).sum()} deles")

    eta = eta_quadrado(mods, d, NOMINAL, ALVO)
    outros = {c: eta_quadrado(mods, d, c, ALVO)
              for c in ("discharge_type", "charge_type", "battery_id")}

    p("")
    p(f"SOH em {len(d)} descargas de {d.battery_id.nunique()} celulas")
    linha = est.set_index("atributo").loc["SOH (%)"]
    p(f"  media {linha.media:.1f}  mediana {linha.mediana:.1f}  dp {linha.desvio_padrao:.1f}"
      f"  CV {linha.coef_variacao_pct:.0f}%  assimetria {linha.assimetria:+.2f}")
    p(f"  min {linha.minimo:.1f}  Q1 {linha.q1:.1f}  Q3 {linha.q3:.1f}  max {linha.maximo:.1f}")
    p("")
    p(f"Variancia do SOH explicada (eta quadrado):")
    p(f"  {NOMINAL}: {eta:.3f}   " + "   ".join(f"{k}: {v:.3f}" for k, v in outros.items()))
    p("")
    p("Condicao de ensaio:")
    for cond, r in freq.iterrows():
        p(f"  {cond:>12}  {int(r.descargas):>4} descargas ({r.frequencia_relativa_pct:4.1f}%)"
          f"  {int(r.celulas)} celulas  SOH mediano {r.soh_mediana:5.1f}%"
          f"  capacidade mediana {r.capacidade_mediana_Ah:.3f} Ah")
    p("")
    p("  estatisticas_numericas.csv")
    p("  frequencias_condicao.csv")
    return est, freq, eta


def estilo(mods):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
        "font.size": 11, "text.color": INK, "axes.labelcolor": INK2,
        "xtick.color": INK2, "ytick.color": INK2, "axes.edgecolor": GRID,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 2.0,
        "legend.frameon": False, "figure.dpi": 200,
    })
    return plt


def titulo_figura(plt, fig, texto, sub):
    """Titulo e subtitulo alinhados a esquerda, sem colidir com os paineis.

    O subtitulo e quebrado na largura da figura: sem isso `bbox_inches="tight"`
    alarga o PNG inteiro para caber uma linha de texto que ninguem pediu.
    """
    import textwrap
    linhas = textwrap.wrap(sub, width=int(fig.get_figwidth() * 13.5))
    altura_linha = 0.1875 / fig.get_figheight()          # 10 pt com entrelinha 1,35
    fig.suptitle(texto, fontsize=14, fontweight="bold", color=INK,
                 x=0.007, ha="left", y=0.99)
    topo_sub = 0.99 - 2.1 * altura_linha
    fig.text(0.007, topo_sub, "\n".join(linhas), fontsize=10, color=INK2,
             ha="left", va="top", linespacing=1.35)
    fig.tight_layout(rect=[0, 0, 1, topo_sub - len(linhas) * altura_linha - 0.015])


def salvar(plt, fig, nome):
    fig.savefig(SAIDA / nome, bbox_inches="tight")
    plt.close(fig)
    p(f"  {nome}")


def desenhar(mods, d, freq):
    np, pd = mods["numpy"], mods["pandas"]
    plt = estilo(mods)
    azul = PAL[0]

    # -- 01 histograma do alvo
    fig, a = plt.subplots(figsize=(8.5, 4.6))
    alturas, _, _ = a.hist(d[ALVO], bins=np.arange(0, 102.5, 2.5),
                           color=azul, edgecolor=SURF, linewidth=0.6)
    med = d[ALVO].median()
    # Folga no topo para que as duas marcacoes fiquem acima das barras, nao sobre elas.
    a.set_ylim(0, alturas.max() * 1.26)
    rotulo = alturas.max() * 1.11
    a.axvline(80, color=PAL[7], linewidth=1.4, zorder=4)
    a.annotate("limiar de EOL 80%", (80, rotulo), xytext=(-7, 0),
               textcoords="offset points", ha="right", va="center",
               fontsize=9.5, color=PAL[7])
    a.axvline(med, color=INK, linewidth=1.4, linestyle=(0, (4, 2)), zorder=4)
    a.annotate(f"mediana {virg(med, 1)}%", (med, rotulo), xytext=(7, 0),
               textcoords="offset points", ha="left", va="center",
               fontsize=9.5, color=INK)
    a.set_xlabel("SOH (%)"); a.set_ylabel("descargas")
    a.set_xlim(-2, 112)
    a.grid(axis="x", visible=False)
    n_pt = f"{len(d):,}".replace(",", ".")      # milhar com ponto, sem tocar no texto
    titulo_figura(plt, fig, "Distribuição do estado de saúde",
                  f"{n_pt} descargas de {d.battery_id.nunique()} células, SOH normalizado "
                  "por célula × condição. Unimodal e assimétrico à esquerda; o pico em 100% "
                  "é construção da referência, não medição.")
    salvar(plt, fig, "01_histograma_soh.png")

    # -- 02 boxplot do alvo por condicao de ensaio
    ordem = freq.sort_values("soh_mediana").index.tolist()
    fig, ax = plt.subplots(figsize=(10.0, 5.4))
    dados = [d.loc[d[NOMINAL] == c, ALVO].to_numpy() for c in ordem]
    bp = ax.boxplot(dados, widths=0.58, patch_artist=True,
                    flierprops=dict(marker="o", markersize=3.4, markerfacecolor=INK2,
                                    markeredgecolor="none", alpha=0.45),
                    medianprops=dict(color=SURF, linewidth=2.0),
                    whiskerprops=dict(color=INK2, linewidth=1.1),
                    capprops=dict(color=INK2, linewidth=1.1))
    for caixa in bp["boxes"]:
        caixa.set(facecolor=azul, edgecolor=SURF, linewidth=1.2)
    ax.axhline(80, color=PAL[7], linewidth=1.4, zorder=0)
    ax.set_xlim(0.4, len(ordem) + 0.85)
    ax.annotate("limiar de EOL 80%", (len(ordem) + 0.8, 80), xytext=(0, 5),
                textcoords="offset points", fontsize=9.5, color=PAL[7],
                ha="right", va="bottom")
    ax.set_xticks(range(1, len(ordem) + 1))
    ax.set_xticklabels([f"{c.replace(' C', ' °C')}\nn = {int(freq.loc[c, 'descargas'])}"
                        for c in ordem], linespacing=1.5)
    ax.set_ylabel("SOH (%)"); ax.set_ylim(0, 104)
    ax.grid(axis="x", visible=False)
    titulo_figura(plt, fig, "SOH por condição de ensaio",
                  "A condição responde por 16% da variância do SOH: a mediana vai de 75% a 1 A / 4 °C "
                  "a 99,7% a 1 A / 44 °C, e a dispersão é tão desigual quanto o nível.")
    salvar(plt, fig, "02_boxplot_soh_condicao.png")

    # -- 03 dispersao SOH x ciclo, um painel por condicao
    def reta(ax, x, y, **kw):
        """Ajuste linear por minimos quadrados, desenhado no intervalo dos dados."""
        x, y = np.asarray(x, float), np.asarray(y, float)
        ok = np.isfinite(x) & np.isfinite(y)
        if ok.sum() < 3 or np.ptp(x[ok]) == 0:
            return
        a, b = np.polyfit(x[ok], y[ok], 1)
        extremos = np.array([x[ok].min(), x[ok].max()])
        ax.plot(extremos, a * extremos + b, **kw)

    ordem = freq.index.tolist()
    # sharey=False de proposito: cada condicao percorre uma faixa de SOH propria, e
    # o eixo comum de 0 a 100 esmagava metade dos paineis numa tira.
    fig, axes = plt.subplots(2, 4, figsize=(13.0, 6.4), sharex=False, sharey=False)
    for ax, cond in zip(axes.ravel(), ordem):
        sub = d[d[NOMINAL] == cond]
        ax.scatter(sub.cycle, sub[ALVO], s=9, color=azul, alpha=0.55,
                   edgecolors="none", zorder=3)
        reta(ax, sub.cycle, sub[ALVO], color=PAL[1], linewidth=2.4,
             linestyle=(0, (5, 2)), zorder=5)
        r = freq.loc[cond, "corr_soh_ciclo"]
        ri = freq.loc[cond, "corr_soh_ciclo_intracelula"]
        sinal = lambda v: ("+" if v >= 0 else "\u2212") + virg(abs(v), 2)
        # Os dois r vao acima do painel: dentro dele colidiam com os pontos.
        ax.set_title(f"{cond.replace(' C', ' °C')}   n={int(freq.loc[cond, 'descargas'])}",
                     fontsize=10.5, fontweight="bold", color=INK, loc="left", pad=20)
        ax.annotate(f"r agrupado {sinal(r)}   ·   intracélula {sinal(ri)}",
                    (0, 1.02), xycoords="axes fraction",
                    ha="left", va="bottom", fontsize=9, color=INK2)
        ax.margins(x=0.04, y=0.12)
        ax.set_xlabel("ciclo de descarga da célula", fontsize=9.5)
        ax.set_ylabel("SOH (%)", fontsize=9.5)
        ax.grid(axis="x", visible=False)
    titulo_figura(plt, fig, "SOH ao longo dos ciclos, por condição de ensaio",
                  "Cada ponto é uma descarga e a reta tracejada é a tendência linear "
                  "sobre todas as células da condição; a escala vertical é própria de cada "
                  "painel. Em 1 A / 4 °C essa reta sobe (r = +0,26) embora dentro de cada "
                  "célula o SOH caia (r = −0,91): é o paradoxo de Simpson, causado por "
                  "células que entraram na condição já em ciclo avançado e reapareceram "
                  "com o SOH renormalizado em 100%.")
    salvar(plt, fig, "03_dispersao_soh_ciclo.png")


def main():
    ap = argparse.ArgumentParser(description="Analise descritiva da tabela analitica.")
    ap.add_argument("--sem-graficos", action="store_true", help="so as tabelas")
    args = ap.parse_args()

    mods = checar()
    bruta, d = carregar(mods)
    est, freq, eta = tabelas(mods, bruta, d)
    if not args.sem_graficos:
        desenhar(mods, d, freq)
    p("")
    p(f"pronto -> {SAIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
