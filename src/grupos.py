#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Grupos de comportamento medido, contra o rotulo nominal de condicao de ensaio.

    python grupos.py                # escolhe k por silhueta + estabilidade
    python grupos.py --grupos 5     # forca k=5
    python grupos.py --sem-graficos # so as tabelas

Escreve saida_nasa/cluster/agrupamento/: as tabelas em tabelas/, os graficos em
figuras/.

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
regime severo, e o cluster acabaria medindo degradacao em vez de regime.

**O agrupamento usa a resposta, nunca o protocolo.** Corrente aplicada,
temperatura ambiente **e tensao de corte** ficam fora do vetor de atributos.
Os dois primeiros sao `test_condition`; o terceiro e o eixo de protocolo que
`test_condition` nao registra, e entrava escondido na versao anterior deste
script: o ultimo ponto da curva, `v49`, *e* a tensao de corte (r = 0,98), e
`queda_V` e quase determinada por ela (r = -0,79). O cluster "descobria" o
corte porque o recebia. Por isso tudo aqui vem da **janela comum** de
curvas.py, que para em 2,7 V para todas as celulas: as tres magnitudes
`_comum`, a forma `c00`..`c49` e os descritores de forma `_comum`.

**Atributos redundantes saem antes da distancia.** Carga, energia e duracao
correlacionam acima de 0,95 entre si: na distancia euclidiana seriam a mesma
grandeza contada tres vezes. Um filtro guloso mantem o primeiro de cada par com
|r| > LIMIAR_REDUNDANCIA, e um PCA que retem VARIANCIA_PCA da variancia
descorrelaciona o que sobra e descarta as direcoes de ruido.

**Pares extremos ficam num grupo proprio, declarado.** Tres celulas a 4 A / 4 C
entregam 0,06 Ah contra ~1,5 das demais. Dentro do agrupamento elas inflam a
silhueta de qualquer particao que as isole, e a silhueta passa a escolher k=2
por patologia. Sao identificadas pelo escore-z modificado de Iglewicz e
Hoaglin (mediana e MAD, robustos ao proprio extremo), e entram no relatorio
como grupo a parte.

**k sai de dois criterios, nao de um.** Para cada k: silhueta media
(separacao) e estabilidade por bootstrap (ARI medio entre a particao completa e
a de reamostragens). Sao candidatos os k com estabilidade >= ESTAB_MIN e nenhum
grupo menor que TAMANHO_MIN, e vence o **menor** candidato. Nao a maior
silhueta: neste dado ela cresce quase sem parar com k, porque pares da mesma
condicao sao quase identicos entre si, e o maximo cai na borda da faixa
avaliada — sinal de fragmentacao, nao de estrutura. Entre particoes igualmente
estaveis, a mais grossa e a que descreve regimes; as mais finas descrevem
celulas.

**A validacao e numerica.** ARI e NMI contra a condicao nominal e contra o corte,
e ARI entre Ward e k-means no mesmo k: se dois algoritmos com vieses distintos
chegam a mesma particao, ela nao e artefato do metodo.

Ligacao de Ward sobre distancia euclidiana no espaco do PCA.

Dependencias: numpy, pandas, scipy, matplotlib
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# A raiz do projeto e a pasta acima de src/: e la que ficam
# cleaned_nasa_dataset/ e saida_nasa/.
RAIZ = Path(__file__).resolve().parent.parent
ENTRADA = RAIZ / "saida_nasa" / "curvas" / "tabelas" / "features_curvas.csv"
SAIDA = RAIZ / "saida_nasa" / "cluster" / "agrupamento"
FIGURAS, TABELAS = SAIDA / "figuras", SAIDA / "tabelas"

PAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
       "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
COR_EXTREMO = "#52514e"
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e3e2de"
SEQ = ["#f0efec", "#cfe0f5", "#9dc3ea", "#6d9fe4", "#2a78d6", "#104281"]

CICLOS_INICIO = 10       # ciclos de inicio de vida que descrevem o regime
MIN_DESCARGAS = 3        # abaixo disso a bateria x condicao nao rende perfil
K_MIN, K_MAX = 2, 10     # faixa de k avaliada

