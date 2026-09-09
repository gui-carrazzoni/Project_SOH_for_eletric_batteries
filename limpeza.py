#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pre-processamento da tabela de atributos: limpeza, faltantes e redundancia.

    python limpeza.py                  # aplica a politica padrao
    python limpeza.py --teto-falta 0.3 # mais rigoroso com coluna esburacada
    python limpeza.py --grupo-minimo 5 # aceita grupos mais curtos
    python limpeza.py --podar          # remove tambem os pares redundantes

Le saida_nasa/correlacao/atributos_descargas.csv e escreve em
saida_nasa/preprocessado/: a tabela pronta para a normalizacao, o relatorio de
tudo que foi decidido e o mapa de faltantes.

**Nao normaliza e nao imputa.** Escalonamento e imputacao dependem da divisao
treino/teste (ajustar no conjunto inteiro vaza informacao do teste), entao ficam
para a etapa seguinte. Aqui os NaN sao preservados de proposito.

O que este script decide, e por que:

1. **Descarta o que esta marcado.** 44 descargas com capacidade ausente ou zero,
   mais as curvas curtas demais para render qualquer atributo.

2. **Descarta grupos curtos.** O SoH e a capacidade sobre a maior capacidade da
   celula naquela condicao. Num grupo de 2 descargas essa referencia quase
   certamente nao mede a capacidade cheia, e o SoH sai distorcido para todo o
   grupo. Nao e ruido de medicao: e um alvo mal definido.

3. **Remove o vazamento.** As tres colunas de que o alvo e derivado.

4. **Faltante estrutural nao e faltante aleatorio.** time_to_3_9_volts_seconds
   falta em 51% das linhas, e a falta e decidida pela condicao: a 4 A a tensao
   sob carga ja parte abaixo de 3,9 V, entao o limiar nunca e cruzado. Em 29 dos
   50 grupos a coluna esta 100% ausente. Imputar isso inventa um platô que a
   celula nunca teve. Coluna acima do teto sai; nas que ficam, a ausencia vira
   coluna indicadora, porque ela carrega sinal — onde time_to_3_5 falta, o SoH
   medio e 74% contra 82% onde existe.

5. **Redundancia e relatada, nao removida.** Onze pares passam de 0,95, ate 0,996
   entre time_to_3_5 e time_from_3_9_to_3_5. Isso atrapalha modelo linear e nao
   atrapalha arvore, entao a decisao e de quem escolhe o modelo. --podar remove.

Dependencias: numpy, pandas, matplotlib
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
ENTRADA = RAIZ / "saida_nasa" / "correlacao" / "tabela_modelagem.csv"
SAIDA = RAIZ / "saida_nasa" / "preprocessado"

PAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
       "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e3e2de"
