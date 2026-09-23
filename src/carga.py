#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A carga como processo proprio, uma linha por ensaio de carga.

    python carga.py                 # usa cache se existir
    python carga.py --remontar      # ignora o cache e rele os 2.815 ensaios
    python carga.py --amostra 100   # teste rapido
    python carga.py --sem-graficos

Escreve saida_nasa/carga/.

**O projeto inteiro, ate aqui, olhou so para a descarga.** O dataset tem 2.815
ensaios de carga contra 2.794 de descarga, cobrindo as 34 celulas, e nenhum
script tocava neles: `graficos_nasa.py` filtra `type == "discharge"`,
`correlacao_soh.py` filtra `discharge` e `impedance`, e `charge_type` entrava
como uma string constante. Metade do dado estava parada.

**Por que a carga merece ser lida a parte.** Na descarga o protocolo varia — 11
combinacoes de corrente x temperatura, mais o corte de 2,0 a 2,7 V — e essa
variacao engole a degradacao: e o motivo de todo o projeto normalizar por
bateria x condicao. Na carga acontece o contrario. **O protocolo e identico nas
34 celulas**: CC de 1,5 A ate 4,2 V, depois CV ate a corrente cair a 20 mA. Com
o estimulo fixo, o que muda de um ciclo para o outro e a celula, nao o ensaio.
A carga e o ensaio controlado que a descarga nao e.

**A carga tem duas fases, e elas medem coisas diferentes.**

- **CC** (corrente constante): a celula aceita 1,5 A e a tensao sobe ate 4,2 V.
  Quanto menos capacidade resta, mais rapido a tensao sobe — a fase CC encurta.
- **CV** (tensao constante): a tensao fica em 4,2 V e a corrente decai. Quanto
  mais degradada a celula, maior a resistencia e mais tempo a corrente leva
  para cair — a fase CV alonga.

As duas andam em sentidos opostos com a idade, e por isso a duracao total da
carga quase nao se mexe (r = 0,01 com o SOH). Quem olha so o total nao ve nada;
quem separa as fases ve as duas metades do efeito. A fronteira e detectada no
proprio dado: a fase CC acaba na primeira vez que a corrente cai abaixo de
95% do seu patamar e **fica** abaixo por 3 amostras seguidas — a exigencia de
persistencia evita que um unico ponto ruidoso corte a fase no meio.

**A janela de tensao fixa, que e a parte que importa.** Cada carga comeca na
tensao em que a descarga anterior deixou a celula, e isso varia de 3,1 a 4,4 V
entre os ensaios. Comparar `t_cc_s` cru entre celulas mede sobretudo quao
descarregada a celula estava, nao a saude dela. A solucao e a mesma que
`curvas.py` usa para as areas: medir dentro de uma **janela fixa, igual para
todos**. `t_janela_CC_s` e o tempo que a carga leva para atravessar de 3,9 V a
4,15 V dentro da fase CC. Como a corrente e constante ali, esse tempo e a carga
aceita naquela faixa de tensao — uma capacidade parcial, medida sempre na mesma
janela, independente de onde a carga comecou.

E o melhor atributo de saude que este projeto produziu ate agora:

| atributo | agrupada | intra-celula | cobertura |
|---|---|---|---|
| `t_janela_CC_s` (3,9-4,15 V) | 0,48 | **0,63** | 75% dos ensaios, 31 celulas |
| `t_janela_CC34_s` (4,0-4,15 V) | 0,27 | 0,50 | 88% dos ensaios, 34 celulas |
| `Ah_cc` | 0,37 | 0,52 | 100% |
| `dqdv_pico` | 0,42 | 0,49 | 94% |

Para efeito de comparacao, o melhor atributo nao vazado do lado da descarga e
`V_medio`, com 0,674 intra-celula. A carga chega perto disso **sem tocar na
descarga que esta sendo prevista**.

As duas janelas ficam na tabela porque a escolha e um troco: a de 3,9 V
correlaciona mais forte, a de 4,0 V alcanca as 34 celulas. Tres celulas
(B0041, e parte dos ensaios de B0038 a B0045) nunca passam por 3,9 V sob carga,
porque comecam a carga ja acima disso. `janela_completa` marca quem tem o
numero.

**O que e quase-capacidade aqui.** `carga_inj_Ah` — a carga total injetada —
correlaciona 0,92 com a capacidade da descarga **anterior** (0,87 intra-celula,
erro mediano de +2,0%, que e a propria ineficiencia coulombica). Ou seja, ela e
a capacidade da celula medida pelo outro lado, um ciclo antes. Nao e o vazamento
que `correlacao_soh.py` marca, porque nao usa a descarga que se quer prever —
para um BMS e atributo legitimo, medido antes de a descarga acontecer. Mas
tambem nao e descoberta nenhuma que ela acompanhe o SOH, e o ranking marca as
duas (`carga_inj_Ah` e `energia_inj_Wh`) com `quase_capacidade` para que ninguem
leia identidade como achado. `t_janela_CC_s`, `Ah_cc` e `dqdv_pico` nao caem
nessa conta: medem um trecho fixo da carga, nao o total devolvido.

**dQ/dV (analise de capacidade incremental).** Na fase CC, a carga acumulada
derivada em relacao a tensao produz picos nos platos de transicao de fase do
eletrodo. O pico encolhe e desliza para tensoes mais altas conforme a celula
perde material ativo — e o que `dqdv_pico` e `dqdv_V_pico` registram, e os dois
aparecem no ranking com 0,49 e -0,41. A curva e reamostrada num passo de 5 mV e
suavizada por media movel de 9 pontos antes de derivar; sem isso a derivada e
ruido de quantizacao do conversor.

