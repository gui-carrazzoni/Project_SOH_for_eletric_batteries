#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Grupos de comportamento medido, contra o rotulo nominal de condicao de ensaio.

    python grupos.py                # escolhe k pela silhueta
    python grupos.py --grupos 5     # forca k=5
    python grupos.py --sem-graficos # so as tabelas

Escreve saida_nasa/cluster/agrupamento/.

Nao e justo comparar uma celula a 2 A / 24 C com outra a 4 A / 4 C: sao regimes
de descarga distintos, e a diferenca entre eles engole a degradacao que se quer
medir. O projeto ja separa por `test_condition`, o rotulo **nominal** do
protocolo. Este script constroi a alternativa: agrupar pelo comportamento
**medido**, e verificar se os dois concordam.

**A unidade agrupada e a bateria x condicao**, nao a descarga solta. E a mesma
unidade que o resto do projeto trata como grupo — e a que recebe referencia de
inicio de vida em normalizar.py e a que limpeza.py conta para descartar grupos
curtos. Agrupar descargas soltas produziria um rotulo que muda no meio da vida
de uma celula, o que nao serve para nada.

**So os ciclos de inicio de vida entram no agrupamento.** Se todos os ciclos
entrassem, uma celula degradada num regime brando pareceria uma celula nova num
regime severo, e o cluster acabaria medindo degradacao em vez de regime. O
recorte inicial descreve a celula quando ela ainda esta inteira, que e quando o
regime e a unica coisa que a distingue.

**O agrupamento usa a resposta, nunca o protocolo.** Corrente aplicada e
temperatura ambiente ficam **fora** do vetor de atributos, de proposito. Inclui-
las faria o cluster reproduzir o rotulo nominal por construcao, e a comparacao
entre os dois nao provaria nada. O que entra e o que a celula respondeu: a forma
da curva de tensao, quanto durou, quanta carga e energia saiu, o quanto a tensao
cedeu e o quanto a celula esquentou. Assim a tabela de contingencia vira um
teste de verdade — o comportamento recupera o protocolo, ou nao?

**As magnitudes entram em log.** Duracao vai de 1 a 106 minutos e carga de 0,06
a 1,77 Ah. Em escala linear a distancia euclidiana entre dois regimes brandos
fica invisivel ao lado da distancia ate 4 A / 4 C, e o agrupamento vira "4 A / 4
C contra todo o resto". O log torna a diferenca **proporcional**, que e como
esses regimes se ordenam.

Ligacao de Ward sobre distancia euclidiana, com os atributos padronizados. O k e
escolhido pela silhueta media, e `--grupos` permite sobrepor a escolha depois de
olhar o dendrograma.

Dependencias: numpy, pandas, scipy, matplotlib
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# A raiz do projeto e a pasta acima de src/: e la que ficam
# cleaned_nasa_dataset/ e saida_nasa/.
RAIZ = Path(__file__).resolve().parent.parent
ENTRADA = RAIZ / "saida_nasa" / "curvas" / "features_curvas.csv"
SAIDA = RAIZ / "saida_nasa" / "cluster" / "agrupamento"

PAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
       "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e3e2de"
SEQ = ["#f0efec", "#cfe0f5", "#9dc3ea", "#6d9fe4", "#2a78d6", "#104281"]

CICLOS_INICIO = 10       # ciclos de inicio de vida que descrevem o regime
MIN_DESCARGAS = 3        # abaixo disso a bateria x condicao nao rende perfil
K_MIN, K_MAX = 2, 10     # faixa de k avaliada pela silhueta

# A resposta da celula. Corrente aplicada e temperatura ambiente ficam fora:
# sao o protocolo, e inclui-las faria o cluster recuperar o nominal por
# construcao. `log` marca as que entram em escala logaritmica.
ATRIBUTOS = [
    ("carga_Ah", True),
    ("energia_Wh", True),
    ("duracao_s", True),
    ("queda_V", False),
    ("V_medio", False),
    ("inclinacao_mV_min", False),
    ("T_subida", False),
    ("fracao_energia_1a_metade", False),
]
N_CURVA = 50             # colunas v00..v49 da curva reamostrada


