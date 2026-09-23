#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tabela de modelagem no esquema da Tabela 2 do artigo, e correlacao contra SOH.

    python correlacao_soh.py                # monta (usa cache), correlaciona, plota
    python correlacao_soh.py --sem-graficos # so as tabelas
    python correlacao_soh.py --remontar     # ignora o cache e rele as 2.794 curvas

Escreve em saida_nasa/correlacao/.

O esquema e o dicionario de dados do artigo, uma coluna por variavel, sem
acrescimo. O que este script resolve para chegar la:

**A Tabela 2 mistura tres niveis de medicao.** No dataset, voltage_measured e
por instante (~490 linhas por ensaio), capacity e por descarga, e re / rct /
rectified_impedance sao por ensaio de impedancia. Nenhuma linha do dataset tem
as tres juntas. A tabela de modelagem tem que morar num nivel so, e o nivel do
alvo e a **descarga** — e ali que SOH existe. Entao cada coluna por instante vira
a media daquela descarga, e as de impedancia vem do ensaio mais proximo da mesma
bateria. Uma coluna do artigo, uma coluna aqui.

**A media e tomada so no trecho sob carga.** Toda descarga termina com um rabo em
repouso, corrente zero e tensao subindo de volta. Incluir isso na media de
voltage_measured mede a bateria descansando, nao descarregando.

**charge_type e discharge_type nao sao colunas do dataset.** Estao em texto
corrido nos README de extra_infos/, um por grupo de baterias. A tabela PROTOCOLO
abaixo transcreve os nove. charge_type e identico nas 34; discharge_type separa
as quatro baterias de carga pulsada das trinta de corrente constante.

**capacity e vazamento para SOH.** SOH e capacity dividido pela capacidade de
referencia. A coluna fica na tabela porque esta na Tabela 2, marcada como
vazamento no ranking. Para o RUL mais adiante ela e atributo legitimo; para o
SOH ela e a resposta.

Dependencias: numpy, pandas, matplotlib
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# A raiz do projeto e a pasta acima de src/: e la que ficam
# cleaned_nasa_dataset/ e saida_nasa/.
RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "cleaned_nasa_dataset"
SAIDA = RAIZ / "saida_nasa" / "correlacao"

PAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
       "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e3e2de"
DIV = ["#7d1f1d", "#b93331", "#d97370", "#eab5b3", "#f0efec",
       "#adc9ee", "#6d9fe4", "#2a78d6", "#104281"]

ALVO = "SOH"
VAZAMENTO = {"capacity", "time"}
MIN_GRUPO = 12
LIMITE_RESISTENCIA = 1.0   # ohm; acima disso e lixo de ajuste numerico

# Protocolo de cada bateria, transcrito dos README de extra_infos/. O carregamento
# e identico nas 34; a descarga separa as pulsadas (B0025-B0028, onda quadrada de
# 0,05 Hz e 50% de duty) das de corrente constante. O corte de tensao varia por
# bateria dentro de cada grupo.
CARGA_PADRAO = "CC 1.5A ate 4.2V + CV ate 20mA"
PROTOCOLO = {
    # README_05_06_07_18
    "B0005": ("CC", 2.7), "B0006": ("CC", 2.5), "B0007": ("CC", 2.2), "B0018": ("CC", 2.5),
    # README_25_26_27_28 — unico grupo com carga pulsada
    "B0025": ("pulsado", 2.0), "B0026": ("pulsado", 2.2),
    "B0027": ("pulsado", 2.5), "B0028": ("pulsado", 2.7),
    # README_29_30_31_32
    "B0029": ("CC", 2.0), "B0030": ("CC", 2.2), "B0031": ("CC", 2.5), "B0032": ("CC", 2.7),
    # README_33_34_36
    "B0033": ("CC", 2.0), "B0034": ("CC", 2.2), "B0036": ("CC", 2.7),
    # README_38_39_40
    "B0038": ("CC", 2.2), "B0039": ("CC", 2.5), "B0040": ("CC", 2.7),
    # README_41_42_43_44
    "B0041": ("CC", 2.0), "B0042": ("CC", 2.2), "B0043": ("CC", 2.5), "B0044": ("CC", 2.7),
    # README_45_46_47_48
    "B0045": ("CC", 2.0), "B0046": ("CC", 2.2), "B0047": ("CC", 2.5), "B0048": ("CC", 2.7),
    # README_49_50_51_52
    "B0049": ("CC", 2.0), "B0050": ("CC", 2.2), "B0051": ("CC", 2.5), "B0052": ("CC", 2.7),
    # README_53_54_55_56
    "B0053": ("CC", 2.0), "B0054": ("CC", 2.2), "B0055": ("CC", 2.5), "B0056": ("CC", 2.7),
}

