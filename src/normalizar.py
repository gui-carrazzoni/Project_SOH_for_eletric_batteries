#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Normalizacao: divisao por bateria, referencia de inicio de vida e escalonamento.

    python normalizar.py                      # politica padrao
    python normalizar.py --ciclos-referencia 10
    python normalizar.py --fracao-teste 0.3
    python normalizar.py --so-relativas       # descarta as colunas brutas
    python normalizar.py --so-brutas          # nao calcula as relativas

Le saida_nasa/preprocessado/dados_modelagem.csv e escreve em
saida_nasa/normalizado/.

Sao tres coisas distintas que costumam receber o mesmo nome:

**1. Divisao por bateria.** Dividir por descarga poria a mesma celula no treino e
no teste, e como cada celula tem seu proprio nivel de tensao, o modelo acertaria
por reconhecer a celula em vez de medir degradacao. E o vazamento entre celulas
que o artigo declara querer evitar. Aqui o teste leva baterias inteiras, e a
escolha e estratificada por condicao para que nenhuma condicao fique so de um
lado. As baterias de treino ainda recebem uma coluna `fold` para validacao
cruzada, tambem por bateria.

**2. Referencia de inicio de vida.** Cada celula vive num nivel proprio:
voltage_load fica em 0,67 V a 4 A / 4 C e em 2,88 V a 1 A / 4 C. Junte as 34 e o
nivel domina a nuvem — a correlacao agrupada de voltage_load com SOH cai para
0,10 enquanto a intra-celula e 0,63. Subtrair de cada valor a mediana dos
primeiros ciclos DAQUELA celula converte "2,5 V" em "0,35 V abaixo do que esta
celula entregava quando nova", e ai o numero atravessa celulas: a correlacao
agrupada sobe de 0,10 para 0,49.

    Isso NAO e vazamento: usa os primeiros ciclos da propria celula, nunca o
    alvo, e e informacao que um BMS real tem — voce conhece a celula quando ela
    e nova. Mas assume que a celula de teste tem historico de inicio de vida. Se
    o cenario for "celula chega no meio da vida, sem historico", nao vale.

    Testadas quatro formas: x-ref ganhou de (x-ref)/ref, de (x-ref)/desvio e de
    usar 10 ciclos de referencia em vez de 5. O ganho nao e uniforme — ajuda
    muito as de tensao e o re, nao mexe em rectified_impedance e piora rct —
    entao por padrao as colunas brutas ficam ao lado das relativas e a escolha
    fica para a modelagem. 01_ganho_da_referencia.png tem a comparacao.

**3. Escalonamento z-score, ajustado SO NO TREINO.** Media e desvio saem das
baterias de treino e sao aplicados aos dois lados. Ajustar no conjunto inteiro
deixaria a escala do teste influenciar o treino.

    A tabela sai escalonada pelos parametros de treino, o que serve para o fluxo
    treino/teste simples. Para validacao cruzada honesta o escalonamento tem que
    ser refeito por fold: parametros_escala.csv traz uma linha por fold alem da
    linha do treino inteiro.

Dependencias: numpy, pandas, matplotlib
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# A raiz do projeto e a pasta acima de src/: e la que ficam
# cleaned_nasa_dataset/ e saida_nasa/.
RAIZ = Path(__file__).resolve().parent.parent
ENTRADA = RAIZ / "saida_nasa" / "preprocessado" / "dados_modelagem.csv"
SAIDA = RAIZ / "saida_nasa" / "normalizado"

PAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
       "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e3e2de"

ALVO = "SOH"
CHAVES = ["battery_id", "test_condition", "filename", "test_id",
          "charge_type", "discharge_type"]
# Nao ganham referencia de inicio de vida: cycle ja e relativo a vida da celula e
# ambient_temperature e constante dentro do grupo.
SEM_REFERENCIA = ["cycle", "ambient_temperature"]

CICLOS_REFERENCIA = 5
FRACAO_TESTE = 0.25
N_FOLDS = 5
SEMENTE = 20260909


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
        p("    Rode antes: python preprocessar.py")
        sys.exit(1)
    return mods