def p(msg: str = "") -> None:
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "ascii"
        print(msg.encode(enc, "replace").decode(enc), flush=True)


def checar():
    faltando, mods = [], {}
    for nome in ("numpy", "pandas", "scipy"):
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


# ---------------------------------------------------------------------------
# perfil de cada bateria x condicao
# ---------------------------------------------------------------------------
def perfis(mods, df):
    """Uma linha por bateria x condicao, descrita pelos ciclos de inicio de vida.

    A mediana, e nao a media, porque as primeiras descargas de varias celulas
    trazem medicao falha — o mesmo motivo que impede normalizar pelo primeiro
    ciclo neste dataset.
    """
    np, pd = mods["numpy"], mods["pandas"]
    d = df[df.carga_Ah.notna() & df.condicao.notna()].copy()

    # Recorte de inicio de vida dentro da condicao: ciclo_na_condicao ja conta
    # a partir da entrada da celula naquele regime, que e o que importa para as
    # 9 baterias que mudam de condicao no meio da vida.
    d = d[d.ciclo_na_condicao < CICLOS_INICIO]

    cols = [c for c, _ in ATRIBUTOS] + [f"v{i:02d}" for i in range(N_CURVA)]
    g = d.groupby(["battery_id", "condicao"])
    perfil = g[cols].median()
    perfil["descargas_inicio"] = g.size()
    perfil = perfil[perfil.descargas_inicio >= MIN_DESCARGAS]
    perfil = perfil.dropna(subset=[c for c, _ in ATRIBUTOS])

    # Quantas descargas a bateria x condicao tem no total, para o relatorio
    # saber o que cada grupo carrega de dados.
    tot = df.groupby(["battery_id", "condicao"]).size().rename("descargas_total")
    perfil = perfil.join(tot)

    # Os rotulos nominais viajam junto, mas so para nomear e comparar depois:
    # nao entram no vetor de atributos do agrupamento.
    nom = g[["corrente_A", "ambient_temperature"]].median()
    perfil = perfil.join(nom)
    return perfil.reset_index()


def matriz(mods, perfil):
    """Perfis -> matriz padronizada para o agrupamento.

    A curva reamostrada entra como bloco unico com peso equivalente ao das
    magnitudes somadas: sao 50 colunas contra 8, e sem reequilibrar a forma
    dominaria a distancia sozinha.
    """
    np = mods["numpy"]
    blocos, nomes = [], []

    for col, usar_log in ATRIBUTOS:
        x = perfil[col].to_numpy(float)
        if usar_log:
            x = np.log10(np.clip(x, 1e-6, None))
        blocos.append(_z(np, x).reshape(-1, 1))
        nomes.append(col)

    curva = perfil[[f"v{i:02d}" for i in range(N_CURVA)]].to_numpy(float)
    curva = np.apply_along_axis(lambda c: _z(np, c), 0, curva)
    # Reescala o bloco inteiro para pesar como len(ATRIBUTOS) colunas.
    curva *= np.sqrt(len(ATRIBUTOS) / N_CURVA)
    blocos.append(curva)
    nomes += [f"v{i:02d}" for i in range(N_CURVA)]

    return np.hstack(blocos), nomes


def _z(np, x):
    s = x.std()
    return (x - x.mean()) / s if s > 0 else x * 0.0


def silhueta(mods, X, rotulos):
    """Silhueta media, na mao: scipy nao traz e nao vale puxar scikit-learn."""
    np = mods["numpy"]
    from scipy.spatial.distance import squareform, pdist
    D = squareform(pdist(X))
    unicos = np.unique(rotulos)
    if len(unicos) < 2:
        return float("nan")
    s = np.zeros(len(X))
    for i in range(len(X)):
        meu = rotulos[i]
        dentro = (rotulos == meu)
        dentro[i] = False
        if dentro.sum() == 0:
            s[i] = 0.0
            continue
        a = D[i, dentro].mean()
        b = min(D[i, rotulos == o].mean() for o in unicos if o != meu)
        s[i] = (b - a) / max(a, b)
    return float(s.mean())