# Dicionario de dados, no texto do artigo. Serve de checagem: montar() reclama de
# coluna que apareca na tabela sem estar aqui.
DICIONARIO = {
 "battery_id": ("Categorica", "-", "metadata.csv", "Identificador da celula de bateria."),
 "cycle": ("Inteiro", "-", "derivado", "Identificador do ciclo de operacao da bateria."),
 "ambient_temperature": ("Numerico", "C", "metadata.csv", "Temperatura ambiente durante o ensaio."),
 "voltage_measured": ("Numerico", "V", "Voltage_measured",
  "Tensao medida na bateria, media do trecho sob carga da descarga."),
 "current_measured": ("Numerico", "A", "Current_measured",
  "Corrente medida durante a descarga, media do trecho sob carga."),
 "temperature_measured": ("Numerico", "C", "Temperature_measured",
  "Temperatura da celula durante a operacao, media do trecho sob carga."),
 "current_load": ("Numerico", "A", "Current_load",
  "Corrente aplicada a carga, media do trecho sob carga."),
 "voltage_load": ("Numerico", "V", "Voltage_load",
  "Tensao observada na carga, media do trecho sob carga."),
 "time": ("Numerico", "s", "Time", "Tempo decorrido durante o ciclo, ate o fim da descarga."),
 "capacity": ("Numerico", "Ah", "metadata.csv",
  "Capacidade disponivel medida no ciclo. VAZAMENTO para SOH: o alvo e derivado dela."),
 "rectified_impedance": ("Numerico", "ohm", "Rectified_Impedance",
  "Impedancia corrigida do ensaio EIS mais proximo, magnitude media da varredura."),
 "re": ("Numerico", "ohm", "metadata.csv (Re)", "Resistencia eletrolitica estimada."),
 "rct": ("Numerico", "ohm", "metadata.csv (Rct)", "Resistencia de transferencia de carga."),
 "charge_type": ("Categorica", "-", "extra_infos/README",
  "Protocolo de carga. Identico nas 34 baterias: CC 1.5A ate 4.2V mais CV ate 20mA."),
 "discharge_type": ("Categorica", "-", "extra_infos/README",
  "Perfil e corte da descarga, ex. 'CC ate 2.5V'. O perfil e CC em 30 baterias e "
  "pulsado (onda quadrada 0,05 Hz, 50% duty) em B0025-B0028; o corte vai de 2,0 a 2,7 V."),
 "SOH": ("Numerico", "%", "derivado", "Estado de saude da bateria. Variavel-alvo."),
 # colunas de trabalho, fora da Tabela 2
 "test_condition": ("Categorica", "-", "derivado",
  "Corrente e temperatura do protocolo. Fora da Tabela 2: agrupa a analise."),
 "quality_flag": ("Categorica", "-", "derivado",
  "Marca de capacidade ausente ou zero. Fora da Tabela 2: limpeza."),
 "test_id": ("Inteiro", "-", "metadata.csv", "Ordem do ensaio na celula. Fora da Tabela 2."),
 "filename": ("Categorica", "-", "metadata.csv", "CSV da curva bruta. Fora da Tabela 2."),
}


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
    if not (RAIZ / "saida_nasa" / "metricas_descargas.csv").exists():
        p("ERRO: saida_nasa/metricas_descargas.csv nao existe.")
        p("    Rode antes: python graficos_nasa.py")
        sys.exit(1)
    if not DADOS.exists():
        p(f"ERRO: {DADOS.name}/ nao existe. Rode antes: python preparar_dados.py")
        sys.exit(1)
    return mods


