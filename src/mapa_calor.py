#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mapa de calor da correlacao, ja com as areas e os descritores de forma.

    python mapa_calor.py
    python mapa_calor.py --sem-graficos

Escreve saida_nasa/curvas/correlacao/.

`correlacao_soh.py` ja produz o mapa de calor das variaveis da Tabela 2 do
artigo, e este script **nao o substitui**: aquele e fiel ao dicionario de dados
publicado, uma coluna por variavel, sem acrescimo. Este acrescenta o que curvas.py
passou a medir — as tres areas e a forma da descarga — e por isso vive a parte.

Tres diferencas em relacao ao mapa existente:

**Todo valor aparece.** O mapa de correlacao_soh.py anota so |r| >= 0.4, o que
mantem a figura limpa quando ha muitas variaveis. Aqui a matriz e menor e o
valor de cada celula e legivel, inclusive os fracos — um r de 0.05 entre duas
variaveis que a intuicao diria acopladas e informacao, nao ruido de tela.

**Duas leituras, agrupada e intra-celula.** Mesma regra do resto do projeto: a
agrupada mistura diferenca entre celulas com degradacao e engana. A intra-celula
centra por bateria x condicao antes de correlacionar. Quando as duas discordam,
quem manda e a intra-celula, e a discordancia e o proprio achado — e o paradoxo
de Simpson que o projeto documenta.

**O vazamento fica marcado na figura.** `carga_Ah_comum`, `tensao_Vs_comum`,
`energia_Wh_comum`, `capacity` e `duracao` correlacionam quase perfeitamente com
o SOH porque **sao** a capacidade, e o SOH e a capacidade normalizada. Um mapa
que mostrasse r = 1.00 sem dizer isso convidaria a ler identidade como achado.
Os rotulos dessas variaveis saem em vermelho, com legenda.

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
SAIDA = RAIZ / "saida_nasa" / "curvas" / "correlacao"

SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e3e2de"
FOGO = "#b93331"
DIV = ["#7d1f1d", "#b93331", "#d97370", "#eab5b3", "#f0efec",
       "#adc9ee", "#6d9fe4", "#2a78d6", "#104281"]

ALVO = "SoH_%"

# As variaveis do mapa, na ordem em que aparecem. As areas primeiro, depois a
# forma da descarga, depois o alvo.
COLUNAS = [
    "carga_Ah_comum", "energia_Wh_comum", "tensao_Vs_comum",
    "duracao_s_comum", "Capacity",
    "V_inicial", "V_final_carga", "V_medio", "queda_V", "inclinacao_mV_min",
    "I_medio", "T_inicial", "T_max", "T_subida",
    "fracao_energia_1a_metade", "ciclo_na_condicao", ALVO,
]

# As que sao a capacidade por outro nome. Ver a docstring.
VAZAMENTO = {"carga_Ah_comum", "energia_Wh_comum", "tensao_Vs_comum",
             "duracao_s_comum", "Capacity"}


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
    if not ENTRADA.exists():
        p(f"ERRO: {ENTRADA.relative_to(RAIZ)} nao existe.")
        p("    Rode antes: python curvas.py")
        sys.exit(1)
    return mods


def preparar(mods):
    pd = mods["pandas"]
    d = pd.read_csv(ENTRADA)
    d = d[d.atingiu_piso.fillna(False).astype(bool) & d.condicao.notna()].copy()
    cols = [c for c in COLUNAS if c in d.columns]
    return d, cols


def matrizes(mods, d, cols):
    """Pearson agrupada e intra-celula (centrada por bateria x condicao)."""
    np, pd = mods["numpy"], mods["pandas"]
    bruto = d[cols].apply(pd.to_numeric, errors="coerce")

    agrupada = bruto.corr()

    # Centrar por grupo remove o nivel proprio de cada celula e deixa so a
    # variacao ao longo da vida, que e o que se quer correlacionar.
    chave = d.battery_id.astype(str) + "|" + d.condicao.astype(str)
    centrado = bruto.groupby(chave).transform(lambda s: s - s.mean())
    intra = centrado.corr()
    return agrupada, intra


def ranking(mods, agrupada, intra):
    pd = mods["pandas"]
    r = pd.DataFrame({
        "correlacao_agrupada": agrupada[ALVO],
        "correlacao_intracelula": intra[ALVO],
    }).drop(index=ALVO, errors="ignore")
    r["is_leakage"] = [i in VAZAMENTO for i in r.index]
    r["forca_intracelula"] = r.correlacao_intracelula.abs()
    return r.sort_values(["is_leakage", "forca_intracelula"],
                         ascending=[True, False])