LIMIAR_REDUNDANCIA = 0.95  # |r| acima disso: o segundo atributo do par sai
VARIANCIA_PCA = 0.95       # fracao da variancia retida pelo PCA
Z_EXTREMO = 3.5            # escore-z modificado (Iglewicz e Hoaglin, 1993)
N_BOOT = 200               # reamostragens para a estabilidade
ESTAB_MIN = 0.75           # estabilidade minima para k ser candidato
TAMANHO_MIN = 2            # grupo de um par so nao e grupo
SEMENTE = 0

# A resposta da celula, toda na janela comum. A ordem importa: no filtro de
# redundancia, o primeiro de cada par correlacionado e o que fica. `log` marca
# as magnitudes que entram em escala logaritmica — duracao vai de 1 a 106 min,
# e em escala linear o agrupamento vira "4 A / 4 C contra o resto".
ATRIBUTOS = [
    ("energia_Wh_comum", True),
    ("carga_Ah_comum", True),
    ("duracao_s_comum", True),
    ("V_medio_comum", False),
    ("T_subida_comum", False),
    ("fracao_energia_1a_metade_comum", False),
]
N_CURVA = 50
CURVA = [f"c{i:02d}" for i in range(N_CURVA)]   # forma na janela comum
# Magnitudes onde o extremo e procurado: as tres areas, em log.
MAGNITUDES = ["energia_Wh_comum", "carga_Ah_comum", "duracao_s_comum"]


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
    d = df[df.carga_Ah_comum.notna() & df.condicao.notna()].copy()

    # Recorte de inicio de vida dentro da condicao: ciclo_na_condicao ja conta
    # a partir da entrada da celula naquele regime, que e o que importa para as
    # 9 baterias que mudam de condicao no meio da vida.
    d = d[d.ciclo_na_condicao < CICLOS_INICIO]

    cols = [c for c, _ in ATRIBUTOS] + CURVA
    g = d.groupby(["battery_id", "condicao"])
    perfil = g[cols].median()
    perfil["descargas_inicio"] = g.size()
    perfil = perfil[perfil.descargas_inicio >= MIN_DESCARGAS]
    perfil = perfil.dropna(subset=cols)

    tot = df.groupby(["battery_id", "condicao"]).size().rename("descargas_total")
    perfil = perfil.join(tot)

    # Os rotulos de protocolo viajam junto, mas so para nomear e validar
    # depois: nenhum entra no vetor de atributos do agrupamento.
    nom = g[["corrente_A", "ambient_temperature"]].median()
    perfil = perfil.join(nom).reset_index()
    proto = protocolo()
    perfil["descarga"] = perfil.battery_id.map(lambda b: proto[b][0])
    perfil["corte_V"] = perfil.battery_id.map(lambda b: proto[b][1])
    return perfil


def protocolo():
    """Perfil de descarga e tensao de corte por bateria.

    So para validar e descrever, nunca para agrupar. Vem de
    correlacao_soh.PROTOCOLO, transcrito dos README da NASA.
    """
    from correlacao_soh import PROTOCOLO
    return PROTOCOLO


def extremos(mods, perfil, ref=None):
    """Pares cujas magnitudes ficam longe demais do resto.

    Escore-z modificado, 0,6745 (x - mediana) / MAD, sobre o log das tres
    areas. Mediana e MAD nao se deixam puxar pelo proprio extremo, ao contrario
    de media e desvio padrao — que e justamente o problema que se quer evitar.
    `ref` sao os pares que definem mediana e MAD; por padrao, os proprios.
    """
    np = mods["numpy"]
    ref = perfil if ref is None else ref
    marca = np.zeros(len(perfil), dtype=bool)
    for col in MAGNITUDES:
        x = np.log10(np.clip(perfil[col].to_numpy(float), 1e-6, None))
        xr = np.log10(np.clip(ref[col].to_numpy(float), 1e-6, None))
        med = np.median(xr)
        mad = np.median(np.abs(xr - med))
        if mad > 0:
            marca |= np.abs(0.6745 * (x - med) / mad) > Z_EXTREMO
    return marca


