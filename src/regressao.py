#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Regressao do SOH com modelo aditivo generalizado (GAM) e conversao em vida util
remanescente (RUL).

    python regressao.py                    # escolhe lambda na validacao, avalia no teste
    python regressao.py --lam 10000        # forca lambda
    python regressao.py --sem-referencias  # so o GAM, sem as familias da literatura
    python regressao.py --sem-graficos     # so as tabelas

Le saida_nasa/normalizado/tabelas/dados_normalizados.csv e escreve em
saida_nasa/regressao/: as tabelas em tabelas/, os graficos em figuras/.

**A tarefa.** Estimar o SOH (%) de cada descarga a partir do que se mede nela —
tensao, corrente, temperatura, impedancia —, sem a capacidade, que e o proprio
SOH, e converter a estimativa em vida util remanescente (RUL), em ciclos:

    RUL = (SOH estimado - 80) / perda de SOH por ciclo da condicao

O limiar de 80% e o da classificacao. O SOH se mede em RMSE e MAE, em pontos
percentuais (p.p.) de SOH, e em R2; o RUL, no erro absoluto medio (MAE) em
ciclos e na fracao das previsoes a ate 20% do RUL real.

**Por que um GAM.** O modulo segue a regra do de classificacao: um algoritmo
fora das familias dos trabalhos relacionados do artigo (regressao linear, SVM,
RVM, processos gaussianos, ensembles de arvores, redes neurais). O modelo
aditivo generalizado escreve o SOH como uma soma de funcoes suaves, uma por
atributo,

    SOH = b0 + f_1(x_1) + ... + f_p(x_p),

e cada f_j e uma P-spline (Eilers e Marx, 1996): nos igualmente espacados, base
B-spline cubica e minimos quadrados com penalidade nas segundas diferencas dos
coeficientes. A penalidade cobra curvatura e deixa a reta passar de graca, entao
um parametro so, lambda, vai de splines que seguem o ruido (lambda -> 0) a retas
(lambda -> infinito), quando o GAM vira regressao linear. A forma de cada f_j
sai dos dados e pode ser desenhada: 07_efeitos_gam.png mostra quanto cada
atributo move o SOH, na unidade fisica dele. Nenhuma referencia mostra isso.

**Extrapolacao constante.** Fora da faixa entre os quantis de 1% e 99% do
treino, cada f_j fica parada no valor da borda. Prolongar a curva, como faz a
regressao linear, explode numa condicao que o treino nunca viu: B0041 e a unica
celula avaliavel a 4 A / 4 C, e quando a validacao a deixa de fora o treino nao
tem nenhuma descarga nessa condicao.

**Quais pares entram.** O SOH e a capacidade sobre a maior capacidade da celula
naquela condicao. Em 8 dos 43 pares celula x condicao essa referencia e uma
leitura isolada, e o SOH ja comeca abaixo de 80%: B0036 marca 99% das descargas
em fim de vida, B0049 a B0051 comecam entre 30% e 60%. Na classificacao isso
troca rotulos; na regressao o erro e quadratico, e um par desses pesa no RMSE
mais que celulas inteiras. Entram so os pares cujo SOH comeca saudavel — a
mediana das 5 primeiras descargas, a janela da referencia de normalizar.py,
acima de 80% —: saem 7 pares do treino (5 celulas inteiras) e 1 do teste. A
regra vale igual dos dois lados, foi fixada antes de qualquer previsao, e a
validacao mede o que acontece quando os 7 pares ficam no treino.

**Atributos.** Os relativos ao inicio de vida de normalizar.py (as colunas
_rel), a temperatura ambiente, a corrente e os ciclos desde o inicio do par —
este no lugar do ciclo da celula, que a classificacao usa: o SOH e relativo a
referencia do par, e nas celulas que mudam de condicao (B0041 a B0044) o ciclo
da celula segue contando enquanto o SOH recomeca em 100%. A troca e medida na
validacao. Temperatura e corrente sao o protocolo, com poucos valores
distintos, e entram no GAM como reta. Os conjuntos bruto e completo rodam ao
lado.

**Validacao deixando uma celula de fora**, nas 20 celulas de treino com par
avaliavel. Imputacao e escala sao reajustadas a cada rodada.

**lambda: o mais suave equivalente ao melhor.** O RMSE contra lambda forma um
plato. Vence o maior lambda a ate TOLERANCIA_LAMBDA do menor RMSE — a logica do
k do kNN e do agrupamento: entre modelos que a validacao nao separa, o mais
simples, aqui o de curvas mais suaves.

**O teste e avaliado uma vez**, nas 8 celulas que nao entram em escolha
nenhuma. O intervalo vem de reamostrar celulas inteiras, e a diferenca para
cada referencia e medida em pares, nas mesmas reamostragens, com e sem
Bonferroni.

**A conversao em RUL.** A perda por ciclo de cada condicao e a mediana, entre os
pares de treino dela, da inclinacao de Theil-Sen do SOH medido contra o ciclo —
robusta aos saltos de regeneracao que as celulas da NASA tem depois das pausas.
Entram todos os pares da condicao, cheguem ou nao a 80%: tirar a taxa so dos que
chegaram escolheria as celulas pelo desfecho. O fim de vida real e a primeira
de 3 descargas seguidas abaixo de 80%, e as previsoes comecam na 5a descarga do
par, quando a referencia de inicio de vida dos atributos ja esta fechada. Par
que nao chega a 80% e censurado: so se pode cobrar dele que a previsao nao
anuncie o fim de vida antes do fim da observacao (alarme antecipado).

**A conversao e escolhida na validacao**, contra a tendencia da propria celula:
uma reta nas ultimas W estimativas, prolongada ate 80%, com W em JANELAS. Vence
a de menor MAE com as estimativas do GAM, nos mesmos instantes.

**Variante pos-hoc: media movel antes de converter.** No teste, a estimativa de
B0054 alterna de uma descarga para a seguinte, porque tensao e temperatura
alternam, e a taxa lenta da condicao amplifica o vaivem. A variante converte a
media das ultimas M estimativas. Como surgiu de olhar o teste, so a validacao a
avalia, e ela nao entra no modelo.

**O oraculo.** A mesma conversao sobre o SOH medido separa o erro da conversao
do erro da estimativa. Pela taxa da condicao, enquanto a previsao nao e cortada
em zero, os dois se somam: o erro do RUL e o do oraculo mais o erro do SOH
dividido pela perda por ciclo. Onde a perda e de 0,12 p.p. por ciclo, 5 p.p. de
SOH sao 40 ciclos.

**Familias da literatura como referencia.** Regressao linear, SVR, Random Forest
e Gradient Boosting, com os hiperparametros padrao do scikit-learn, no mesmo
protocolo, com o mesmo preparo e a mesma conversao. Nao decidem nada: dizem
onde o GAM fica.

**Os resultados de cada algoritmo.** As quatro referencias saem com o mesmo
detalhe do GAM: todas as metricas com o intervalo por celulas
(03_metricas_por_algoritmo.png), SOH estimado contra medido, com as quatro
casas do limiar de 80% (04_previsto_vs_real_por_algoritmo.png), o erro em cada
par de teste (05_erro_por_par.png) e o RUL nos pares que chegam a 80%
(09_rul_teste_por_algoritmo.png). Nada disso escolhe nada; e o que permite
discutir os cinco lado a lado, e nao so o GAM.

**Onde fica cada coisa.** As tabelas vao para saida_nasa/regressao/tabelas/ e
os graficos para saida_nasa/regressao/figuras/, numerados na ordem do artigo:
validacao (01 e 02), teste de todos os algoritmos (03 a 05), o GAM em detalhe
(06 e 07) e o RUL (08 e 09).

Dependencias: numpy, pandas, scipy, scikit-learn, matplotlib
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

try:
    from sklearn.base import BaseEstimator, RegressorMixin
except ImportError:            # checar() avisa e sai antes de qualquer ajuste
    BaseEstimator = RegressorMixin = object

# A raiz do projeto e a pasta acima de src/: e la que ficam
# cleaned_nasa_dataset/ e saida_nasa/.
RAIZ = Path(__file__).resolve().parent.parent
ENTRADA = RAIZ / "saida_nasa" / "normalizado" / "tabelas" / "dados_normalizados.csv"
# So pelo numero do ciclo: a tabela normalizada traz o ciclo escalonado, e os
# ciclos desde o inicio do par, o RUL e o eixo dos graficos precisam dele inteiro.
BRUTA = RAIZ / "saida_nasa" / "preprocessado" / "tabelas" / "dados_modelagem.csv"
# Media e desvio do treino, para desenhar os efeitos do GAM na unidade fisica.
ESCALA = RAIZ / "saida_nasa" / "normalizado" / "tabelas" / "parametros_escala.csv"
SAIDA = RAIZ / "saida_nasa" / "regressao"
FIGURAS, TABELAS = SAIDA / "figuras", SAIDA / "tabelas"

# Paleta categorica validada para daltonismo (modo claro), slots 1..8 em ordem fixa
PAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
       "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e3e2de"
MUTED = "#898781"          # o SOH medido: fundo, para a estimativa aparecer

ALVO = "SOH"
FIM_DE_VIDA = 80.0         # limiar de 80% do artigo, em SOH (%)
CICLOS_INICIO = 5          # a janela da referencia de inicio de vida de normalizar.py
SEGUIDAS = 3               # descargas seguidas abaixo de 80% que confirmam o fim de vida

# Os ciclos desde o inicio do par entram no lugar do ciclo da celula (cycle).
CONTEXTO = ["ambient_temperature", "current_load", "ciclo_par"]
# Protocolo, com poucos valores distintos: entram no GAM como reta, nao como spline.
LINEARES = {"ambient_temperature", "current_load", "current_load_rel"}
CONJUNTOS = ("relativas", "brutas", "todas")
NOME_CONJUNTO = {"relativas": "atributos relativos ao início de vida",
                 "brutas": "atributos brutos", "todas": "todos os atributos"}
# As cores e formas de normalizar.py e classificacao.py: bruto em circulo
# vermelho, relativo em losango azul, completo em quadrado violeta.
COR_CONJUNTO = {"relativas": (PAL[0], "D"), "brutas": (PAL[7], "o"),
                "todas": (PAL[6], "s")}
# No terminal e nos CSV os nomes ficam sem acento, como no resto do projeto; o
# acento volta so nos graficos, que vao para o artigo.
ROTULO_MODELO = {"Regressao linear": "Regressão linear"}
SLUG = {"GAM": "gam", "Regressao linear": "regressao_linear", "SVR (RBF)": "svr",
        "Random Forest": "random_forest", "Gradient Boosting": "gradient_boosting",
        "oraculo": "oraculo"}
# Apelido no terminal, onde a tabela por par tem uma coluna por modelo.
CURTO = {"GAM": "GAM", "Regressao linear": "linear", "SVR (RBF)": "SVR",
         "Random Forest": "RF", "Gradient Boosting": "GB"}
# Rampa sequencial do erro, a mesma de classificacao.py: o laranja que marca os
# erros, do quase-nada ao escuro, com a luminosidade (OKLCH) caindo a cada passo.
SEQ_ERRO = ["#f0efec", "#f7d9c9", "#f4b394", "#ef8c5f", "#eb6834", "#bf4a1b", "#86300c"]
# Nome, unidade e fator de cada atributo nos graficos de efeito; as resistencias
# vao a miliohm, onde as variacoes deixam de ser so casas decimais.
FISICO = {
    "voltage_load_rel": ("tensão na carga", "V", 1.0),
    "voltage_measured_rel": ("tensão medida na bateria", "V", 1.0),
    "temperature_measured_rel": ("temperatura da célula", "°C", 1.0),
    "current_measured_rel": ("corrente medida", "A", 1.0),
    "re_rel": ("resistência eletrolítica Re", "mΩ", 1000.0),
    "rct_rel": ("resistência de transferência Rct", "mΩ", 1000.0),
    "rectified_impedance_rel": ("impedância retificada", "mΩ", 1000.0),
    "current_load_rel": ("corrente na carga, relativa", "A", 1.0),
    "ambient_temperature": ("temperatura ambiente", "°C", 1.0),
    "current_load": ("corrente na carga", "A", 1.0),
    "ciclo_par": ("idade", "ciclos", 1.0),
}

GRADE_LAMBDA = [0.1, 0.3, 1, 3, 10, 30, 100, 300, 1e3, 3e3, 1e4, 3e4, 1e5, 1e6]
N_NOS = 20                 # nos por spline: sobra flexibilidade, a penalidade decide
TOLERANCIA_LAMBDA = 0.02   # fracao do menor RMSE; com 20 celulas, menos que isso e ruido
JANELAS = [10, 20, 30, 50, None]   # tendencia da propria celula; None: todas as estimativas
MEDIAS_POS_HOC = [3, 5, 10]        # media movel antes de converter: so a variante pos-hoc
HORIZONTE = 200            # ciclos, o tamanho do maior par; previsao sem fim a vista conta isso
ALFA_RUL = 0.2             # cone de +-20% em torno do RUL real
FAIXAS_VIDA = [0.0, 0.25, 0.5, 0.75, 1.0]
FOLDS_ALEATORIOS = 5       # particao vazada, so para medir o vazamento
N_BOOT = 2000              # reamostragens de celulas para o intervalo do teste
SEMENTE = 0