def agrupar(mods, X, k_forcado=None):
    np = mods["numpy"]
    from scipy.cluster.hierarchy import linkage, fcluster
    Z = linkage(X, method="ward")

    escolha, tabela = None, []
    for k in range(K_MIN, min(K_MAX, len(X) - 1) + 1):
        r = fcluster(Z, k, criterion="maxclust")
        tabela.append((k, silhueta(mods, X, r)))
    p("")
    p("  silhueta por numero de grupos:")
    for k, s in tabela:
        marca = ""
        p(f"    k={k:<3} {s:+.3f}{marca}")
    escolha = max(tabela, key=lambda t: t[1])[0]

    if k_forcado:
        p(f"\n  k={escolha} pela silhueta, mas --grupos {k_forcado} foi pedido")
        escolha = k_forcado
    else:
        p(f"\n  k={escolha} escolhido pela silhueta")
    return Z, fcluster(Z, escolha, criterion="maxclust"), escolha, tabela


def nomear(mods, perfil):
    """Da a cada grupo um nome legivel, a partir do que ele contem.

    Um numero de cluster nao diz nada a quem le o artigo. O nome sai das
    correntes e temperaturas nominais que caem no grupo — o rotulo nominal nao
    define o grupo, mas descreve bem o que ele reuniu.
    """
    pd = mods["pandas"]
    nomes = {}
    for gid, bloco in perfil.groupby("grupo"):
        corr = sorted({c for c in bloco.corrente_A.dropna()})
        temp = sorted({int(t) for t in bloco.ambient_temperature.dropna()})
        fc = (f"{corr[0]:.0f} A" if len(corr) == 1
              else f"{min(corr):.0f}-{max(corr):.0f} A")
        ft = (f"{temp[0]} C" if len(temp) == 1
              else f"{min(temp)}-{max(temp)} C")
        nomes[gid] = f"G{gid}: {fc} / {ft}"
    return nomes


# ---------------------------------------------------------------------------
# relatorio
# ---------------------------------------------------------------------------
def relatar(mods, perfil, nomes):
    pd = mods["pandas"]
    p("")
    p("  grupos de comportamento medido:")
    for gid, bloco in perfil.groupby("grupo"):
        p(f"    {nomes[gid]:<22} {len(bloco):>2} pares bateria x condicao, "
          f"{int(bloco.descargas_total.sum()):>4} descargas, "
          f"{bloco.carga_Ah.median():.3f} Ah  {bloco.duracao_s.median()/60:.1f} min")
        for cond, sub in bloco.groupby("condicao"):
            cels = ", ".join(sorted(sub.battery_id))
            p(f"        {cond:<12} {cels}")

    cont = pd.crosstab(perfil.condicao, perfil.grupo.map(nomes))
    p("")
    p("  contingencia: condicao nominal x grupo medido")
    p("  (celula = pares bateria x condicao)")
    linhas = cont.to_string().split("\n")
    for lin in linhas:
        p("    " + lin)
    return cont


def veredito(mods, perfil, cont, nomes):
    """O que o agrupamento medido muda em relacao ao nominal."""
    pd = mods["pandas"]
    p("")
    p("  o que muda:")

    # Condicoes nominais que o comportamento funde.
    fundidas = {}
    for gid, bloco in perfil.groupby("grupo"):
        conds = sorted(bloco.condicao.unique())
        if len(conds) > 1:
            fundidas[nomes[gid]] = conds
    if fundidas:
        for g, conds in fundidas.items():
            p(f"    funde   {g}: {', '.join(conds)}")
    else:
        p("    nenhuma condicao nominal foi fundida")

    # Condicoes nominais que o comportamento parte em mais de um grupo.
    partidas = {}
    for cond, bloco in perfil.groupby("condicao"):
        gs = sorted(bloco.grupo.unique())
        if len(gs) > 1:
            partidas[cond] = [nomes[g] for g in gs]
    if partidas:
        for c, gs in partidas.items():
            p(f"    parte   {c}: {', '.join(gs)}")
    else:
        p("    nenhuma condicao nominal foi partida")

    # O ganho pratico: grupos que hoje morrem por serem curtos demais e que,
    # fundidos, passam a ter dados suficientes.
    p("")
    n_nom = perfil.groupby("condicao").descargas_total.sum()
    n_med = perfil.groupby(perfil.grupo.map(nomes)).descargas_total.sum()
    p(f"    condicoes nominais com menos de 30 descargas: "
      f"{int((n_nom < 30).sum())} de {len(n_nom)}")
    p(f"    grupos medidos   com menos de 30 descargas: "
      f"{int((n_med < 30).sum())} de {len(n_med)}")


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
        "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 2.0,
        "legend.frameon": False, "figure.dpi": 200,
    })
    return plt