def matriz(mods, perfil):
    """Perfis -> escores do PCA, prontos para a distancia euclidiana.

    1. magnitudes padronizadas (log onde marcado);
    2. filtro de redundancia: sai o segundo de cada par com |r| > limiar;
    3. a curva entra centrada, com uma escala unica para o bloco todo, e nao
       coluna a coluna: c49 e ~2,7 V em todas as celulas por construcao, e
       padroniza-la coluna a coluna transformaria ruido de medicao em sinal.
       O bloco e reescalado para ter a mesma variancia total das magnitudes
       que ficaram — sem isso 50 colunas abafariam 4;
    4. PCA retendo VARIANCIA_PCA da variancia.
    """
    np = mods["numpy"]
    blocos, escala = {}, {}
    for col, usar_log in ATRIBUTOS:
        x = perfil[col].to_numpy(float)
        if usar_log:
            x = np.log10(np.clip(x, 1e-6, None))
        escala[col] = (x.mean(), x.std())
        blocos[col] = _z(np, x)

    mantidos, removidos = [], []
    for col, _ in ATRIBUTOS:
        par = next((m for m in mantidos
                    if abs(np.corrcoef(blocos[col], blocos[m])[0, 1]) > LIMIAR_REDUNDANCIA),
                   None)
        if par:
            removidos.append((col, par, np.corrcoef(blocos[col], blocos[par])[0, 1]))
        else:
            mantidos.append(col)

    mag = np.column_stack([blocos[c] for c in mantidos])
    curva = perfil[CURVA].to_numpy(float)
    media_curva = curva.mean(0)
    curva = curva - media_curva
    var_curva = (curva ** 2).sum() / len(curva)
    fator_curva = np.sqrt(len(mantidos) / var_curva) if var_curva > 0 else 1.0
    curva *= fator_curva
    X = np.hstack([mag, curva])

    media_X = X.mean(0)
    X = X - media_X
    U, S, Vt = np.linalg.svd(X, full_matrices=False)
    ev = S ** 2 / (S ** 2).sum()
    q = int(np.searchsorted(np.cumsum(ev), VARIANCIA_PCA) + 1)
    escores = U[:, :q] * S[:q]

    def projetar(novos):
        """Os mesmos passos, com os parametros deste ajuste, para pares de fora dele."""
        usar_log = dict(ATRIBUTOS)
        cols = []
        for col in mantidos:
            x = novos[col].to_numpy(float)
            if usar_log[col]:
                x = np.log10(np.clip(x, 1e-6, None))
            m, s = escala[col]
            cols.append((x - m) / s if s > 0 else x * 0.0)
        cur = (novos[CURVA].to_numpy(float) - media_curva) * fator_curva
        return (np.hstack([np.column_stack(cols), cur]) - media_X) @ Vt[:q].T

    # Quanto cada atributo pesa nas componentes retidas, para o relatorio dizer
    # o que cada eixo do PCA esta medindo.
    nomes = mantidos + ["curva"]
    carga_pc = np.vstack([Vt[:q, :len(mantidos)].T,
                          np.sqrt((Vt[:q, len(mantidos):] ** 2).sum(1))])
    info = {"mantidos": mantidos, "removidos": removidos,
            "variancia": ev[:q], "nomes_carga": nomes, "carga_pc": carga_pc,
            "projetar": projetar}
    return escores, info


def _z(np, x):
    s = x.std()
    return (x - x.mean()) / s if s > 0 else x * 0.0


# ---------------------------------------------------------------------------
# metricas de agrupamento, na mao: scipy nao traz e nao vale puxar scikit-learn
# ---------------------------------------------------------------------------
def silhueta(mods, X, rotulos):
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
            continue                      # grupo unitario: s = 0 por convencao
        a = D[i, dentro].mean()
        b = min(D[i, rotulos == o].mean() for o in unicos if o != meu)
        s[i] = (b - a) / max(a, b)
    return float(s.mean())


def _contingencia(mods, a, b):
    pd = mods["pandas"]
    return pd.crosstab(pd.Series(list(a)), pd.Series(list(b))).to_numpy(float)


def ari(mods, a, b):
    """Indice de Rand ajustado (Hubert e Arabie, 1985). 0 = acaso, 1 = identico."""
    np = mods["numpy"]
    ct = _contingencia(mods, a, b)
    c2 = lambda x: x * (x - 1) / 2
    soma = c2(ct).sum()
    sa, sb = c2(ct.sum(1)).sum(), c2(ct.sum(0)).sum()
    esperado = sa * sb / c2(ct.sum())
    maximo = (sa + sb) / 2
    return float((soma - esperado) / (maximo - esperado)) if maximo != esperado else 1.0