def para_complexo(serie, np, pd):
    """As colunas de impedancia vem como '(0.17-0.023j)'. float perde a fase."""
    def um(v):
        if pd.isna(v):
            return complex("nan+nanj")
        try:
            return complex(str(v).strip())
        except ValueError:
            return complex("nan+nanj")
    return serie.map(um).to_numpy(complex)


# ---------------------------------------------------------------------------
# tabela de modelagem
# ---------------------------------------------------------------------------
def agregar_descarga(c, np):
    """Uma descarga -> uma linha, uma coluna por variavel da Tabela 2.

    A media e tomada so no trecho sob carga: o rabo em repouso, com corrente zero
    e tensao subindo de volta, mede a bateria descansando e nao descarregando.
    """
    il = np.abs(c.Current_load.to_numpy(float))
    carga = il > 0.1
    if carga.sum() < 5:
        return {}
    k0 = int(carga.argmax())
    k1 = int(len(carga) - 1 - carga[::-1].argmax())
    faixa = slice(k0, k1 + 1)
    t = c.Time.to_numpy(float)
    return {
        "voltage_measured": float(c.Voltage_measured.to_numpy(float)[faixa].mean()),
        "current_measured": float(c.Current_measured.to_numpy(float)[faixa].mean()),
        "temperature_measured": float(c.Temperature_measured.to_numpy(float)[faixa].mean()),
        "current_load": float(c.Current_load.to_numpy(float)[faixa].mean()),
        "voltage_load": float(c.Voltage_load.to_numpy(float)[faixa].mean()),
        "time": float(t[k1] - t[k0]),
    }


def impedancia_por_ensaio(mods):
    """re, rct e rectified_impedance de cada ensaio de impedancia."""
    np, pd = mods["numpy"], mods["pandas"]
    meta = pd.read_csv(DADOS / "metadata.csv")
    z = meta[meta.type == "impedance"].copy()
    z["re"] = np.abs(para_complexo(z.Re, np, pd))
    z["rct"] = np.abs(para_complexo(z.Rct, np, pd))

    # rectified_impedance: a Tabela 2 pede um numero por ensaio; a varredura tem
    # 48 frequencias, entao entra a magnitude media da varredura.
    valores = []
    for arquivo in z.filename:
        try:
            d = pd.read_csv(DADOS / "data" / arquivo)
            zc = para_complexo(d.Rectified_Impedance, np, pd)
            valores.append(float(np.nanmean(np.abs(zc))))
        except Exception:
            valores.append(np.nan)
    z["rectified_impedance"] = valores

    # Os 14 ensaios com resistencia de ate 1e15 ohm sao lixo de ajuste numerico:
    # a mediana e 0,07 ohm. Viram vazio em vez de contaminar a media.
    for col in ("re", "rct", "rectified_impedance"):
        z.loc[~z[col].between(0, LIMITE_RESISTENCIA, inclusive="right"), col] = np.nan
    return z[["battery_id", "test_id", "re", "rct", "rectified_impedance"]]