def titulo_figura(plt, fig, texto, sub):
    import textwrap
    linhas = textwrap.wrap(sub, width=int(fig.get_figwidth() * 13.5))
    altura_linha = 0.1875 / fig.get_figheight()
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


def desenhar(mods, plt, perfil, Z, k, tabela, cont, nomes):
    np, pd = mods["numpy"], mods["pandas"]
    from scipy.cluster.hierarchy import dendrogram

    gids = sorted(perfil.grupo.unique())
    cor = {g: PAL[i % len(PAL)] for i, g in enumerate(gids)}

    # 01 — dendrograma
    rot = [f"{r.battery_id} {r.condicao}" for r in perfil.itertuples(index=False)]
    fig, ax = plt.subplots(figsize=(9, max(6, 0.22 * len(perfil) + 2)))
    corte = _altura_corte(Z, k, np)
    dendrogram(Z, labels=rot, orientation="right", ax=ax,
               color_threshold=corte, above_threshold_color=INK2,
               leaf_font_size=7.5)
    ax.axvline(corte, color=INK2, linestyle="--", linewidth=1.2)
    ax.set_xlabel("distancia de ligacao (Ward)")
    ax.grid(axis="y", visible=False)
    titulo_figura(plt, fig, "Agrupamento por comportamento medido",
                  f"Cada folha e uma bateria x condicao, descrita pelos {CICLOS_INICIO} "
                  f"primeiros ciclos naquele regime. Corrente e temperatura nominais "
                  f"ficaram fora dos atributos: o agrupamento ve so a resposta da celula. "
                  f"Linha tracejada marca o corte em k={k}.")
    salvar(plt, fig, "01_dendrograma.png")

    # 02 — curvas medias por grupo
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    grade = np.linspace(0, 1, N_CURVA)
    vcols = [f"v{i:02d}" for i in range(N_CURVA)]
    for g in gids:
        bloco = perfil[perfil.grupo == g]
        axes[0].plot(grade, bloco[vcols].median().to_numpy(float),
                     color=cor[g], label=nomes[g])
        axes[1].scatter(bloco.duracao_s / 60, bloco.carga_Ah,
                        color=cor[g], s=42, alpha=0.85, edgecolor=SURF, linewidth=0.6)
    axes[0].set_xlabel("tempo normalizado da descarga")
    axes[0].set_ylabel("tensao medida (V)")
    axes[0].set_title("forma da curva, por grupo", fontsize=11, color=INK2)
    axes[0].legend(fontsize=8.5, loc="lower left")
    axes[1].set_xscale("log")
    axes[1].set_xlabel("duracao sob carga (min, log)")
    axes[1].set_ylabel("carga integrada (Ah)")
    axes[1].set_title("magnitude, por grupo", fontsize=11, color=INK2)
    titulo_figura(plt, fig, "O que separa os grupos",
                  "A esquerda a forma da descarga com o tempo normalizado, a direita a "
                  "magnitude. Um grupo so se justifica se as celulas dentro dele se "
                  "parecerem mais entre si do que com as de fora.")
    salvar(plt, fig, "02_curvas_por_grupo.png")

    # 03 — contingencia nominal x medido
    m = cont.to_numpy(float)
    fig, ax = plt.subplots(figsize=(max(7, 0.9 * m.shape[1] + 4), 0.45 * m.shape[0] + 3))
    from matplotlib.colors import LinearSegmentedColormap
    ax.imshow(m, cmap=LinearSegmentedColormap.from_list("seq", SEQ),
              vmin=0, vmax=max(1.0, m.max()))
    ax.set_xticks(range(m.shape[1]), cont.columns, rotation=30, ha="right", fontsize=9)
    ax.set_yticks(range(m.shape[0]), cont.index, fontsize=9)
    for a in range(m.shape[0]):
        for b in range(m.shape[1]):
            if m[a, b] > 0:
                ax.text(b, a, f"{int(m[a, b])}", ha="center", va="center",
                        fontsize=9.5, color=INK if m[a, b] < m.max() * 0.6 else SURF)
    ax.set_xticks(np.arange(m.shape[1] + 1) - 0.5, minor=True)
    ax.set_yticks(np.arange(m.shape[0] + 1) - 0.5, minor=True)
    ax.grid(which="minor", color=SURF, linewidth=2)
    ax.tick_params(which="minor", length=0)
    ax.grid(which="major", visible=False)
    for lado in ax.spines.values():
        lado.set_visible(False)
    titulo_figura(plt, fig, "Condicao nominal contra grupo medido",
                  "Cada celula conta pares bateria x condicao. Diagonal limpa significa "
                  "que o comportamento recupera o protocolo; linha espalhada por varias "
                  "colunas significa que o rotulo nominal reune regimes distintos.")
    salvar(plt, fig, "03_contingencia.png")

    # 04 — silhueta
    fig, ax = plt.subplots(figsize=(7, 4))
    ks = [t[0] for t in tabela]
    ss = [t[1] for t in tabela]
    ax.plot(ks, ss, marker="o", color=PAL[0])
    ax.axvline(k, color=PAL[1], linestyle="--", linewidth=1.4)
    ax.set_xlabel("numero de grupos (k)")
    ax.set_ylabel("silhueta media")
    titulo_figura(plt, fig, "Quantos grupos o dado sustenta",
                  f"Silhueta media por k. Escolhido k={k}. Valores altos indicam grupos "
                  f"internamente parecidos e bem separados entre si.")
    salvar(plt, fig, "04_silhueta.png")