def nmi(mods, a, b):
    """Informacao mutua normalizada pela media aritmetica das entropias."""
    np = mods["numpy"]
    ct = _contingencia(mods, a, b)
    pij = ct / ct.sum()
    pi, pj = pij.sum(1), pij.sum(0)
    nz = pij > 0
    mi = (pij[nz] * np.log(pij[nz] / np.outer(pi, pj)[nz])).sum()
    h = lambda q: -(q[q > 0] * np.log(q[q > 0])).sum()
    den = (h(pi) + h(pj)) / 2
    return float(mi / den) if den > 0 else 1.0


def ward(X, k):
    from scipy.cluster.hierarchy import linkage, fcluster
    return fcluster(linkage(X, method="ward"), k, criterion="maxclust")


def ajustar(mods, perfil, k):
    """O agrupamento deste script com k fixo, e quem encaixa pares novos nele.

    Para quem precisa refazer os grupos so com parte dos pares:
    classificacao.py os refaz a cada rodada da validacao so com as celulas de
    treino, para que nem os grupos tenham visto a celula avaliada. Devolve o
    grupo de cada par de `perfil` (0 = extremo) e uma funcao que encaixa pares
    novos: extremo pela mediana e MAD de `perfil`, senao o grupo de centroide
    mais proximo no espaco do PCA ajustado aqui.
    """
    np = mods["numpy"]
    ext = extremos(mods, perfil)
    X, info = matriz(mods, perfil[~ext].reset_index(drop=True))
    rot = np.zeros(len(perfil), dtype=int)
    rot[~ext] = ward(X, k)
    gs = np.unique(rot[~ext])
    centros = np.vstack([X[rot[~ext] == g].mean(0) for g in gs])

    def encaixar(novos):
        Z = info["projetar"](novos)
        perto = gs[((Z[:, None, :] - centros[None]) ** 2).sum(-1).argmin(1)]
        return np.where(extremos(mods, novos, ref=perfil), 0, perto)

    return rot, encaixar


def kmeans(mods, X, k, reinicios=20):
    """k-means++ com varios reinicios; fica a solucao de menor inercia."""
    np = mods["numpy"]
    from scipy.cluster.vq import kmeans2
    melhor = None
    for s in range(reinicios):
        c, r = kmeans2(X, k, minit="++", rng=SEMENTE + s)
        inercia = ((X - c[r]) ** 2).sum()
        if melhor is None or inercia < melhor[0]:
            melhor = (inercia, r)
    return melhor[1]


def estabilidade(mods, X, k, rng):
    """ARI medio entre a particao completa e a de cada reamostragem bootstrap.

    Cada reamostragem e reagrupada do zero, e a comparacao e feita so nos pares
    sorteados. Particao estavel e a que nao depende de quais pares estavam la.
    """
    np = mods["numpy"]
    cheia = ward(X, k)
    vals = []
    for _ in range(N_BOOT):
        idx = np.unique(rng.choice(len(X), len(X), replace=True))
        if len(idx) <= k:
            continue
        vals.append(ari(mods, cheia[idx], ward(X[idx], k)))
    return float(np.mean(vals)), float(np.std(vals))


def avaliar(mods, X, perfil):
    """Uma linha por k: separacao, estabilidade, tamanho e concordancias."""
    np, pd = mods["numpy"], mods["pandas"]
    rng = np.random.default_rng(SEMENTE)
    linhas = []
    for k in range(K_MIN, min(K_MAX, len(X) - 1) + 1):
        r = ward(X, k)
        est, dp = estabilidade(mods, X, k, rng)
        linhas.append({
            "k": k,
            "silhueta": silhueta(mods, X, r),
            "estabilidade": est,
            "estabilidade_dp": dp,
            "menor_grupo": int(np.bincount(r)[1:].min()),
            "ari_kmeans": ari(mods, r, kmeans(mods, X, k)),
            "ari_condicao": ari(mods, r, perfil.condicao),
            "ari_corte": ari(mods, r, perfil.corte_V),
        })
    return pd.DataFrame(linhas)