def montar(mods, remontar=False):
    """Tabela de modelagem. Cacheada: ler 2.794 curvas leva minutos."""
    np, pd = mods["numpy"], mods["pandas"]
    cache = SAIDA / "tabela_modelagem.csv"
    if cache.exists() and not remontar:
        p(f"  cache: {cache.relative_to(RAIZ)}")
        return pd.read_csv(cache)

    base = pd.read_csv(RAIZ / "saida_nasa" / "metricas_descargas.csv")
    p(f"  agregando {len(base)} descargas...")
    linhas = []
    for n, arquivo in enumerate(base.filename, 1):
        if n % 500 == 0:
            p(f"    {n}/{len(base)}")
        try:
            linhas.append(agregar_descarga(pd.read_csv(DADOS / "data" / arquivo), np))
        except Exception:
            linhas.append({})
    df = pd.DataFrame(linhas, index=base.index)

    df["battery_id"] = base.battery_id
    df["cycle"] = base.ciclo
    df["ambient_temperature"] = base.ambient_temperature
    df["capacity"] = base.Capacity
    df[ALVO] = base["SoH_%"]
    df["test_condition"] = base.condicao
    df["quality_flag"] = base.alerta
    df["test_id"] = base.test_id
    df["filename"] = base.filename

    # Protocolo, dos README de extra_infos/
    df["charge_type"] = CARGA_PADRAO
    # Perfil e corte juntos numa coluna so: a Tabela 2 tem discharge_type e nao
    # tem coluna de corte, e o corte e constante dentro da bateria — como coluna
    # numerica separada ele zera ao centrar e nao mede degradacao nenhuma.
    def rotulo_descarga(b):
        perfil, corte = PROTOCOLO.get(b, (None, None))
        return f"{perfil} ate {corte:g}V" if perfil else "?"
    df["discharge_type"] = df.battery_id.map(rotulo_descarga)
    if (df.discharge_type == "?").any():
        faltam = sorted(df.loc[df.discharge_type == "?", "battery_id"].unique())
        p(f"  AVISO: sem protocolo em PROTOCOLO: {', '.join(faltam)}")

    # Impedancia do ensaio mais proximo da mesma bateria
    z = impedancia_por_ensaio(mods)
    for col in ("re", "rct", "rectified_impedance"):
        df[col] = np.nan
    for bateria, g in df.groupby("battery_id"):
        gz = z[z.battery_id == bateria]
        if gz.empty:
            continue
        idx = np.abs(g.test_id.to_numpy()[:, None]
                     - gz.test_id.to_numpy()[None, :]).argmin(axis=1)
        for col in ("re", "rct", "rectified_impedance"):
            df.loc[g.index, col] = gz[col].to_numpy()[idx]

    orfas = [c for c in df.columns if c not in DICIONARIO]
    if orfas:
        p(f"  AVISO: colunas fora do DICIONARIO: {', '.join(orfas)}")

    ordem = [c for c in DICIONARIO if c in df.columns]
    df = df[ordem]
    SAIDA.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache, index=False)
    p(f"  tabela_modelagem.csv  ({len(df)} x {len(df.columns)})")
    return df


# ---------------------------------------------------------------------------
# correlacao
# ---------------------------------------------------------------------------
def preparar(mods, df):
    bom = df[df.quality_flag.isna() | (df.quality_flag == "")].copy()
    num = bom.select_dtypes("number").drop(columns=["test_id"], errors="ignore")
    num = num.loc[:, num.notna().mean() >= 0.30]
    return bom, num.loc[:, num.std(numeric_only=True) > 0]


def centrar(mods, bom, num):
    """Centra por bateria x condicao: mede degradacao, nao diferenca entre celulas."""
    chave = [bom.battery_id, bom.test_condition]
    tam = num.groupby(chave, observed=True).transform("size")
    return (num - num.groupby(chave, observed=True).transform("mean")).where(tam >= MIN_GRUPO)


def por_celula(mods, bom, num):
    np, pd = mods["numpy"], mods["pandas"]
    linhas = {}
    for col in num.columns:
        if col == ALVO:
            continue
        rs = []
        for _, g in num.groupby([bom.battery_id, bom.test_condition], observed=True):
            par = g[[col, ALVO]].dropna()
            if len(par) >= MIN_GRUPO and par[col].std() > 0:
                rs.append(par[col].corr(par[ALVO]))
        rs = np.array([r for r in rs if r == r])
        if len(rs):
            linhas[col] = {"group_count": len(rs),
                           "median_per_cell_correlation": float(np.median(rs)),
                           "per_cell_correlation_p10": float(np.percentile(rs, 10)),
                           "per_cell_correlation_p90": float(np.percentile(rs, 90)),
                           "same_sign_fraction": float((np.sign(rs) == np.sign(np.median(rs))).mean())}
    return pd.DataFrame(linhas).T