def estilo(mods):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
        "font.size": 11, "text.color": INK, "axes.labelcolor": INK2,
        "xtick.color": INK2, "ytick.color": INK2, "figure.dpi": 200,
    })
    return plt


def mapa(mods, plt, m, nome, titulo, sub):
    from matplotlib.colors import LinearSegmentedColormap
    np = mods["numpy"]
    n = len(m)
    cmap = LinearSegmentedColormap.from_list("div", DIV)
    fig, ax = plt.subplots(figsize=(0.62 * n + 3.4, 0.62 * n + 2.8))
    ax.imshow(m.to_numpy(float), cmap=cmap, vmin=-1, vmax=1)

    def pinta(rotulos):
        return [FOGO if r in VAZAMENTO else INK2 for r in rotulos]

    ax.set_xticks(range(n), m.columns, rotation=90, fontsize=8.5)
    ax.set_yticks(range(n), m.index, fontsize=8.5)
    for t, c in zip(ax.get_xticklabels(), pinta(m.columns)):
        t.set_color(c)
    for t, c in zip(ax.get_yticklabels(), pinta(m.index)):
        t.set_color(c)

    ax.set_xticks(np.arange(n + 1) - 0.5, minor=True)
    ax.set_yticks(np.arange(n + 1) - 0.5, minor=True)
    ax.grid(which="minor", color=SURF, linewidth=2)
    ax.tick_params(which="minor", length=0)
    ax.grid(which="major", visible=False)
    for lado in ax.spines.values():
        lado.set_visible(False)

    for a in range(n):
        for b in range(n):
            v = m.iat[a, b]
            if v != v or a == b:
                continue
            # Texto claro sobre fundo saturado, escuro sobre fundo claro.
            cor = SURF if abs(v) > 0.55 else INK
            ax.text(b, a, f"{v:.2f}", ha="center", va="center",
                    fontsize=7.2, color=cor)

    fig.text(0.007, 0.995, titulo, fontsize=14, fontweight="bold",
             color=INK, ha="left", va="top")
    import textwrap
    linhas = textwrap.wrap(sub, width=int(fig.get_figwidth() * 12))
    fig.text(0.007, 0.968, "\n".join(linhas), fontsize=9.5, color=INK2,
             ha="left", va="top", linespacing=1.35)
    fig.text(0.007, 0.006, "rotulo em vermelho = vazamento: a variavel e a "
             "capacidade por outro nome, e o SOH deriva dela.",
             fontsize=9, color=FOGO, ha="left", va="bottom")
    fig.tight_layout(rect=[0, 0.02, 1, 0.955 - 0.016 * len(linhas)])
    fig.savefig(SAIDA / nome, bbox_inches="tight")
    plt.close(fig)
    p(f"  {nome}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--sem-graficos", action="store_true")
    a = ap.parse_args()

    mods = checar()
    SAIDA.mkdir(parents=True, exist_ok=True)
    p("Mapa de calor com as areas e a forma da descarga")
    p("=" * 60)

    d, cols = preparar(mods)
    p(f"  {len(d)} descargas, {len(cols)} variaveis, "
      f"{d.battery_id.nunique()} baterias")

    agrupada, intra = matrizes(mods, d, cols)
    rank = ranking(mods, agrupada, intra)

    agrupada.to_csv(SAIDA / "matriz_agrupada.csv")
    intra.to_csv(SAIDA / "matriz_intracelula.csv")
    rank.to_csv(SAIDA / "ranking_vs_soh.csv")

    p("")
    p("  correlacao com o SOH, sem as vazadas no topo:")
    p(f"    {'variavel':<26} {'agrupada':>10} {'intra-celula':>13}")
    for i, r in rank.iterrows():
        marca = "  <- vazamento" if r.is_leakage else ""
        p(f"    {i:<26} {r.correlacao_agrupada:>10.3f} "
          f"{r.correlacao_intracelula:>13.3f}{marca}")

    p("")
    p(f"  {(SAIDA / 'ranking_vs_soh.csv').relative_to(RAIZ)}")

    if not a.sem_graficos:
        plt = estilo(mods)
        mapa(mods, plt, agrupada, "01_mapa_agrupado",
             "Correlacao agrupada",
             "Todas as descargas juntas. Mistura a diferenca entre celulas com a "
             "degradacao dentro de cada uma, e por isso engana: compare com o mapa "
             "intra-celula antes de concluir qualquer coisa daqui.")
        mapa(mods, plt, intra, "02_mapa_intracelula",
             "Correlacao intra-celula",
             "Cada variavel centrada na media da sua bateria x condicao antes de "
             "correlacionar. Remove o nivel proprio de cada celula e deixa so a "
             "variacao ao longo da vida. E esta que manda.")


if __name__ == "__main__":
    main()