def escolher_k(tab, k_forcado=None):
    cand = tab[(tab.estabilidade >= ESTAB_MIN) & (tab.menor_grupo >= TAMANHO_MIN)]
    p("")
    p(f"  {'k':>3} {'silhueta':>9} {'estab.':>12} {'menor':>6} "
      f"{'Ward~km':>8} {'ARI cond':>9} {'ARI corte':>10}")
    for r in tab.itertuples(index=False):
        ok = "*" if r.k in set(cand.k) else " "
        p(f"  {r.k:>3} {r.silhueta:>+9.3f} {r.estabilidade:>6.2f} +-{r.estabilidade_dp:.2f} "
          f"{r.menor_grupo:>6} {r.ari_kmeans:>+8.2f} {r.ari_condicao:>+9.2f} "
          f"{r.ari_corte:>+10.2f} {ok}")
    p(f"  * candidatos: estabilidade >= {ESTAB_MIN} e nenhum grupo com menos "
      f"de {TAMANHO_MIN} pares")

    if len(cand):
        escolha = int(cand.k.min())
        p(f"\n  k={escolha}: o menor candidato")
    else:
        escolha = int(tab.loc[tab.silhueta.idxmax(), "k"])
        p(f"\n  AVISO: nenhum k passou nos dois criterios; k={escolha} so pela silhueta")
    if k_forcado:
        p(f"  --grupos {k_forcado} sobrepoe a escolha")
        escolha = k_forcado
    return escolha


def nomear(mods, perfil):
    """Da a cada grupo um nome legivel, a partir do que ele contem.

    O nome sai das correntes e temperaturas nominais que caem no grupo — o
    rotulo nominal nao define o grupo, mas descreve bem o que ele reuniu.
    """
    nomes = {}
    for gid, bloco in perfil.groupby("grupo"):
        corr = sorted({c for c in bloco.corrente_A.dropna()})
        temp = sorted({int(t) for t in bloco.ambient_temperature.dropna()})
        fc = (f"{corr[0]:.0f} A" if len(corr) == 1
              else f"{min(corr):.0f}-{max(corr):.0f} A")
        ft = (f"{temp[0]} C" if len(temp) == 1
              else f"{min(temp)}-{max(temp)} C")
        sufixo = " (extremo)" if bloco.extremo.all() else ""
        nomes[gid] = f"G{gid}: {fc} / {ft}{sufixo}"
    return nomes


# ---------------------------------------------------------------------------
# relatorio
# ---------------------------------------------------------------------------
def relatar(mods, perfil, nomes):
    pd = mods["pandas"]
    p("")
    p("  grupos de comportamento medido:")
    for gid, bloco in perfil.groupby("grupo"):
        p(f"    {nomes[gid]:<32} {len(bloco):>2} pares, "
          f"{int(bloco.descargas_total.sum()):>4} descargas, "
          f"{bloco.energia_Wh_comum.median():.2f} Wh  "
          f"{bloco.duracao_s_comum.median()/60:.1f} min  "
          f"{bloco.V_medio_comum.median():.2f} V")
        for cond, sub in bloco.groupby("condicao"):
            cels = ", ".join(f"{b} ({c:.1f} V{', pulsada' if d == 'pulsado' else ''})"
                             for b, c, d in sorted(zip(sub.battery_id, sub.corte_V,
                                                       sub.descarga)))
            p(f"        {cond:<12} {cels}")

    cont = pd.crosstab(perfil.condicao, perfil.grupo.map(nomes))
    p("")
    p("  contingencia: condicao nominal x grupo medido (pares bateria x condicao)")
    for lin in cont.to_string().split("\n"):
        p("    " + lin)
    return cont