def _altura_corte(Z, k, np):
    """Altura que produz exatamente k grupos, para a linha do dendrograma."""
    alturas = np.sort(Z[:, 2])
    if k <= 1 or k > len(alturas) + 1:
        return alturas[-1] * 1.05
    return (alturas[-k] + alturas[-k + 1]) / 2 if k > 1 else alturas[-1]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--grupos", type=int, default=None,
                    help="forca o numero de grupos (por padrao, silhueta escolhe)")
    ap.add_argument("--sem-graficos", action="store_true")
    a = ap.parse_args()

    mods = checar()
    pd = mods["pandas"]
    SAIDA.mkdir(parents=True, exist_ok=True)

    p("Grupos de comportamento medido")
    p("=" * 60)
    df = pd.read_csv(ENTRADA)
    perfil = perfis(mods, df)
    p(f"  {len(perfil)} pares bateria x condicao com pelo menos "
      f"{MIN_DESCARGAS} descargas nos {CICLOS_INICIO} primeiros ciclos")

    X, nomes_attr = matriz(mods, perfil)
    p(f"  vetor de atributos: {len(ATRIBUTOS)} magnitudes + "
      f"{N_CURVA} pontos de curva (reescalados para pesar como {len(ATRIBUTOS)})")

    Z, rotulos, k, tabela = agrupar(mods, X, a.grupos)
    perfil["grupo"] = rotulos
    nomes = nomear(mods, perfil)
    perfil["grupo_comportamento"] = perfil.grupo.map(nomes)

    cont = relatar(mods, perfil, nomes)
    veredito(mods, perfil, cont, nomes)

    saida = perfil[["battery_id", "condicao", "grupo", "grupo_comportamento",
                    "descargas_inicio", "descargas_total", "carga_Ah",
                    "energia_Wh", "duracao_s", "queda_V", "T_subida"]]
    saida.to_csv(SAIDA / "grupos_comportamento.csv", index=False)
    cont.to_csv(SAIDA / "contingencia.csv")
    p("")
    p(f"  {(SAIDA / 'grupos_comportamento.csv').relative_to(RAIZ)}")
    p(f"  {(SAIDA / 'contingencia.csv').relative_to(RAIZ)}")

    if not a.sem_graficos:
        p("")
        desenhar(mods, estilo(mods), perfil, Z, k, tabela, cont, nomes)


if __name__ == "__main__":
    main()