def correlacionar(mods, bom, num):
    np, pd = mods["numpy"], mods["pandas"]
    dentro = centrar(mods, bom, num)
    matrizes = {
        "pearson_agrupada": num.corr(),
        "pearson_intracelula": dentro.corr(),
        "spearman_intracelula": dentro.corr(method="spearman"),
    }
    rank = pd.DataFrame({
        "pooled_correlation": matrizes["pearson_agrupada"][ALVO],
        "within_cell_correlation": matrizes["pearson_intracelula"][ALVO],
        "within_cell_spearman": matrizes["spearman_intracelula"][ALVO],
        "sample_count": num.notna().sum(),
    }).join(por_celula(mods, bom, num)).drop(index=[ALVO], errors="ignore")
    rank["is_leakage"] = rank.index.isin(VAZAMENTO)
    rank["within_cell_strength"] = rank.within_cell_correlation.abs()
    return matrizes, rank.sort_values(["is_leakage", "within_cell_strength"],
                                      ascending=[True, False])


def escrever_dicionario(mods, df, rank):
    pd = mods["pandas"]
    linhas = [{"variavel": n, "tipo": t, "unidade": u, "origem": o, "descricao": d}
              for n, (t, u, o, d) in DICIONARIO.items() if n in df.columns]
    dic = pd.DataFrame(linhas).set_index("variavel").join(
        rank[["within_cell_correlation", "median_per_cell_correlation",
              "same_sign_fraction", "sample_count"]])
    dic.to_csv(SAIDA / "dicionario_tabela2.csv")
    p("  dicionario_tabela2.csv")


# ---------------------------------------------------------------------------
# graficos
# ---------------------------------------------------------------------------
def estilo(plt):
    plt.rcParams.update({
        "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
        "font.size": 10, "text.color": INK, "axes.labelcolor": INK2,
        "xtick.color": INK2, "ytick.color": INK2, "axes.edgecolor": GRID,
        "grid.color": GRID, "grid.linewidth": 0.8, "axes.spines.top": False,
        "axes.spines.right": False, "lines.linewidth": 2.0,
        "legend.frameon": False, "figure.dpi": 150,
    })


def titulo_figura(fig, texto, sub):
    fig.suptitle(texto, fontsize=15, fontweight="bold", color=INK,
                 x=0.007, ha="left", y=0.995)
    fig.text(0.007, 0.945, sub, fontsize=10.5, color=INK2, ha="left", va="top")


def mapa(mods, plt, m, nome, texto, sub):
    from matplotlib.colors import LinearSegmentedColormap
    np = mods["numpy"]
    viva = m.columns[m.notna().sum() > 1]
    m = m.loc[viva, viva]
    n = len(m)
    cmap = LinearSegmentedColormap.from_list("div", DIV)
    fig, ax = plt.subplots(figsize=(max(7, 0.55 * n + 3), max(6, 0.55 * n + 2.4)))
    ax.imshow(m.to_numpy(float), cmap=cmap, vmin=-1, vmax=1)
    ax.set_xticks(range(n), m.columns, rotation=90, fontsize=8.5)
    ax.set_yticks(range(n), m.index, fontsize=8.5)
    ax.set_xticks(np.arange(n + 1) - 0.5, minor=True)
    ax.set_yticks(np.arange(n + 1) - 0.5, minor=True)
    ax.grid(which="minor", color=SURF, linewidth=2)
    ax.tick_params(which="minor", length=0)
    ax.grid(which="major", visible=False)
    for lado in ax.spines.values():
        lado.set_visible(False)
    for a in range(n):
        for b in range(n):
            val = m.iat[a, b]
            if val == val and abs(val) >= 0.4 and a != b:
                ax.text(b, a, f"{val:.2f}", ha="center", va="center", fontsize=7.5,
                        color=SURF if abs(val) > 0.72 else INK)
    barra = fig.colorbar(ax.images[0], ax=ax, shrink=0.55, pad=0.02)
    barra.set_label("correlacao", color=INK2, fontsize=9)
    barra.outline.set_visible(False)
    titulo_figura(fig, texto, sub)
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    fig.savefig(SAIDA / nome, bbox_inches="tight")
    plt.close(fig)
    p(f"  {nome}")