def validar(mods, perfil, X, normais, k):
    """As concordancias que viram numero no artigo."""
    pd = mods["pandas"]
    todos = perfil.grupo
    sub = perfil[normais]
    linhas = [
        ("condicao nominal", "todos os pares", ari(mods, todos, perfil.condicao),
         nmi(mods, todos, perfil.condicao)),
        ("tensao de corte", "todos os pares", ari(mods, todos, perfil.corte_V),
         nmi(mods, todos, perfil.corte_V)),
        ("condicao nominal", "sem extremos", ari(mods, sub.grupo, sub.condicao),
         nmi(mods, sub.grupo, sub.condicao)),
        ("tensao de corte", "sem extremos", ari(mods, sub.grupo, sub.corte_V),
         nmi(mods, sub.grupo, sub.corte_V)),
    ]
    km = kmeans(mods, X, k)
    linhas.append(("k-means (mesmo k)", "sem extremos", ari(mods, sub.grupo, km),
                   nmi(mods, sub.grupo, km)))
    val = pd.DataFrame(linhas, columns=["referencia", "conjunto", "ARI", "NMI"])
    p("")
    p("  concordancia do agrupamento com:")
    for r in val.itertuples(index=False):
        p(f"    {r.referencia:<20} {r.conjunto:<16} ARI {r.ARI:+.2f}   NMI {r.NMI:.2f}")
    return val


def veredito(mods, perfil, nomes):
    """O que o agrupamento medido muda em relacao ao nominal."""
    p("")
    p("  o que muda:")
    for gid, bloco in perfil.groupby("grupo"):
        conds = sorted(bloco.condicao.unique())
        if len(conds) > 1:
            p(f"    funde   {nomes[gid]}: {', '.join(conds)}")
    for cond, bloco in perfil.groupby("condicao"):
        gs = sorted(bloco.grupo.unique())
        if len(gs) > 1:
            p(f"    parte   {cond}: {', '.join(nomes[g] for g in gs)}")

    # A pergunta que a versao anterior respondia errado: dentro de uma mesma
    # condicao, o corte separa as celulas?
    p("")
    p("  dentro de cada condicao com mais de um corte, o grupo segue o corte?")
    for cond, bloco in perfil.groupby("condicao"):
        if bloco.corte_V.nunique() < 2 or len(bloco) < 4:
            continue
        segue = (bloco.groupby("corte_V").grupo.nunique().max() == 1
                 and bloco.groupby("grupo").corte_V.nunique().max() == 1)
        p(f"    {cond:<12} {bloco.corte_V.nunique()} cortes, "
          f"{bloco.grupo.nunique()} grupo(s): {'sim' if segue else 'nao'}")

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
    FIGURAS.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURAS / nome, bbox_inches="tight")
    plt.close(fig)
    p(f"  {nome}")