# ---------------------------------------------------------------------------
def dividir(mods, df, fracao_teste, n_folds):
    """Teste leva baterias inteiras, estratificado por condicao principal."""
    np, pd = mods["numpy"], mods["pandas"]
    principal = df.groupby("battery_id").test_condition.agg(
        lambda s: s.mode().iloc[0])
    rng = np.random.default_rng(SEMENTE)

    # As baterias tem tamanhos muito diferentes (12 a 197 descargas), entao
    # separar uma fracao das BATERIAS nao separa a mesma fracao das DESCARGAS.
    # Dentro de cada condicao, o teste recebe baterias enquanto o total de
    # descargas nao passar da fracao pedida.
    tamanho = df.groupby("battery_id").size()
    teste, treino = [], []
    for cond, grupo in principal.groupby(principal):
        bats = sorted(grupo.index)
        rng.shuffle(bats)
        if len(bats) < 2:
            treino += bats           # condicao com uma bateria so fica no treino
            continue
        alvo_n = tamanho[bats].sum() * fracao_teste
        acumulado, escolhidas = 0, []
        for b in bats[:-1]:          # nunca leva todas: a condicao perderia o treino
            if acumulado == 0 or acumulado + tamanho[b] / 2 <= alvo_n:
                escolhidas.append(b)
                acumulado += tamanho[b]
        teste += escolhidas
        treino += [b for b in bats if b not in escolhidas]

    # Folds sobre as baterias de treino, distribuindo por condicao para nao
    # concentrar uma condicao inteira num fold so.
    fold = {}
    for cond, grupo in principal[principal.index.isin(treino)].groupby(principal):
        bats = sorted(grupo.index)
        rng.shuffle(bats)
        for i, b in enumerate(bats):
            fold[b] = i % n_folds

    df = df.copy()
    df["split"] = np.where(df.battery_id.isin(teste), "teste", "treino")
    df["fold"] = df.battery_id.map(fold).astype("Int64")
    return df, sorted(teste), sorted(treino)


def referenciar(mods, df, colunas, n_ciclos):
    """x menos a mediana dos primeiros n_ciclos daquela bateria x condicao."""
    np, pd = mods["numpy"], mods["pandas"]
    chave = ["battery_id", "test_condition"]
    inicio = (df.sort_values(chave + ["cycle"]).groupby(chave, observed=True)
              .head(n_ciclos))
    ref = inicio.groupby(chave, observed=True)[colunas].median()
    ref.columns = [c + "_ref" for c in colunas]
    juncao = df[chave].merge(ref, left_on=chave, right_index=True, how="left")
    for c in colunas:
        df[c + "_rel"] = df[c].to_numpy() - juncao[c + "_ref"].to_numpy()
    return df, ref.reset_index()


def escalonar(mods, df, colunas, rel):
    """z-score com media e desvio das baterias de treino."""
    np, pd = mods["numpy"], mods["pandas"]
    treino = df[df.split == "treino"]
    linhas = [{"conjunto": "treino_completo", "coluna": c,
               "media": float(treino[c].mean()), "desvio": float(treino[c].std())}
              for c in colunas]
    # Parametros por fold, para quem for fazer validacao cruzada honesta
    for k in sorted(df.fold.dropna().unique()):
        sub = treino[treino.fold != k]
        linhas += [{"conjunto": f"fold_{int(k)}", "coluna": c,
                    "media": float(sub[c].mean()), "desvio": float(sub[c].std())}
                   for c in colunas]
    par = pd.DataFrame(linhas)

    completo = par[par.conjunto == "treino_completo"].set_index("coluna")
    for c in colunas:
        s = completo.loc[c, "desvio"]
        df[c] = (df[c] - completo.loc[c, "media"]) / (s if s > 0 else 1.0)
    return df, par