def p(msg: str = "") -> None:
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "ascii"
        print(msg.encode(enc, "replace").decode(enc), flush=True)


def virg(v, casas=1):
    """Numero com virgula decimal, como manda a norma brasileira."""
    return f"{v:.{casas}f}".replace(".", ",").replace("-", "−")


def ascii_unidade(u):
    """Unidade para o terminal, que no Windows nem sempre imprime grau e ohm."""
    return u.replace("°C", "C").replace("mΩ", "mohm").replace("Ω", "ohm")


def potencia(v):
    """1000 -> '10³', 3000 -> '3×10³': lambda nos graficos."""
    import math
    e = int(math.floor(math.log10(v) + 1e-9))
    m = v / 10 ** e
    sup = str(e).translate(str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹"))
    return f"10{sup}" if abs(m - 1) < 1e-9 else f"{m:g}×10{sup}".replace(".", ",")


def checar():
    faltando, mods = [], {}
    for nome in ("numpy", "pandas", "scipy", "sklearn"):
        try:
            mods[nome] = __import__(nome)
        except ImportError:
            faltando.append("scikit-learn" if nome == "sklearn" else nome)
    if faltando:
        p("ERRO: faltam dependencias: " + ", ".join(faltando))
        p("    python -m pip install -r requirements.txt")
        sys.exit(1)
    for f, etapa in ((ENTRADA, "normalizar.py"), (BRUTA, "limpeza.py"),
                     (ESCALA, "normalizar.py")):
        if not f.exists():
            p(f"ERRO: {f.relative_to(RAIZ)} nao existe.")
            p(f"    Rode antes: python src/{etapa}")
            sys.exit(1)
    return mods


# ---------------------------------------------------------------------------
# o modelo
# ---------------------------------------------------------------------------
class GAM(BaseEstimator, RegressorMixin):
    """Modelo aditivo generalizado ajustado por P-splines.

        SOH = b0 + soma_j f_j(x_j) + soma_l g_l * z_l

    Cada f_j e uma spline cubica: n_nos + 2 funcoes B-spline com nos igualmente
    espacados entre os quantis de 1% e 99% do treino. Os coeficientes saem de

        min ||y - b0 - B theta||^2 + lam * soma_j ||D2 theta_j||^2,

    com D2 a matriz de segundas diferencas (Eilers e Marx, 1996). Fora da faixa
    1%-99% cada f_j fica no valor da borda. As colunas de `lineares` (indices)
    entram como reta, sem penalidade.
    """

    def __init__(self, lam=1.0, n_nos=N_NOS, lineares=()):
        self.lam = lam
        self.n_nos = n_nos
        self.lineares = lineares

    def _bases(self, X):
        import numpy as np
        partes = [self.splines_[j].transform(X[:, [j]]) for j in self.suaves_]
        partes.append(X[:, self.lineares_])
        return np.hstack(partes)

    def fit(self, X, y):
        import numpy as np
        from sklearn.preprocessing import SplineTransformer
        X, y = np.asarray(X, dtype=float), np.asarray(y, dtype=float)
        self.lineares_ = [j for j in range(X.shape[1]) if j in set(self.lineares)]
        self.suaves_, self.splines_ = [], {}
        for j in range(X.shape[1]):
            if j in self.lineares_:
                continue
            lo, hi = np.percentile(X[:, j], [1, 99])
            if hi <= lo:             # constante no treino: nao ha forma a estimar
                continue
            nos = np.linspace(lo, hi, self.n_nos)[:, None]
            self.splines_[j] = SplineTransformer(
                knots=nos, degree=3, extrapolation="constant").fit(X[:, [j]])
            self.suaves_.append(j)
        B = self._bases(X)
        self.media_ = B.mean(axis=0)
        B = B - self.media_
        nb = self.n_nos + 2
        dif = np.diff(np.eye(nb), 2, axis=0)
        pen = np.zeros((B.shape[1], B.shape[1]))
        for i in range(len(self.suaves_)):
            bloco = slice(i * nb, (i + 1) * nb)
            pen[bloco, bloco] = dif.T @ dif
        btb = B.T @ B
        # Centrar as colunas tira de cada f_j a constante (as B-splines somam 1),
        # e a penalidade nao cobra constante: um empurrao minimo fixa essa
        # direcao sem mexer em previsao nenhuma.
        a = btb + self.lam * pen + 1e-8 * np.trace(btb) / len(btb) * np.eye(len(btb))
        self.intercept_ = float(y.mean())
        self.coef_ = np.linalg.solve(a, B.T @ (y - self.intercept_))
        # Graus de liberdade efetivos: o traco da matriz chapeu, mais a media.
        self.graus_de_liberdade_ = float(np.trace(np.linalg.solve(a, btb))) + 1.0
        return self

    def predict(self, X):
        import numpy as np
        return self.intercept_ + (self._bases(np.asarray(X, dtype=float)) - self.media_) @ self.coef_

    def efeito(self, j, z):
        """f_j em z (escala de entrada do GAM), centrada na media do treino."""
        import numpy as np
        z = np.asarray(z, dtype=float)
        nb = self.n_nos + 2
        if j in self.suaves_:
            i = self.suaves_.index(j)
            bloco = slice(i * nb, (i + 1) * nb)
            return (self.splines_[j].transform(z[:, None]) - self.media_[bloco]) @ self.coef_[bloco]
        if j in self.lineares_:
            k = len(self.suaves_) * nb + self.lineares_.index(j)
            return (z - self.media_[k]) * self.coef_[k]
        return np.zeros(len(z))


def preparo():
    """Imputacao e escala, sempre ajustadas so no treino de cada rodada.

    A tabela ja vem escalonada pelo treino inteiro; reescalar por rodada e o que
    impede a celula deixada de fora de pesar na propria escala. A mediana
    preenche as lacunas, todas de impedancia.
    """
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler())


def gam(lam, colunas):
    from sklearn.pipeline import make_pipeline
    lineares = tuple(i for i, c in enumerate(colunas) if c in LINEARES)
    return make_pipeline(preparo(), GAM(lam=lam, lineares=lineares))


def referencias():
    """As familias dos trabalhos relacionados, com os hiperparametros padrao."""
    from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
    from sklearn.linear_model import LinearRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.svm import SVR
    return {
        "Regressao linear": make_pipeline(preparo(), LinearRegression()),
        "SVR (RBF)": make_pipeline(preparo(), SVR()),
        "Random Forest": make_pipeline(
            preparo(), RandomForestRegressor(random_state=SEMENTE, n_jobs=-1)),
        "Gradient Boosting": make_pipeline(
            preparo(), HistGradientBoostingRegressor(random_state=SEMENTE)),
    }


# ---------------------------------------------------------------------------
# dados
# ---------------------------------------------------------------------------
def carregar(mods):
    """Tabela normalizada com o ciclo de verdade, a idade no par e quem e avaliavel.

    As linhas saem ordenadas por celula, condicao e ciclo: as contas de RUL
    percorrem cada par em ordem cronologica.
    """
    pd = mods["pandas"]
    df = pd.read_csv(ENTRADA)
    if not any(c.endswith("_rel") for c in df.columns):
        p("ERRO: dados_normalizados.csv nao tem as colunas relativas (_rel).")
        p("    Rode antes: python src/normalizar.py   (sem --so-brutas)")
        sys.exit(1)
    ciclo = pd.read_csv(BRUTA, usecols=["battery_id", "test_id", "cycle"])
    df = df.merge(ciclo.rename(columns={"cycle": "ciclo"}),
                  on=["battery_id", "test_id"], how="left", validate="one_to_one")
    chave = ["battery_id", "test_condition"]
    df = df.sort_values(chave + ["ciclo"]).reset_index(drop=True)
    df["ciclo_par"] = df.ciclo - df.groupby(chave).ciclo.transform("min")
    df["soh_inicio"] = df.groupby(chave)[ALVO].transform(
        lambda s: s.head(CICLOS_INICIO).median())
    df["avaliavel"] = df.soh_inicio >= FIM_DE_VIDA
    return df


def conjuntos(df):
    """Os tres conjuntos de atributos, fixados antes de olhar resultado."""
    rel = sorted(c for c in df.columns if c.endswith("_rel"))
    contexto = [c for c in CONTEXTO if c in df.columns]
    brutas = sorted({c[:-4] for c in rel} | set(contexto))
    todos = {"relativas": rel + contexto, "brutas": brutas, "todas": brutas + rel}
    return {n: cols for n, cols in todos.items() if set(cols) <= set(df.columns)}


def condicao(c):
    """'2 A / 24 C' -> '2 A / 24 °C', para os graficos."""
    return c[:-1] + "°C" if c.endswith(" C") else c


# ---------------------------------------------------------------------------
# metricas e protocolo
# ---------------------------------------------------------------------------
def metricas(np, y, pred):
    """RMSE, MAE e vies em p.p. de SOH, e R2 contra a media das descargas avaliadas."""
    e = pred - y
    sst = float(np.sum((y - y.mean()) ** 2))
    return {"rmse": float(np.sqrt(np.mean(e ** 2))), "mae": float(np.mean(np.abs(e))),
            "vies": float(np.mean(e)),
            "r2": 1 - float(np.sum(e ** 2)) / sst if sst > 0 else float("nan"),
            "descargas": len(y)}


def prever_fora(mods, modelo, X, y, grupos, treinar, avaliar):
    """Cada grupo com descarga a avaliar e previsto por um modelo ajustado sem ele.

    So as descargas de `treinar` entram no ajuste. Grupo sem descarga a avaliar
    nao gera rodada: as 5 celulas que so tem pares fora nao tem o que medir.
    """
    np = mods["numpy"]
    from sklearn.base import clone
    pred = np.full(len(y), np.nan)
    for g in np.unique(grupos[avaliar]):
        te = grupos == g
        base = ~te & treinar
        pred[te] = clone(modelo).fit(X[base], y[base]).predict(X[te])
    return pred


def media_fora(mods, y, grupos, treinar, avaliar):
    """O modelo nulo: cada grupo recebe a media do SOH no treino sem ele."""
    np = mods["numpy"]
    pred = np.full(len(y), np.nan)
    for g in np.unique(grupos[avaliar]):
        te = grupos == g
        pred[te] = y[~te & treinar].mean()
    return pred


def particao_aleatoria(mods, n):
    """Folds por descarga: a mesma celula cai dos dois lados."""
    np = mods["numpy"]
    from sklearn.model_selection import KFold
    grupos = np.zeros(n, dtype=int)
    kf = KFold(FOLDS_ALEATORIOS, shuffle=True, random_state=SEMENTE)
    for i, (_, te) in enumerate(kf.split(np.zeros(n))):
        grupos[te] = i
    return grupos


def reamostrar(mods, y, preds, celulas, metrica):
    """Uma metrica de cada modelo em N_BOOT reamostragens de celulas inteiras.

    Descargas seguidas da mesma celula sao quase copias, e reamostra-las uma a
    uma daria um intervalo estreito demais. Todos os modelos passam pelas mesmas
    reamostragens — a semente fixa repete as mesmas para cada metrica —, entao a
    diferenca entre dois deles e medida em pares.
    """
    np = mods["numpy"]
    rng = np.random.default_rng(SEMENTE)
    unicas = np.unique(celulas)
    linhas = {c: np.flatnonzero(celulas == c) for c in unicas}
    amostras = {m: np.empty(N_BOOT) for m in preds}
    for b in range(N_BOOT):
        idx = np.concatenate([linhas[c] for c in rng.choice(unicas, len(unicas))])
        for m, pr in preds.items():
            amostras[m][b] = metrica(y[idx], pr[idx])
    return amostras


def escolher_lambda(serie, tolerancia):
    """O maior lambda (curvas mais suaves) a ate `tolerancia` do menor RMSE."""
    return float(max(lam for lam, v in serie.items() if v <= serie.min() * (1 + tolerancia)))


# ---------------------------------------------------------------------------
# RUL
# ---------------------------------------------------------------------------
def inclinacoes(mods, d):
    """Inclinacao de Theil-Sen do SOH medido contra o ciclo, em cada par avaliavel."""
    pd = mods["pandas"]
    from scipy.stats import theilslopes
    linhas = [{"battery_id": b, "test_condition": c, "descargas": len(g),
               "inclinacao": float(theilslopes(g[ALVO].to_numpy(float),
                                               g.ciclo.to_numpy(float))[0])}
              for (b, c), g in d[d.avaliavel].groupby(["battery_id", "test_condition"])]
    return pd.DataFrame(linhas)