SEQ = ["#fcfcfb", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#104281"]

# Colunas de que o alvo e derivado: usar como atributo e prever SoH a partir do SoH.
VAZAMENTO = ["capacity", "time"]
# Identificam a linha, nao entram no modelo, mas a divisao treino/teste precisa delas.
CHAVES = ["battery_id", "test_condition", "filename", "test_id",
          "charge_type", "discharge_type"]
ALVO = "SOH"

TETO_FALTA = 0.50      # coluna com mais falta que isso sai da tabela
GRUPO_MINIMO = 10      # descargas por bateria x condicao para o SoH ter referencia
LIMITE_REDUNDANCIA = 0.95
FALTA_INDICADORA = 0.01  # acima disso a ausencia vira coluna propria


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
        p("    Rode antes: python correlacao_soh.py")
        sys.exit(1)
    return mods


class Relatorio:
    """Acumula cada decisao com o custo em linhas e colunas."""

    def __init__(self):
        self.linhas = []

    def passo(self, titulo):
        self.linhas.append(("", ""))
        self.linhas.append((titulo, ""))

    def item(self, texto, valor=""):
        self.linhas.append(("  " + texto, str(valor)))
        p(f"  {texto:58s} {valor}")

    def escrever(self, caminho):
        larg = max(len(a) for a, _ in self.linhas) + 2
        with open(caminho, "w", encoding="utf-8") as f:
            f.write("Relatorio de limpeza\n")
            f.write("=" * (larg + 12) + "\n")
            for a, b in self.linhas:
                f.write(f"{a:<{larg}}{b}\n".rstrip() + "\n" if a or b else "\n")


# ---------------------------------------------------------------------------
def limpar(mods, df, rel, grupo_minimo):
    """Descarta ensaios marcados, extracoes falhas e grupos sem referencia."""
    pd = mods["pandas"]
    n0 = len(df)
    rel.passo("1. Limpeza de linhas")
    rel.item("descargas na entrada", n0)

    marcadas = df.quality_flag.notna() & (df.quality_flag != "")
    for motivo, n in df.loc[marcadas, "quality_flag"].value_counts().items():
        rel.item(f"descartadas por {motivo}", -n)
    df = df[~marcadas].drop(columns=["quality_flag"])

    # Curva curta demais para render atributo: atributos_curva devolveu vazio.
    # Colunas que so existem se a curva rendeu agregacao: se todas faltam, a
    # descarga foi curta demais para medir qualquer coisa.
    colunas_curva = ["voltage_measured", "current_measured", "temperature_measured",
                     "current_load", "voltage_load", "time"]
    colunas_curva = [c for c in colunas_curva if c in df.columns]
    vazias = df[colunas_curva].isna().all(axis=1)
    if vazias.any():
        rel.item("descartadas por extracao falha (curva curta demais)", -int(vazias.sum()))
        df = df[~vazias]

    # Grupo curto: cap_ref e o maximo do grupo e nao mede a capacidade cheia.
    tam = df.groupby(["battery_id", "test_condition"])[ALVO].transform("size")
    curto = tam < grupo_minimo
    if curto.any():
        gs = (df[curto].groupby(["battery_id", "test_condition"]).size()
              .sort_values(ascending=False))
        rel.item(f"descartadas em grupos com menos de {grupo_minimo} descargas",
                 -int(curto.sum()))
        for (b, c), n in gs.items():
            rel.item(f"    {b} / {c}", -n)
        df = df[~curto]

    rel.item("descargas restantes", len(df))
    rel.item("baterias restantes", df.battery_id.nunique())
    rel.item("grupos bateria x condicao restantes",
             df.groupby(["battery_id", "test_condition"]).ngroups)
    return df


def tirar_vazamento(df, rel):
    rel.passo("2. Remocao de vazamento")
    presentes = [c for c in VAZAMENTO if c in df.columns]
    for c in presentes:
        rel.item(f"removida: {c}", "o alvo e derivado dela")
    return df.drop(columns=presentes)


def tratar_faltantes(mods, df, rel, teto):
    """Descarta coluna esburacada; nas demais, a ausencia vira indicador."""
    np, pd = mods["numpy"], mods["pandas"]
    rel.passo("3. Faltantes")
    atributos = [c for c in df.columns if c not in CHAVES + [ALVO]]
    falta = df[atributos].isna().mean().sort_values(ascending=False)

    acima = falta[falta > teto]
    for c, f in acima.items():
        # Quantos grupos tem a coluna 100% ausente diz se a falta e estrutural
        g = df.groupby(["battery_id", "test_condition"])[c].apply(lambda s: s.isna().all())
        rel.item(f"removida: {c}", f"{f*100:.1f}% ausente, "
                 f"{int(g.sum())}/{len(g)} grupos sem nenhum valor")
    df = df.drop(columns=list(acima.index))

    restantes = [c for c in atributos if c not in acima.index]
    falta = df[restantes].isna().mean()
    indicadas = falta[falta > FALTA_INDICADORA].sort_values(ascending=False)
    for c, f in indicadas.items():
        sem = df.loc[df[c].isna(), ALVO].mean()
        com = df.loc[df[c].notna(), ALVO].mean()
        df[c + "_ausente"] = df[c].isna().astype(int)
        rel.item(f"indicador criado: {c}_ausente",
                 f"{f*100:.1f}% ausente, SoH {sem:.1f} sem contra {com:.1f} com")

    total = df[restantes].isna().sum().sum()
    completas = int(df[restantes].notna().all(axis=1).sum())
    rel.item("NaN preservados na tabela", total)
    rel.item("linhas sem nenhum NaN (caso completo)",
             f"{completas} de {len(df)} ({completas/len(df)*100:.1f}%)")
    rel.item("imputacao", "adiada: depende da divisao treino/teste")
    return df


def redundancia(mods, df, rel, podar):
    """Pares quase colineares: relatados sempre, removidos so com --podar."""
    np, pd = mods["numpy"], mods["pandas"]
    rel.passo("4. Redundancia")
    atributos = [c for c in df.columns
                 if c not in CHAVES + [ALVO] and not c.endswith("_ausente")]
    c = df[atributos].corr().abs()
    alto = (c.where(np.triu(np.ones(c.shape), 1).astype(bool)).stack()
            .sort_values(ascending=False))
    alto = alto[alto > LIMITE_REDUNDANCIA]
    if alto.empty:
        rel.item("nenhum par acima de", LIMITE_REDUNDANCIA)
        return df, pd.DataFrame()

    # Do par, sai quem tem correlacao mais fraca com o alvo; empate desempata
    # por cobertura. Nada e removido sem --podar.
    #
    # A forca aqui e a correlacao INTRA-CELULA, centrada por bateria x condicao.
    # Usar a correlacao agrupada inverteria a escolha em varios pares: agrupada,
    # time_to_3_0 da 0,29 e time_to_3_2 da 0,30, e o par acabaria descartando o
    # atributo mais forte da tabela (0,87 contra 0,80 intra-celula).
    chave = [df.battery_id, df.test_condition]
    dentro = df[atributos + [ALVO]].groupby(chave, observed=True).transform(
        lambda g: g - g.mean())
    # Coluna constante dentro do grupo (corrente, temperatura ambiente) zera ao
    # centrar: correlacao indefinida, forca zero, e sai do par se disputar.
    varia = [c for c in atributos if dentro[c].std() > 0]
    forca = dentro[varia].corrwith(dentro[ALVO]).abs().reindex(atributos).fillna(0.0)
    cobertura = df[atributos].notna().mean()
    pares, remover = [], set()
    for (a, b), r in alto.items():
        pior = a if (forca.get(a, 0), cobertura[a]) < (forca.get(b, 0), cobertura[b]) else b
        melhor = b if pior == a else a
        pares.append({"atributo_a": a, "atributo_b": b, "correlacao": round(r, 4),
                      "sugerido_remover": pior, "mantido": melhor})
        rel.item(f"r={r:.3f}  {a} ~ {b}", f"sugere remover {pior}")
        if a not in remover and b not in remover:
            remover.add(pior)
    if podar:
        rel.item("removidas por --podar", ", ".join(sorted(remover)))
        df = df.drop(columns=list(remover))
    else:
        rel.item("mantidas", "use --podar para remover as sugeridas")
    return df, pd.DataFrame(pares)


# ---------------------------------------------------------------------------
def mapa_faltantes(mods, plt, bruto, nome):
    """Falta por condicao x coluna: mostra que o buraco segue o protocolo."""
    from matplotlib.colors import LinearSegmentedColormap
    np, pd = mods["numpy"], mods["pandas"]
    d = bruto[bruto.quality_flag.isna()]
    cols = [c for c in d.columns
            if c not in CHAVES + [ALVO, "quality_flag"] and d[c].dtype.kind == "f"]
    m = (d.groupby("test_condition")[cols].apply(lambda g: g.isna().mean()) * 100)
    m = m.loc[:, m.max() > 0].sort_index()
    ordem = m.mean().sort_values(ascending=False).index
    m = m[ordem]
    # Mapa de faltantes so vale a pena se houver falta para mostrar. No esquema da
    # Tabela 2 a tabela sai praticamente completa, e um mapa em branco engana mais
    # do que informa.
    if m.empty or m.to_numpy().max() < 5:
        pico = 0.0 if m.empty else float(m.to_numpy().max())
        p(f"  mapa de faltantes dispensado: pico de ausencia e {pico:.1f}%")
        return
    n_l, n_c = m.shape
    cmap = LinearSegmentedColormap.from_list("seq", SEQ)
    fig, ax = plt.subplots(figsize=(0.55 * n_c + 5, 0.45 * n_l + 3.4))
    ax.imshow(m.to_numpy(float), cmap=cmap, vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(n_c), m.columns, rotation=90, fontsize=8)
    ax.set_yticks(range(n_l), [f"{i}  (n={int((d.test_condition == i).sum())})"
                               for i in m.index], fontsize=9)
    ax.set_xticks(np.arange(n_c + 1) - 0.5, minor=True)
    ax.set_yticks(np.arange(n_l + 1) - 0.5, minor=True)
    ax.grid(which="minor", color=SURF, linewidth=2)
    ax.tick_params(which="minor", length=0)
    ax.grid(which="major", visible=False)
    for lado in ax.spines.values():
        lado.set_visible(False)
    for a in range(n_l):
        for b in range(n_c):
            val = m.iat[a, b]
            if val >= 5:
                ax.text(b, a, f"{val:.0f}", ha="center", va="center", fontsize=7.5,
                        color=SURF if val > 55 else INK)
    barra = fig.colorbar(ax.images[0], ax=ax, shrink=0.6, pad=0.015)
    barra.set_label("% ausente", color=INK2, fontsize=9)
    barra.outline.set_visible(False)
    pior_col = m.max().idxmax()
    pior_lin = m[pior_col].idxmax()
    fig.suptitle("Onde a falta se concentra", fontsize=15,
                 fontweight="bold", color=INK, x=0.007, ha="left", y=0.995)
    fig.text(0.007, 0.945, "Percentual ausente por condicao de ensaio. O pior caso e "
             f"{pior_col} em {pior_lin}, com {m.loc[pior_lin, pior_col]:.0f}% ausente. "
             "Falta concentrada numa condicao e estrutural, nao acaso: veja o protocolo "
             "antes de imputar.",
             fontsize=10.5, color=INK2, ha="left", va="top")
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    fig.savefig(SAIDA / nome, bbox_inches="tight")
    plt.close(fig)
    p(f"  {nome}")


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--teto-falta", type=float, default=TETO_FALTA,
                    help=f"fracao maxima de ausencia tolerada (padrao {TETO_FALTA})")
    ap.add_argument("--grupo-minimo", type=int, default=GRUPO_MINIMO,
                    help=f"descargas minimas por grupo (padrao {GRUPO_MINIMO})")
    ap.add_argument("--podar", action="store_true",
                    help="remove os atributos redundantes sugeridos")
    ap.add_argument("--sem-graficos", action="store_true")
    args = ap.parse_args()

    mods = checar()
    pd = mods["pandas"]
    SAIDA.mkdir(parents=True, exist_ok=True)
    bruto = pd.read_csv(ENTRADA)
    rel = Relatorio()

    p("pre-processamento:")
    df = limpar(mods, bruto.copy(), rel, args.grupo_minimo)
    df = tirar_vazamento(df, rel)
    df = tratar_faltantes(mods, df, rel, args.teto_falta)
    df, pares = redundancia(mods, df, rel, args.podar)

    # Chaves primeiro, alvo por ultimo: facilita a divisao por bateria depois.
    atributos = [c for c in df.columns if c not in CHAVES + [ALVO]]
    df = df[[c for c in CHAVES if c in df.columns] + sorted(atributos) + [ALVO]]

    rel.passo("5. Saida")
    rel.item("linhas", len(df))
    rel.item("atributos (fora chaves e alvo)", len(atributos))
    rel.item("baterias", df.battery_id.nunique())
    rel.item("proxima etapa", "normalizacao, ajustada so no treino")

    df.to_csv(SAIDA / "dados_modelagem.csv", index=False)
    p(f"  dados_modelagem.csv  ({len(df)} x {len(df.columns)})")
    if not pares.empty:
        pares.to_csv(SAIDA / "pares_redundantes.csv", index=False)
        p("  pares_redundantes.csv")
    rel.escrever(SAIDA / "relatorio_preprocessamento.txt")
    p("  relatorio_preprocessamento.txt")

    if not args.sem_graficos:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.rcParams.update({
            "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
            "font.size": 10, "text.color": INK, "axes.labelcolor": INK2,
            "xtick.color": INK2, "ytick.color": INK2, "figure.dpi": 150,
        })
        mapa_faltantes(mods, plt, bruto, "01_mapa_faltantes.png")


if __name__ == "__main__":
    main()