**O pareamento com a descarga.** Cada carga recebe o rotulo da **descarga
seguinte** da mesma celula — a que aquela carga preparou —, e com ele vem
`condicao`, `ciclo_na_condicao` e `SoH_%`. A ordem cronologica e a de `uid`: o
campo `start_time` tem 1.526 registros corrompidos (ano "2"), e uid concorda com
o relogio em todas as 34 celulas onde o relogio e legivel. Dos 2.815 ensaios,
2.783 rendem atributos — 32 nao tem trecho sob carga utilizavel — e 2.754 tem
descarga seguinte com SOH; o resto e a ultima carga de cada serie e fica na
tabela sem rotulo, marcado em `alerta`.

**Cargas truncadas.** O ensaio tem teto de 3 h, e 40% das cargas batem nele.
Em 16% dos casos a corrente ainda nao tinha caido aos 50 mA quando o tempo
acabou, entao `t_cv_s` esta cortado por cima e nao mede o que deveria. `truncada_3h` e
`terminou_por_corrente` marcam esses casos — e sao a razao de as metricas de CV
(`t_cv_s`, `t_cv_ate_50mA`) renderem menos que as de CC apesar de a fisica
prometer o contrario.

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
DESCARGAS = RAIZ / "saida_nasa" / "metricas_descargas.csv"
SAIDA = RAIZ / "saida_nasa" / "carga"

PAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
       "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e3e2de"
FOGO = "#b93331"
SEQ = ["#cfe0f5", "#9dc3ea", "#6d9fe4", "#2a78d6", "#104281"]
DIV = ["#7d1f1d", "#b93331", "#d97370", "#eab5b3", "#f0efec",
       "#adc9ee", "#6d9fe4", "#2a78d6", "#104281"]

ALVO = "SoH_%"

LIMIAR_CARGA = 0.01      # A; define o trecho sob carga em Current_measured
MIN_PONTOS = 20          # abaixo disso o ensaio nao rende agregacao
MIN_PONTOS_CC = 5        # abaixo disso nao ha fase CC para medir
FRAC_CC = 0.95           # a fase CC e onde a corrente >= 95% do patamar
CORRIDA_CV = 3           # amostras seguidas abaixo do patamar para fechar a CC
I_TERMINO = 0.05         # A; abaixo disso a carga terminou por corrente
DUR_MAX = 10_700.0       # s; o ensaio tem teto de 3 h (10.800 s)
EF_MIN, EF_MAX = 80.0, 110.0   # faixa em que a eficiencia coulombica e crivel

# As duas janelas de tensao fixa dentro da fase CC. A primeira correlaciona mais
# forte com o SOH, a segunda alcanca as 34 celulas. Ver a docstring.
JANELA_CC = (3.90, 4.15)
JANELA_CC34 = (4.00, 4.15)

N_REAMOSTRA = 50         # pontos de tensao e corrente em tempo normalizado
PASSO_ICA = 0.005        # V; grade da curva dQ/dV
SUAVIZA_ICA = 9          # pontos da media movel antes de derivar

# As variaveis do ranking e do mapa de calor, na ordem em que aparecem.
COLUNAS = [
    "t_janela_CC_s", "t_janela_CC34_s", "Ah_cc", "t_cc_s", "frac_t_cc",
    "dqdv_pico", "dqdv_V_pico",
    "t_cv_s", "t_cv_ate_50mA", "frac_Ah_cv", "I_final",
    "carga_inj_Ah", "energia_inj_Wh",
    "V_inicial", "V_transicao", "T_subida", "ciclo_na_condicao", ALVO,
]

# A capacidade da celula medida pelo lado da carga, um ciclo antes. Ver a
# docstring: nao e o vazamento da Tabela 2, mas tambem nao e achado.
QUASE_CAPACIDADE = {"carga_inj_Ah", "energia_inj_Wh"}


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
    if not DADOS.exists():
        p(f"ERRO: {DADOS.name}/ nao existe. Rode antes: python preparar_dados.py")
        sys.exit(1)
    if not DESCARGAS.exists():
        p(f"ERRO: {DESCARGAS.relative_to(RAIZ)} nao existe.")
        p("    Rode antes: python graficos_nasa.py")
        sys.exit(1)
    return mods


def integrar(np, y, t):
    """Trapezio, tolerante ao numpy 2.x (np.trapz virou np.trapezoid)."""
    f = getattr(np, "trapezoid", None) or np.trapz
    return float(f(y, t))


# ---------------------------------------------------------------------------
# pareamento carga <-> descarga
# ---------------------------------------------------------------------------
def pareamentos(mods):
    """Para cada carga, a descarga que vem depois e a que veio antes.

    A ordem e a de `uid`, e nao a de `start_time`: 1.526 dos 7.565 registros tem
    a data corrompida (ano "2"), e nas linhas legiveis uid concorda com o relogio
    nas 34 baterias. Ensaios de impedancia no meio nao interrompem o par — a
    descarga seguinte continua sendo a descarga seguinte.
    """
    pd = mods["pandas"]
    meta = pd.read_csv(DADOS / "metadata.csv")
    seguinte, anterior = {}, {}
    for _, g in meta.groupby("battery_id"):
        g = g.sort_values("uid")
        tipos, arqs = g.type.tolist(), g.filename.tolist()

        prox = None
        for j in range(len(tipos) - 1, -1, -1):
            if tipos[j] == "discharge":
                prox = arqs[j]
            elif tipos[j] == "charge":
                seguinte[arqs[j]] = prox

        ult = None
        for j in range(len(tipos)):
            if tipos[j] == "discharge":
                ult = arqs[j]
            elif tipos[j] == "charge":
                anterior[arqs[j]] = ult
    return meta, seguinte, anterior