def taxas(incl, excluir=None):
    """Perda de SOH por ciclo de cada condicao: a mediana das inclinacoes dos pares.

    `excluir` tira uma celula da conta: na validacao, a taxa que converte a
    celula deixada de fora nao pode ter sido medida nela.
    """
    sub = incl if excluir is None else incl[incl.battery_id != excluir]
    return sub.groupby("test_condition").inclinacao.median()


def fins_de_vida(mods, d):
    """Ciclo do fim de vida de cada par avaliavel; NaN quando nao chega (censurado)."""
    np, pd = mods["numpy"], mods["pandas"]
    linhas = []
    for (b, c), g in d[d.avaliavel].groupby(["battery_id", "test_condition"]):
        s, ci = g[ALVO].to_numpy(float), g.ciclo.to_numpy(float)
        abaixo = s < FIM_DE_VIDA
        fim = next((ci[i] for i in range(len(s) - SEGUIDAS + 1)
                    if abaixo[i:i + SEGUIDAS].all()), np.nan)
        linhas.append({"battery_id": b, "test_condition": c, "descargas": len(g),
                       "ciclo_inicial": ci[0], "ultimo_ciclo": ci[-1], "fim_de_vida": fim})
    return pd.DataFrame(linhas)


def media_movel(np, x, janela):
    """Media das ultimas `janela` posicoes ate cada uma; no comeco, das que houver."""
    soma = np.cumsum(np.insert(np.asarray(x, dtype=float), 0, 0.0))
    i = np.arange(1, len(x) + 1)
    lo = np.maximum(i - janela, 0)
    return (soma[i] - soma[lo]) / (i - lo)


def rul_condicao(np, soh, taxa, ciclos=None, media=1):
    """RUL = (SOH - 80) / perda por ciclo. Sem perda (taxa >= 0), infinito.

    Com media > 1 (so a variante pos-hoc), entra a media das ultimas `media`
    estimativas, e o RUL e descontado do atraso dela: a media mede o SOH no
    ciclo medio da janela, nao no atual.
    """
    if np.isnan(taxa):
        return np.full(len(soh), np.nan)
    if taxa >= 0:
        return np.full(len(soh), np.inf)
    if media > 1:
        s, c = media_movel(np, soh, media), media_movel(np, ciclos, media)
        return np.maximum(np.maximum(s - FIM_DE_VIDA, 0.0) / -taxa - (ciclos - c), 0.0)
    return np.maximum(soh - FIM_DE_VIDA, 0.0) / -taxa


def rul_tendencia(np, ciclos, soh, janela):
    """Reta nas ultimas `janela` estimativas da propria celula, prolongada ate 80%."""
    out = np.full(len(soh), np.nan)
    for i in range(1, len(soh)):
        lo = 0 if janela is None else max(0, i - janela + 1)
        b, a = np.polyfit(ciclos[lo:i + 1], soh[lo:i + 1], 1)
        out[i] = max((FIM_DE_VIDA - a) / b - ciclos[i], 0.0) if b < 0 else np.inf
    return out


def nome_conversao(conv):
    tipo, janela = conv
    if tipo == "condicao":
        return f"taxa da condicao, media de {janela}" if janela and janela > 1 else "taxa da condicao"
    return f"tendencia da celula, W = {janela}" if janela else "tendencia da celula, todas"


def instantes(mods, d, fins, estimativas, taxa_de, conv):
    """Uma linha por descarga avaliada e por fonte de SOH.

    Avaliada: da 5a descarga do par em diante e, se o par chega a 80%, antes do
    fim de vida. `estimativas` sao vetores alinhados a `d`; `taxa_de(celula,
    condicao)` da a perda por ciclo usada na conversao pela condicao.
    """
    np, pd = mods["numpy"], mods["pandas"]
    tipo, janela = conv
    linhas = []
    for r in fins.itertuples(index=False):
        g = d[(d.battery_id == r.battery_id) & (d.test_condition == r.test_condition)]
        idx, ci, real = g.index.to_numpy(), g.ciclo.to_numpy(float), g[ALVO].to_numpy(float)
        censurado = bool(np.isnan(r.fim_de_vida))
        sel = np.arange(len(ci)) >= CICLOS_INICIO - 1
        if not censurado:
            sel &= ci < r.fim_de_vida
        if not sel.any():
            continue
        taxa = taxa_de(r.battery_id, r.test_condition) if tipo == "condicao" else np.nan
        vida = np.nan if censurado else r.fim_de_vida - r.ciclo_inicial
        for fonte, soh in estimativas.items():
            s = soh[idx]
            prev = (rul_condicao(np, s, taxa, ci, janela or 1) if tipo == "condicao"
                    else rul_tendencia(np, ci, s, janela))
            prev = np.minimum(prev, HORIZONTE)
            for i in np.flatnonzero(sel):
                linhas.append({
                    "fonte": fonte, "conversao": nome_conversao(conv),
                    "battery_id": r.battery_id, "test_condition": r.test_condition,
                    "ciclo": ci[i], "censurado": censurado, "fim_de_vida": r.fim_de_vida,
                    "ultimo_ciclo": r.ultimo_ciclo, "taxa": taxa,
                    "soh_real": real[i], "soh_estimado": s[i],
                    "fracao_vida": (ci[i] - r.ciclo_inicial) / vida if not censurado else np.nan,
                    "rul_real": r.fim_de_vida - ci[i] if not censurado else np.nan,
                    "rul_previsto": prev[i]})
    return pd.DataFrame(linhas)


def resumir_rul(mods, inst):
    """Por fonte e conversao: o erro nos pares com fim de vida e o alarme nos censurados."""
    np, pd = mods["numpy"], mods["pandas"]
    linhas = []
    for (fonte, conv), g in inst.groupby(["fonte", "conversao"], sort=False):
        f = g[~g.censurado & g.rul_previsto.notna()]
        c = g[g.censurado & g.rul_previsto.notna()]
        erro = f.rul_previsto - f.rul_real
        lin = {"fonte": fonte, "conversao": conv, "instantes": len(f),
               "pares": f.groupby(["battery_id", "test_condition"]).ngroups,
               "mae_ciclos": erro.abs().mean(), "mediana_erro_abs": erro.abs().median(),
               "vies_ciclos": erro.mean(),
               "dentro_20pc": (erro.abs() <= ALFA_RUL * f.rul_real).mean()}
        faixa = pd.cut(f.fracao_vida, FAIXAS_VIDA, include_lowest=True)
        por_faixa = erro.abs().groupby(faixa, observed=False).mean().to_numpy()
        for lo, hi, v in zip(FAIXAS_VIDA[:-1], FAIXAS_VIDA[1:], por_faixa):
            lin[f"mae_vida_{100 * lo:.0f}_{100 * hi:.0f}"] = v
        lin["instantes_censurados"] = len(c)
        lin["alarme_antecipado"] = ((c.ciclo + c.rul_previsto < c.ultimo_ciclo).mean()
                                    if len(c) else np.nan)
        linhas.append(lin)
    return pd.DataFrame(linhas)


def rul_por_par(mods, inst):
    """Erro de RUL por par com fim de vida, com o vies do SOH que o explica."""
    f = inst[~inst.censurado & inst.rul_previsto.notna()].copy()
    f["erro"] = f.rul_previsto - f.rul_real
    f["erro_soh"] = f.soh_estimado - f.soh_real
    f["dentro"] = f.erro.abs() <= ALFA_RUL * f.rul_real
    f["abs"] = f.erro.abs()
    por = (f.groupby(["fonte", "battery_id", "test_condition"], sort=False)
           .agg(instantes=("erro", "size"), fim_de_vida=("fim_de_vida", "first"),
                taxa=("taxa", "first"), vies_soh=("erro_soh", "mean"),
                mae_ciclos=("abs", "mean"), vies_ciclos=("erro", "mean"),
                dentro_20pc=("dentro", "mean"))
           .reset_index())
    # Pela taxa da condicao o erro do RUL e o do oraculo mais erro_soh / perda
    # por ciclo, enquanto nada e cortado em 0 ou no horizonte.
    por["vies_soh_em_ciclos"] = por.vies_soh / -por.taxa
    return por


# ---------------------------------------------------------------------------
# as etapas
# ---------------------------------------------------------------------------
def etapa_lambda(mods, tr, conj, tolerancia, lam_forcado):
    """RMSE contra lambda em cada conjunto, e o lambda de cada um."""
    np, pd = mods["numpy"], mods["pandas"]
    y, cel, ok = tr[ALVO].to_numpy(float), tr.battery_id.to_numpy(), tr.avaliavel.to_numpy()
    curvas = dict(conj)
    # O ciclo da celula, como na classificacao, so para medir a troca.
    if "relativas" in conj and "cycle" in tr.columns:
        curvas["relativas_ciclo_da_celula"] = [
            "cycle" if c == "ciclo_par" else c for c in conj["relativas"]]
    tab = {}
    for n, cols in curvas.items():
        X = tr[cols].to_numpy(float)
        tab[n] = [metricas(np, y[ok], prever_fora(mods, gam(lam, cols), X, y, cel, ok, ok)[ok])["rmse"]
                  for lam in GRADE_LAMBDA]
    tab = pd.DataFrame(tab, index=pd.Index(GRADE_LAMBDA, name="lambda"))
    lam_conj = {n: escolher_lambda(tab[n], tolerancia) for n in conj}

    p(f"  {'lambda':>8} " + " ".join(f"{n[:12]:>12}" for n in tab.columns))
    for lam, r in tab.iterrows():
        marca = " *" if lam == lam_conj["relativas"] else ""
        p(f"  {lam:>8g} " + " ".join(f"{v:>12.3f}" for v in r) + marca)
    melhor = tab.relativas
    p(f"  * lambda={lam_conj['relativas']:g}: o maior a ate {100 * tolerancia:.0f}% do menor "
      f"RMSE dos relativos ({melhor.min():.3f} em lambda={melhor.idxmin():g})")
    outros = {n: v for n, v in lam_conj.items() if n != "relativas"}
    if outros:
        p("  mesma regra nos outros conjuntos: "
          + ", ".join(f"{n} lambda={v:g}" for n, v in outros.items()))
    if "relativas_ciclo_da_celula" in tab:
        lam = lam_conj["relativas"]
        p(f"  com o ciclo da celula no lugar da idade no par, no mesmo lambda: RMSE "
          f"{tab.relativas_ciclo_da_celula[lam]:.3f} contra {tab.relativas[lam]:.3f}")
    if lam_forcado:
        p(f"  --lam {lam_forcado:g} sobrepoe a escolha, nos tres conjuntos")
        lam_conj = {n: float(lam_forcado) for n in lam_conj}
    return tab, lam_conj