def barras(plt, rank, nome):
    r = rank[~rank.is_leakage].dropna(subset=["within_cell_correlation"]).iloc[::-1]
    if r.empty:
        return
    fig, ax = plt.subplots(figsize=(9.5, 0.42 * len(r) + 2.8))
    y = range(len(r))
    ax.barh(y, r.within_cell_correlation,
            color=[PAL[0] if v > 0 else PAL[7] for v in r.within_cell_correlation],
            height=0.6)
    if "per_cell_correlation_p10" in r.columns:
        ax.hlines(y, r.per_cell_correlation_p10, r.per_cell_correlation_p90,
                  color=INK2, linewidth=1.2, alpha=0.55)
    ax.set_yticks(list(y), r.index, fontsize=9.5)
    for k, v in enumerate(r.within_cell_correlation):
        ax.text(v + (0.03 if v > 0 else -0.03), k, f"{v:.2f}", va="center",
                ha="left" if v > 0 else "right", fontsize=8.5, color=INK2)
    ax.axvline(0, color=INK2, linewidth=1)
    ax.set_xlim(-1.12, 1.12)
    ax.set_xlabel("correlacao com SOH, intra-celula")
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    titulo_figura(fig, "Variaveis da Tabela 2 contra SOH",
                  "Barra: Pearson sobre valores centrados por bateria x condicao. "
                  "Linha cinza: faixa p10-p90 celula a celula. capacity e time ficam "
                  "de fora por serem vazamento.")
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    fig.savefig(SAIDA / nome, bbox_inches="tight")
    plt.close(fig)
    p(f"  {nome}")