# ---------------------------------------------------------------------------
# uma curva de carga -> os atributos
# ---------------------------------------------------------------------------
def fronteira_cc(np, i, patamar):
    """Primeiro indice fora da fase CC, exigindo persistencia.

    Sem a exigencia, uma unica amostra ruidosa abaixo do patamar cortaria a fase
    CC no meio e `t_cc_s` mediria o ruido em vez do protocolo.
    """
    fora = (i < FRAC_CC * patamar).astype(int)
    if len(fora) <= CORRIDA_CV:
        return len(i)
    corrida = np.convolve(fora, np.ones(CORRIDA_CV, int), "valid")
    onde = np.where(corrida == CORRIDA_CV)[0]
    return int(onde[0]) if len(onde) else len(i)


def ica(np, v, q):
    """Pico da curva dQ/dV na fase CC, e a tensao em que ele acontece.

    Devolve (nan, nan) quando a fase CC e curta demais ou a tensao nao sobe o
    bastante para render uma faixa. A suavizacao vem antes da derivada porque
    dQ/dV cru e dominado pelo passo de quantizacao do conversor de tensao.
    """
    sobe = np.diff(v) > 0
    if sobe.sum() < 30:
        return float("nan"), float("nan")
    vv, qq = v[:-1][sobe], q[:-1][sobe]
    ordem = np.argsort(vv)
    vv, qq = vv[ordem], qq[ordem]
    lo, hi = max(float(vv[0]), 3.5), min(float(vv[-1]), 4.2)
    if hi - lo <= 0.1:
        return float("nan"), float("nan")

    grade = np.arange(lo, hi, PASSO_ICA)
    if len(grade) <= SUAVIZA_ICA:
        return float("nan"), float("nan")
    qg = np.interp(grade, vv, qq)
    nucleo = np.ones(SUAVIZA_ICA) / SUAVIZA_ICA
    qs = np.convolve(qg, nucleo, "valid")
    gs = grade[SUAVIZA_ICA // 2:len(grade) - SUAVIZA_ICA // 2][:len(qs)]
    if len(gs) < 3:
        return float("nan"), float("nan")
    dq = np.gradient(qs, gs)
    k = int(np.nanargmax(dq))
    return float(dq[k]), float(gs[k])


def extrair(c, np):
    """Um ensaio de carga -> fases, janelas, ICA e forma. {} se nao der."""
    i = c.Current_measured.to_numpy(float)
    v = c.Voltage_measured.to_numpy(float)
    t = c.Time.to_numpy(float)
    tp = c.Temperature_measured.to_numpy(float)
    ic = c.Current_charge.to_numpy(float)

    # Trecho sob carga. O ensaio comeca e termina com corrente zero, e o repouso
    # nas pontas nao e carga: integra-lo somaria area de celula parada.
    sob = i > LIMIAR_CARGA
    if sob.sum() < MIN_PONTOS:
        return {}
    k0 = int(sob.argmax())
    k1 = int(len(sob) - 1 - sob[::-1].argmax())
    faixa = slice(k0, k1 + 1)
    i, v, t, tp, ic = i[faixa], v[faixa], t[faixa], tp[faixa], ic[faixa]

    dur = float(t[-1] - t[0])
    if dur <= 0:
        return {}

    r = {
        "carga_inj_Ah": integrar(np, i, t) / 3600.0,
        "carga_inj_load_Ah": integrar(np, np.abs(ic), t) / 3600.0,
        "energia_inj_Wh": integrar(np, v * i, t) / 3600.0,
        "duracao_s": dur,
        "n_pontos": int(k1 - k0 + 1),
        "V_inicial": float(v[0]),
        "V_max": float(v.max()),
        "T_inicial": float(tp[0]),
        "T_max": float(tp.max()),
        "T_subida": float(tp.max() - tp[0]),
    }

    # ---- fase CC
    patamar = float(np.percentile(i, 95))
    kcc = fronteira_cc(np, i, patamar)
    if kcc < MIN_PONTOS_CC:
        return {}
    vcc, icc, tcc = v[:kcc], i[:kcc], t[:kcc]

    # Carga acumulada dentro da CC, ponto a ponto: serve ao Ah_cc e a curva ICA.
    q = np.concatenate([[0.0], np.cumsum(np.diff(tcc) * (icc[:-1] + icc[1:]) / 2)])
    q = q / 3600.0

    t_cc = float(tcc[-1] - tcc[0])
    r["I_cc_A"] = patamar
    r["t_cc_s"] = t_cc
    r["Ah_cc"] = float(q[-1])
    r["V_transicao"] = float(vcc[-1])
    r["frac_t_cc"] = t_cc / dur
    r["inclinacao_mV_min_cc"] = (
        float((vcc[-1] - vcc[0]) / t_cc * 1000.0 * 60.0) if t_cc > 0
        else float("nan"))

    # ---- janelas de tensao fixa dentro da CC
    # np.interp exige o eixo x crescente; a tensao de carga sobe, mas com ruido
    # de conversor. O acumulado maximo impoe a monotonia sem mexer na forma.
    vmono = np.maximum.accumulate(vcc)
    for nome, (lo, hi) in (("t_janela_CC_s", JANELA_CC),
                           ("t_janela_CC34_s", JANELA_CC34)):
        if vmono[0] <= lo and vmono[-1] >= hi:
            a = float(np.interp(lo, vmono, tcc))
            b = float(np.interp(hi, vmono, tcc))
            r[nome] = b - a
        else:
            r[nome] = float("nan")
    r["janela_completa"] = bool(r["t_janela_CC_s"] == r["t_janela_CC_s"])
    # Em corrente constante a carga aceita na janela e o tempo vezes a corrente:
    # o mesmo numero em Ah, que e como um engenheiro de bateria prefere le-lo.
    r["Ah_janela_CC"] = (r["t_janela_CC_s"] * patamar / 3600.0
                         if r["janela_completa"] else float("nan"))

    # ---- fase CV
    tcv, icv = t[kcc:], i[kcc:]
    r["t_cv_s"] = float(t[-1] - t[kcc]) if kcc < len(t) else 0.0
    r["Ah_cv"] = r["carga_inj_Ah"] - r["Ah_cc"]
    r["frac_Ah_cv"] = (r["Ah_cv"] / r["carga_inj_Ah"]
                       if r["carga_inj_Ah"] > 0 else float("nan"))
    r["I_final"] = float(i[-1])
    for limiar, nome in ((0.10, "t_cv_ate_100mA"), (0.05, "t_cv_ate_50mA")):
        abaixo = np.where(icv <= limiar)[0]
        r[nome] = (float(tcv[abaixo[0]] - t[kcc]) if len(abaixo)
                   else float("nan"))
    r["terminou_por_corrente"] = bool(i[-1] <= I_TERMINO)
    r["truncada_3h"] = bool(dur >= DUR_MAX)

    # ---- dQ/dV
    r["dqdv_pico"], r["dqdv_V_pico"] = ica(np, vcc, q)

    # ---- forma, em tempo normalizado. Mesma convencao de curvas.py: separa a
    # forma da duracao, e e o que permite comparar cargas de 30 e de 180 min.
    tn = (t - t[0]) / dur
    grade = np.linspace(0.0, 1.0, N_REAMOSTRA)
    for nome, serie in (("cv", v), ("ci", i)):
        vq = np.interp(grade, tn, serie)
        for k, val in enumerate(vq):
            r[f"{nome}{k:02d}"] = float(val)
    return r


# ---------------------------------------------------------------------------
# montagem da tabela
# ---------------------------------------------------------------------------
def montar(mods, remontar=False, amostra=None):
    np, pd = mods["numpy"], mods["pandas"]
    cache = SAIDA / "features_carga.csv"
    if cache.exists() and not remontar and amostra is None:
        p(f"  cache: {cache.relative_to(RAIZ)}")
        return pd.read_csv(cache)

    meta, seguinte, anterior = pareamentos(mods)
    cargas = meta[meta.type == "charge"].sort_values(["battery_id", "uid"]).copy()
    cargas["ciclo_carga"] = cargas.groupby("battery_id").cumcount()
    if amostra:
        cargas = cargas.head(amostra)
    p(f"  lendo {len(cargas)} ensaios de carga...")

    linhas, vazios = [], 0
    for n, lin in enumerate(cargas.itertuples(index=False), 1):
        if n % 250 == 0:
            p(f"    {n}/{len(cargas)}")
        arq = DADOS / "data" / lin.filename
        if not arq.exists():
            vazios += 1
            continue
        f = extrair(pd.read_csv(arq), np)
        if not f:
            vazios += 1
            continue
        f["filename"] = lin.filename
        f["battery_id"] = lin.battery_id
        f["ciclo_carga"] = lin.ciclo_carga
        f["test_id"] = lin.test_id
        f["uid"] = lin.uid
        f["ambient_carga"] = lin.ambient_temperature
        f["descarga_seguinte"] = seguinte.get(lin.filename)
        f["descarga_anterior"] = anterior.get(lin.filename)
        linhas.append(f)
    if vazios:
        p(f"  {vazios} ensaios sem trecho sob carga utilizavel (sem features)")

    df = pd.DataFrame(linhas)

    # O rotulo vem da descarga que esta carga preparou: condicao, ciclo e SOH.
    d = pd.read_csv(DESCARGAS)
    rotulo = d[["filename", "ciclo", "ciclo_na_condicao", "condicao",
                "corrente_A", "ambient_temperature", "Capacity", "cap_ref_Ah",
                ALVO]].rename(columns={"filename": "descarga_seguinte"})
    df = df.merge(rotulo, on="descarga_seguinte", how="left")

    # A capacidade da descarga anterior, so para medir o que a carga devolveu.
    cap = d[["filename", "Capacity"]].rename(
        columns={"filename": "descarga_anterior", "Capacity": "cap_anterior_Ah"})
    df = df.merge(cap, on="descarga_anterior", how="left")
    df["eficiencia_coulombica_pct"] = df.Capacity / df.carga_inj_Ah * 100.0

    # A eficiencia coulombica so significa alguma coisa quando a descarga
    # seguinte esvazia a celula. Em 4 A / 4 C ela entrega 0,077 Ah contra 1,7 Ah
    # das demais condicoes: a razao cai para 5% e mede o protocolo, nao perda de
    # carga. O mesmo vale para a primeira carga de cada serie, que parte de uma
    # celula ja parcialmente cheia. Marcado, nunca apagado — a convencao das
    # tabelas de metricas do projeto.
    ef = df.eficiencia_coulombica_pct
    df["alerta"] = np.where(
        df.descarga_seguinte.isna(), "sem_descarga_seguinte",
        np.where(ef.isna(), "sem_capacidade_na_descarga",
        np.where((ef < EF_MIN) | (ef > EF_MAX), "eficiencia_implausivel", "")))

    frente = ["battery_id", "ciclo_carga", "ciclo", "ciclo_na_condicao",
              "condicao", "test_id", "uid", "filename", "descarga_seguinte",
              "descarga_anterior", ALVO, "alerta"]
    resto = [c for c in df.columns if c not in frente]
    df = df[frente + resto]

    SAIDA.mkdir(parents=True, exist_ok=True)
    if amostra is None:
        df.to_csv(cache, index=False)
        p(f"  {cache.relative_to(RAIZ)}  ({len(df)} x {df.shape[1]})")
    return df


# ---------------------------------------------------------------------------
# correlacoes
# ---------------------------------------------------------------------------
def matrizes(mods, d, cols):
    """Pearson agrupada e intra-celula (centrada por bateria x condicao).

    Mesma regra do resto do projeto: a agrupada mistura a diferenca entre
    celulas com a degradacao dentro de cada uma, e quando as duas discordam
    quem manda e a intra-celula.
    """
    pd = mods["pandas"]
    bruto = d[cols].apply(pd.to_numeric, errors="coerce")
    agrupada = bruto.corr()
    chave = d.battery_id.astype(str) + "|" + d.condicao.astype(str)
    centrado = bruto.groupby(chave).transform(lambda s: s - s.mean())
    return agrupada, centrado.corr()


def ranking(mods, d, agrupada, intra, cols):
    pd = mods["pandas"]
    r = pd.DataFrame({
        "correlacao_agrupada": agrupada[ALVO],
        "correlacao_intracelula": intra[ALVO],
    }).drop(index=ALVO, errors="ignore")
    r["cobertura_pct"] = [d[c].notna().mean() * 100.0 for c in r.index]
    r["celulas"] = [int(d.loc[d[c].notna(), "battery_id"].nunique())
                    for c in r.index]
    r["quase_capacidade"] = [i in QUASE_CAPACIDADE for i in r.index]
    r["forca_intracelula"] = r.correlacao_intracelula.abs()
    return r.sort_values(["quase_capacidade", "forca_intracelula"],
                         ascending=[True, False])


def preparar(mods, df):
    """So as cargas com rotulo: sem a descarga seguinte nao ha SOH a comparar."""
    d = df[df.condicao.notna() & df[ALVO].notna()].copy()
    cols = [c for c in COLUNAS if c in d.columns]
    return d, cols


def resumir(mods, df, d):
    pd = mods["pandas"]
    p("")
    p(f"  ensaios de carga com features: {len(df)}")
    p(f"  pareados com a descarga seguinte: {len(d)}"
      f"  ({d.battery_id.nunique()} baterias)")

    trunc = df.truncada_3h.fillna(False).astype(bool)
    term = df.terminou_por_corrente.fillna(False).astype(bool)
    p(f"  cargas no teto de 3 h: {trunc.mean() * 100:.1f}%   "
      f"terminadas por corrente (<= {I_TERMINO * 1000:.0f} mA): "
      f"{term.mean() * 100:.1f}%")
    p(f"  janela {JANELA_CC[0]:.2f}-{JANELA_CC[1]:.2f} V disponivel em "
      f"{df.t_janela_CC_s.notna().mean() * 100:.1f}% dos ensaios "
      f"({df.loc[df.t_janela_CC_s.notna(), 'battery_id'].nunique()} celulas); "
      f"janela {JANELA_CC34[0]:.2f}-{JANELA_CC34[1]:.2f} V em "
      f"{df.t_janela_CC34_s.notna().mean() * 100:.1f}% "
      f"({df.loc[df.t_janela_CC34_s.notna(), 'battery_id'].nunique()} celulas)")

    # A carga injetada contra a capacidade que a descarga anterior tirou: o
    # numero que mostra que `carga_inj_Ah` e a capacidade pelo outro lado.
    v = df[df.cap_anterior_Ah.notna() & (df.cap_anterior_Ah > 0)]
    if len(v):
        erro = (v.carga_inj_Ah - v.cap_anterior_Ah) / v.cap_anterior_Ah * 100
        p(f"  carga injetada vs capacidade da descarga anterior: "
          f"r = {v.carga_inj_Ah.corr(v.cap_anterior_Ah):.3f}, "
          f"excesso mediano {erro.median():+.2f}%")
    # Lido do cache, o alerta vazio volta como NaN: normaliza antes de comparar.
    alerta = df.alerta.fillna("")
    ef = df.loc[alerta == "", "eficiencia_coulombica_pct"].dropna()
    if len(ef):
        fora = int((alerta == "eficiencia_implausivel").sum())
        p(f"  eficiencia coulombica (descarga seguinte / carga injetada): "
          f"mediana {ef.median():.1f}% em {len(ef)} ciclos; "
          f"{fora} fora de [{EF_MIN:.0f}, {EF_MAX:.0f}]% marcados em `alerta` "
          f"(descarga que nao esvazia a celula, nao perda de carga)")

    g = d.groupby("condicao").agg(
        cargas=("carga_inj_Ah", "size"),
        celulas=("battery_id", "nunique"),
        carga_inj_Ah=("carga_inj_Ah", "median"),
        t_cc_min=("t_cc_s", lambda s: s.median() / 60.0),
        t_cv_min=("t_cv_s", lambda s: s.median() / 60.0),
        t_janela_CC_s=("t_janela_CC_s", "median"),
        frac_Ah_cv=("frac_Ah_cv", "median"),
    ).sort_values("cargas", ascending=False)
    p("")
    p("  medianas por condicao da descarga seguinte:")
    p(f"    {'condicao':<14} {'n':>5} {'cel':>4} {'Ah inj':>7} "
      f"{'CC min':>7} {'CV min':>7} {'janela s':>9}")
    for lin in g.reset_index().itertuples(index=False):
        jan = (f"{lin.t_janela_CC_s:.0f}"
               if lin.t_janela_CC_s == lin.t_janela_CC_s else "-")
        p(f"    {lin.condicao:<14} {lin.cargas:>5} {lin.celulas:>4} "
          f"{lin.carga_inj_Ah:>7.3f} {lin.t_cc_min:>7.1f} "
          f"{lin.t_cv_min:>7.1f} {jan:>9}")
    g.to_csv(SAIDA / "resumo_por_condicao.csv")
    p(f"\n  {(SAIDA / 'resumo_por_condicao.csv').relative_to(RAIZ)}")


def relatar(rank):
    p("")
    p("  correlacao com o SOH da descarga seguinte:")
    p(f"    {'atributo':<20} {'agrupada':>9} {'intra':>8} {'cobert':>8} {'cel':>4}")
    for i, r in rank.iterrows():
        marca = "  <- quase-capacidade" if r.quase_capacidade else ""
        p(f"    {i:<20} {r.correlacao_agrupada:>9.3f} "
          f"{r.correlacao_intracelula:>8.3f} {r.cobertura_pct:>7.1f}% "
          f"{int(r.celulas):>4}{marca}")


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
        "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 1.6,
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


def gradiente(plt, n):
    """n cores do claro ao escuro: idade da celula lida como intensidade."""
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("idade", SEQ)
    return [cmap(k / max(n - 1, 1)) for k in range(n)]


def escolher_celulas(d, quantas):
    """As celulas com serie mais longa, entre as que de fato envelheceram.

    A amplitude de SOH entra como corte, e nao como criterio de ordenacao: as
    celulas de maior amplitude sao B0042 a B0044, que entram no dataset no ciclo
    87 e foram renormalizadas pelo maximo do grupo novo — a serie delas comeca
    no meio da vida e desenha uma degradacao fora de ordem. Ordenar pelo numero
    de ciclos entrega as series inteiras, que e o que a figura precisa mostrar.
    """
    g = d.groupby("battery_id").agg(n=(ALVO, "size"),
                                    faixa=(ALVO, lambda s: s.max() - s.min()))
    g = g[(g.n >= 20) & (g.faixa >= 15)].sort_values("n", ascending=False)
    return list(g.index[:quantas])


def trecho_sob_carga(mods, c):
    """O recorte que extrair() mede, para as figuras desenharem a mesma coisa."""
    np = mods["numpy"]
    i = c.Current_measured.to_numpy(float)
    sob = i > LIMIAR_CARGA
    if sob.sum() < MIN_PONTOS:
        return None
    k0 = int(sob.argmax())
    k1 = int(len(sob) - 1 - sob[::-1].argmax())
    return c.iloc[k0:k1 + 1]


def curvas_da_celula(mods, d, bateria, quantas):
    """Os ensaios de carga de uma celula, espacados do primeiro ao ultimo."""
    np = mods["numpy"]
    b = d[d.battery_id == bateria].sort_values("ciclo_carga")
    if len(b) < quantas:
        return b
    idx = np.linspace(0, len(b) - 1, quantas).astype(int)
    return b.iloc[idx]


def fig_curva_de_carga(mods, plt, d, saida):
    """A carga CC-CV envelhecendo: tensao e corrente, duas celulas."""
    pd = mods["pandas"]
    celulas = escolher_celulas(d, 2)
    if not celulas:
        return
    fig, axes = plt.subplots(len(celulas), 2,
                             figsize=(11, 3.2 * len(celulas)), squeeze=False)
    for r, bat in enumerate(celulas):
        sel = curvas_da_celula(mods, d, bat, 6)
        cores = gradiente(plt, len(sel))
        # to_dict em vez de itertuples: a coluna se chama "SoH_%", e itertuples
        # troca o nome por um posicional quando ele nao e identificador valido.
        for k, lin in enumerate(sel.to_dict("records")):
            arq = DADOS / "data" / lin["filename"]
            if not arq.exists():
                continue
            c = pd.read_csv(arq)
            # Mesmo recorte que extrair() usa: so o trecho sob carga. Fora dele
            # o ensaio tem pontos de repouso e, em algumas celulas, uma amostra
            # negativa isolada que sozinha estica o eixo da corrente ate -3,5 A.
            c = trecho_sob_carga(mods, c)
            if c is None:
                continue
            t = c.Time.to_numpy(float) / 60.0
            rot = (f"ciclo {int(lin['ciclo_carga'])}, SoH {lin[ALVO]:.0f}%"
                   if k in (0, len(sel) - 1) else None)
            axes[r][0].plot(t, c.Voltage_measured, color=cores[k], label=rot)
            axes[r][1].plot(t, c.Current_measured, color=cores[k], label=rot)
        axes[r][0].set_ylabel(f"{bat}\ntensao (V)", fontsize=9.5)
        axes[r][1].set_ylabel("corrente (A)", fontsize=9.5)
        axes[r][0].legend(fontsize=8, loc="lower right")
        # O painel da tensao para pouco depois do fim da fase CC mais longa: o
        # plato de 4,2 V ocupa duas horas e nao tem nada para mostrar, e deixa-lo
        # no eixo espreme a rampa da CC, que e onde a idade aparece.
        fim = sel.t_cc_s.max() / 60.0
        if fim == fim and fim > 0:
            axes[r][0].set_xlim(0, fim * 1.6)
        for ax in axes[r]:
            ax.tick_params(labelsize=8.5)
    for ax in axes[-1]:
        ax.set_xlabel("tempo (min)", fontsize=9.5)
    titulo_figura(plt, fig, "A carga CC-CV, do primeiro ao ultimo ciclo",
                  "Claro = celula nova, escuro = celula velha. A esquerda a tensao subindo "
                  "ate 4,2 V (fase CC), recortada logo depois do fim da rampa; a direita a "
                  "corrente inteira, 1,5 A na CC e decaindo na CV. Com a idade a tensao "
                  "chega a 4,2 V mais cedo — a fase CC encurta — e a CV alonga para "
                  "compensar. Os dois efeitos se cancelam no tempo total, e e por isso que a "
                  "duracao da carga nao diz nada e as fases separadas dizem.")
    fig.savefig(saida / "01_curva_de_carga.png", bbox_inches="tight")
    plt.close(fig)
    p("  01_curva_de_carga.png")


def fig_ciclo_completo(mods, plt, d, saida):
    """Carga e descarga na mesma linha do tempo, em tres idades."""
    pd = mods["pandas"]
    celulas = escolher_celulas(d, 1)
    if not celulas:
        return
    bat = celulas[0]
    sel = curvas_da_celula(mods, d, bat, 3)
    fig, axes = plt.subplots(1, len(sel), figsize=(4.0 * len(sel), 3.6),
                             squeeze=False)
    for k, lin in enumerate(sel.to_dict("records")):
        ax = axes[0][k]
        ac = DADOS / "data" / lin["filename"]
        ad = (DADOS / "data" / lin["descarga_seguinte"]
              if isinstance(lin["descarga_seguinte"], str) else None)
        if not ac.exists() or ad is None or not ad.exists():
            ax.axis("off")
            continue
        cc = trecho_sob_carga(mods, pd.read_csv(ac))
        dd = pd.read_csv(ad)
        if cc is None:
            ax.axis("off")
            continue
        tc = cc.Time.to_numpy(float) / 60.0
        # A pausa entre os dois ensaios e removida: o eixo e tempo de ensaio,
        # nao tempo de relogio. Emendar pelo relogio abriria um vao de horas de
        # repouso que nao mede nada e esmagaria as duas curvas contra o eixo.
        td = dd.Time.to_numpy(float) / 60.0 + tc[-1]
        ax.axvspan(tc[0], tc[-1], color="#e8f0fb", zorder=0)
        ax.axvspan(td[0], td[-1], color="#fdeee6", zorder=0)
        ax.plot(tc, cc.Voltage_measured, color=PAL[0])
        ax.plot(td, dd.Voltage_measured, color=PAL[1])
        ax.set_title(f"ciclo {int(lin['ciclo_carga'])} — SoH "
                     f"{lin[ALVO]:.0f}%", fontsize=9.5, color=INK2)
        ax.set_xlabel("tempo de ensaio (min)", fontsize=9)
        ax.tick_params(labelsize=8.5)
    axes[0][0].set_ylabel("tensao (V)", fontsize=9.5)
    titulo_figura(plt, fig, f"O ciclo inteiro: carga e descarga — {bat}",
                  "Azul = carga, laranja = descarga, no mesmo eixo. A pausa de relogio entre "
                  "os dois ensaios foi removida. A carga ocupa a maior parte do ciclo e "
                  "termina sempre no mesmo lugar, 4,2 V, porque o protocolo de carga e o "
                  "mesmo nas 34 celulas; a descarga e que encurta com a idade. Sao processos "
                  "distintos e e por isso que cada um rende atributos proprios.")
    fig.savefig(saida / "02_ciclo_completo.png", bbox_inches="tight")
    plt.close(fig)
    p("  02_ciclo_completo.png")


def fig_por_grupo(mods, plt, d, coluna, rotulo, nome, titulo, sub, saida):
    """Um painel por condicao, uma linha por celula: a metrica ao longo dos ciclos."""
    grupos = (d.groupby("condicao").size().sort_values(ascending=False).index)
    grupos = [g for g in grupos if d.loc[d.condicao == g, coluna].notna().any()]
    if not grupos:
        return
    n = len(grupos)
    cols = min(4, n)
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(3.6 * cols, 2.9 * rows),
                             squeeze=False)
    for k, g in enumerate(grupos):
        ax = axes[k // cols][k % cols]
        bloco = d[(d.condicao == g) & d[coluna].notna()]
        for i, (bat, b) in enumerate(bloco.groupby("battery_id")):
            b = b.sort_values("ciclo_na_condicao")
            ax.plot(b.ciclo_na_condicao, b[coluna],
                    color=PAL[i % len(PAL)], linewidth=1.3, alpha=0.9)
        ax.set_title(str(g), fontsize=8.5, color=INK2)
        ax.tick_params(labelsize=8)
    for k in range(n, rows * cols):
        axes[k // cols][k % cols].axis("off")
    fig.supxlabel("ciclo dentro da condicao", fontsize=10, color=INK2)
    fig.supylabel(rotulo, fontsize=10, color=INK2)
    titulo_figura(plt, fig, titulo, sub)
    fig.savefig(saida / nome, bbox_inches="tight")
    plt.close(fig)
    p(f"  {nome}")


def fig_ranking(mods, plt, rank, saida):
    np = mods["numpy"]
    r = rank.iloc[::-1]
    y = np.arange(len(r))
    fig, ax = plt.subplots(figsize=(9, 0.38 * len(r) + 3.2))
    ax.barh(y + 0.19, r.correlacao_agrupada, height=0.36,
            color="#c9d8ee", label="agrupada")
    ax.barh(y - 0.19, r.correlacao_intracelula, height=0.36,
            color=PAL[0], label="intra-celula")
    ax.set_yticks(y, r.index, fontsize=9)
    for t, q in zip(ax.get_yticklabels(), r.quase_capacidade):
        t.set_color(FOGO if q else INK2)
    ax.axvline(0, color=INK2, linewidth=1)
    ax.set_xlabel("correlacao de Pearson com o SOH da descarga seguinte")
    ax.legend(fontsize=9, loc="lower right")
    ax.grid(axis="y", visible=False)
    titulo_figura(plt, fig, "O que na carga acompanha o SOH",
                  "Barra escura = correlacao intra-celula, que e a que manda: cada atributo "
                  "centrado na media da sua bateria x condicao antes de correlacionar. "
                  "Rotulo em vermelho = quase-capacidade: a carga injetada e a capacidade da "
                  "descarga anterior medida pelo outro lado (r = 0,92), entao acompanhar o "
                  "SOH ali nao e achado. O resto e informacao nova, vinda de um ensaio que "
                  "o projeto nao usava.")
    fig.savefig(saida / "05_ranking_vs_soh.png", bbox_inches="tight")
    plt.close(fig)
    p("  05_ranking_vs_soh.png")


def fig_mapa(mods, plt, m, nome, titulo, sub, saida):
    from matplotlib.colors import LinearSegmentedColormap
    np = mods["numpy"]
    n = len(m)
    cmap = LinearSegmentedColormap.from_list("div", DIV)
    fig, ax = plt.subplots(figsize=(0.62 * n + 3.4, 0.62 * n + 2.8))
    ax.imshow(m.to_numpy(float), cmap=cmap, vmin=-1, vmax=1)

    def pinta(rotulos):
        return [FOGO if r in QUASE_CAPACIDADE else INK2 for r in rotulos]

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
            cor = SURF if abs(v) > 0.55 else INK
            ax.text(b, a, f"{v:.2f}", ha="center", va="center",
                    fontsize=7.2, color=cor)

    import textwrap
    fig.text(0.007, 0.995, titulo, fontsize=14, fontweight="bold",
             color=INK, ha="left", va="top")
    linhas = textwrap.wrap(sub, width=int(fig.get_figwidth() * 12))
    fig.text(0.007, 0.968, "\n".join(linhas), fontsize=9.5, color=INK2,
             ha="left", va="top", linespacing=1.35)
    fig.text(0.007, 0.006, "rotulo em vermelho = quase-capacidade: a carga "
             "injetada e a capacidade da descarga anterior por outro caminho.",
             fontsize=9, color=FOGO, ha="left", va="bottom")
    fig.tight_layout(rect=[0, 0.02, 1, 0.955 - 0.016 * len(linhas)])
    fig.savefig(saida / nome, bbox_inches="tight")
    plt.close(fig)
    p(f"  {nome}")


def desenhar(mods, d, agrupada, intra, rank):
    plt = estilo(mods)
    p("")
    fig_curva_de_carga(mods, plt, d, SAIDA)
    fig_ciclo_completo(mods, plt, d, SAIDA)
    fig_por_grupo(
        mods, plt, d, "Ah_cc", "carga aceita na fase CC (Ah)",
        "03_ah_cc_por_ciclo.png",
        "A carga aceita na fase CC, ao longo dos ciclos",
        "Uma linha por celula, um painel por condicao da descarga seguinte. E o "
        "analogo, do lado da carga, do Ah por ciclo que capacidade.py mede na "
        "descarga — e cai pelo mesmo motivo: a celula aceita menos carga antes de "
        "chegar a 4,2 V. Ao contrario da area de descarga, este numero nao e o alvo "
        "por outro nome: ele e medido antes de a descarga acontecer.", SAIDA)
    fig_por_grupo(
        mods, plt, d, "t_janela_CC_s",
        f"tempo de {JANELA_CC[0]:.2f} V a {JANELA_CC[1]:.2f} V (s)",
        "04_janela_CC_por_ciclo.png",
        "O tempo na janela de tensao fixa, ao longo dos ciclos",
        "Quanto tempo a carga leva para atravessar de 3,90 V a 4,15 V dentro da fase "
        "CC. Como a corrente e constante ali, esse tempo e a carga aceita naquela "
        "faixa — uma capacidade parcial medida sempre na mesma janela, imune a quao "
        "descarregada a celula estava. E o atributo de carga que melhor acompanha o "
        "SOH (0,63 intra-celula). Paineis vazios ou ralos sao celulas que comecam a "
        "carga acima de 3,90 V e nunca atravessam a janela.", SAIDA)
    fig_ranking(mods, plt, rank, SAIDA)
    fig_mapa(mods, plt, agrupada, "06_mapa_agrupado.png",
             "Correlacao agrupada — atributos de carga",
             "Todos os ensaios de carga juntos. Mistura a diferenca entre celulas com a "
             "degradacao dentro de cada uma, e por isso engana: compare com o mapa "
             "intra-celula antes de concluir qualquer coisa daqui.", SAIDA)
    fig_mapa(mods, plt, intra, "07_mapa_intracelula.png",
             "Correlacao intra-celula — atributos de carga",
             "Cada atributo centrado na media da sua bateria x condicao antes de "
             "correlacionar. Remove o nivel proprio de cada celula e deixa so a variacao "
             "ao longo da vida. E esta que manda.", SAIDA)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--remontar", action="store_true",
                    help="ignora o cache e rele os ensaios de carga")
    ap.add_argument("--amostra", type=int, default=None,
                    help="le so os N primeiros ensaios (teste rapido)")
    ap.add_argument("--sem-graficos", action="store_true")
    a = ap.parse_args()

    mods = checar()
    SAIDA.mkdir(parents=True, exist_ok=True)
    p("A carga como processo proprio")
    p("=" * 60)

    df = montar(mods, remontar=a.remontar, amostra=a.amostra)
    d, cols = preparar(mods, df)
    resumir(mods, df, d)

    agrupada, intra = matrizes(mods, d, cols)
    rank = ranking(mods, d, agrupada, intra, cols)
    agrupada.to_csv(SAIDA / "matriz_agrupada.csv")
    intra.to_csv(SAIDA / "matriz_intracelula.csv")
    rank.to_csv(SAIDA / "ranking_vs_soh.csv")
    relatar(rank)
    p("")
    p(f"  {(SAIDA / 'ranking_vs_soh.csv').relative_to(RAIZ)}")

    if not a.sem_graficos:
        desenhar(mods, d, agrupada, intra, rank)


if __name__ == "__main__":
    main()