def etapa_comparacao(mods, tr, conj, lam_conj, refs):
    """Protocolo, rotulos, atributos e algoritmo, so nas celulas de treino."""
    np, pd = mods["numpy"], mods["pandas"]
    y, cel, ok = tr[ALVO].to_numpy(float), tr.battery_id.to_numpy(), tr.avaliavel.to_numpy()
    tudo = np.ones(len(y), dtype=bool)
    aleat = particao_aleatoria(mods, len(y))
    modelos = {"GAM": None, **refs}
    linhas, previsoes = [], {}
    for nome, modelo in modelos.items():
        t0 = time.time()
        for n, cols in conj.items():
            m = gam(lam_conj[n], cols) if modelo is None else modelo
            X = tr[cols].to_numpy(float)
            esquemas = [("uma celula de fora", "pares avaliaveis", cel, ok)]
            if n == "relativas":
                esquemas += [("aleatoria por descarga", "pares avaliaveis", aleat, ok),
                             ("uma celula de fora", "todos os pares", cel, tudo)]
            for validacao, rotulos, grupos, treinar in esquemas:
                pred = prever_fora(mods, m, X, y, grupos, treinar, ok)
                if n == "relativas" and grupos is cel and treinar is ok:
                    previsoes[nome] = pred
                met = metricas(np, y[ok], pred[ok])
                # O lambda vai na coluna propria: cada conjunto tem o seu.
                linhas.append({"modelo": nome, "atributos": n, "validacao": validacao,
                               "rotulos_no_treino": rotulos,
                               "lambda": lam_conj[n] if modelo is None else None,
                               **{k: met[k] for k in ("rmse", "mae", "vies", "r2")}})
        p(f"  {nome:<22} {time.time() - t0:>5.0f}s")
    comp = pd.DataFrame(linhas)
    nulo = metricas(np, y[ok], media_fora(mods, y, cel, ok, ok)[ok])["rmse"]

    base = comp[(comp.validacao == "uma celula de fora")
                & (comp.rotulos_no_treino == "pares avaliaveis")]
    piv = base.pivot(index="modelo", columns="atributos", values="rmse")
    piv["aleatoria"] = comp[comp.validacao == "aleatoria por descarga"].set_index("modelo").rmse
    piv["todos_os_pares"] = comp[comp.rotulos_no_treino == "todos os pares"].set_index(
        "modelo").rmse
    piv = piv.loc[list(modelos)]
    cols = [c for c in CONJUNTOS if c in piv.columns]
    p("")
    p(f"  {'RMSE (p.p.)':<22} " + " ".join(f"{c:>10}" for c in cols)
      + f" {'aleatoria':>10} {'todos pares':>12}")
    for nome, r in piv.iterrows():
        p(f"  {nome:<22} " + " ".join(f"{r[c]:>10.3f}" for c in cols)
          + f" {r.aleatoria:>10.3f} {r.todos_os_pares:>12.3f}")
    p("  colunas de atributos: uma celula de fora por vez, so pares avaliaveis no treino;")
    p("  aleatoria: mesmos atributos relativos, particao por descarga (vazada);")
    p("  todos pares: relativos, com os 7 pares de SOH artificial no treino")
    p(f"  modelo nulo (media do SOH no treino de cada rodada): RMSE {nulo:.3f}")

    piv_r2 = base.pivot(index="modelo", columns="atributos", values="r2").loc[list(modelos)]
    p("")
    p(f"  {'R2':<22} " + " ".join(f"{c:>10}" for c in cols))
    for nome, r in piv_r2.iterrows():
        p(f"  {nome:<22} " + " ".join(f"{r[c]:>10.3f}" for c in cols))

    # Erro por par na validacao: onde cada modelo erra, e quanto.
    pares = tr.loc[ok, ["battery_id", "test_condition"]]
    por_par = []
    for nome, pred in previsoes.items():
        e = pd.Series(pred[ok] - y[ok], index=pares.index)
        g = pd.concat([pares, e.rename("erro"), tr.loc[ok, ALVO]], axis=1).groupby(
            ["battery_id", "test_condition"])
        t = g.agg(descargas=("erro", "size"), soh_medio=(ALVO, "mean"),
                  vies=("erro", "mean")).reset_index()
        t["rmse"] = g.erro.apply(lambda s: float(np.sqrt(np.mean(s ** 2)))).to_numpy()
        t.insert(0, "modelo", nome)
        por_par.append(t)
    por_par = pd.concat(por_par, ignore_index=True)
    p("")
    p("  pior par de cada modelo, com os atributos relativos:")
    for nome in modelos:
        t = por_par[por_par.modelo == nome]
        r = t.loc[t.rmse.idxmax()]
        p(f"    {nome:<22} {r.battery_id} {r.test_condition:<11} RMSE {r.rmse:6.1f}, "
          f"vies {r.vies:+6.1f}  (mediana entre pares: {t.rmse.median():.2f})")
    return comp, piv, por_par, previsoes, nulo


def etapa_teste(mods, tr, te, conj, lam, refs):
    """Ajuste nas celulas de treino, uma avaliacao nas 8 de teste."""
    np, pd = mods["numpy"], mods["pandas"]
    from sklearn.base import clone
    cols = conj["relativas"]
    ok_tr, ok_te = tr.avaliavel.to_numpy(), te.avaliavel.to_numpy()
    Xtr, Xte = tr.loc[ok_tr, cols].to_numpy(float), te[cols].to_numpy(float)
    y_tr = tr.loc[ok_tr, ALVO].to_numpy(float)

    final = gam(lam, cols).fit(Xtr, y_tr)
    preds = {"GAM": final.predict(Xte)}
    for nome, modelo in refs.items():
        preds[nome] = clone(modelo).fit(Xtr, y_tr).predict(Xte)

    y = te.loc[ok_te, ALVO].to_numpy(float)
    cel = te.loc[ok_te, "battery_id"].to_numpy()
    av = {m: pr[ok_te] for m, pr in preds.items()}
    # O modelo nulo, que preve para toda descarga a media do SOH do treino.
    nulo = metricas(np, y, np.full(len(y), y_tr.mean()))
    am = {k: reamostrar(mods, y, av, cel, lambda yy, pp, k=k: metricas(np, yy, pp)[k])
          for k in ("rmse", "mae", "r2", "vies")}
    # Bonferroni: com uma comparacao por referencia, cada intervalo pareado
    # precisa de 95% divididos entre elas para o conjunto manter os 95%.
    alfa = 0.05 / max(len(refs), 1)
    rmse_gam = metricas(np, y, av["GAM"])["rmse"]
    linhas = []
    for nome, pr in av.items():
        met = metricas(np, y, pr)
        lin = {"modelo": nome, **met}
        for k in ("rmse", "mae", "r2", "vies"):
            lin[f"{k}_ic95_inferior"], lin[f"{k}_ic95_superior"] = np.percentile(
                am[k][nome], [2.5, 97.5])
        # O limiar de 80% sobre o SOH estimado vira uma classificacao: as quatro
        # casas da matriz de confusao, que 04_previsto_vs_real_por_algoritmo.png
        # mostra como quadrantes.
        real, est = y < FIM_DE_VIDA, pr < FIM_DE_VIDA
        lin.update({"fim_de_vida_detectado": int((real & est).sum()),
                    "fim_de_vida_nao_percebido": int((real & ~est).sum()),
                    "alarme_falso": int((~real & est).sum()),
                    "saudavel_reconhecida": int((~real & ~est).sum())})
        if nome != "GAM":
            # Positiva: a referencia erra mais que o GAM.
            dif = am["rmse"][nome] - am["rmse"]["GAM"]
            lin["diferenca_rmse_para_gam"] = met["rmse"] - rmse_gam
            lin["dif_ic95_inferior"], lin["dif_ic95_superior"] = np.percentile(dif, [2.5, 97.5])
            lin["dif_bonferroni_inferior"], lin["dif_bonferroni_superior"] = np.percentile(
                dif, [100 * alfa / 2, 100 * (1 - alfa / 2)])
        linhas.append(lin)
    res = pd.DataFrame(linhas)

    p(f"  {len(y)} descargas avaliaveis de {len(np.unique(cel))} celulas; fora: "
      + ", ".join(f"{b} {c}" for b, c in
                  te.loc[~ok_te, ["battery_id", "test_condition"]].drop_duplicates().to_numpy()))
    p(f"  {'':<22} {'RMSE':>6} {'IC 95% (celulas)':>17} {'MAE':>6} {'R2':>7} "
      f"{'IC 95% (celulas)':>17} {'vies':>6}")
    for r in res.itertuples(index=False):
        p(f"  {r.modelo:<22} {r.rmse:>6.2f}   [{r.rmse_ic95_inferior:5.2f}, "
          f"{r.rmse_ic95_superior:5.2f}] {r.mae:>6.2f} {r.r2:>7.3f}   [{r.r2_ic95_inferior:5.2f}, "
          f"{r.r2_ic95_superior:5.2f}] {r.vies:>+6.2f}")
    p(f"  modelo nulo (media do SOH no treino): RMSE {nulo['rmse']:.2f}")
    p("")
    p(f"  o SOH estimado cortado em {FIM_DE_VIDA:.0f}%, como classificacao de fim de vida:")
    p(f"  {'':<22} {'detectado':>10} {'nao percebido':>14} {'alarme falso':>13} "
      f"{'saudavel':>9}")
    for r in res.itertuples(index=False):
        p(f"  {r.modelo:<22} {r.fim_de_vida_detectado:>10} {r.fim_de_vida_nao_percebido:>14} "
          f"{r.alarme_falso:>13} {r.saudavel_reconhecida:>9}")
    if refs:
        p("")
        p("  diferenca de RMSE para o GAM (referencia - GAM; positiva: o GAM erra menos),")
        p("  pareada nas mesmas reamostragens de celulas:")
        for r in res.iloc[1:].itertuples(index=False):
            exclui = "exclui" if r.dif_ic95_inferior > 0 or r.dif_ic95_superior < 0 else "inclui"
            bonf = ("exclui" if r.dif_bonferroni_inferior > 0 or r.dif_bonferroni_superior < 0
                    else "inclui")
            p(f"    {r.modelo:<22} {r.diferenca_rmse_para_gam:>+6.2f} p.p.  IC 95% "
              f"[{r.dif_ic95_inferior:+.2f}, {r.dif_ic95_superior:+.2f}] {exclui} o zero; "
              f"com Bonferroni [{r.dif_bonferroni_inferior:+.2f}, "
              f"{r.dif_bonferroni_superior:+.2f}] {bonf}")

    prev = te[["battery_id", "test_condition", "ciclo", "ciclo_par", ALVO, "avaliavel"]].copy()
    for nome, pr in preds.items():
        prev[f"soh_{SLUG[nome]}"] = pr
    por = []
    for nome, pr in preds.items():
        t = prev.assign(erro=pr - prev[ALVO]).groupby(
            ["battery_id", "test_condition"], sort=False)
        a = t.agg(avaliavel=("avaliavel", "first"), descargas=("erro", "size"),
                  soh_medio=(ALVO, "mean"), vies=("erro", "mean")).reset_index()
        a["rmse"] = t.erro.apply(lambda s: float(np.sqrt(np.mean(s ** 2)))).to_numpy()
        a.insert(0, "modelo", nome)
        por.append(a)
    por = pd.concat(por, ignore_index=True)
    p("")
    p(f"  por par, GAM (lambda = {lam:g}):")
    for r in por[por.modelo == "GAM"].itertuples(index=False):
        fora = "" if r.avaliavel else "   (fora das metricas: SOH comeca abaixo de 80%)"
        p(f"    {r.battery_id} {r.test_condition:<11} {r.descargas:>4} descargas, SOH medio "
          f"{r.soh_medio:5.1f}%, RMSE {r.rmse:5.2f}, vies {r.vies:+6.2f}{fora}")
    if refs:
        tab = por.pivot(index=["battery_id", "test_condition"], columns="modelo",
                        values="rmse")[list(preds)]
        aval = por[por.modelo == "GAM"].set_index(["battery_id", "test_condition"]).avaliavel
        p("")
        p("  RMSE por par, todos os algoritmos:")
        p(f"    {'':<17} " + " ".join(f"{CURTO[n]:>7}" for n in tab.columns))
        for (b, c), r in tab.iterrows():
            fora = "" if aval[(b, c)] else "   (fora das metricas)"
            p(f"    {b} {c:<11} " + " ".join(f"{v:>7.2f}" for v in r) + fora)
    return res, prev, por, preds, final, nulo