def agrupada_vs_intra(mods, plt, bom, num, nome, col="voltage_load"):
    """Por que as duas leituras discordam, sobre o mesmo dado.

    Cada celula tem seu proprio NIVEL de tensao — 0,67 V a 4 A / 4 C, 2,88 V a
    1 A / 4 C. Juntando tudo, essa diferenca de nivel domina a nuvem e a reta
    agrupada mede protocolo, nao degradacao. Centrar por bateria x condicao
    remove o nivel e deixa so a inclinacao, que e a degradacao.
    """
    np, pd = mods["numpy"], mods["pandas"]
    # Seis grupos longos, escolhidos para varrer a faixa de nivel de ponta a ponta
    destaque = [("B0042", "4 A / 4 C"), ("B0033", "4 A / 24 C"), ("B0030", "4 A / 43 C"),
                ("B0056", "2 A / 4 C"), ("B0006", "2 A / 24 C"), ("B0046", "1 A / 4 C")]
    dentro = centrar(mods, bom, num)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.5, 6.2))

    # ---- painel 1: dado cru, todas as celulas juntas
    ax1.scatter(bom[col], bom[ALVO], s=7, color="#cfcec9", alpha=0.55,
                edgecolors="none", label="outras celulas", zorder=1)
    for k, (bat, cond) in enumerate(destaque):
        g = bom[(bom.battery_id == bat) & (bom.test_condition == cond)]
        if len(g) < 5:
            continue
        r = g[col].corr(g[ALVO])
        ax1.scatter(g[col], g[ALVO], s=11, color=PAL[k], alpha=0.85,
                    edgecolors="none", zorder=3, label=f"{bat}  {cond}   r={r:+.2f}")
        b, a = np.polyfit(g[col], g[ALVO], 1)
        xs = np.linspace(g[col].min(), g[col].max(), 20)
        ax1.plot(xs, b * xs + a, color=PAL[k], linewidth=2.2, zorder=4)
    par = bom[[col, ALVO]].dropna()
    b, a = np.polyfit(par[col], par[ALVO], 1)
    xs = np.linspace(par[col].min(), par[col].max(), 20)
    r_pool = par[col].corr(par[ALVO])
    ax1.plot(xs, b * xs + a, color=INK, linewidth=3.2, zorder=5,
             label=f"reta agrupada   r={r_pool:+.2f}")
    ax1.set_xlabel(f"{col} (V)")
    ax1.set_ylabel("SOH (%)")
    ax1.set_title("Agrupada: cada celula num nivel diferente", fontsize=12.5,
                  color=INK, loc="left", pad=8)
    ax1.legend(fontsize=8.5, loc="lower right", ncol=1)
    ax1.grid(color=GRID, linewidth=0.8)
    ax1.set_axisbelow(True)

    # ---- painel 2: mesmo dado, centrado por bateria x condicao
    pc = dentro[[col, ALVO]].dropna()
    ax2.scatter(pc[col], pc[ALVO], s=7, color=PAL[0], alpha=0.3,
                edgecolors="none", zorder=2)
    b, a = np.polyfit(pc[col], pc[ALVO], 1)
    xs = np.linspace(pc[col].min(), pc[col].max(), 20)
    r_in = pc[col].corr(pc[ALVO])
    ax2.plot(xs, b * xs + a, color=PAL[1], linewidth=3.2, zorder=4,
             label=f"reta intra-celula   r={r_in:+.2f}")
    ax2.axhline(0, color=GRID, linewidth=1, zorder=1)
    ax2.axvline(0, color=GRID, linewidth=1, zorder=1)
    ax2.set_xlabel(f"{col} centrado por bateria x condicao (V)")
    ax2.set_ylabel("SOH centrado (%)")
    ax2.set_title("Intra-celula: o nivel some, sobra a inclinacao", fontsize=12.5,
                  color=INK, loc="left", pad=8)
    ax2.legend(fontsize=9, loc="lower right")
    ax2.grid(color=GRID, linewidth=0.8)
    ax2.set_axisbelow(True)

    titulo_figura(fig, "O mesmo dado, duas respostas opostas",
                  f"{col} contra SOH. A esquerda a nuvem inteira; a direita a mesma "
                  "nuvem com a media de cada bateria x condicao subtraida. Nada foi "
                  "filtrado entre um painel e outro.")
    fig.tight_layout(rect=[0, 0, 1, 0.89])
    fig.savefig(SAIDA / nome, bbox_inches="tight")
    plt.close(fig)
    p(f"  {nome}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sem-graficos", action="store_true")
    ap.add_argument("--remontar", action="store_true")
    args = ap.parse_args()

    mods = checar()
    SAIDA.mkdir(parents=True, exist_ok=True)
    p("tabela de modelagem:")
    df = montar(mods, args.remontar)
    bom, num = preparar(mods, df)
    p(f"  {len(bom)} descargas validas, {num.shape[1]} colunas numericas")

    p("correlacao:")
    matrizes, rank = correlacionar(mods, bom, num)
    for nome, m in matrizes.items():
        m.round(4).to_csv(SAIDA / f"matriz_{nome}.csv")
        p(f"  matriz_{nome}.csv")
    rank.round(4).to_csv(SAIDA / "ranking_vs_soh.csv")
    p("  ranking_vs_soh.csv")
    escrever_dicionario(mods, df, rank)

    if not args.sem_graficos:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        estilo(plt)
        p("graficos:")
        ordem = [c for c in list(rank.index[::-1]) + [ALVO] if c in num.columns]
        mapa(mods, plt, matrizes["pearson_agrupada"].loc[ordem, ordem],
             "01_matriz_agrupada.png", "Tabela 2 — todas as celulas juntas",
             "Mistura diferenca entre celulas com degradacao. Serve de contraste "
             "com a proxima.")
        mapa(mods, plt, matrizes["pearson_intracelula"].loc[ordem, ordem],
             "02_matriz_intracelula.png", "Tabela 2 — intra-celula",
             "Valores centrados por bateria x condicao. E esta que diz o que serve "
             "de atributo.")
        barras(plt, rank, "03_ranking_vs_soh.png")
        agrupada_vs_intra(mods, plt, bom, num, "04_agrupada_vs_intra.png")

    p()
    cols = ["pooled_correlation", "within_cell_correlation", "within_cell_spearman",
            "median_per_cell_correlation", "same_sign_fraction", "sample_count"]
    p("Variaveis da Tabela 2 contra SOH:")
    p(rank[~rank.is_leakage][cols].round(3).to_string())
    p()
    p("Vazamento (na Tabela 2, mas o alvo e derivado delas):")
    p(rank[rank.is_leakage][cols[:3]].round(3).to_string())


if __name__ == "__main__":
    main()