# ---------------------------------------------------------------------------
def ganho(mods, plt, bruto, df, colunas, nome):
    """Quanto a referencia de inicio de vida aproxima a agrupada da intra."""
    np, pd = mods["numpy"], mods["pandas"]
    chave = ["battery_id", "test_condition"]
    linhas = []
    for c in colunas:
        dentro = bruto.groupby(chave)[[c, ALVO]].transform(lambda s: s - s.mean())
        linhas.append({
            "coluna": c,
            "agrupada": bruto[c].corr(bruto[ALVO]),
            "relativa": df[c + "_rel"].corr(bruto[ALVO]) if c + "_rel" in df else np.nan,
            "intra": dentro[c].corr(dentro[ALVO]),
        })
    g = pd.DataFrame(linhas).set_index("coluna")
    g = g.reindex(g.intra.abs().sort_values().index)

    fig, ax = plt.subplots(figsize=(9.5, 0.52 * len(g) + 2.9))
    y = np.arange(len(g))
    for k in y:
        ax.plot([g.agrupada.iloc[k], g.intra.iloc[k]], [k, k],
                color=GRID, linewidth=2.5, zorder=1, solid_capstyle="round")
    # Cor e forma juntas: as tres cores passam o validador de daltonismo
    # (pior par deutan dE 13,0), e a forma sustenta a identidade em impressao
    # preto e branco.
    ax.scatter(g.agrupada, y, s=95, color=PAL[7], marker="o", zorder=3,
               label="agrupada, bruta", edgecolors=SURF, linewidths=2)
    ax.scatter(g.relativa, y, s=105, color=PAL[0], marker="D", zorder=4,
               label="agrupada, com referencia de inicio de vida",
               edgecolors=SURF, linewidths=2)
    ax.scatter(g.intra, y, s=115, color=PAL[6], marker="s", zorder=3,
               label="intra-celula (teto)", edgecolors=SURF, linewidths=2)
    ax.set_yticks(y, g.index, fontsize=9.5)
    ax.axvline(0, color=INK2, linewidth=1)
    ax.set_xlim(-1.02, 1.02)
    ax.set_xlabel("correlacao com SOH")
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.legend(fontsize=9, loc="lower center", bbox_to_anchor=(0.5, 1.005),
              ncol=3, borderaxespad=0)
    fig.suptitle("O que a referencia de inicio de vida recupera", fontsize=15,
                 fontweight="bold", color=INK, x=0.007, ha="left", y=0.995)
    fig.text(0.007, 0.945, "Cada linha e uma variavel. O circulo vermelho e a correlacao "
             "agrupada crua, o quadrado roxo e o teto que a intra-celula mostra existir, e o "
             "losango azul e onde a agrupada chega depois de subtrair a mediana dos primeiros "
             "ciclos de cada celula.", fontsize=10.5, color=INK2, ha="left", va="top")
    fig.subplots_adjust(top=0.80)
    fig.tight_layout(rect=[0, 0, 1, 0.86])
    fig.savefig(SAIDA / nome, bbox_inches="tight")
    plt.close(fig)
    p(f"  {nome}")
    return g


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ciclos-referencia", type=int, default=CICLOS_REFERENCIA)
    ap.add_argument("--fracao-teste", type=float, default=FRACAO_TESTE)
    ap.add_argument("--folds", type=int, default=N_FOLDS)
    ap.add_argument("--so-relativas", action="store_true",
                    help="descarta as colunas brutas, fica so com as relativas")
    ap.add_argument("--so-brutas", action="store_true",
                    help="nao calcula as colunas relativas")
    ap.add_argument("--sem-graficos", action="store_true")
    args = ap.parse_args()

    mods = checar()
    np, pd = mods["numpy"], mods["pandas"]
    SAIDA.mkdir(parents=True, exist_ok=True)
    bruto = pd.read_csv(ENTRADA)
    numericas = [c for c in bruto.columns
                 if c not in CHAVES + [ALVO] and bruto[c].dtype.kind in "if"]

    p("1. divisao por bateria:")
    df, teste, treino = dividir(mods, bruto, args.fracao_teste, args.folds)
    n_tr, n_te = int((df.split == "treino").sum()), int((df.split == "teste").sum())
    p(f"  treino  {len(treino)} baterias, {n_tr} descargas ({n_tr/len(df)*100:.0f}%)")
    p(f"  teste   {len(teste)} baterias, {n_te} descargas ({n_te/len(df)*100:.0f}%)")
    p(f"  teste:  {', '.join(teste)}")
    cob = df.groupby("test_condition").split.agg(lambda s: sorted(set(s)))
    orfas = cob[cob.map(len) == 1]
    for cond, lados in orfas.items():
        p(f"  AVISO: condicao {cond} so aparece em {lados[0]}")

    p("2. referencia de inicio de vida:")
    if args.so_brutas:
        p("  pulada (--so-brutas)")
        com_ref = []
    else:
        com_ref = [c for c in numericas if c not in SEM_REFERENCIA]
        df, ref = referenciar(mods, df, com_ref, args.ciclos_referencia)
        ref.to_csv(SAIDA / "referencias_por_celula.csv", index=False)
        p(f"  mediana dos {args.ciclos_referencia} primeiros ciclos de cada "
          f"bateria x condicao, em {len(com_ref)} colunas")
        p("  referencias_por_celula.csv")

    if args.so_relativas and com_ref:
        df = df.drop(columns=com_ref)
        numericas = [c for c in numericas if c in SEM_REFERENCIA]
    escalaveis = [c for c in df.columns
                  if (c in numericas or c.endswith("_rel")) and c != ALVO]

    p("3. escalonamento z-score, ajustado so no treino:")
    df, par = escalonar(mods, df, escalaveis, com_ref)
    par.round(6).to_csv(SAIDA / "parametros_escala.csv", index=False)
    p(f"  {len(escalaveis)} colunas escalonadas")
    p(f"  parametros_escala.csv  (treino completo + {args.folds} folds)")

    ordem = ([c for c in CHAVES if c in df.columns] + ["split", "fold"]
             + sorted(escalaveis) + [ALVO])
    df = df[ordem]
    df.to_csv(SAIDA / "dados_normalizados.csv", index=False)
    p(f"  dados_normalizados.csv  ({len(df)} x {len(df.columns)})")

    if not args.sem_graficos and com_ref:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.rcParams.update({
            "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
            "font.size": 10, "text.color": INK, "axes.labelcolor": INK2,
            "xtick.color": INK2, "ytick.color": INK2, "axes.edgecolor": GRID,
            "axes.spines.top": False, "axes.spines.right": False,
            "legend.frameon": False, "figure.dpi": 150,
        })
        p("graficos:")
        # O grafico compara correlacoes na escala original, nao na escalonada
        g = ganho(mods, plt, bruto, pd.read_csv(ENTRADA).join(
            df[[c for c in df.columns if c.endswith("_rel")]]), com_ref,
            "01_ganho_da_referencia.png")
        p()
        p("Correlacao com SOH, antes e depois da referencia de inicio de vida:")
        p(g.round(3).to_string())


if __name__ == "__main__":
    main()