def etapa_rul(mods, tr, te, previsoes_val, preds_te):
    """Conversao do SOH em RUL: escolhida na validacao, aplicada uma vez ao teste."""
    np, pd = mods["numpy"], mods["pandas"]
    incl = inclinacoes(mods, tr)
    tx = taxas(incl)
    fins_tr, fins_te = fins_de_vida(mods, tr), fins_de_vida(mods, te)
    n_pares = incl.groupby("test_condition").size()
    p("  perda de SOH por ciclo de cada condicao (mediana de Theil-Sen nos pares de treino):")
    for c, v in tx.sort_values().items():
        p(f"    {c:<11} {v:+.3f} p.p./ciclo  ({n_pares[c]} par(es))")
    for nome, f in (("treino", fins_tr), ("teste", fins_te)):
        com = f[f.fim_de_vida.notna()]
        p(f"  {nome}: {len(com)} dos {len(f)} pares avaliaveis chegam a 80% ("
          + ", ".join(f"{r.battery_id} ciclo {r.fim_de_vida:.0f}" for r in com.itertuples())
          + "); os demais sao censurados")

    # Validacao: estimativas fora da celula e taxa medida sem ela.
    est_val = {"oraculo": tr[ALVO].to_numpy(float), **previsoes_val}
    taxa_val = lambda b, c: float(taxas(incl, excluir=b).get(c, np.nan))
    conversoes = [("condicao", None)] + [("tendencia", w) for w in JANELAS]
    inst_val = pd.concat([instantes(mods, tr, fins_tr, est_val, taxa_val, cv)
                          for cv in conversoes], ignore_index=True)
    # Todas as conversoes nos mesmos instantes: onde a taxa da condicao existe.
    chave = ["battery_id", "test_condition", "ciclo"]
    com_taxa = inst_val[(inst_val.conversao == nome_conversao(conversoes[0]))
                        & (inst_val.fonte == "oraculo")
                        & inst_val.rul_previsto.notna()][chave]
    comum = inst_val.merge(com_taxa, on=chave)
    conv_val = resumir_rul(mods, comum)
    mae = conv_val.pivot(index="conversao", columns="fonte", values="mae_ciclos")
    mae = mae.loc[[nome_conversao(c) for c in conversoes], list(est_val)]
    escolhida = next(c for c in conversoes if nome_conversao(c) == mae["GAM"].idxmin())
    f = comum[(comum.fonte == "oraculo") & (comum.conversao == nome_conversao(escolhida))]
    p("")
    p(f"  validacao: as conversoes nos mesmos {int((~f.censurado).sum())} instantes de "
      f"{f[~f.censurado].groupby(['battery_id', 'test_condition']).ngroups} pares com fim de vida")
    p(f"  (MAE em ciclos; censurados ficam para o alarme antecipado)")
    p(f"  {'':<30} " + " ".join(f"{SLUG[c][:10]:>10}" for c in mae.columns))
    for conv, r in mae.iterrows():
        marca = " *" if conv == nome_conversao(escolhida) else ""
        p(f"  {conv:<30} " + " ".join(f"{v:>10.1f}" for v in r) + marca)
    p(f"  * a de menor MAE com o GAM: {nome_conversao(escolhida)}")

    # Variante pos-hoc, so na validacao: media movel das estimativas antes de
    # converter. A ideia veio da estimativa serrilhada de B0054 no teste, entao o
    # teste nao pode julga-la.
    base = inst_val[inst_val.conversao == nome_conversao(("condicao", None))]
    var = resumir_rul(mods, pd.concat(
        [base] + [instantes(mods, tr, fins_tr, est_val, taxa_val, ("condicao", m))
                  for m in MEDIAS_POS_HOC], ignore_index=True))
    p("")
    p("  variante pos-hoc, so validacao: media das ultimas M estimativas antes de converter")
    p(f"  {'MAE (ciclos)':<30} " + " ".join(f"{SLUG[c][:10]:>10}" for c in est_val)
      + f" {'alarme GAM':>11}")
    for r in var[var.fonte == "GAM"].itertuples(index=False):
        linha = var[var.conversao == r.conversao].set_index("fonte").mae_ciclos
        p(f"  {r.conversao:<30} " + " ".join(f"{linha[c]:>10.1f}" for c in est_val)
          + f" {r.alarme_antecipado:>11.0%}")

    # Teste: taxa de todos os pares de treino, modelos ajustados no treino.
    est_te = {"oraculo": te[ALVO].to_numpy(float), **preds_te}
    taxa_te = lambda b, c: float(tx.get(c, np.nan))
    inst_te = instantes(mods, te, fins_te, est_te, taxa_te, escolhida)
    resumo = pd.concat([
        resumir_rul(mods, inst_val[inst_val.conversao == nome_conversao(escolhida)]).assign(
            conjunto="validacao"),
        resumir_rul(mods, inst_te).assign(conjunto="teste")], ignore_index=True)
    por_par = rul_por_par(mods, inst_te)

    p("")
    p(f"  teste, {nome_conversao(escolhida)}:")
    rt = resumo[resumo.conjunto == "teste"]
    faixas = [c for c in rt.columns if c.startswith("mae_vida_")]
    p(f"  {'':<22} {'MAE':>6} {'vies':>7} {'+-20%':>6} | MAE por fracao da vida: "
      + " ".join(f"{c[9:]:>7}" for c in faixas) + f" | {'alarme':>6}")
    for r in rt.itertuples(index=False):
        p(f"  {r.fonte:<22} {r.mae_ciclos:>6.1f} {r.vies_ciclos:>+7.1f} {r.dentro_20pc:>6.0%} | "
          + " " * 24 + " ".join(f"{getattr(r, c):>7.1f}" for c in faixas)
          + f" | {r.alarme_antecipado:>6.0%}")
    p(f"  MAE e vies em ciclos, nos {int(rt.instantes.iloc[0])} instantes de "
      f"{int(rt.pares.iloc[0])} pares com fim de vida; alarme: fracao dos "
      f"{int(rt.instantes_censurados.iloc[0])} instantes")
    p("  de pares censurados em que a previsao poe o fim de vida antes do fim da observacao")
    p("")
    p("  por par: vies do RUL do GAM, do oraculo e do SOH do GAM convertido em ciclos;")
    p("  sem os cortes em zero, o primeiro seria a soma dos outros dois")
    ora = por_par[por_par.fonte == "oraculo"].set_index(["battery_id", "test_condition"])
    for r in por_par[por_par.fonte == "GAM"].itertuples(index=False):
        o = ora.loc[(r.battery_id, r.test_condition)]
        p(f"    {r.battery_id} {r.test_condition:<11} fim no ciclo {r.fim_de_vida:>4.0f}: "
          f"GAM {r.vies_ciclos:+6.1f} | oraculo {o.vies_ciclos:+6.1f} | SOH {r.vies_soh:+5.2f} "
          f"p.p. / {-r.taxa:.3f} = {r.vies_soh_em_ciclos:+6.1f}; MAE GAM {r.mae_ciclos:5.1f}, "
          f"oraculo {o.mae_ciclos:5.1f} ciclos")
    return {"inclinacoes": incl, "taxas": tx, "fins": pd.concat(
                [fins_tr.assign(split="treino"), fins_te.assign(split="teste")], ignore_index=True),
            "conversoes": conv_val, "escolhida": escolhida, "variante": var, "resumo": resumo,
            "instantes_teste": inst_te, "por_par": por_par}


def efeitos_gam(mods, final, cols, tr):
    """f_j de cada atributo na unidade fisica dele, com o efeito tipico no treino.

    A grade percorre a faixa 1%-99% do treino na escala de entrada do pipeline
    (com os outros atributos na mediana: num modelo aditivo eles nao mudam a
    forma de f_j), passa pelo mesmo preparo e volta a unidade fisica pela media
    e desvio de normalizar.py. O efeito tipico e a distancia entre os quantis
    de 5% e 95% de f_j nas descargas de treino: quanto o atributo move o SOH
    nas descargas que de fato acontecem.
    """
    np, pd = mods["numpy"], mods["pandas"]
    escala = pd.read_csv(ESCALA)
    escala = escala[escala.conjunto == "treino_completo"].set_index("coluna")
    Xtr = tr.loc[tr.avaliavel, cols].to_numpy(float)
    prep, modelo = final[:-1], final[-1]
    Ztr = prep.transform(Xtr)
    curvas, resumo = [], []
    for j, c in enumerate(cols):
        m, s = ((escala.loc[c, "media"], escala.loc[c, "desvio"]) if c in escala.index
                else (0.0, 1.0))
        fator = FISICO.get(c, (c, "", 1.0))[2]
        fisico = lambda v: (v * s + m) * fator
        grade = np.linspace(*np.nanpercentile(Xtr[:, j], [1, 99]), 101)
        M = np.tile(np.nanmedian(Xtr, axis=0), (len(grade), 1))
        M[:, j] = grade
        f = modelo.efeito(j, prep.transform(M)[:, j])
        f_tr = modelo.efeito(j, Ztr[:, j])
        tipo = "spline" if j in modelo.suaves_ else ("reta" if j in modelo.lineares_ else "fora")
        curvas.append(pd.DataFrame({"coluna": c, "x_fisico": fisico(grade), "efeito_pp": f}))
        lo, hi = np.percentile(f_tr, [5, 95])
        xs = fisico(grade)
        inclinacao = float((f[-1] - f[0]) / (xs[-1] - xs[0])) if tipo == "reta" else np.nan
        resumo.append({"coluna": c, "termo": tipo, "efeito_tipico_pp": hi - lo,
                       "efeito_min_pp": f.min(), "efeito_max_pp": f.max(),
                       "pp_por_unidade": inclinacao, "unidade": FISICO.get(c, (c, "", 1))[1]})
    resumo = pd.DataFrame(resumo).sort_values("efeito_tipico_pp", ascending=False)
    rug = {c: (Xtr[:, j] * escala.loc[c, "desvio"] + escala.loc[c, "media"]
               if c in escala.index else Xtr[:, j]) * FISICO.get(c, (c, "", 1.0))[2]
           for j, c in enumerate(cols)}
    return pd.concat(curvas, ignore_index=True), resumo, rug


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


def fig_escolha_lambda(mods, plt, tab, lam, tolerancia):
    from matplotlib.patches import Patch
    from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator
    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    melhor = tab.relativas.min()
    ax.axhspan(melhor, melhor * (1 + tolerancia), color=PAL[0], alpha=0.12, linewidth=0,
               zorder=0)
    if "relativas_ciclo_da_celula" in tab:
        ax.plot(tab.index, tab.relativas_ciclo_da_celula, color=MUTED, linestyle="--",
                linewidth=1.5, marker="D", markersize=5, markerfacecolor=SURF,
                markeredgecolor=MUTED, zorder=1,
                label="relativos, com o ciclo da célula no lugar da idade no par")
    for n in [c for c in ("brutas", "todas", "relativas") if c in tab.columns]:
        cor, mk = COR_CONJUNTO[n]
        ax.plot(tab.index, tab[n], color=cor, marker=mk, markersize=6.5,
                markeredgecolor=SURF, markeredgewidth=1.4, zorder=3 if n == "relativas" else 2,
                label=NOME_CONJUNTO[n])
    ax.axvline(lam, color=INK2, linestyle="--", linewidth=1.2, zorder=1)
    ax.set_xscale("log")
    ax.xaxis.set_major_locator(FixedLocator([0.1, 1, 10, 100, 1e3, 1e4, 1e5, 1e6]))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: potencia(v)))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.set_xlabel("λ, peso da penalidade de curvatura (escala log)")
    ax.set_ylabel("RMSE do SOH (p.p.)")
    topo = ax.get_ylim()[1]
    ax.text(lam * 1.15, topo, f"λ = {potencia(lam)}", fontsize=10, color=INK, va="top",
            ha="left")
    alcas, _ = ax.get_legend_handles_labels()
    alcas.append(Patch(color=PAL[0], alpha=0.12, linewidth=0,
                       label=f"até {virg(100 * tolerancia, 0)}% acima do menor RMSE dos relativos"))
    # Alca longa: com a curta, linha cheia e tracejada se confundem na legenda.
    ax.legend(handles=alcas, fontsize=9, loc="lower center", bbox_to_anchor=(0.5, 1.0),
              ncol=2, borderaxespad=0.4, handlelength=3.4)
    sub = ("Validação nas 20 células de treino, deixando uma de fora por vez. À esquerda, "
           "cada função do GAM segue o ruído; à direita, vira reta. A faixa sombreada vai do "
           f"menor RMSE com os atributos relativos até {virg(100 * tolerancia, 0)}% acima "
           f"dele, e vence o maior λ dentro dela, o de curvas mais suaves: λ = {potencia(lam)}.")
    titulo_figura(plt, fig, "Quanto suavizar", sub)
    salvar(plt, fig, "01_escolha_de_lambda.png")