def desenhar(mods, plt, perfil, normais, X, info, k, tab, cont, nomes):
    np = mods["numpy"]
    from scipy.cluster.hierarchy import dendrogram, linkage

    gids = sorted(perfil.grupo.unique())
    cor = {g: (COR_EXTREMO if perfil[perfil.grupo == g].extremo.all()
               else PAL[i % len(PAL)]) for i, g in enumerate(gids)}
    sub = perfil[normais].reset_index(drop=True)

    # 01 — dendrograma
    Z = linkage(X, method="ward")
    rot = [f"{r.battery_id} {r.condicao} ({r.corte_V:.1f} V)"
           for r in sub.itertuples(index=False)]
    fig, ax = plt.subplots(figsize=(9, max(6, 0.22 * len(sub) + 2)))
    corte = _altura_corte(Z, k, np)
    dendrogram(Z, labels=rot, orientation="right", ax=ax,
               color_threshold=corte, above_threshold_color=INK2,
               leaf_font_size=7.5)
    ax.axvline(corte, color=INK2, linestyle="--", linewidth=1.2)
    ax.set_xlabel("distancia de ligacao (Ward, espaco do PCA)")
    ax.grid(axis="y", visible=False)
    titulo_figura(plt, fig, "Agrupamento por comportamento medido",
                  f"Cada folha e uma bateria x condicao, descrita pelos {CICLOS_INICIO} "
                  f"primeiros ciclos na janela comum ate 2,7 V. Corrente, temperatura e "
                  f"tensao de corte ficaram fora dos atributos. Os "
                  f"{int((~normais).sum())} pares extremos sao grupo a parte e nao "
                  f"aparecem aqui. Linha tracejada marca o corte em k={k}.")
    salvar(plt, fig, "01_dendrograma.png")

    # 02 — curvas medias por grupo
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    grade = np.linspace(0, 1, N_CURVA)
    for g in gids:
        bloco = perfil[perfil.grupo == g]
        axes[0].plot(grade, bloco[CURVA].median().to_numpy(float),
                     color=cor[g], label=nomes[g])
        axes[1].scatter(bloco.duracao_s_comum / 60, bloco.energia_Wh_comum,
                        color=cor[g], s=42, alpha=0.85, edgecolor=SURF, linewidth=0.6)
    axes[0].set_xlabel("tempo normalizado na janela comum")
    axes[0].set_ylabel("tensao medida (V)")
    axes[0].set_title("forma da curva, por grupo", fontsize=11, color=INK2)
    axes[0].legend(fontsize=8, loc="lower left")
    axes[1].set_xscale("log")
    axes[1].set_yscale("log")
    axes[1].set_xlabel("duracao ate 2,7 V (min, log)")
    axes[1].set_ylabel("energia ate 2,7 V (Wh, log)")
    axes[1].set_title("magnitude, por grupo", fontsize=11, color=INK2)
    titulo_figura(plt, fig, "O que separa os grupos",
                  "A esquerda a forma da descarga com o tempo normalizado, a direita a "
                  "magnitude, ambas na janela comum. Cinza: o grupo extremo, separado "
                  "antes do agrupamento.")
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

    # 04 — escolha de k: silhueta e estabilidade
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    cand = (tab.estabilidade >= ESTAB_MIN) & (tab.menor_grupo >= TAMANHO_MIN)
    axes[0].plot(tab.k, tab.silhueta, marker="o", color=PAL[0])
    axes[0].scatter(tab.k[~cand], tab.silhueta[~cand], color=SURF,
                    edgecolor=PAL[0], s=40, zorder=3, linewidth=1.5)
    axes[0].set_ylabel("silhueta media")
    axes[1].errorbar(tab.k, tab.estabilidade, yerr=tab.estabilidade_dp,
                     marker="o", color=PAL[2], capsize=3)
    axes[1].axhline(ESTAB_MIN, color=INK2, linestyle=":", linewidth=1.2)
    axes[1].set_ylabel("estabilidade (ARI bootstrap)")
    for ax in axes:
        ax.axvline(k, color=PAL[1], linestyle="--", linewidth=1.4)
        ax.set_xlabel("numero de grupos (k)")
    titulo_figura(plt, fig, "Quantos grupos o dado sustenta",
                  f"Silhueta (separacao) e estabilidade sob {N_BOOT} reamostragens "
                  f"bootstrap. Pontos vazados nao sao candidatos: estabilidade abaixo "
                  f"de {ESTAB_MIN} ou grupo com menos de {TAMANHO_MIN} pares. "
                  f"Escolhido k={k}, o menor candidato.")
    salvar(plt, fig, "04_escolha_de_k.png")

    # 05 — os pares no plano das duas primeiras componentes
    fig, ax = plt.subplots(figsize=(8.5, 6))
    marcadores = dict(zip(sorted(sub.condicao.unique()), "osD^v<>pPhX"))
    for g in sorted(sub.grupo.unique()):
        for cond, mk in marcadores.items():
            s = (sub.grupo == g).to_numpy() & (sub.condicao == cond).to_numpy()
            if s.any():
                ax.scatter(X[s, 0], X[s, 1], color=cor[g], marker=mk, s=55,
                           edgecolor=SURF, linewidth=0.6, alpha=0.9)
    from matplotlib.lines import Line2D
    leg_g = [Line2D([], [], color=cor[g], marker="o", linestyle="", label=nomes[g])
             for g in sorted(sub.grupo.unique())]
    leg_c = [Line2D([], [], color=INK2, marker=mk, linestyle="", label=c)
             for c, mk in marcadores.items()]
    l1 = ax.legend(handles=leg_g, fontsize=8, loc="upper left", title="grupo")
    ax.add_artist(l1)
    ax.legend(handles=leg_c, fontsize=8, loc="lower right", title="condicao nominal")
    v = info["variancia"]
    ax.set_xlabel(f"PC1 ({v[0]:.0%} da variancia)")
    ax.set_ylabel(f"PC2 ({v[1]:.0%} da variancia)" if len(v) > 1 else "PC2")
    titulo_figura(plt, fig, "Os grupos no plano principal",
                  "Cor e o grupo encontrado, forma e a condicao nominal. Sem os pares "
                  "extremos, que distorceriam a escala.")
    salvar(plt, fig, "05_pca.png")