def fig_hierarquia(mods, plt, piv, nulo, lam):
    np = mods["numpy"]
    refs = [m for m in piv.sort_values("relativas").index if m != "GAM"]
    piv = piv.loc[["GAM"] + refs]
    n = len(piv)
    cols = [c for c in CONJUNTOS if c in piv.columns]
    todas = cols + ["aleatoria", "todos_os_pares"]
    # Valores muito altos (a regressao linear que extrapola) iriam esmagar o
    # resto: o eixo para num teto e eles ganham seta e numero.
    teto = 1.6 * nulo
    corta = lambda v: np.minimum(np.asarray(v, dtype=float), teto)
    fig, ax = plt.subplots(figsize=(10, 0.66 * n + 3.4))
    ys = np.arange(n)[::-1]
    for y, (_, r) in zip(ys, piv.iterrows()):
        v = r[todas].astype(float)
        ax.plot(corta([v.min(), v.max()]), [y, y], color=GRID, linewidth=3,
                solid_capstyle="round", zorder=1)
    # Os conjuntos saem um pouco da linha: quando dois empatam, um marcador
    # cobriria o outro. O relativo e o vazado ficam na linha.
    desvio = {"brutas": 0.16, "todas": -0.16, "relativas": 0.0}
    for c in [c for c in ("brutas", "todas", "relativas") if c in cols]:
        cor, mk = COR_CONJUNTO[c]
        ax.scatter(corta(piv[c]), ys + desvio[c], s=80, color=cor, marker=mk,
                   edgecolors=SURF, linewidths=1.5, zorder=3, label=NOME_CONJUNTO[c])
    ax.scatter(corta(piv.aleatoria), ys, s=80, marker="D", facecolors=SURF,
               edgecolors=PAL[0], linewidths=1.8, zorder=3,
               label="relativos, partição aleatória (vazada)")
    ax.scatter(corta(piv.todos_os_pares), ys - 0.16, s=85, marker="^", facecolors=SURF,
               edgecolors=INK2, linewidths=1.6, zorder=3,
               label="relativos, com os pares de SOH artificial no treino")
    for y, (_, r) in zip(ys, piv.iterrows()):
        for c, dy in [(c, desvio.get(c, 0.0)) for c in cols] + [("aleatoria", 0.0),
                                                                ("todos_os_pares", -0.16)]:
            if r[c] > teto:
                ax.annotate(f"{virg(r[c], 0)} ▸", (teto, y + dy), xytext=(7, 0),
                            textcoords="offset points", fontsize=8.5, color=INK2,
                            va="center", ha="left")
    ax.axvline(nulo, color=INK2, linewidth=1, linestyle=":", zorder=0)
    ax.text(nulo, n - 0.45, " prever a média", fontsize=9, color=INK2, va="bottom", ha="left")
    rotulos = [f"GAM (λ = {potencia(lam)})" if m == "GAM" else ROTULO_MODELO.get(m, m)
               for m in piv.index]
    ax.set_yticks(ys, rotulos)
    for t in ax.get_yticklabels():
        if t.get_text().startswith("GAM"):
            t.set_fontweight("bold")
            t.set_color(INK)
    ax.set_xlim(0, min(teto, float(np.nanmax(piv[todas].to_numpy(float))), ) * 1.1)
    ax.set_ylim(-0.7, n - 0.1)
    ax.set_xlabel("RMSE do SOH (p.p.), menor é melhor")
    ax.grid(axis="y", visible=False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.legend(fontsize=9, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2,
              borderaxespad=0.4)
    sinal = lambda v: ("+" if v >= 0 else "") + virg(v)
    faixa = lambda s: f"{sinal(s.min())} a {sinal(s.max())} p.p."
    sub = ("RMSE na validação nas 20 células de treino. Pontos cheios: uma célula de fora por "
           "vez; losango vazado: partição aleatória por descarga, que põe a mesma célula dos "
           f"dois lados e muda o RMSE em {faixa(piv.aleatoria - piv.relativas)}; triângulo: os "
           "7 pares de SOH artificial de volta ao treino, que mudam o RMSE em "
           f"{faixa(piv.todos_os_pares - piv.relativas)}")
    if "brutas" in cols:
        sub += (f" Trocar atributos brutos por relativos muda o RMSE em "
                f"{faixa(piv.relativas - piv.brutas)}")
    sub += " Negativo: o RMSE cai."
    titulo_figura(plt, fig, "Protocolo, rótulos, atributos e algoritmo", sub)
    salvar(plt, fig, "02_protocolo_rotulos_atributos_algoritmo.png")


def fig_celulas(mods, plt, prev, por, lam):
    from matplotlib.lines import Line2D
    a = prev[prev.avaliavel]
    grupos = list(a.groupby(["battery_id", "test_condition"], sort=True))
    erro = por[por.modelo == "GAM"].set_index(["battery_id", "test_condition"])
    ncol = 4
    nlin = -(-len(grupos) // ncol)
    fig, axes = plt.subplots(nlin, ncol, figsize=(13, 2.9 * nlin + 1.9), squeeze=False)
    for i, (ax, ((bat, cond), g)) in enumerate(zip(axes.flat, grupos)):
        ax.axhline(FIM_DE_VIDA, color=INK2, linestyle="--", linewidth=1.1, zorder=1)
        ax.scatter(g.ciclo, g[ALVO], s=12, color=MUTED, alpha=0.7, linewidths=0, zorder=2)
        ax.plot(g.ciclo, g.soh_gam, color=PAL[0], linewidth=1.8, zorder=3)
        v = list(g[ALVO]) + list(g.soh_gam) + [FIM_DE_VIDA]
        folga = max(2.0, 0.08 * (max(v) - min(v)))
        ax.set_ylim(min(v) - folga, min(max(v) + folga, 106))
        e = erro.loc[(bat, cond)]
        ax.set_title(f"{bat} · {condicao(cond)}\nRMSE {virg(e.rmse)} p.p., viés "
                     f"{virg(e.vies)}", fontsize=9.5, color=INK, loc="left")
        ax.tick_params(labelsize=8.5)
        if i % ncol == 0:
            ax.set_ylabel("SOH (%)", fontsize=9.5)
        if i >= len(grupos) - ncol:
            ax.set_xlabel("ciclo da célula", fontsize=9.5)
    alcas = [Line2D([], [], color=MUTED, marker="o", linestyle="", markersize=5,
                    label="SOH medido"),
             Line2D([], [], color=PAL[0], linewidth=1.8, label="SOH estimado pelo GAM"),
             Line2D([], [], color=INK2, linestyle="--", linewidth=1.1,
                    label=f"limiar de fim de vida ({FIM_DE_VIDA:.0f}%)")]
    sobra = list(axes.flat)[len(grupos):]
    for ax in sobra:
        ax.axis("off")
    if sobra:
        sobra[0].legend(handles=alcas, loc="center", fontsize=9.5)
    else:
        fig.legend(handles=alcas, loc="lower center", ncol=3, fontsize=9.5)
    sub = (f"Cada painel é um par célula × condição de teste, com o GAM de λ = {potencia(lam)} "
           "ajustado nas células de treino. O viés é a média de estimado menos medido: "
           "positivo, o GAM vê a célula mais saudável do que ela está.")
    titulo_figura(plt, fig, "O GAM em cada célula de teste", sub)
    salvar(plt, fig, "06_teste_por_celula.png")


def fig_efeitos(mods, plt, curvas, resumo, rug):
    np = mods["numpy"]
    suaves = list(resumo[resumo.termo == "spline"].coluna)
    ncol = 4
    nlin = -(-len(suaves) // ncol)
    fig, axes = plt.subplots(nlin, ncol, figsize=(13, 2.8 * nlin + 2.0), squeeze=False,
                             sharey=True)
    f_all = curvas[curvas.coluna.isin(suaves)].efeito_pp
    base = float(f_all.min()) - 0.12 * float(f_all.max() - f_all.min())
    for ax, c in zip(axes.flat, suaves):
        g = curvas[curvas.coluna == c]
        r = resumo.set_index("coluna").loc[c]
        nome, unidade, _ = FISICO.get(c, (c, "", 1.0))
        ax.axhline(0, color=INK2, linewidth=0.9, zorder=1)
        ax.plot(g.x_fisico, g.efeito_pp, color=PAL[0], linewidth=2.0, zorder=3)
        xs = rug[c]
        xs = xs[(xs >= g.x_fisico.min()) & (xs <= g.x_fisico.max())]
        ax.plot(xs, np.full(len(xs), base), "|", color=INK2, alpha=0.12, markersize=7,
                zorder=2)
        ax.set_title(f"{nome}\nefeito típico {virg(r.efeito_tipico_pp)} p.p.", fontsize=9.5,
                     color=INK, loc="left")
        rotulo = unidade if c == "ciclo_par" else f"variação desde o início ({unidade})"
        ax.set_xlabel(rotulo, fontsize=9)
        ax.tick_params(labelsize=8.5)
    for ax in axes[:, 0]:
        ax.set_ylabel("efeito no SOH (p.p.)", fontsize=9.5)
    for ax in list(axes.flat)[len(suaves):]:
        ax.axis("off")
    retas = resumo[resumo.termo == "reta"]
    partes = [f"{FISICO.get(r.coluna, (r.coluna,))[0]} {virg(r.pp_por_unidade, 2)} p.p. por "
              f"{r.unidade}" for r in retas.itertuples()]
    sub = ("Cada painel é uma função f_j do GAM ajustado nas células de treino, na unidade "
           "física do atributo e centrada na média: a soma delas, mais a média do SOH, dá a "
           "estimativa. Os traços no pé mostram onde caem as descargas de treino; fora da faixa "
           "de 1% a 99% delas a função fica constante. O efeito típico é a distância entre os "
           "quantis de 5% e 95% da função nas descargas de treino.")
    if partes:
        sub += " O protocolo entra como reta: " + "; ".join(partes) + "."
    titulo_figura(plt, fig, "O que move o SOH, segundo o GAM", sub)
    salvar(plt, fig, "07_efeitos_gam.png")


def fig_conversoes(mods, plt, conv_val, escolhida):
    np = mods["numpy"]
    faixas = [c for c in conv_val.columns if c.startswith("mae_vida_")]
    rotulos = [f"{c.split('_')[2]}–{c.split('_')[3]}%" for c in faixas]
    tend = conv_val[conv_val.conversao.str.startswith("tendencia") & (conv_val.fonte == "GAM")]
    melhor_tend = tend.loc[tend.mae_ciclos.idxmin(), "conversao"]
    series = [(nome_conversao(("condicao", None)), "GAM", PAL[0], "D", "-",
               "taxa da condição, SOH do GAM"),
              (nome_conversao(("condicao", None)), "oraculo", PAL[0], "D", "--",
               "taxa da condição, SOH medido (oráculo)"),
              (melhor_tend, "GAM", PAL[1], "o", "-",
               f"tendência da célula ({melhor_tend.split(', ')[1]}), SOH do GAM"),
              (melhor_tend, "oraculo", PAL[1], "o", "--",
               f"tendência da célula ({melhor_tend.split(', ')[1]}), SOH medido")]
    fig, ax = plt.subplots(figsize=(9.5, 5.4))
    x = np.arange(len(faixas))
    for conv, fonte, cor, mk, ls, rot in series:
        r = conv_val[(conv_val.conversao == conv) & (conv_val.fonte == fonte)].iloc[0]
        cheio = ls == "-"
        ax.plot(x, [r[c] for c in faixas], color=cor, linestyle=ls, marker=mk, markersize=7,
                markerfacecolor=cor if cheio else SURF, markeredgecolor=cor if not cheio else SURF,
                markeredgewidth=1.4, label=rot, zorder=3 if cheio else 2)
    ax.set_xticks(x, rotulos)
    ax.set_xlabel("fração da vida do par já decorrida no instante da previsão")
    ax.set_ylabel("erro absoluto médio do RUL (ciclos)")
    ax.set_ylim(0, None)
    ax.legend(fontsize=9, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2,
              borderaxespad=0.4, handlelength=3.4)
    g = conv_val[conv_val.fonte == "GAM"].set_index("conversao").mae_ciclos
    o = conv_val[conv_val.fonte == "oraculo"].set_index("conversao").mae_ciclos
    c0 = nome_conversao(("condicao", None))
    vence = (nome_conversao(escolhida).replace("condicao", "condição")
             .replace("tendencia", "tendência").replace("celula", "célula"))
    sub = ("Validação nas células de treino que chegam a 80%, cada uma prevista por modelos "
           "e taxas que não a viram, nos mesmos instantes para as duas conversões. Pela taxa "
           f"da condição o erro médio é de {virg(g[c0])} ciclos com o GAM e "
           f"{virg(o[c0])} com o SOH medido; pela tendência da própria célula, "
           f"{virg(g[melhor_tend])} e {virg(o[melhor_tend])}, na melhor janela. A tendência "
           "erra mais no começo da vida, quando a célula ainda quase não perdeu capacidade e "
           "a reta prolongada passa longe dos 80%. Vence a de menor erro com o GAM: "
           f"{vence}.")
    titulo_figura(plt, fig, "Converter pela condição ou pela tendência da célula", sub)
    salvar(plt, fig, "08_rul_conversoes.png")


# ---------------------------------------------------------------------------
# graficos por algoritmo: as referencias com o mesmo detalhe do GAM
# ---------------------------------------------------------------------------
def ordem_modelos(piv):
    """O GAM e depois as referencias pelo RMSE na validacao, como em 02 e 03."""
    return ["GAM"] + [m for m in piv.sort_values("relativas").index if m != "GAM"]


def rotulo_modelo(m, lam):
    return f"GAM (λ = {potencia(lam)})" if m == "GAM" else ROTULO_MODELO.get(m, m)


def lista(itens):
    """['a', 'b', 'c'] -> 'a, b e c'."""
    return itens[0] if len(itens) == 1 else ", ".join(itens[:-1]) + " e " + itens[-1]


def sinal(v, casas=1):
    """+2,6 / −4,4: o vies com sinal, nos graficos. O que arredonda a zero sai 0,0."""
    v = round(float(v), casas) + 0.0
    return ("+" if v > 0 else "") + virg(v, casas)


def _tinta(cor):
    """Texto sobre um preenchimento: tinta escura ou clara pela luminancia dele."""
    from matplotlib.colors import to_rgb
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in to_rgb(cor)]
    lum = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    return INK if lum > 0.18 else SURF


def fig_previsto_real_todos(mods, plt, prev, res, ordem, lam):
    """SOH estimado contra medido no teste, um painel por algoritmo, no mesmo quadro."""
    np = mods["numpy"]
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    a = prev[prev.avaliavel]
    x = a[ALVO].to_numpy(float)
    t = res.set_index("modelo")
    est = {m: a[f"soh_{SLUG[m]}"].to_numpy(float) for m in ordem}
    # Um quadro so, que acompanha a nuvem; o que sai dele fica na borda, como seta.
    lo = 5 * np.floor((min([np.percentile(x, 0.5)]
                           + [np.percentile(v, 0.5) for v in est.values()]) - 1) / 5)
    hi = 103.0
    ncol = 3
    nlin = -(-(len(ordem) + 1) // ncol)
    fig, axes = plt.subplots(nlin, ncol, figsize=(12.6, 4.2 * nlin + 2.4), squeeze=False)
    seta = dict(s=34, color=PAL[0], linewidths=0, zorder=2, clip_on=False)
    for i, (ax, m) in enumerate(zip(axes.flat, ordem)):
        y = est[m]
        ax.fill_between([lo, FIM_DE_VIDA], FIM_DE_VIDA, hi, color=PAL[1], alpha=0.09,
                        linewidth=0, zorder=0)
        ax.fill_between([FIM_DE_VIDA, hi], lo, FIM_DE_VIDA, color=PAL[1], alpha=0.09,
                        linewidth=0, zorder=0)
        ax.plot([lo, hi], [lo, hi], color=INK2, linestyle="--", linewidth=1.1, zorder=1)
        ax.axhline(FIM_DE_VIDA, color=INK2, linestyle=":", linewidth=1, zorder=1)
        ax.axvline(FIM_DE_VIDA, color=INK2, linestyle=":", linewidth=1, zorder=1)
        dentro = (x >= lo) & (y >= lo) & (y <= hi)
        ax.scatter(x[dentro], y[dentro], s=10, color=PAL[0], alpha=0.45, linewidths=0,
                   zorder=2)
        esq = x < lo
        if esq.any():
            ax.scatter(np.full(esq.sum(), lo + 0.6), np.clip(y[esq], lo + 0.6, hi - 0.6),
                       marker="<", **seta)
        for fora, borda, mk in (((x >= lo) & (y < lo), lo + 0.6, "v"),
                                ((x >= lo) & (y > hi), hi - 0.6, "^")):
            if fora.any():
                ax.scatter(x[fora], np.full(fora.sum(), borda), marker=mk, **seta)
        nao_visto = int(((x < FIM_DE_VIDA) & (y >= FIM_DE_VIDA)).sum())
        falso = int(((x >= FIM_DE_VIDA) & (y < FIM_DE_VIDA)).sum())
        ax.text(lo + 1.3, hi - 1.2, f"fim de vida não percebido\n{nao_visto} descargas",
                fontsize=8.5, color=INK2, va="top", ha="left")
        ax.text(hi - 1.2, lo + 1.3, f"alarme falso\n{falso} descargas", fontsize=8.5,
                color=INK2, va="bottom", ha="right")
        ax.set_xlim(lo, hi)
        ax.set_ylim(lo, hi)
        ax.set_aspect("equal")
        r = t.loc[m]
        ax.set_title(rotulo_modelo(m, lam), loc="left", fontsize=10.5, color=INK, pad=17,
                     fontweight="bold" if m == "GAM" else "normal")
        ax.text(0, 1.015, f"RMSE {virg(r.rmse, 2)} p.p. · R² {virg(r.r2, 2)} · viés "
                f"{sinal(r.vies)} p.p.", transform=ax.transAxes, fontsize=9, color=INK2,
                ha="left", va="bottom")
        ax.tick_params(labelsize=8.5)
        if i % ncol == 0:
            ax.set_ylabel("SOH estimado (%)", fontsize=9.5)
        if i + ncol >= len(ordem):
            ax.set_xlabel("SOH medido (%)", fontsize=9.5)
    sobra = list(axes.flat)[len(ordem):]
    for ax in sobra:
        ax.axis("off")
    alcas = [Line2D([], [], color=PAL[0], marker="o", linestyle="", markersize=5, alpha=0.6,
                    label="descarga de teste"),
             Line2D([], [], color=INK2, linestyle="--", linewidth=1.1, label="acerto exato"),
             Line2D([], [], color=INK2, linestyle=":", linewidth=1,
                    label=f"limiar de fim de vida ({FIM_DE_VIDA:.0f}%)"),
             Patch(color=PAL[1], alpha=0.09, linewidth=0,
                   label="estimativa do outro lado do limiar"),
             Line2D([], [], color=PAL[0], marker="<", linestyle="", markersize=6,
                    label="fora do quadro, na borda")]
    if sobra:
        sobra[0].legend(handles=alcas, loc="center", fontsize=9.5)
    nv = {m: int(((x < FIM_DE_VIDA) & (est[m] >= FIM_DE_VIDA)).sum()) for m in ordem}
    af = {m: int(((x >= FIM_DE_VIDA) & (est[m] < FIM_DE_VIDA)).sum()) for m in ordem}
    rot = lambda m: rotulo_modelo(m, lam)
    sub = (f"As {len(x)} descargas avaliáveis das 8 células de teste; cada painel é um algoritmo "
           "ajustado nas 20 células de treino, com os atributos relativos, na ordem da validação. "
           "A diagonal é o acerto exato; nos cantos sombreados a estimativa cai do outro lado do "
           f"limiar de {FIM_DE_VIDA:.0f}%. Menor RMSE: {rot(t.loc[ordem].rmse.idxmin())}; menos "
           f"fins de vida não percebidos: {rot(min(nv, key=nv.get))}, com {min(nv.values())}; "
           f"menos alarmes falsos: {rot(min(af, key=af.get))}, com {min(af.values())}.")
    esq = x < lo
    if esq.any():
        sub += (f" As setas na borda esquerda são {int(esq.sum())} descargas com SOH medido "
                f"abaixo de {lo:.0f}% ({', '.join(virg(v, 0) + '%' for v in sorted(x[esq]))}), "
                "leituras isoladas no meio de células saudáveis.")
    titulo_figura(plt, fig, "SOH estimado contra medido, algoritmo por algoritmo", sub)
    salvar(plt, fig, "04_previsto_vs_real_por_algoritmo.png")


def fig_metricas(mods, plt, comp, res, nulo, ordem, lam):
    """RMSE, MAE, R2 e vies de cada algoritmo: o teste com intervalo, ao lado da validacao."""
    np = mods["numpy"]
    from matplotlib.lines import Line2D
    from matplotlib.ticker import FuncFormatter
    val = comp[(comp.atributos == "relativas") & (comp.validacao == "uma celula de fora")
               & (comp.rotulos_no_treino == "pares avaliaveis")].set_index("modelo").loc[ordem]
    te = res.set_index("modelo").loc[ordem]
    paineis = [("rmse", "RMSE do SOH (p.p.), menor é melhor"),
               ("mae", "MAE do SOH (p.p.), menor é melhor"),
               ("r2", "R², maior é melhor"),
               ("vies", "viés do SOH (p.p.), estimado − medido")]
    n = len(ordem)
    fig, axes = plt.subplots(1, len(paineis), figsize=(13.5, 0.62 * n + 3.4), sharey=True)
    ys = np.arange(n)[::-1]
    for ax, (col, titulo) in zip(axes, paineis):
        lo_ic, hi_ic = te[f"{col}_ic95_inferior"], te[f"{col}_ic95_superior"]
        # Teste e validacao em alturas um pouco diferentes: quando os dois
        # coincidem, o circulo cobriria o losango.
        ax.hlines(ys - 0.1, lo_ic, hi_ic, color=PAL[0], linewidth=2, zorder=2)
        ax.scatter(te[col], ys - 0.1, s=60, marker="D", color=PAL[0], edgecolors=SURF,
                   linewidths=1.3, zorder=3)
        ax.scatter(val[col], ys + 0.14, s=52, marker="o", facecolors=SURF, edgecolors=INK2,
                   linewidths=1.5, zorder=3)
        valores = np.r_[lo_ic, hi_ic, val[col]].astype(float)
        if col == "vies":
            ax.axvline(0, color=INK2, linewidth=1, zorder=0)
            ax.text(0, -0.62, " sem viés", fontsize=8.5, color=INK2, va="bottom", ha="left")
            lim = 1.15 * float(np.nanmax(np.abs(valores)))
            ax.set_xlim(-lim, lim)
        else:
            ax.axvline(nulo[col], color=INK2, linewidth=1, linestyle=":", zorder=0)
            ax.text(nulo[col], -0.62, " prever a média", fontsize=8.5, color=INK2,
                    va="bottom", ha="left")
            valores = np.r_[valores, nulo[col]]
            if col == "r2":
                ax.set_xlim(min(0.0, float(np.nanmin(valores))) - 0.05, 1.0)
            else:
                ax.set_xlim(0, 1.1 * float(np.nanmax(valores)))
        ax.xaxis.set_major_formatter(
            FuncFormatter(lambda v, _: virg(v, 2).rstrip("0").rstrip(",")))
        ax.set_title(titulo, fontsize=10, color=INK, loc="left")
        ax.set_ylim(-0.7, n - 0.3)
        ax.grid(axis="y", visible=False)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
    axes[0].set_yticks(ys, [rotulo_modelo(m, lam) for m in ordem])
    for tk in axes[0].get_yticklabels():
        if tk.get_text().startswith("GAM"):
            tk.set_fontweight("bold")
            tk.set_color(INK)
    alcas = [Line2D([], [], color=PAL[0], marker="D", markersize=7, markeredgecolor=SURF,
                    linewidth=2, label="teste: 8 células, com IC 95% por reamostragem de células"),
             Line2D([], [], color=INK2, marker="o", markersize=7, markerfacecolor=SURF,
                    markeredgewidth=1.5, linestyle="",
                    label="validação: 20 células de treino, uma de fora por vez")]
    fig.legend(handles=alcas, loc="lower center", ncol=2, fontsize=9.5,
               bbox_to_anchor=(0.5, -0.02))
    rot = lambda m: rotulo_modelo(m, lam)
    sub = ("Atributos relativos ao início de vida. O losango é o teste nas 8 células nunca vistas, "
           "com o intervalo de 95% de reamostrar células inteiras; o círculo vazado é a validação "
           "nas 20 células de treino. A linha pontilhada é o modelo nulo no teste, que prevê para "
           "toda descarga a média do SOH do treino. Viés positivo: o modelo vê a célula mais "
           f"saudável do que ela está. No teste, menor RMSE: {rot(te.rmse.idxmin())}; menor MAE: "
           f"{rot(te.mae.idxmin())}; o viés vai de {sinal(te.vies.min())} p.p., com "
           f"{rot(te.vies.idxmin())}, a {sinal(te.vies.max())} p.p., com {rot(te.vies.idxmax())}.")
    titulo_figura(plt, fig, "Todas as métricas, algoritmo por algoritmo", sub)
    fig.subplots_adjust(bottom=0.15)
    salvar(plt, fig, "03_metricas_por_algoritmo.png")


def fig_erro_por_par(mods, plt, por, res, ordem, lam):
    """RMSE e vies de cada algoritmo em cada par de teste avaliavel, e nos pares juntos."""
    np = mods["numpy"]
    from matplotlib.colors import LinearSegmentedColormap, LogNorm
    cmap = LinearSegmentedColormap.from_list("erro", SEQ_ERRO)
    base = por[(por.modelo == "GAM") & por.avaliavel].reset_index(drop=True)
    t = por.set_index(["modelo", "battery_id", "test_condition"])
    tot = res.set_index("modelo")
    # (RMSE, vies) por par e modelo
    pares = [[tuple(t.loc[(m, r.battery_id, r.test_condition), ["rmse", "vies"]])
              for m in ordem] for r in base.itertuples()]
    total = [(tot.loc[m, "rmse"], tot.loc[m, "vies"]) for m in ordem]
    n_lin, n_col = len(pares), len(ordem)
    # Os pares juntos ficam embaixo, separados por uma faixa vazia.
    folga = 0.45
    bordas_y = list(range(n_lin + 1)) + [n_lin + folga, n_lin + folga + 1]
    rmse = np.array([[e for e, _v in lin] for lin in pares]
                    + [[np.nan] * n_col] + [[e for e, _v in total]], dtype=float)
    # Cor em escala log: o RMSE vai de pouco mais de 1 a mais de 20 p.p., e na
    # linear quase tudo ficaria no claro.
    norm = LogNorm(vmin=max(0.5, float(np.floor(np.nanmin(rmse)))),
                   vmax=float(np.nanmax(rmse)))
    fig, ax = plt.subplots(figsize=(1.95 * n_col + 3.6, 0.56 * (n_lin + 1) + 2.9))
    ax.pcolormesh(np.arange(n_col + 1), bordas_y, np.ma.masked_invalid(rmse), cmap=cmap,
                  norm=norm, edgecolors=SURF, linewidth=2.5)
    centros = [i + 0.5 for i in range(n_lin)] + [n_lin + folga + 0.5]
    for yc, lin in zip(centros, pares + [total]):
        for j, (e, v) in enumerate(lin):
            tinta = _tinta(cmap(norm(e)))
            ax.text(j + 0.5, yc - 0.12, virg(e), ha="center", va="center", fontsize=10.5,
                    color=tinta, fontweight="bold")
            ax.text(j + 0.5, yc + 0.24, f"viés {sinal(v)}", ha="center", va="center",
                    fontsize=8, color=tinta)
    ax.set_xlim(0, n_col)
    ax.set_ylim(bordas_y[-1], 0)
    ax.xaxis.tick_top()
    ax.set_xticks(np.arange(n_col) + 0.5, [rotulo_modelo(m, lam) for m in ordem], fontsize=10)
    for tk in ax.get_xticklabels():
        if tk.get_text().startswith("GAM"):
            tk.set_fontweight("bold")
            tk.set_color(INK)
    rotulos = [f"{r.battery_id} · {condicao(r.test_condition)}\n"
               f"{r.descargas} descargas, SOH médio {virg(r.soh_medio, 0)}%"
               for r in base.itertuples()]
    rotulos.append(f"os {n_lin} pares\n{int(base.descargas.sum())} descargas")
    ax.set_yticks(centros, rotulos, fontsize=9)
    ax.tick_params(length=0)
    ax.grid(False)
    for lado in ax.spines.values():
        lado.set_visible(False)
    media = rmse[:n_lin].mean(axis=1)
    piores = np.argsort(media)[::-1][:3]
    vies = np.array([[v for _e, v in lin] for lin in pares])
    mesmo_lado = int(((vies > 0).all(axis=1) | (vies < 0).all(axis=1)).sum())
    sub = ("Cada linha é um par célula × condição de teste com SOH inicial saudável, e cada coluna "
           "um algoritmo ajustado nas 20 células de treino, com os atributos relativos. A cor e o "
           "número são o RMSE do SOH no par, em p.p., com a cor em escala logarítmica; embaixo, o "
           "viés, estimado menos medido. Na média dos algoritmos, os pares com mais erro são "
           + lista([f"{base.battery_id[i]} a {condicao(base.test_condition[i])} "
                    f"({virg(media[i])} p.p.)" for i in piores])
           + f". Em {mesmo_lado} dos {n_lin} pares, os {n_col} algoritmos erram para o mesmo lado.")
    titulo_figura(plt, fig, "Onde cada algoritmo erra", sub)
    salvar(plt, fig, "05_erro_por_par.png")


def fig_rul_todos(mods, plt, inst, resumo, ordem, lam):
    """RUL de cada algoritmo nos pares de teste que chegam a 80%: uma linha por algoritmo."""
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    from matplotlib.ticker import MaxNLocator
    f = inst[~inst.censurado & inst.rul_previsto.notna()]
    pares = sorted({(b, c) for b, c in zip(f.battery_id, f.test_condition)})
    if not pares:
        return
    n_lin, n_col = len(ordem), len(pares)
    fig, axes = plt.subplots(n_lin, n_col, figsize=(3.1 * n_col + 1.5, 2.2 * n_lin + 3.0),
                             squeeze=False)
    for j, (bat, cond) in enumerate(pares):
        g = f[(f.battery_id == bat) & (f.test_condition == cond)]
        ora = g[g.fonte == "oraculo"].sort_values("ciclo")
        topo = 1.7 * float(ora.rul_real.max())
        mae_o = (ora.rul_previsto - ora.rul_real).abs().mean()
        for i, m in enumerate(ordem):
            ax = axes[i, j]
            h = g[g.fonte == m].sort_values("ciclo")
            ax.fill_between(h.ciclo, (1 - ALFA_RUL) * h.rul_real, (1 + ALFA_RUL) * h.rul_real,
                            color=PAL[0], alpha=0.10, linewidth=0, zorder=0)
            ax.plot(h.ciclo, h.rul_real, color=INK, linewidth=1.3, zorder=2)
            ax.plot(ora.ciclo, ora.rul_previsto, color=PAL[1], linewidth=1.2, zorder=3)
            ax.plot(h.ciclo, h.rul_previsto, color=PAL[0], linewidth=1.8, zorder=4)
            ax.set_ylim(0, topo)
            if h.rul_previsto.median() > topo:
                ax.text(0.03, 0.05, f"acima do quadro: mediana de "
                        f"{virg(h.rul_previsto.median(), 0)} ciclos", transform=ax.transAxes,
                        fontsize=8, color=INK2, ha="left", va="bottom")
            mae = (h.rul_previsto - h.rul_real).abs().mean()
            cab = (f"{bat} · {condicao(cond)}, fim no ciclo {h.fim_de_vida.iloc[0]:.0f}\n"
                   f"oráculo: MAE {virg(mae_o)} ciclos\n" if i == 0 else "")
            ax.set_title(f"{cab}MAE {virg(mae)} ciclos", fontsize=9, color=INK, loc="left")
            ax.xaxis.set_major_locator(MaxNLocator(integer=True, steps=[1, 2, 5, 10]))
            ax.tick_params(labelsize=8)
            if i == n_lin - 1:
                ax.set_xlabel("ciclo da célula", fontsize=9)
            if j == 0:
                ax.set_ylabel(f"{rotulo_modelo(m, lam)}\nRUL (ciclos)", fontsize=9.5,
                              color=INK, fontweight="bold" if m == "GAM" else "normal")
    alcas = [Line2D([], [], color=INK, linewidth=1.3, label="RUL real"),
             Patch(color=PAL[0], alpha=0.10, linewidth=0,
                   label=f"±{virg(100 * ALFA_RUL, 0)}% do RUL real"),
             Line2D([], [], color=PAL[0], linewidth=1.8,
                    label="algoritmo da linha: SOH estimado convertido"),
             Line2D([], [], color=PAL[1], linewidth=1.2, label="oráculo: SOH medido convertido")]
    fig.legend(handles=alcas, loc="lower center", ncol=4, fontsize=9.5,
               bbox_to_anchor=(0.5, -0.005))
    r = resumo[resumo.conjunto == "teste"].set_index("fonte")
    maes = r.loc[ordem, "mae_ciclos"]
    rot = lambda m: rotulo_modelo(m, lam)
    sub = ("RUL = (SOH − 80) / perda de SOH por ciclo da condição, medida nas células de treino. "
           "Cada linha é um algoritmo e cada coluna um par de teste que chega a 80%, da 5ª "
           "descarga até o fim de vida; a faixa é ±20% do RUL real, e a linha laranja é o "
           "oráculo, o SOH medido convertido do mesmo jeito. "
           f"Nos {n_col} pares juntos, o erro médio vai de {virg(maes.min())} ciclos, com "
           f"{rot(maes.idxmin())}, a {virg(maes.max())}, com {rot(maes.idxmax())}, contra "
           f"{virg(r.loc['oraculo', 'mae_ciclos'])} do oráculo. Previsões acima do quadro saem "
           "dele.")
    titulo_figura(plt, fig, "Vida útil remanescente, algoritmo por algoritmo", sub)
    fig.subplots_adjust(bottom=0.07)
    salvar(plt, fig, "09_rul_teste_por_algoritmo.png")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--lam", type=float, default=None,
                    help="forca lambda (por padrao, o mais suave equivalente ao melhor)")
    ap.add_argument("--tolerancia", type=float, default=TOLERANCIA_LAMBDA,
                    help="distancia ao menor RMSE, em fracao dele, que ainda conta como "
                         f"equivalente (padrao {TOLERANCIA_LAMBDA})")
    ap.add_argument("--sem-referencias", action="store_true",
                    help="so o GAM, sem as familias dos trabalhos relacionados")
    ap.add_argument("--sem-graficos", action="store_true")
    a = ap.parse_args()

    mods = checar()
    TABELAS.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    p("Regressao do SOH com GAM e conversao em RUL")
    p("=" * 60)
    df = carregar(mods)
    conj = conjuntos(df)
    tr = df[df.split == "treino"].reset_index(drop=True)
    te = df[df.split == "teste"].reset_index(drop=True)
    for nome, d in (("treino", tr), ("teste", te)):
        ok = d[d.avaliavel]
        p(f"  {nome:<6} {len(ok):>4} descargas avaliaveis de {ok.battery_id.nunique():>2} "
          f"celulas, SOH medio {ok[ALVO].mean():.1f}% (dp {ok[ALVO].std():.1f})")
    fora = (df[~df.avaliavel].groupby(["battery_id", "test_condition", "split"]).soh_inicio
            .first().reset_index())
    p(f"  {len(fora)} pares com SOH ja abaixo de {FIM_DE_VIDA:.0f}% no inicio ficam de fora: "
      + ", ".join(f"{r.battery_id} {r.test_condition} ({r.soh_inicio:.0f}%, {r.split})"
                  for r in fora.itertuples()))
    for n, cols in conj.items():
        p(f"  atributos {n:<9} {len(cols):>2}: {', '.join(cols)}")

    p("")
    p("1. escolha de lambda, uma celula de treino de fora por vez:")
    tab, lam_conj = etapa_lambda(mods, tr, conj, a.tolerancia, a.lam)
    lam = lam_conj["relativas"]

    p("")
    p("2. protocolo, rotulos, atributos e algoritmo (so treino):")
    refs = {} if a.sem_referencias else referencias()
    comp, piv, val_par, previsoes, nulo_val = etapa_comparacao(mods, tr, conj, lam_conj, refs)

    p("")
    p("3. teste: 8 celulas, avaliadas uma vez:")
    res, prev, por, preds, final, nulo_te = etapa_teste(mods, tr, te, conj, lam, refs)
    p(f"  GAM final: {final[-1].graus_de_liberdade_:.1f} graus de liberdade efetivos "
      f"(a regressao linear usa {len(conj['relativas']) + 1})")

    p("")
    p("4. vida util remanescente (RUL):")
    rul = etapa_rul(mods, tr, te, previsoes, preds)
    inst = rul["instantes_teste"]
    fontes = ["GAM", *refs, "oraculo"]
    for fonte in fontes:
        r = inst[inst.fonte == fonte][["battery_id", "test_condition", "ciclo", "rul_real",
                                       "rul_previsto"]]
        prev = prev.merge(r.rename(columns={"rul_real": "rul_real_" + SLUG[fonte],
                                            "rul_previsto": "rul_" + SLUG[fonte]}),
                          on=["battery_id", "test_condition", "ciclo"], how="left")
    prev = prev.drop(columns=[f"rul_real_{SLUG[f]}" for f in fontes[1:]]).rename(
        columns={"rul_real_gam": "rul_real"})

    p("")
    p("5. efeitos do GAM final:")
    curvas, efeitos, rug = efeitos_gam(mods, final, conj["relativas"], tr)
    for r in efeitos.itertuples(index=False):
        extra = (f", {r.pp_por_unidade:+.3f} p.p. por {ascii_unidade(r.unidade)}"
                 if r.termo == "reta" else "")
        p(f"    {r.coluna:<26} {r.termo:<6} efeito tipico {r.efeito_tipico_pp:6.2f} p.p.{extra}")

    arquivos = {"escolha_de_lambda.csv": tab, "comparacao.csv": comp,
                "validacao_por_par.csv": val_par, "teste.csv": res, "teste_por_par.csv": por,
                "predicoes_teste.csv": prev, "efeitos_gam.csv": curvas,
                "efeitos_resumo.csv": efeitos, "taxas_por_condicao.csv": rul["inclinacoes"].merge(
                    rul["taxas"].rename("taxa_da_condicao").reset_index(), on="test_condition"),
                "fins_de_vida.csv": rul["fins"], "rul_conversoes_validacao.csv": rul["conversoes"],
                "rul_variante_media_movel.csv": rul["variante"],
                "rul_resumo.csv": rul["resumo"], "rul_teste_por_par.csv": rul["por_par"]}
    p("")
    for nome, tabela in arquivos.items():
        tabela.round(4).to_csv(TABELAS / nome, index=nome == "escolha_de_lambda.csv")
        p(f"  {(TABELAS / nome).relative_to(RAIZ)}")

    if not a.sem_graficos:
        p("")
        p("graficos:")
        plt = estilo(mods)
        # Na ordem do artigo: validacao, teste de todos os algoritmos, o GAM em
        # detalhe e o RUL. Sem referencias, os graficos por algoritmo saem so
        # com o GAM.
        ordem = ordem_modelos(piv)
        fig_escolha_lambda(mods, plt, tab, lam, a.tolerancia)
        if refs:
            fig_hierarquia(mods, plt, piv, nulo_val, lam)
        fig_metricas(mods, plt, comp, res, nulo_te, ordem, lam)
        fig_previsto_real_todos(mods, plt, prev, res, ordem, lam)
        fig_erro_por_par(mods, plt, por, res, ordem, lam)
        fig_celulas(mods, plt, prev, por, lam)
        fig_efeitos(mods, plt, curvas, efeitos, rug)
        fig_conversoes(mods, plt, rul["conversoes"], rul["escolhida"])
        fig_rul_todos(mods, plt, inst, rul["resumo"], ordem, lam)
    p("")
    p(f"  tempo total: {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