def _altura_corte(Z, k, np):
    """Altura que produz exatamente k grupos, para a linha do dendrograma."""
    alturas = np.sort(Z[:, 2])
    if k <= 1 or k > len(alturas) + 1:
        return alturas[-1] * 1.05
    return (alturas[-k] + alturas[-k + 1]) / 2


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--grupos", type=int, default=None,
                    help="forca o numero de grupos (por padrao, silhueta + estabilidade)")
    ap.add_argument("--sem-graficos", action="store_true")
    a = ap.parse_args()

    mods = checar()
    np, pd = mods["numpy"], mods["pandas"]
    TABELAS.mkdir(parents=True, exist_ok=True)

    p("Grupos de comportamento medido")
    p("=" * 60)
    df = pd.read_csv(ENTRADA)
    if not set(CURVA).issubset(df.columns):
        p("ERRO: features_curvas.csv e de uma versao anterior, sem a janela comum.")
        p("    Rode antes: python src/curvas.py --remontar")
        sys.exit(1)

    perfil = perfis(mods, df)
    p(f"  {len(perfil)} pares bateria x condicao com pelo menos "
      f"{MIN_DESCARGAS} descargas nos {CICLOS_INICIO} primeiros ciclos")

    ext = extremos(mods, perfil)
    perfil["extremo"] = ext
    normais = ~ext
    p(f"  {int(ext.sum())} pares extremos (escore-z modificado > {Z_EXTREMO}), "
      f"grupo a parte: " + ", ".join(f"{r.battery_id} {r.condicao}"
                                     for r in perfil[ext].itertuples()))

    X, info = matriz(mods, perfil[normais].reset_index(drop=True))
    p(f"  atributos mantidos: {', '.join(info['mantidos'])} + curva c00..c49")
    for col, par, r in info["removidos"]:
        p(f"  removido por redundancia: {col} (r = {r:+.3f} com {par})")
    p(f"  PCA: {X.shape[1]} componentes retem "
      f"{info['variancia'].sum():.1%} da variancia "
      f"({', '.join(f'{v:.1%}' for v in info['variancia'])})")
    for j in range(X.shape[1]):
        pesos = sorted(zip(info["nomes_carga"], info["carga_pc"][:, j]),
                       key=lambda t: -abs(t[1]))[:3]
        p(f"    PC{j + 1}: " + ", ".join(f"{n} {w:+.2f}" for n, w in pesos))

    tab = avaliar(mods, X, perfil[normais].reset_index(drop=True))
    k = escolher_k(tab, a.grupos)

    perfil["grupo"] = 0
    perfil.loc[normais, "grupo"] = ward(X, k)
    perfil.loc[ext, "grupo"] = k + 1
    nomes = nomear(mods, perfil)
    perfil["grupo_comportamento"] = perfil.grupo.map(nomes)

    cont = relatar(mods, perfil, nomes)
    val = validar(mods, perfil, X, normais, k)
    veredito(mods, perfil, nomes)

    saida = perfil[["battery_id", "condicao", "descarga", "corte_V", "grupo", "grupo_comportamento",
                    "extremo", "descargas_inicio", "descargas_total",
                    "energia_Wh_comum", "carga_Ah_comum", "duracao_s_comum",
                    "V_medio_comum", "T_subida_comum", "fracao_energia_1a_metade_comum"]]
    saida.to_csv(TABELAS / "grupos_comportamento.csv", index=False)
    cont.to_csv(TABELAS / "contingencia.csv")
    tab.to_csv(TABELAS / "escolha_de_k.csv", index=False)
    val.to_csv(TABELAS / "validacao.csv", index=False)
    p("")
    for nome in ("grupos_comportamento.csv", "contingencia.csv",
                 "escolha_de_k.csv", "validacao.csv"):
        p(f"  {(TABELAS / nome).relative_to(RAIZ)}")

    if not a.sem_graficos:
        p("")
        desenhar(mods, estilo(mods), perfil, normais, X, info, k, tab, cont, nomes)


if __name__ == "__main__":
    main()
