#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Classificacao de fim de vida com k vizinhos mais proximos (kNN).

    python classificacao.py                    # escolhe k na validacao, avalia no teste
    python classificacao.py --k 25             # forca k
    python classificacao.py --sem-referencias  # so o kNN, sem as familias da literatura
    python classificacao.py --sem-graficos     # so as tabelas
    python classificacao.py --com-grupo        # com baterias_por_condicao entre os atributos

Le saida_nasa/normalizado/tabelas/dados_normalizados.csv e escreve em
saida_nasa/classificacao/: as tabelas em tabelas/, os graficos em figuras/.
Com --com-grupo, em saida_nasa/baterias_por_condicao/classificacao/.

**A tarefa.** Cada descarga e rotulada fim de vida (SOH < 80%, o limiar do
artigo) ou saudavel. As classes ja saem quase equilibradas — 44% de fim de vida
no treino, 47% no teste — e dispensam reamostragem. A metrica principal e a
acuracia balanceada, a media da taxa de acerto das duas classes: nao premia
quem chuta a classe maior, e o acaso fica em 0,5.

**Por que kNN.** O modulo de classificacao do curso pede um algoritmo fora das
familias dos trabalhos relacionados do artigo (regressao linear, SVM, RVM,
processos gaussianos, ensembles de arvores, redes recorrentes). O kNN classifica
uma descarga pelo voto das k
descargas de treino mais proximas no espaco padronizado dos atributos:
distancia euclidiana, voto por maioria, k impar para nao empatar. Nao tem
parametro treinado — guarda o treino e decide na hora —, e cada previsao vem
com os vizinhos que a decidiram, que predicoes_teste.csv lista para um
especialista em baterias conferir.

**Atributos relativos ao inicio de vida.** As colunas `_rel` de normalizar.py,
mais temperatura ambiente, corrente e ciclo. Nas brutas cada celula vive num
nivel proprio, e a distancia passa a medir de que celula a descarga veio, nao
quanto ela degradou — o paradoxo de Simpson que o projeto documenta. Os
conjuntos bruto e completo rodam ao lado, para medir o efeito.

**Validacao deixando uma celula de fora.** k sai de uma validacao cruzada nas
25 celulas de treino, uma celula por rodada. A coluna `fold` de normalizar.py
fica de lado: os cinco folds sairam desiguais (um deles e uma celula so, com 24
descargas), e a nota de um fold desses e ruido. Imputacao e escala sao
reajustadas a cada rodada, so com as celulas que ficaram no treino.

**k pelo menor equivalente ao melhor.** A acuracia contra k forma um plato: de
k=15 a k=101 tudo fica a 2 p.p. do maximo, e com 25 celulas diferencas desse
tamanho sao ruido — o maximo isolado e sorte da grade. Vence o menor k a ate
TOLERANCIA_K do maximo: mantem a vizinhanca local, para o voto vir de descargas
de fato parecidas, e fica longe da queda que aparece quando k passa de ~100 e a
vizinhanca vira media regional.

**O teste e avaliado uma vez.** As 8 celulas de teste nao entram na escolha de
nada. O modelo final e ajustado nas 25 de treino, e o intervalo de confianca
vem de reamostrar celulas de teste inteiras. Com 8 celulas ele e largo, e e ele
que o artigo deve reportar junto com a acuracia. A diferenca entre o kNN e cada
referencia e medida em pares, nas mesmas reamostragens: intervalos que se
sobrepoem nao bastam para dizer que dois modelos empatam.

**AUC ao lado da acuracia balanceada.** A acuracia balanceada julga a decisao,
com o voto cortado em 50%; a area sob a curva ROC (AUC) julga a ordem: a chance
de uma descarga em fim de vida receber escore maior que uma saudavel, em todos
os limiares. O escore e a probabilidade de fim de vida quando o modelo a tem —
no kNN, a fracao de vizinhos em fim de vida — e a funcao de decisao no SVM. Na
validacao, os escores das rodadas sao juntados antes do calculo: a AUC de uma
celula sozinha nao existe quando ela tem uma classe so, e dez das 25 quase nao
tem fim de vida. Nada e escolhido pela AUC; ela so descreve.

**F1 da classe fim de vida.** A media harmonica entre precisao (dos alarmes,
quantos sao fim de vida) e sensibilidade (do fim de vida, quanto e detectado):
mede a qualidade do alarme. Sai com o mesmo intervalo por celulas e a mesma
comparacao em pares da acuracia balanceada. Ignora as saudaveis reconhecidas e
muda com a proporcao de fim de vida, por isso complementa a acuracia
balanceada em vez de substitui-la.

**O protocolo e medido, nao so declarado.** O mesmo kNN, com particao aleatoria
por descarga (a mesma celula dos dois lados), mostra o vazamento que o artigo
aponta em [13]: o vizinho mais proximo de uma descarga passa a ser, quase
sempre, outra descarga da mesma celula, e o modelo acerta por reconhecer a
celula. O terminal mostra quanto.

**Familias da literatura como referencia.** Regressao logistica, SVM, Random
Forest e Gradient Boosting rodam no mesmo protocolo e com o mesmo preparo, com
os hiperparametros padrao do scikit-learn. Nao decidem nada: dizem onde o kNN
fica. Sao o motivo de o scikit-learn entrar no projeto — o kNN caberia em numpy,
as quatro nao.

**Os resultados de cada algoritmo.** As quatro referencias saem com o mesmo
detalhe do kNN: matriz de confusao na validacao e no teste
(03_matrizes_de_confusao.png), todas as metricas com o intervalo por celulas
(04_metricas_por_algoritmo.png), as curvas ROC (05_curvas_roc.png) e o erro em
cada celula de teste (06_erro_por_celula.png). Em teste_por_modelo/,
<algoritmo>_por_celula.png e a 07 de cada algoritmo: os erros dele em cada
celula de teste, ao longo dos ciclos. Nada disso escolhe nada; e o que permite
discutir os cinco lado a lado, e nao so o kNN.

**Onde fica cada coisa.** As tabelas vao para saida_nasa/classificacao/tabelas/
e os graficos para saida_nasa/classificacao/figuras/, numerados na ordem do
artigo: validacao (01 e 02), teste de todos os algoritmos (03 a 06), os erros do
kNN ao longo dos ciclos (07), a variante pos-hoc (08), a logistica melhorada
(09 e 10) e o ensemble (11). As imagens por algoritmo ficam em
figuras/teste_por_modelo/.

**Variante pos-hoc: vizinhos so do mesmo grupo de comportamento.** Na analise
dos erros do teste, mais da metade dos vizinhos que enganaram B0018 vinha de
outros grupos do agrupamento do modulo 2. A variante restringe a vizinhanca ao
grupo da descarga, com o agrupamento refeito a cada rodada so com as celulas de
treino (grupos.ajustar) e a celula de fora encaixada no grupo mais proximo.
Como surgiu de olhar o teste, so a validacao a avalia. Precisa das saidas de
curvas.py e grupos.py; sem elas, e pulada.

**Logistica melhorada (pos-hoc).** A mesma regressao logistica, com tres trocas,
medidas uma a uma em logistica_melhorada.csv: regularizacao mais forte (o C do
padrao, 1, deixa os coeficientes soltos entre atributos colineares, e os das
duas tensoes trocam de sinal de uma rodada para outra); a idade no par no lugar
do ciclo da celula, como em regressao.py, porque o SOH recomeca em 100% quando a
celula muda de condicao e o ciclo dela nao; e a media movel exponencial dos
atributos relativos, so com descargas ate a atual, contra o vaivem de um ciclo
para o seguinte. C sai da validacao, pela regra do k: o menor a ate TOLERANCIA_K
do maximo. A ideia veio depois de ver o teste, entao o numero do teste dela nao
e avaliacao independente, e o artigo que a usar tem de declarar isso. Por isso
ela roda a parte e nao entra nas tabelas e nos graficos dos cinco algoritmos. A
avaliacao nas 33 celulas, uma de fora por vez, mostra o quanto o resultado
depende das 8 sorteadas para o teste.

**Ensemble (pos-hoc).** Um membro de cada familia, todos com os atributos da
logistica melhorada: ela, o SVM e um Gradient Boosting monotonico, de arvores
rasas e com o sinal fisico imposto — mais idade e mais resistencia so podem
aumentar o escore de fim de vida, mais tensao so pode diminuir. O sinal imposto
impede as arvores de aprender a curva particular de uma celula, que e o que elas
fazem com 25 celulas e ciclos vizinhos quase iguais. Os hiperparametros do
Gradient Boosting e do SVM foram fixados, nao ajustados. Duas formas de juntar:
voto majoritario (cada membro diz sim ou nao) e voto suave (a media dos escores,
cada um dividido pelo seu desvio no treino). A forma e os membros saem da
validacao, em ensemble_composicao.csv. Como a logistica melhorada, veio depois
de o teste ser visto e roda a parte.

**--com-grupo: o grupo como atributo.** Tudo de novo, com a variavel
baterias_por_condicao — o grupo de comportamento do modulo 2, em sete
indicadores — nos tres conjuntos de atributos. O agrupamento so ve as celulas
de treino, e na validacao e refeito a cada rodada sem a celula deixada de fora
(baterias_por_condicao.Codificacao). A particao aleatoria, que ja vaza por
construcao, usa o agrupamento de todas as celulas de treino. A variante
pos-hoc nao roda: com o grupo entre os atributos, ela deixa de ser a
alternativa. A logistica melhorada e o ensemble tambem nao: neles o agrupamento
nao e refeito a cada rodada, e o grupo vazaria na validacao.
baterias_por_condicao.py poe os dois resultados lado a lado.

Dependencias: numpy, pandas, scipy, scikit-learn, matplotlib
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

try:
    from sklearn.base import BaseEstimator, ClassifierMixin
except ImportError:            # checar() avisa e sai antes de qualquer ajuste
    BaseEstimator = ClassifierMixin = object

# A raiz do projeto e a pasta acima de src/: e la que ficam
# cleaned_nasa_dataset/ e saida_nasa/.
RAIZ = Path(__file__).resolve().parent.parent
ENTRADA = RAIZ / "saida_nasa" / "normalizado" / "tabelas" / "dados_normalizados.csv"
# So pelo numero do ciclo: a tabela normalizada traz o ciclo escalonado, e o
# eixo dos graficos e o CSV de previsoes precisam do ciclo de verdade.
BRUTA = RAIZ / "saida_nasa" / "preprocessado" / "tabelas" / "dados_modelagem.csv"
# So a variante pos-hoc le o agrupamento do modulo 2: os perfis de
# comportamento saem das curvas, e o k e o que grupos.py escolheu.
CURVAS = RAIZ / "saida_nasa" / "curvas" / "tabelas" / "features_curvas.csv"
GRUPOS = (RAIZ / "saida_nasa" / "cluster" / "agrupamento" / "tabelas"
          / "grupos_comportamento.csv")
SAIDA = RAIZ / "saida_nasa" / "classificacao"
FIGURAS, TABELAS = SAIDA / "figuras", SAIDA / "tabelas"
# --com-grupo troca a pasta de saida e acrescenta esta frase a todo subtitulo.
SAIDA_COM_GRUPO = RAIZ / "saida_nasa" / "baterias_por_condicao" / "classificacao"
NOTA_COM_GRUPO = (" Com baterias_por_condicao, o grupo de comportamento do módulo 2, entre os "
                  "atributos.")
NOTA = ""

# Paleta categorica validada para daltonismo (modo claro), slots 1..8 em ordem fixa
PAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
       "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e3e2de"
MUTED = "#898781"          # o que o kNN acertou: fundo, para o erro aparecer
SEQ = ["#f0efec", "#cfe0f5", "#9dc3ea", "#6d9fe4", "#2a78d6", "#104281"]
FAIXA = SEQ[1]             # intervalo de confianca: o azul do teste, lavado
RECUO_SETA = 6.5           # pt: a seta para antes do centro do marcador, sem cobri-lo

ALVO = "SOH"
FIM_DE_VIDA = 80.0         # limiar de 80% do artigo, em SOH (%)

# Ficam brutas ao lado das relativas: ambient_temperature e cycle nao ganham
# referencia em normalizar.py, e current_load e o protocolo (a corrente
# aplicada), que a versao relativa praticamente zera.
CONTEXTO = ["ambient_temperature", "current_load", "cycle"]
CONJUNTOS = ("relativas", "brutas", "todas")
NOME_CONJUNTO = {"relativas": "atributos relativos ao início de vida",
                 "brutas": "atributos brutos", "todas": "todos os atributos"}
# As cores e formas de normalizar.py: bruto em circulo vermelho, relativo em
# losango azul. O trio passa o validador de daltonismo em todos os pares (pior
# par deutan dE 13,0), e a forma sustenta a identidade impressa em preto e branco.
COR_CONJUNTO = {"relativas": (PAL[0], "D"), "brutas": (PAL[7], "o"),
                "todas": (PAL[6], "s")}
# No terminal e nos CSV os nomes ficam sem acento, como no resto do projeto; o
# acento volta so nos graficos, que vao para o artigo.
ROTULO_MODELO = {"Regressao logistica": "Regressão logística",
                 "Regressao logistica melhorada": "Regressão logística melhorada",
                 "Gradient Boosting monotonico": "Gradient Boosting monotônico",
                 "SVM (RBF), suavizado": "SVM (RBF), suavizado"}
# Apelido no terminal, onde a tabela por celula tem uma coluna por modelo, e
# nome das colunas de cada referencia em predicoes_teste.csv.
CURTO = {"Regressao logistica": "logistica", "SVM (RBF)": "SVM",
         "Random Forest": "RF", "Gradient Boosting": "GB"}
SLUG = {"Regressao logistica": "regressao_logistica", "SVM (RBF)": "svm",
        "Random Forest": "random_forest", "Gradient Boosting": "gradient_boosting",
        "Regressao logistica melhorada": "regressao_logistica_melhorada",
        "Ensemble": "ensemble"}
LOGISTICA, MELHORADA = "Regressao logistica", "Regressao logistica melhorada"
SVM_SUAVE, GB_MONO = "SVM (RBF), suavizado", "Gradient Boosting monotonico"
ENSEMBLE = "Ensemble"
# Rampa sequencial do erro: o laranja que marca os erros nos outros graficos, do
# quase-nada ao escuro, com a luminosidade (OKLCH) caindo a cada passo.
SEQ_ERRO = ["#f0efec", "#f7d9c9", "#f4b394", "#ef8c5f", "#eb6834", "#bf4a1b", "#86300c"]

# k impar: no voto por maioria entre duas classes nao ha empate.
GRADE_K = [1, 3, 5, 7, 9, 11, 15, 21, 25, 31, 41, 51, 61, 81, 101, 151, 201]
TOLERANCIA_K = 0.01        # acuracia balanceada; com 25 celulas, menos que isso e ruido
N_VIZINHOS_CSV = 3         # vizinhos listados por previsao em predicoes_teste.csv
C_PADRAO = 1.0             # o do scikit-learn, o da logistica do artigo
GRADE_C = [1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2, 0.1, 0.3, C_PADRAO, 3.0, 10.0]
# Media movel exponencial da logistica melhorada: alfa = 2 / (JANELA_MEDIA + 1).
# E a janela da referencia de inicio de vida de normalizar.py; nao foi ajustada.
JANELA_MEDIA = 5
# O sinal fisico de cada sinal no escore de fim de vida, imposto ao Gradient
# Boosting do ensemble; o que nao esta aqui fica livre.
SINAL_FIM_DE_VIDA = {"ciclo_par": 1, "re_rel": 1, "rct_rel": 1, "rectified_impedance_rel": 1,
                     "voltage_load_rel": -1, "voltage_measured_rel": -1}
# Arvores rasas, folhas grandes e passo curto: fixados, nao ajustados.
GB_RASO = dict(learning_rate=0.05, max_iter=200, max_leaf_nodes=8, min_samples_leaf=40,
               l2_regularization=5.0)
FOLDS_ALEATORIOS = 5       # particao vazada, so para medir o vazamento
N_BOOT = 2000              # reamostragens de celulas para o intervalo do teste
PERTO_DO_LIMIAR = 5.0      # p.p. de SOH; erro a essa distancia de 80% e fronteira
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


def sinal(v, casas=1):
    """+7,4 / −1,3: uma diferenca com sinal, nos graficos. O que arredonda a zero sai 0,0."""
    v = round(float(v), casas) + 0.0
    return ("+" if v > 0 else "") + virg(v, casas)


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
    for f, etapa in ((ENTRADA, "normalizar.py"), (BRUTA, "limpeza.py")):
        if not f.exists():
            p(f"ERRO: {f.relative_to(RAIZ)} nao existe.")
            p(f"    Rode antes: python src/{etapa}")
            sys.exit(1)
    return mods


# ---------------------------------------------------------------------------
# dados
# ---------------------------------------------------------------------------
def carregar(mods):
    """Tabela normalizada, com o rotulo de fim de vida e o ciclo sem escala."""
    pd = mods["pandas"]
    df = pd.read_csv(ENTRADA)
    if not any(c.endswith("_rel") for c in df.columns):
        p("ERRO: dados_normalizados.csv nao tem as colunas relativas (_rel).")
        p("    Rode antes: python src/normalizar.py   (sem --so-brutas)")
        sys.exit(1)
    ciclo = pd.read_csv(BRUTA, usecols=["battery_id", "test_id", "cycle"])
    df = df.merge(ciclo.rename(columns={"cycle": "ciclo"}),
                  on=["battery_id", "test_id"], how="left", validate="one_to_one")
    df["fim_de_vida"] = (df[ALVO] < FIM_DE_VIDA).astype(int)
    return suavizar(df)


def suavizar(df):
    """A idade no par e as colunas _suave, que so a logistica melhorada usa.

    A media movel percorre cada par em ordem cronologica e so enxerga as
    descargas ate a atual. Lacuna de impedancia repete o ultimo valor do par; a
    que abre o par fica para a imputacao de preparo(). A ordem das linhas nao
    muda: dela dependem os desempates do kNN e o sorteio do Random Forest.
    """
    chave = ["battery_id", "test_condition"]
    df["ciclo_par"] = df.ciclo - df.groupby(chave).ciclo.transform("min")
    rel = sorted(c for c in df.columns if c.endswith("_rel"))
    suave = df.sort_values(chave + ["ciclo"]).groupby(chave)[rel].transform(
        lambda s: s.ffill().ewm(span=JANELA_MEDIA, min_periods=1).mean())
    return df.join(suave.add_suffix("_suave"))


def conjuntos(df):
    """Os tres conjuntos de atributos, fixados antes de olhar resultado.

    Um conjunto so entra se todas as colunas dele existem: normalizar.py
    --so-relativas descarta as brutas, e ai so o relativo roda.
    """
    rel = sorted(c for c in df.columns if c.endswith("_rel"))
    contexto = [c for c in CONTEXTO if c in df.columns]
    brutas = sorted({c[:-4] for c in rel} | set(contexto))
    todos = {"relativas": rel + contexto, "brutas": brutas, "todas": brutas + rel}
    return {n: cols for n, cols in todos.items() if set(cols) <= set(df.columns)}


def passos_logistica(conj, c):
    """Da logistica do artigo a melhorada, uma troca por vez: (passo, colunas, C)."""
    artigo = conj["relativas"]
    idade = ["ciclo_par" if x == "cycle" else x for x in artigo]
    suave = [x + "_suave" if x.endswith("_rel") else x for x in idade]
    return [("artigo", artigo, C_PADRAO), ("C menor", artigo, c),
            ("idade no par", idade, c), ("media movel", suave, c)]


def condicao(c):
    """'2 A / 24 C' -> '2 A / 24 °C', para os graficos."""
    return c[:-1] + "°C" if c.endswith(" C") else c


def curto(nome):
    """'kNN (k = 25)' -> 'kNN'; as referencias pelo apelido de CURTO."""
    return CURTO.get(nome, nome.split(" (")[0])


# ---------------------------------------------------------------------------
# modelos e metricas
# ---------------------------------------------------------------------------
def preparo():
    """Imputacao e escala, sempre ajustadas so no treino de cada rodada.

    A tabela ja vem escalonada pelo treino inteiro; reescalar por rodada e o que
    impede a celula deixada de fora de pesar na propria escala. A mediana
    preenche as 15 lacunas, todas de impedancia, sem se deixar puxar por valor
    extremo.
    """
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler())


def knn(k):
    from sklearn.neighbors import KNeighborsClassifier
    from sklearn.pipeline import make_pipeline
    return make_pipeline(preparo(), KNeighborsClassifier(n_neighbors=k))


def logistica(c):
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    return make_pipeline(preparo(), LogisticRegression(C=c, max_iter=2000))


def referencias():
    """As familias dos trabalhos relacionados, com os hiperparametros padrao.

    max_iter da logistica e a unica excecao: com os pares colineares o padrao
    de 100 iteracoes nao converge.
    """
    from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.svm import SVC
    return {
        LOGISTICA: logistica(C_PADRAO),
        "SVM (RBF)": make_pipeline(preparo(), SVC()),
        "Random Forest": make_pipeline(preparo(), RandomForestClassifier(random_state=SEMENTE)),
        "Gradient Boosting": make_pipeline(
            preparo(), HistGradientBoostingClassifier(random_state=SEMENTE)),
    }


class Voto(BaseEstimator, ClassifierMixin):
    """Varios classificadores e uma decisao so.

    O escore de cada membro e a funcao de decisao dele dividida pelo desvio dela
    no treino, para as escalas se compararem; zero separa as classes em todos.
    No voto suave o escore do conjunto e a media; no majoritario, a mediana, que
    com um numero impar de membros tem o sinal da maioria — a decisao e o voto, e
    a AUC ainda tem um escore continuo para ordenar.
    """

    def __init__(self, membros=(), tipo="majoritario"):
        self.membros = membros
        self.tipo = tipo

    def fit(self, X, y):
        import numpy as np
        from sklearn.base import clone
        self.classes_ = np.array([0, 1])
        self.ajustados_ = [clone(m).fit(X, y) for m in self.membros]
        self.escalas_ = [float(m.decision_function(X).std()) for m in self.ajustados_]
        return self

    def decision_function(self, X):
        import numpy as np
        z = np.column_stack([m.decision_function(X) / e
                             for m, e in zip(self.ajustados_, self.escalas_)])
        return juntar(np, z, self.tipo)

    def predict(self, X):
        return (self.decision_function(X) > 0).astype(int)


def juntar(np, z, tipo):
    """Escores dos membros, um por coluna -> o escore do conjunto."""
    return np.median(z, axis=1) if tipo == "majoritario" else z.mean(axis=1)


def membros_ensemble(colunas, c):
    """Um membro por familia: linear, nucleo e arvores."""
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.svm import SVC
    sinais = [SINAL_FIM_DE_VIDA.get(x.removesuffix("_suave"), 0) for x in colunas]
    return {MELHORADA: logistica(c),
            SVM_SUAVE: make_pipeline(preparo(), SVC()),
            GB_MONO: make_pipeline(preparo(), HistGradientBoostingClassifier(
                monotonic_cst=sinais, random_state=SEMENTE, **GB_RASO))}


def acuracia_balanceada(np, y, pred):
    """Media da taxa de acerto de cada classe presente; o acaso fica em 0,5."""
    return float(np.mean([np.mean(pred[y == c] == c) for c in (0, 1) if (y == c).any()]))


def metricas(np, y, pred):
    """Matriz de confusao e o que se le dela; fim de vida e a classe positiva."""
    vp = int(((pred == 1) & (y == 1)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    vn = int(((pred == 0) & (y == 0)).sum())
    nan = float("nan")
    sens = vp / (vp + fn) if vp + fn else nan
    esp = vn / (vn + fp) if vn + fp else nan
    return {"acuracia_balanceada": (sens + esp) / 2,
            "acuracia": (vp + vn) / len(y),
            "sensibilidade": sens,
            "especificidade": esp,
            "precisao": vp / (vp + fp) if vp + fp else nan,
            "f1_fim_de_vida": 2 * vp / (2 * vp + fp + fn) if vp + fp + fn else nan,
            "vp": vp, "fn": fn, "fp": fp, "vn": vn, "descargas": len(y)}


def pontuar(modelo, X):
    """Escore continuo de fim de vida, para a AUC.

    A probabilidade de fim de vida quando o modelo a tem (no kNN, a fracao de
    vizinhos em fim de vida); senao a funcao de decisao, como no SVM sem
    calibracao. A AUC so depende da ordem dos escores, nao da escala.
    """
    if hasattr(modelo, "predict_proba"):
        return modelo.predict_proba(X)[:, list(modelo.classes_).index(1)]
    return modelo.decision_function(X)


def auc(np, y, escore):
    """Area sob a curva ROC; nan quando so ha uma classe."""
    from sklearn.metrics import roc_auc_score
    return float(roc_auc_score(y, escore)) if len(np.unique(y)) == 2 else float("nan")


def votos_loco(mods, X, y, celulas, ks, rodada=None):
    """Fracao de vizinhos em fim de vida para cada k, uma celula de fora por vez.

    Os vizinhos de cada rodada sao procurados uma vez so, com o maior k, e o
    voto de cada k sai dos primeiros k da lista ordenada por distancia. Da o
    mesmo resultado que ajustar um KNeighborsClassifier por k, numa fracao do
    tempo. `rodada(X, te)`, quando dada, devolve o X da rodada: com --com-grupo,
    os indicadores do agrupamento refeito sem a celula de fora.
    """
    np = mods["numpy"]
    from sklearn.neighbors import NearestNeighbors
    ks = np.asarray(ks)
    votos = np.zeros((len(y), len(ks)))
    for c in np.unique(celulas):
        te = celulas == c
        Xr = X if rodada is None else rodada(X, te)
        prep = preparo().fit(Xr[~te])
        nn = NearestNeighbors(n_neighbors=int(ks.max())).fit(prep.transform(Xr[~te]))
        _, idx = nn.kneighbors(prep.transform(Xr[te]))
        votos[te] = np.cumsum(y[~te][idx], axis=1)[:, ks - 1] / ks
    return votos


def votos_loco_grupo(mods, tr, X, y, perfil, k_grupos, ks):
    """Como votos_loco, mas cada descarga so consulta vizinhas do mesmo grupo.

    O grupo e o de comportamento do modulo 2, refeito a cada rodada por
    grupos.ajustar so com as celulas de treino da rodada; os pares da celula
    deixada de fora entram no grupo de centroide mais proximo, entao nem os
    grupos viram a celula avaliada. Grupo com menos descargas que k vota com
    todas. Devolve os votos e, para cada grupo consultado, quantas celulas ele
    oferecia como vizinhas.
    """
    np = mods["numpy"]
    import grupos
    from sklearn.neighbors import NearestNeighbors
    ks = np.asarray(ks)
    cel = tr.battery_id.to_numpy()
    pares = list(zip(tr.battery_id, tr.test_condition))
    votos = np.zeros((len(y), len(ks)))
    oferta = []
    for c in np.unique(cel):
        te = cel == c
        pt = perfil[perfil.battery_id.isin(set(cel[~te]))].reset_index(drop=True)
        pn = perfil[perfil.battery_id == c].reset_index(drop=True)
        rot, encaixar = grupos.ajustar(mods, pt, k_grupos)
        grupo_de = dict(zip(zip(pt.battery_id, pt.condicao), rot))
        grupo_de.update(zip(zip(pn.battery_id, pn.condicao), encaixar(pn)))
        # Par sem perfil de comportamento (-1) consulta o treino todo.
        g = np.array([grupo_de.get(par, -1) for par in pares])
        prep = preparo().fit(X[~te])
        Xt = prep.transform(X)
        for gi in np.unique(g[te]):
            alvo = te & (g == gi)
            base = ~te & (g == gi) if gi >= 0 else ~te
            if not base.any():
                base = ~te
            oferta.append(len(set(cel[base])))
            kmax = min(int(ks.max()), int(base.sum()))
            _, idx = NearestNeighbors(n_neighbors=kmax).fit(Xt[base]).kneighbors(Xt[alvo])
            kk = np.minimum(ks, kmax)
            votos[alvo] = np.cumsum(y[base][idx], axis=1)[:, kk - 1] / kk
    return votos, oferta


def escolher_k(tab, tolerancia):
    """Em cada conjunto, o menor k a ate `tolerancia` do maximo."""
    return {c: int(tab.index[tab[c] >= tab[c].max() - tolerancia].min())
            for c in tab.columns}


def prever_fora(mods, modelo, X, y, grupos, rodada=None):
    """Cada grupo e previsto por um modelo ajustado sem ele: classe e escore.

    `rodada(X, te)`, quando dada, devolve o X da rodada (ver votos_loco).
    """
    np = mods["numpy"]
    from sklearn.base import clone
    pred, escore = np.zeros_like(y), np.zeros(len(y))
    for g in np.unique(grupos):
        te = grupos == g
        Xr = X if rodada is None else rodada(X, te)
        m = clone(modelo).fit(Xr[~te], y[~te])
        pred[te] = m.predict(Xr[te])
        escore[te] = pontuar(m, Xr[te])
    return pred, escore


def particao_aleatoria(mods, y):
    """Folds por descarga, estratificados pelo rotulo: a mesma celula cai dos dois lados."""
    np = mods["numpy"]
    from sklearn.model_selection import StratifiedKFold
    grupos = np.zeros(len(y), dtype=int)
    skf = StratifiedKFold(FOLDS_ALEATORIOS, shuffle=True, random_state=SEMENTE)
    for i, (_, te) in enumerate(skf.split(np.zeros(len(y)), y)):
        grupos[te] = i
    return grupos


def mesma_celula(mods, X, celulas, grupos, k):
    """Na particao aleatoria, de onde vem os vizinhos de cada descarga.

    Devolve a fracao de descargas cujo vizinho mais proximo e da mesma celula e
    a fracao media dos k vizinhos que sao da mesma celula. Deixando uma celula
    de fora, as duas sao zero por construcao.
    """
    np = mods["numpy"]
    from sklearn.neighbors import NearestNeighbors
    primeiro, todos = [], []
    for g in np.unique(grupos):
        te = grupos == g
        prep = preparo().fit(X[~te])
        _, idx = (NearestNeighbors(n_neighbors=k).fit(prep.transform(X[~te]))
                  .kneighbors(prep.transform(X[te])))
        viz = celulas[~te][idx]
        primeiro.append(viz[:, 0] == celulas[te])
        todos.append((viz == celulas[te][:, None]).mean(axis=1))
    return float(np.concatenate(primeiro).mean()), float(np.concatenate(todos).mean())


def reamostrar(mods, y, preds, celulas, metrica=None):
    """Uma metrica de cada modelo em N_BOOT reamostragens de celulas.

    A unidade independente e a celula, nao a descarga: descargas seguidas da
    mesma celula sao quase copias, e reamostra-las uma a uma daria um intervalo
    estreito demais. Todos os modelos passam pelas mesmas reamostragens, entao a
    diferenca entre dois deles e medida em pares — mais precisa que comparar
    intervalos lado a lado. Reamostragem sem uma das classes fica de fora.
    `metrica(y, valores)` e a acuracia balanceada sobre as classes previstas, a
    menos que se passe outra (a AUC recebe os escores); a semente fixa faz as
    duas metricas usarem as mesmas reamostragens.
    """
    np = mods["numpy"]
    if metrica is None:
        metrica = lambda yy, pr: acuracia_balanceada(np, yy, pr)
    rng = np.random.default_rng(SEMENTE)
    unicas = np.unique(celulas)
    linhas = {c: np.flatnonzero(celulas == c) for c in unicas}
    amostras = {m: [] for m in preds}
    for _ in range(N_BOOT):
        idx = np.concatenate([linhas[c] for c in rng.choice(unicas, len(unicas))])
        if len(np.unique(y[idx])) < 2:
            continue
        for m, pr in preds.items():
            amostras[m].append(metrica(y[idx], pr[idx]))
    return {m: np.asarray(v) for m, v in amostras.items()}


# ---------------------------------------------------------------------------
# as tres etapas
# ---------------------------------------------------------------------------
def etapa_k(mods, tr, conj, tolerancia, k_forcado, cod=None):
    """Curva de acuracia contra k em cada conjunto, e o k de cada um."""
    np, pd = mods["numpy"], mods["pandas"]
    y, cel = tr.fim_de_vida.to_numpy(), tr.battery_id.to_numpy()
    tab = {}
    for n, cols in conj.items():
        v = votos_loco(mods, tr[cols].to_numpy(), y, cel, GRADE_K,
                       cod.rodada(cols, cel) if cod else None)
        tab[n] = [acuracia_balanceada(np, y, (v[:, j] > 0.5).astype(int))
                  for j in range(len(GRADE_K))]
    tab = pd.DataFrame(tab, index=pd.Index(GRADE_K, name="k"))
    k_conj = escolher_k(tab, tolerancia)

    p(f"  {'k':>5} " + " ".join(f"{n:>10}" for n in tab.columns))
    for k, r in tab.iterrows():
        marca = " *" if k == k_conj["relativas"] else ""
        p(f"  {k:>5} " + " ".join(f"{v:>10.3f}" for v in r) + marca)
    melhor = tab.relativas
    p(f"  * k={k_conj['relativas']}: o menor k a ate {100 * tolerancia:.0f} p.p. do "
      f"maximo dos relativos ({melhor.max():.3f} em k={int(melhor.idxmax())})")
    outros = {n: k for n, k in k_conj.items() if n != "relativas"}
    if outros:
        p("  mesma regra nos outros conjuntos: "
          + ", ".join(f"{n} k={k}" for n, k in outros.items()))
    if k_forcado:
        p(f"  --k {k_forcado} sobrepoe a escolha, nos tres conjuntos")
        k_conj = {n: k_forcado for n in k_conj}
    return tab, k_conj


def etapa_comparacao(mods, tr, conj, k_conj, refs, cod=None):
    """Protocolo, atributos e algoritmo, so nas celulas de treino.

    Com `cod` (--com-grupo), so a validacao por celula troca o agrupamento a
    cada rodada; a particao aleatoria mistura celulas nos dois lados e fica com
    o agrupamento de todas as de treino.
    """
    np, pd = mods["numpy"], mods["pandas"]
    y, cel = tr.fim_de_vida.to_numpy(), tr.battery_id.to_numpy()
    aleat = particao_aleatoria(mods, y)
    nome_knn = f"kNN (k = {k_conj['relativas']})"
    modelos = {nome_knn: None, **refs}
    linhas, pred_val = [], {}
    for nome, modelo in modelos.items():
        t0 = time.time()
        for n, cols in conj.items():
            m = knn(k_conj[n]) if modelo is None else modelo
            X = tr[cols].to_numpy()
            esquemas = [("uma celula de fora", cel)]
            if n == "relativas":
                esquemas.append(("aleatoria por descarga", aleat))
            for esquema, grupos in esquemas:
                rodada = cod.rodada(cols, cel) if cod and grupos is cel else None
                pred, escore = prever_fora(mods, m, X, y, grupos, rodada)
                if n == "relativas" and grupos is cel:
                    pred_val[nome] = pred
                met = metricas(np, y, pred)
                # No CSV o kNN e "kNN" e o k vai na coluna propria: cada conjunto
                # tem o seu k, e o nome com o k do relativo enganaria. A matriz de
                # confusao (vp a vn) fica em todas as linhas.
                linhas.append({"modelo": "kNN" if modelo is None else nome,
                               "atributos": n, "validacao": esquema,
                               "k": k_conj[n] if modelo is None else None,
                               "acuracia_balanceada": met["acuracia_balanceada"],
                               "sensibilidade": met["sensibilidade"],
                               "especificidade": met["especificidade"],
                               "f1_fim_de_vida": met["f1_fim_de_vida"],
                               "auc": auc(np, y, escore),
                               **{c: met[c] for c in ("precisao", "acuracia",
                                                      "vp", "fn", "fp", "vn")}})
        p(f"  {nome:<22} {time.time() - t0:>5.0f}s")
    comp = pd.DataFrame(linhas)
    comp["k"] = comp.k.astype("Int64")

    piv = comp[comp.validacao == "uma celula de fora"].pivot(
        index="modelo", columns="atributos", values="acuracia_balanceada")
    piv["aleatoria"] = comp[comp.validacao == "aleatoria por descarga"].set_index(
        "modelo").acuracia_balanceada
    piv = piv.rename(index={"kNN": nome_knn}).loc[list(modelos)]
    p("")
    cols = [c for c in CONJUNTOS if c in piv.columns]
    p(f"  {'acuracia balanceada':<22} " + " ".join(f"{c:>10}" for c in cols)
      + f" {'aleatoria':>10} {'inflacao':>9}")
    for nome, r in piv.iterrows():
        p(f"  {nome:<22} " + " ".join(f"{r[c]:>10.3f}" for c in cols)
          + f" {r.aleatoria:>10.3f} {100 * (r.aleatoria - r.relativas):>+7.1f}pp")
    p("  colunas de atributos: uma celula de fora por vez; aleatoria: mesmos")
    p("  atributos relativos, particao por descarga (vazada)")

    piv_auc = comp[comp.validacao == "uma celula de fora"].pivot(
        index="modelo", columns="atributos", values="auc")
    piv_auc["aleatoria"] = comp[comp.validacao == "aleatoria por descarga"].set_index(
        "modelo").auc
    piv_auc = piv_auc.rename(index={"kNN": nome_knn}).loc[list(modelos)]
    p("")
    p(f"  {'AUC':<22} " + " ".join(f"{c:>10}" for c in cols) + f" {'aleatoria':>10}")
    for nome, r in piv_auc.iterrows():
        p(f"  {nome:<22} " + " ".join(f"{r[c]:>10.3f}" for c in cols) + f" {r.aleatoria:>10.3f}")
    p("  escores das 25 rodadas juntados antes do calculo")

    piv_f1 = comp[comp.validacao == "uma celula de fora"].pivot(
        index="modelo", columns="atributos", values="f1_fim_de_vida")
    piv_f1["aleatoria"] = comp[comp.validacao == "aleatoria por descarga"].set_index(
        "modelo").f1_fim_de_vida
    piv_f1 = piv_f1.rename(index={"kNN": nome_knn}).loc[list(modelos)]
    p("")
    p(f"  {'F1 (fim de vida)':<22} " + " ".join(f"{c:>10}" for c in cols) + f" {'aleatoria':>10}")
    for nome, r in piv_f1.iterrows():
        p(f"  {nome:<22} " + " ".join(f"{r[c]:>10.3f}" for c in cols) + f" {r.aleatoria:>10.3f}")

    perto, media = mesma_celula(mods, tr[conj["relativas"]].to_numpy(), cel, aleat,
                                k_conj["relativas"])
    p(f"  particao aleatoria: o vizinho mais proximo e da mesma celula em {perto:.1%}")
    p(f"  das descargas, e {media:.1%} dos {k_conj['relativas']} vizinhos tambem, "
      f"em media")

    # Quanto o acerto varia de uma celula para outra: e essa variacao que decide
    # se 8 celulas de teste bastam para ordenar algoritmos. A coluna `acuracia` e
    # a do kNN; cada referencia ganha a sua.
    por_cel = (pd.DataFrame({"battery_id": cel, "fim_de_vida": y,
                             "acerto": pred_val[nome_knn] == y})
               .groupby("battery_id")
               .agg(descargas=("acerto", "size"), fracao_fim_de_vida=("fim_de_vida", "mean"),
                    acuracia=("acerto", "mean"))
               .reset_index())
    for nome in refs:
        por_cel[f"acuracia_{SLUG[nome]}"] = por_cel.battery_id.map(
            pd.Series(pred_val[nome] == y).groupby(cel).mean())
    p("  acerto por celula de treino, quando ela e a deixada de fora:")
    for nome in modelos:
        col = "acuracia" if nome == nome_knn else f"acuracia_{SLUG[nome]}"
        q = por_cel[col].quantile([0, 0.25, 0.5, 1]).to_numpy()
        p(f"    {nome:<22} de {q[0]:.0%} a {q[3]:.0%} "
          f"(quartil inferior {q[1]:.0%}, mediana {q[2]:.0%})")
    return comp, piv, por_cel, nome_knn


def etapa_teste(mods, tr, te, conj, k, refs, nome_knn):
    """Ajuste nas 25 celulas de treino, uma avaliacao nas 8 de teste."""
    np, pd = mods["numpy"], mods["pandas"]
    from sklearn.base import clone
    cols = conj["relativas"]
    Xtr, Xte = tr[cols].to_numpy(), te[cols].to_numpy()
    y_tr, y_te = tr.fim_de_vida.to_numpy(), te.fim_de_vida.to_numpy()
    cel_te = te.battery_id.to_numpy()

    final = knn(k).fit(Xtr, y_tr)
    pred = final.predict(Xte)
    preds = {nome_knn: pred}
    escores = {nome_knn: pontuar(final, Xte)}
    for nome, modelo in refs.items():
        m = clone(modelo).fit(Xtr, y_tr)
        preds[nome] = m.predict(Xte)
        escores[nome] = pontuar(m, Xte)
    amostras = reamostrar(mods, y_te, preds, cel_te)
    amostras_auc = reamostrar(mods, y_te, escores, cel_te, lambda yy, s: auc(np, yy, s))
    amostras_f1 = reamostrar(mods, y_te, preds, cel_te,
                             lambda yy, pr: metricas(np, yy, pr)["f1_fim_de_vida"])
    # As outras taxas da matriz de confusao, com o mesmo intervalo: o grafico por
    # algoritmo mostra todas. A precisao fica indefinida na reamostragem em que o
    # modelo nao da alarme nenhum, e o percentil ignora essas.
    amostras_taxas = {c: reamostrar(mods, y_te, preds, cel_te,
                                    lambda yy, pr, c=c: metricas(np, yy, pr)[c])
                      for c in ("acuracia", "sensibilidade", "especificidade", "precisao")}
    f1_knn = metricas(np, y_te, pred)["f1_fim_de_vida"]
    # Bonferroni: com uma comparacao por referencia, cada intervalo pareado
    # precisa de 95% divididos entre elas para o conjunto manter os 95%.
    alfa = 0.05 / max(len(refs), 1)
    auc_knn = auc(np, y_te, escores[nome_knn])
    linhas = []
    for nome, pr in preds.items():
        lo, hi = np.percentile(amostras[nome], [2.5, 97.5])
        m = metricas(np, y_te, pr)
        lin = {"modelo": nome, **m, "ic95_inferior": lo, "ic95_superior": hi,
               "auc": auc(np, y_te, escores[nome])}
        lin["auc_ic95_inferior"], lin["auc_ic95_superior"] = np.percentile(
            amostras_auc[nome], [2.5, 97.5])
        lin["f1_ic95_inferior"], lin["f1_ic95_superior"] = np.percentile(
            amostras_f1[nome], [2.5, 97.5])
        for c, am in amostras_taxas.items():
            lin[f"{c}_ic95_inferior"], lin[f"{c}_ic95_superior"] = np.nanpercentile(
                am[nome], [2.5, 97.5])
        if nome != nome_knn:
            dif = amostras[nome] - amostras[nome_knn]
            lin["diferenca_para_knn"] = m["acuracia_balanceada"] - acuracia_balanceada(
                np, y_te, pred)
            lin["dif_ic95_inferior"], lin["dif_ic95_superior"] = np.percentile(dif, [2.5, 97.5])
            lin["dif_bonferroni_inferior"], lin["dif_bonferroni_superior"] = np.percentile(
                dif, [100 * alfa / 2, 100 * (1 - alfa / 2)])
            dif_auc = amostras_auc[nome] - amostras_auc[nome_knn]
            lin["diferenca_auc_para_knn"] = lin["auc"] - auc_knn
            lin["dif_auc_ic95_inferior"], lin["dif_auc_ic95_superior"] = np.percentile(
                dif_auc, [2.5, 97.5])
            lin["dif_auc_bonferroni_inferior"], lin["dif_auc_bonferroni_superior"] = (
                np.percentile(dif_auc, [100 * alfa / 2, 100 * (1 - alfa / 2)]))
            dif_f1 = amostras_f1[nome] - amostras_f1[nome_knn]
            lin["diferenca_f1_para_knn"] = m["f1_fim_de_vida"] - f1_knn
            lin["dif_f1_ic95_inferior"], lin["dif_f1_ic95_superior"] = np.percentile(
                dif_f1, [2.5, 97.5])
            lin["dif_f1_bonferroni_inferior"], lin["dif_f1_bonferroni_superior"] = (
                np.percentile(dif_f1, [100 * alfa / 2, 100 * (1 - alfa / 2)]))
        linhas.append(lin)
    res = pd.DataFrame(linhas)

    p(f"  {'':<22} {'acur.bal':>8} {'IC 95% (celulas)':>17} {'sensib.':>8} "
      f"{'especif.':>8} {'precisao':>8}")
    for r in res.itertuples(index=False):
        p(f"  {r.modelo:<22} {r.acuracia_balanceada:>8.3f}    "
          f"[{r.ic95_inferior:.3f}, {r.ic95_superior:.3f}] "
          f"{r.sensibilidade:>8.3f} {r.especificidade:>8.3f} {r.precisao:>8.3f}")
    p(f"  {'':<22} {'F1':>8} {'IC 95% (celulas)':>17} {'AUC':>8} {'IC 95% (celulas)':>17}")
    for r in res.itertuples(index=False):
        p(f"  {r.modelo:<22} {r.f1_fim_de_vida:>8.3f}    "
          f"[{r.f1_ic95_inferior:.3f}, {r.f1_ic95_superior:.3f}] {r.auc:>8.3f}    "
          f"[{r.auc_ic95_inferior:.3f}, {r.auc_ic95_superior:.3f}]")
    p("  sensibilidade: fim de vida detectado; especificidade: saudavel reconhecida;")
    p("  precisao: alarmes que eram fim de vida; F1: media harmonica de precisao e")
    p("  sensibilidade; AUC: ordem dos escores, em todos os limiares")
    if refs:
        p("")
        p("  diferenca para o kNN, pareada nas mesmas reamostragens de celulas:")
        for r in res.iloc[1:].itertuples(index=False):
            exclui = "exclui" if r.dif_ic95_inferior > 0 or r.dif_ic95_superior < 0 else "inclui"
            bonf = ("exclui" if r.dif_bonferroni_inferior > 0 or r.dif_bonferroni_superior < 0
                    else "inclui")
            p(f"    {r.modelo:<22} {100 * r.diferenca_para_knn:>+6.1f} p.p.  IC 95% "
              f"[{100 * r.dif_ic95_inferior:+.1f}, {100 * r.dif_ic95_superior:+.1f}] "
              f"{exclui} o zero; com Bonferroni [{100 * r.dif_bonferroni_inferior:+.1f}, "
              f"{100 * r.dif_bonferroni_superior:+.1f}] {bonf}")
        p("")
        p("  diferenca de AUC para o kNN, nas mesmas reamostragens:")
        for r in res.iloc[1:].itertuples(index=False):
            exclui = ("exclui" if r.dif_auc_ic95_inferior > 0 or r.dif_auc_ic95_superior < 0
                      else "inclui")
            bonf = ("exclui" if r.dif_auc_bonferroni_inferior > 0
                    or r.dif_auc_bonferroni_superior < 0 else "inclui")
            p(f"    {r.modelo:<22} {r.diferenca_auc_para_knn:>+6.3f}  IC 95% "
              f"[{r.dif_auc_ic95_inferior:+.3f}, {r.dif_auc_ic95_superior:+.3f}] "
              f"{exclui} o zero; com Bonferroni [{r.dif_auc_bonferroni_inferior:+.3f}, "
              f"{r.dif_auc_bonferroni_superior:+.3f}] {bonf}")
        p("")
        p("  diferenca de F1 para o kNN, nas mesmas reamostragens:")
        for r in res.iloc[1:].itertuples(index=False):
            exclui = ("exclui" if r.dif_f1_ic95_inferior > 0 or r.dif_f1_ic95_superior < 0
                      else "inclui")
            bonf = ("exclui" if r.dif_f1_bonferroni_inferior > 0
                    or r.dif_f1_bonferroni_superior < 0 else "inclui")
            p(f"    {r.modelo:<22} {r.diferenca_f1_para_knn:>+6.3f}  IC 95% "
              f"[{r.dif_f1_ic95_inferior:+.3f}, {r.dif_f1_ic95_superior:+.3f}] "
              f"{exclui} o zero; com Bonferroni [{r.dif_f1_bonferroni_inferior:+.3f}, "
              f"{r.dif_f1_bonferroni_superior:+.3f}] {bonf}")

    # Explicacao por exemplo: os vizinhos de cada previsao, com ciclo e SOH.
    dist, idx = final[-1].kneighbors(final[0].transform(Xte), n_neighbors=N_VIZINHOS_CSV)
    viz = [
        "; ".join(f"{tr.battery_id.iat[j]} ciclo {int(tr.ciclo.iat[j])} "
                  f"(SOH {tr[ALVO].iat[j]:.0f}%)" for j in linha)
        for linha in idx]
    votos = final.predict_proba(Xte)[:, list(final[-1].classes_).index(1)]
    prev = te[["battery_id", "test_condition", "ciclo", ALVO, "fim_de_vida"]].assign(
        previsto=pred, votos_fim_de_vida=votos, acerto=pred == y_te,
        vizinhos_mais_proximos=viz)
    # As referencias ao lado: a classe prevista e o escore que a AUC ordena.
    for nome in refs:
        prev[f"previsto_{SLUG[nome]}"] = preds[nome]
        prev[f"escore_{SLUG[nome]}"] = escores[nome]

    # Por celula, para cada modelo: onde cada um erra, e de que jeito.
    por = []
    for nome, pr in preds.items():
        t = (te[["battery_id", "test_condition", "fim_de_vida", ALVO]]
             .assign(previsto=pr, acerto=pr == y_te, alarme_falso=(pr == 1) & (y_te == 0),
                     nao_detectado=(pr == 0) & (y_te == 1))
             .groupby(["battery_id", "test_condition"])
             .agg(descargas=("acerto", "size"), fim_de_vida_real=("fim_de_vida", "sum"),
                  fim_de_vida_previsto=("previsto", "sum"), acuracia=("acerto", "mean"),
                  alarmes_falsos=("alarme_falso", "sum"),
                  nao_detectados=("nao_detectado", "sum"), soh_minimo=(ALVO, "min"))
             .reset_index())
        t.insert(0, "modelo", nome)
        por.append(t)
    por = pd.concat(por, ignore_index=True)
    p("")
    p(f"  por celula, kNN (k = {k}):")
    for r in por[por.modelo == nome_knn].itertuples(index=False):
        p(f"    {r.battery_id} {r.test_condition:<11} {r.descargas:>4} descargas, "
          f"{r.fim_de_vida_real:>3} em fim de vida, acerto {r.acuracia:.0%}, "
          f"{r.alarmes_falsos} alarme(s) falso(s), {r.nao_detectados} nao detectado(s)")
    if refs:
        tab = por.pivot(index=["battery_id", "test_condition"], columns="modelo",
                        values="acuracia")[list(preds)]
        p("")
        p("  acerto por celula, todos os algoritmos:")
        p(f"    {'':<17} " + " ".join(f"{curto(n):>9}" for n in tab.columns))
        for (b, c), r in tab.iterrows():
            p(f"    {b} {c:<11} " + " ".join(f"{v:>9.0%}" for v in r))
    erros = prev[~prev.acerto]
    if len(erros):
        perto = (erros[ALVO] - FIM_DE_VIDA).abs() < PERTO_DO_LIMIAR
        p(f"  {perto.mean():.0%} dos {len(erros)} erros ficam a menos de "
          f"{PERTO_DO_LIMIAR:.0f} p.p. do limiar de {FIM_DE_VIDA:.0f}%")
    return res, prev, por, escores, y_te


def etapa_variante(mods, tr, conj, tab, k_base, tolerancia):
    """Pos-hoc: vizinhos so do mesmo grupo de comportamento, so na validacao.

    Surgiu da analise dos erros no teste — os vizinhos que enganaram B0018
    vinham de outros grupos —, entao o teste nao pode julga-la: so a validacao
    nas celulas de treino entra aqui.
    """
    np, pd = mods["numpy"], mods["pandas"]
    import grupos
    perfil = grupos.perfis(mods, pd.read_csv(CURVAS))
    k_grupos = int(pd.read_csv(GRUPOS).query("not extremo").grupo.nunique())
    y, cel = tr.fim_de_vida.to_numpy(), tr.battery_id.to_numpy()
    X = tr[conj["relativas"]].to_numpy()
    votos, oferta = votos_loco_grupo(mods, tr, X, y, perfil, k_grupos, GRADE_K)
    curva = pd.DataFrame(
        {"sem_restricao": tab.relativas.to_numpy(),
         "mesmo_grupo": [acuracia_balanceada(np, y, (votos[:, j] > 0.5).astype(int))
                         for j in range(len(GRADE_K))]},
        index=tab.index)
    k_var = escolher_k(curva[["mesmo_grupo"]], tolerancia)["mesmo_grupo"]
    base, _ = prever_fora(mods, knn(k_base), X, y, cel)
    var = (votos[:, GRADE_K.index(k_var)] > 0.5).astype(int)

    p(f"  agrupamento de grupos.py ({k_grupos} grupos + extremos) refeito a cada rodada so "
      f"com as celulas de treino;")
    p("  a celula de fora entra no grupo de centroide mais proximo")
    p(f"  celulas que o grupo oferece como vizinhas: mediana {np.median(oferta):.0f} "
      f"(de {min(oferta)} a {max(oferta)}); sem restricao, {len(np.unique(cel)) - 1}")
    p(f"  {'k':>5} {'sem restricao':>14} {'mesmo grupo':>12}")
    for k, r in curva.iterrows():
        marca = " *" if k == k_var else ""
        p(f"  {k:>5} {r.sem_restricao:>14.3f} {r.mesmo_grupo:>12.3f}{marca}")
    resumo = {"k_base": k_base, "k_var": k_var, "oferta_mediana": float(np.median(oferta))}
    for nome, k, pr in (("sem restricao", k_base, base), ("mesmo grupo", k_var, var)):
        m = metricas(np, y, pr)
        resumo[nome] = m["acuracia_balanceada"]
        p(f"  {nome:<14} k={k:<3} acur.bal {m['acuracia_balanceada']:.3f}, sensib. "
          f"{m['sensibilidade']:.3f}, especif. {m['especificidade']:.3f}")
    acerto = (pd.DataFrame({"battery_id": cel, "acerto": var == y})
              .groupby("battery_id").acerto.mean().rename("acuracia_mesmo_grupo"))
    antes = pd.DataFrame({"battery_id": cel, "acerto": base == y}).groupby(
        "battery_id").acerto.mean()
    mudanca = (acerto - antes).sort_values()
    p("  celulas que mais mudam de acerto: " + ", ".join(
        f"{b} {antes[b]:.0%} -> {acerto[b]:.0%}"
        for b in list(mudanca.index[:3]) + list(mudanca.index[-2:])))
    return curva, acerto, resumo


def por_celula(te, preds):
    """Acertos, alarmes falsos e fins de vida perdidos de cada modelo em cada par de teste."""
    import pandas as pd
    y = te.fim_de_vida.to_numpy()
    partes = []
    for modelo, pr in preds.items():
        t = (te[["battery_id", "test_condition", "fim_de_vida"]]
             .assign(acerto=pr == y, alarme_falso=(pr == 1) & (y == 0),
                     nao_detectado=(pr == 0) & (y == 1))
             .groupby(["battery_id", "test_condition"])
             .agg(descargas=("acerto", "size"), fim_de_vida_real=("fim_de_vida", "sum"),
                  acuracia=("acerto", "mean"), alarmes_falsos=("alarme_falso", "sum"),
                  nao_detectados=("nao_detectado", "sum"))
             .reset_index())
        t.insert(0, "modelo", modelo)
        partes.append(t)
    return pd.concat(partes, ignore_index=True)


def escolher_c(serie, tolerancia):
    """O menor C (mais regularizado) a ate `tolerancia` do maximo, a regra do k."""
    return float(serie.index[serie >= serie.max() - tolerancia].min())


def etapa_logistica(mods, tr, te, conj, tolerancia):
    """Pos-hoc: a logistica melhorada, uma troca por vez, contra a do artigo.

    C so ve a validacao nas celulas de treino. Cada passo sai na validacao, no
    teste e nas 33 celulas com uma de fora por vez; a diferenca para a do artigo
    e pareada nas mesmas reamostragens de celulas.
    """
    np, pd = mods["numpy"], mods["pandas"]
    y_tr, y_te = tr.fim_de_vida.to_numpy(), te.fim_de_vida.to_numpy()
    cel_tr, cel_te = tr.battery_id.to_numpy(), te.battery_id.to_numpy()

    colunas = {nome: cols for nome, cols, _ in passos_logistica(conj, None)
               if nome != "C menor"}
    tab = pd.DataFrame(
        {nome: [acuracia_balanceada(np, y_tr, prever_fora(
                    mods, logistica(c), tr[cols].to_numpy(), y_tr, cel_tr)[0])
                for c in GRADE_C] for nome, cols in colunas.items()},
        index=pd.Index(GRADE_C, name="C"))
    c_final = escolher_c(tab["media movel"], tolerancia)
    p(f"  {'C':>7} " + " ".join(f"{n:>13}" for n in tab.columns))
    for c, r in tab.iterrows():
        marca = " *" if c == c_final else ""
        p(f"  {c:>7g} " + " ".join(f"{v:>13.3f}" for v in r) + marca)
    p(f"  * C={c_final:g}: o menor a ate {100 * tolerancia:.0f} p.p. do maximo com a media "
      f"movel, o passo final; a do artigo usa C={C_PADRAO:g}")

    tudo = pd.concat([tr, te], ignore_index=True)
    y_33, cel_33 = tudo.fim_de_vida.to_numpy(), tudo.battery_id.to_numpy()
    alvos = {"validacao": (y_tr, cel_tr), "teste": (y_te, cel_te), "33 celulas": (y_33, cel_33)}
    passos = passos_logistica(conj, c_final)
    preds, escores, coefs = {a: {} for a in alvos}, {a: {} for a in alvos}, []
    for nome, cols, c in passos:
        modelo = logistica(c)
        X = tr[cols].to_numpy()
        preds["validacao"][nome], escores["validacao"][nome] = prever_fora(
            mods, modelo, X, y_tr, cel_tr)
        preds["33 celulas"][nome], escores["33 celulas"][nome] = prever_fora(
            mods, modelo, tudo[cols].to_numpy(), y_33, cel_33)
        final = logistica(c).fit(X, y_tr)
        preds["teste"][nome] = final.predict(te[cols].to_numpy())
        escores["teste"][nome] = pontuar(final, te[cols].to_numpy())
        if nome in ("artigo", "media movel"):
            # O quanto cada coeficiente se mexe quando uma celula sai do treino.
            rodadas = np.array([logistica(c).fit(X[cel_tr != b], y_tr[cel_tr != b])[-1].coef_[0]
                                for b in np.unique(cel_tr)])
            coefs.append(pd.DataFrame({
                "modelo": LOGISTICA if nome == "artigo" else MELHORADA, "atributo": cols,
                "coeficiente": final[-1].coef_[0], "minimo_rodadas": rodadas.min(axis=0),
                "maximo_rodadas": rodadas.max(axis=0)}))

    linhas = []
    for alvo, (y, cel) in alvos.items():
        amostras = reamostrar(mods, y, preds[alvo], cel)
        base = acuracia_balanceada(np, y, preds[alvo]["artigo"])
        for nome, cols, c in passos:
            m = metricas(np, y, preds[alvo][nome])
            lin = {"passo": nome, "C": c, "avaliacao": alvo, **m,
                   "auc": auc(np, y, escores[alvo][nome])}
            lin["ic95_inferior"], lin["ic95_superior"] = np.percentile(
                amostras[nome], [2.5, 97.5])
            if nome != "artigo":
                lin["diferenca_para_artigo"] = m["acuracia_balanceada"] - base
                lin["dif_ic95_inferior"], lin["dif_ic95_superior"] = np.percentile(
                    amostras[nome] - amostras["artigo"], [2.5, 97.5])
            linhas.append(lin)
    res = pd.DataFrame(linhas)

    piv = res.pivot(index="passo", columns="avaliacao", values="acuracia_balanceada")
    p("")
    p(f"  {'acuracia balanceada':<20} " + " ".join(f"{a:>11}" for a in alvos))
    for nome, _cols, c in passos:
        p(f"  {nome:<14} C={c:<4g} " + " ".join(f"{piv.loc[nome, a]:>11.3f}" for a in alvos))
    p("  cada linha mantem as trocas das anteriores; 33 celulas: treino e teste juntos,")
    p("  uma celula de fora por vez, com o C que saiu so do treino")
    p("")
    for r in res[res.passo == "media movel"].itertuples(index=False):
        exclui = "exclui" if r.dif_ic95_inferior > 0 or r.dif_ic95_superior < 0 else "inclui"
        p(f"  {r.avaliacao:<11} sensib. {r.sensibilidade:.3f}, especif. {r.especificidade:.3f}, "
          f"F1 {r.f1_fim_de_vida:.3f}, AUC {r.auc:.3f}; diferenca para a do artigo "
          f"{100 * r.diferenca_para_artigo:+.1f} p.p. IC 95% [{100 * r.dif_ic95_inferior:+.1f}, "
          f"{100 * r.dif_ic95_superior:+.1f}] {exclui} o zero")

    prev = {f"previsto_{SLUG[MELHORADA]}": preds["teste"]["media movel"],
            f"escore_{SLUG[MELHORADA]}": escores["teste"]["media movel"]}
    por = por_celula(te, {LOGISTICA: preds["teste"]["artigo"],
                          MELHORADA: preds["teste"]["media movel"]})
    p("")
    p("  acerto por celula de teste, artigo -> melhorada:")
    ac = por.pivot(index=["battery_id", "test_condition"], columns="modelo", values="acuracia")
    for (b, cond), r in ac.iterrows():
        p(f"    {b} {cond:<11} {r[LOGISTICA]:>5.0%} -> {r[MELHORADA]:>4.0%}")
    return tab, c_final, res, pd.concat(coefs, ignore_index=True), por, prev


def etapa_ensemble(mods, tr, te, conj, c, refs):
    """Pos-hoc: o ensemble, com a composicao e o tipo de voto escolhidos na validacao.

    `c` e o da logistica melhorada. Os membros, o ensemble e as referencias do
    artigo saem na validacao, no teste e nas 33 celulas com uma de fora por vez;
    a diferenca para a logistica melhorada e pareada nas mesmas reamostragens.
    """
    np, pd = mods["numpy"], mods["pandas"]
    from itertools import combinations
    from sklearn.base import clone
    y_tr, y_te = tr.fim_de_vida.to_numpy(), te.fim_de_vida.to_numpy()
    cel_tr, cel_te = tr.battery_id.to_numpy(), te.battery_id.to_numpy()
    suaves = passos_logistica(conj, c)[-1][1]
    membros = membros_ensemble(suaves, c)

    # Os escores dos membros fora da celula, ja na escala do treino da rodada.
    X = tr[suaves].to_numpy()
    z = np.zeros((len(y_tr), len(membros)))
    for b in np.unique(cel_tr):
        fora = cel_tr == b
        for j, m in enumerate(membros.values()):
            m = clone(m).fit(X[~fora], y_tr[~fora])
            z[fora, j] = m.decision_function(X[fora]) / m.decision_function(X[~fora]).std()
    nomes, linhas = list(membros), []
    for n in (2, 3):
        for q in combinations(range(len(nomes)), n):
            # O voto majoritario de dois empata; so o de tres decide.
            for tipo in ("suave", "majoritario") if n % 2 else ("suave",):
                s = juntar(np, z[:, list(q)], tipo)
                linhas.append({"membros": " + ".join(nomes[j] for j in q), "voto": tipo,
                               "acuracia_balanceada": acuracia_balanceada(
                                   np, y_tr, (s > 0).astype(int)),
                               "auc": auc(np, y_tr, s), "quais": q})
    comp = pd.DataFrame(linhas).sort_values("acuracia_balanceada", ascending=False,
                                            ignore_index=True)
    tipo, quais = comp.voto[0], comp.quais[0]
    p(f"  {'composicao, so na validacao':<84} {'voto':<12} {'acur.bal':>8} {'AUC':>6}")
    for i, r in comp.iterrows():
        p(f"  {r.membros:<84} {r.voto:<12} {r.acuracia_balanceada:>8.3f} {r.auc:>6.3f}"
          + (" *" if i == 0 else ""))

    escolhidos = [nomes[j] for j in quais]
    ensemble = Voto([membros[n] for n in escolhidos], tipo)
    rel = conj["relativas"]
    modelos = {**{n: (m, rel) for n, m in refs.items()},
               **{n: (m, suaves) for n, m in membros.items()}, ENSEMBLE: (ensemble, suaves)}
    tudo = pd.concat([tr, te], ignore_index=True)
    alvos = {"validacao": (y_tr, cel_tr), "teste": (y_te, cel_te),
             "33 celulas": (tudo.fim_de_vida.to_numpy(), tudo.battery_id.to_numpy())}
    preds, escores = {a: {} for a in alvos}, {a: {} for a in alvos}
    for nome, (m, cols) in modelos.items():
        for alvo, d in (("validacao", tr), ("33 celulas", tudo)):
            preds[alvo][nome], escores[alvo][nome] = prever_fora(
                mods, m, d[cols].to_numpy(), *alvos[alvo])
        final = clone(m).fit(tr[cols].to_numpy(), y_tr)
        preds["teste"][nome] = final.predict(te[cols].to_numpy())
        escores["teste"][nome] = pontuar(final, te[cols].to_numpy())

    linhas = []
    for alvo, (y, cel) in alvos.items():
        amostras = reamostrar(mods, y, preds[alvo], cel)
        base = acuracia_balanceada(np, y, preds[alvo][MELHORADA])
        for nome in modelos:
            m = metricas(np, y, preds[alvo][nome])
            lin = {"modelo": nome, "avaliacao": alvo, **m,
                   "auc": auc(np, y, escores[alvo][nome])}
            lin["ic95_inferior"], lin["ic95_superior"] = np.percentile(
                amostras[nome], [2.5, 97.5])
            # Do ensemble para cada modelo: positiva, o ensemble acerta mais.
            lin["ensemble_menos_modelo"] = (
                acuracia_balanceada(np, y, preds[alvo][ENSEMBLE]) - m["acuracia_balanceada"])
            lin["dif_ic95_inferior"], lin["dif_ic95_superior"] = np.percentile(
                amostras[ENSEMBLE] - amostras[nome], [2.5, 97.5])
            linhas.append(lin)
    res = pd.DataFrame(linhas)

    piv = res.pivot(index="modelo", columns="avaliacao", values="acuracia_balanceada")
    p("")
    p(f"  {'acuracia balanceada':<30} " + " ".join(f"{a:>11}" for a in alvos))
    for nome in modelos:
        p(f"  {nome:<30} " + " ".join(f"{piv.loc[nome, a]:>11.3f}" for a in alvos))
    p("  33 celulas: treino e teste juntos, uma celula de fora por vez")
    p("")
    for r in res[res.modelo == ENSEMBLE].itertuples(index=False):
        p(f"  ensemble, {r.avaliacao:<11} sensib. {r.sensibilidade:.3f}, especif. "
          f"{r.especificidade:.3f}, F1 {r.f1_fim_de_vida:.3f}, AUC {r.auc:.3f}, "
          f"{r.fn} nao detectado(s), {r.fp} alarme(s) falso(s)")
    for alvo in ("teste", "33 celulas"):
        p(f"  ensemble menos cada modelo, {alvo}, pareada por celulas:")
        for r in res[(res.avaliacao == alvo) & (res.modelo != ENSEMBLE)].itertuples(index=False):
            exclui = "exclui" if r.dif_ic95_inferior > 0 or r.dif_ic95_superior < 0 else "inclui"
            p(f"    {r.modelo:<30} {100 * r.ensemble_menos_modelo:+.1f} p.p. IC 95% "
              f"[{100 * r.dif_ic95_inferior:+.1f}, {100 * r.dif_ic95_superior:+.1f}] "
              f"{exclui} o zero")

    por = por_celula(te, {n: preds["teste"][n] for n in (MELHORADA, ENSEMBLE)})
    prev = {f"previsto_{SLUG[ENSEMBLE]}": preds["teste"][ENSEMBLE],
            f"escore_{SLUG[ENSEMBLE]}": escores["teste"][ENSEMBLE]}
    return comp.drop(columns="quais"), res, por, prev, tipo, escolhidos


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
    linhas = textwrap.wrap(sub + NOTA, width=int(fig.get_figwidth() * 13.5))
    altura_linha = 0.1875 / fig.get_figheight()
    fig.suptitle(texto, fontsize=14, fontweight="bold", color=INK,
                 x=0.007, ha="left", y=0.99)
    topo_sub = 0.99 - 2.1 * altura_linha
    fig.text(0.007, topo_sub, "\n".join(linhas), fontsize=10, color=INK2,
             ha="left", va="top", linespacing=1.35)
    fig.tight_layout(rect=[0, 0, 1, topo_sub - len(linhas) * altura_linha - 0.015])


def salvar(plt, fig, nome):
    (FIGURAS / nome).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURAS / nome, bbox_inches="tight")
    plt.close(fig)
    p(f"  {nome}")


def _tinta(cor):
    """Texto sobre um preenchimento: tinta escura ou clara pela luminancia dele."""
    from matplotlib.colors import to_rgb
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in to_rgb(cor)]
    lum = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    return INK if lum > 0.18 else SURF


def _setas(fig, setas):
    """Setas horizontais (ax, x0, x1, y), desenhadas depois do layout.

    So com o layout pronto se sabe quantos pontos ha entre os dois marcadores.
    Onde a ponta nao cabe, os marcadores quase se tocam e a seta fica de fora:
    a diferenca e pequena demais para a direcao importar.
    """
    for ax, x0, x1, y in setas:
        (a, _), (b, _) = ax.transData.transform([(x0, y), (x1, y)])
        if abs(b - a) * 72 / fig.dpi < 2 * RECUO_SETA + 5:
            continue
        ax.annotate("", xy=(x1, y), xytext=(x0, y), zorder=2, annotation_clip=False,
                    arrowprops=dict(arrowstyle="-|>", color=INK2, linewidth=1.4,
                                    mutation_scale=10, shrinkA=RECUO_SETA,
                                    shrinkB=RECUO_SETA))


def fig_escolha_k(mods, plt, tab, k, tolerancia):
    from matplotlib.patches import Patch
    from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator
    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    melhor = tab.relativas.max()
    ax.axhspan(100 * (melhor - tolerancia), 100 * melhor, color=PAL[0], alpha=0.10,
               linewidth=0, zorder=0)
    for n in [c for c in ("brutas", "todas", "relativas") if c in tab.columns]:
        cor, mk = COR_CONJUNTO[n]
        ax.plot(tab.index, 100 * tab[n], color=cor, marker=mk, markersize=6.5,
                markeredgecolor=SURF, markeredgewidth=1.4, zorder=3 if n == "relativas" else 2,
                label=NOME_CONJUNTO[n])
    ax.axvline(k, color=INK2, linestyle="--", linewidth=1.2, zorder=1)
    ax.set_xscale("log")
    ax.xaxis.set_major_locator(FixedLocator([1, 3, 5, 9, 15, 25, 41, 61, 101, 201]))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}"))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.set_xlabel("k, número de vizinhos consultados (escala log)")
    ax.set_ylabel("acurácia balanceada (%)")
    topo = ax.get_ylim()[1]
    ax.text(k * 1.06, topo, f"k = {k}", fontsize=10, color=INK, va="top", ha="left")
    alcas, _ = ax.get_legend_handles_labels()
    alcas.append(Patch(color=PAL[0], alpha=0.10, linewidth=0,
                       label=f"a até {virg(100 * tolerancia, 0)} p.p. do melhor relativo"))
    # Acima do grafico: dentro dele a legenda cobriria as curvas em qualquer canto.
    ax.legend(handles=alcas, fontsize=9, loc="lower center", bbox_to_anchor=(0.5, 1.0),
              ncol=2, borderaxespad=0.4)
    acima = int((tab.relativas >= tab.drop(columns="relativas").max(axis=1)).sum()) \
        if tab.shape[1] > 1 else None
    sub = ("Validação nas 25 células de treino, deixando uma de fora por vez. A faixa "
           f"sombreada vai até {virg(100 * tolerancia, 0)} p.p. abaixo do melhor resultado "
           f"com os atributos relativos, e vence o menor k dentro dela: k = {k}.")
    if acima is not None:
        sub += (f" Os atributos relativos ficam à frente dos outros dois conjuntos em "
                f"{acima} dos {len(tab)} valores de k.")
    titulo_figura(plt, fig, "Quantos vizinhos consultar", sub)
    salvar(plt, fig, "01_escolha_de_k.png")


def fig_hierarquia(mods, plt, piv, nome_knn):
    np = mods["numpy"]
    from matplotlib.lines import Line2D
    refs = [m for m in piv.sort_values("relativas", ascending=False).index if m != nome_knn]
    piv = piv.loc[[nome_knn] + refs]
    n = len(piv)
    ys = np.arange(n)[::-1]
    # Uma escolha por painel e uma seta por algoritmo: do que sai ao que entra,
    # com o resto fixo, e a mudanca escrita sobre a seta. O losango cheio, o
    # resultado honesto com os atributos relativos, e a ponta da seta dos
    # atributos e o pe da seta do protocolo. O conjunto completo fica na tabela:
    # nao responde a nenhuma das duas perguntas.
    marca = {"brutas": dict(marker="o", markersize=9, markerfacecolor=PAL[7],
                            markeredgecolor=SURF, markeredgewidth=1.5),
             "relativas": dict(marker="D", markersize=8.5, markerfacecolor=PAL[0],
                               markeredgecolor=SURF, markeredgewidth=1.5),
             "aleatoria": dict(marker="D", markersize=8.5, markerfacecolor=SURF,
                               markeredgecolor=PAL[0], markeredgewidth=1.8)}
    paineis = []
    if "brutas" in piv.columns:
        paineis.append(("Atributos: brutos → relativos",
                        ("brutas", "atributos brutos"), ("relativas", "atributos relativos")))
    paineis.append(("Protocolo: uma célula de fora → aleatória",
                    ("relativas", "uma célula de fora por vez"),
                    ("aleatoria", "partição aleatória (vazada)")))
    fig, axes = plt.subplots(1, len(paineis), figsize=(5.2 * len(paineis) + 1.9, 0.62 * n + 3.6),
                             sharex=True, sharey=True, squeeze=False)
    setas = []
    for ax, (titulo, (de, rot_de), (para, rot_para)) in zip(axes[0], paineis):
        for y, a, b in zip(ys, 100 * piv[de], 100 * piv[para]):
            setas.append((ax, a, b, y))
            ax.text((a + b) / 2, y + 0.17, sinal(b - a), fontsize=9, color=INK2,
                    ha="center", va="bottom")
        for c in (de, para):
            ax.plot(100 * piv[c], ys, linestyle="", zorder=3, clip_on=False, **marca[c])
        ax.axvline(50, color=INK2, linewidth=1, linestyle=":", zorder=0)
        ax.text(50.5, -0.6, "acaso", fontsize=9, color=INK2, va="bottom", ha="left")
        ax.set_title(titulo, loc="left", fontsize=11, color=INK, pad=24)
        ax.legend(handles=[Line2D([], [], linestyle="", label=rot, **marca[c])
                           for c, rot in ((de, rot_de), (para, rot_para))],
                  fontsize=9, loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2,
                  borderaxespad=0.2, handletextpad=0.2, columnspacing=1.4)
        ax.set_xlabel("acurácia balanceada (%)")
        ax.grid(axis="y", visible=False)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
    ax.set_xlim(45, 100)
    ax.set_ylim(-0.7, n - 0.3)
    axes[0, 0].set_yticks(ys, [ROTULO_MODELO.get(m, m) for m in piv.index])
    for t in axes[0, 0].get_yticklabels():
        if t.get_text() == nome_knn:
            t.set_fontweight("bold")
            t.set_color(INK)

    rot = lambda m: ROTULO_MODELO.get(m, m)
    # Espaco inseparavel antes de "p.p.": a quebra de linha nao separa o numero da unidade.
    faixa = lambda s: f"de {sinal(s.min())} a {sinal(s.max())}\u00a0p.p."
    sub = ("Validação nas 25 células de treino. Cada seta troca uma escolha e mantém o resto; o "
           "número sobre ela é quanto a acurácia balanceada muda, em p.p.")
    if "brutas" in piv.columns:
        sub += f" Atributos relativos no lugar dos brutos: {faixa(100 * (piv.relativas - piv.brutas))}"
    sub += (" Partição aleatória por descarga no lugar de deixar uma célula de fora: "
            f"{faixa(100 * (piv.aleatoria - piv.relativas))}, um ganho que só existe porque a "
            "mesma célula fica no treino e na validação.")
    if refs:
        rel = 100 * piv.relativas.sort_values(ascending=False)
        sub += (f" Entre os algoritmos, nos losangos cheios, a distância chega a "
                f"{virg(rel.iloc[0] - rel.iloc[-1])}\u00a0p.p., e {rot(rel.index[0])} e "
                f"{rot(rel.index[1])} ficam a {virg(rel.iloc[0] - rel.iloc[1])}\u00a0p.p. um do outro.")
    titulo_figura(plt, fig, "Protocolo, atributos e algoritmo: o que mais pesa", sub)
    _setas(fig, setas)
    salvar(plt, fig, "02_protocolo_atributos_algoritmo.png")


def _grade_celulas(plt, prev, acerto, rotulo_erro):
    """Um painel por celula de teste numa condicao: o SOH ao longo dos ciclos,
    com as descargas classificadas errado em destaque.

    `acerto` diz, descarga a descarga de `prev`, se a classe prevista bateu. O
    eixo de SOH de cada painel so depende do medido.
    """
    from matplotlib.lines import Line2D
    grupos = list(prev.assign(certo=acerto).groupby(["battery_id", "test_condition"],
                                                    sort=True))
    ncol = 4
    nlin = -(-len(grupos) // ncol)
    fig, axes = plt.subplots(nlin, ncol, figsize=(13, 2.9 * nlin + 1.9), squeeze=False)
    for i, (ax, ((bat, cond), g)) in enumerate(zip(axes.flat, grupos)):
        certo = g.certo.to_numpy()
        ax.axhline(FIM_DE_VIDA, color=INK2, linestyle="--", linewidth=1.1, zorder=1)
        ax.scatter(g.ciclo[certo], g[ALVO][certo], s=14, color=MUTED, alpha=0.6,
                   linewidths=0, zorder=2)
        ax.scatter(g.ciclo[~certo], g[ALVO][~certo], s=48, marker="X", color=PAL[1],
                   edgecolors=SURF, linewidths=0.7, zorder=3)
        lo, hi = min(g[ALVO].min(), FIM_DE_VIDA), max(g[ALVO].max(), FIM_DE_VIDA)
        folga = max(2.0, 0.08 * (hi - lo))
        ax.set_ylim(lo - folga, min(hi + folga, 104))
        ax.set_title(f"{bat} · {condicao(cond)}\nacerto {virg(100 * certo.mean(), 0)}%, "
                     f"{int((~certo).sum())} erro(s)", fontsize=9.5, color=INK, loc="left")
        ax.tick_params(labelsize=8.5)
        if i % ncol == 0:
            ax.set_ylabel("SOH (%)", fontsize=9.5)
        if i >= len(grupos) - ncol:
            ax.set_xlabel("ciclo de descarga da célula", fontsize=9.5)
    alcas = [Line2D([], [], color=MUTED, marker="o", linestyle="", markersize=6,
                    label="classificada certo"),
             Line2D([], [], color=PAL[1], marker="X", linestyle="", markersize=8,
                    markeredgecolor=SURF, label=rotulo_erro),
             Line2D([], [], color=INK2, linestyle="--", linewidth=1.1,
                    label=f"limiar de fim de vida ({FIM_DE_VIDA:.0f}%)")]
    sobra = list(axes.flat)[len(grupos):]
    for ax in sobra:
        ax.axis("off")
    if sobra:
        sobra[0].legend(handles=alcas, loc="center", fontsize=9.5)
    else:
        fig.legend(handles=alcas, loc="lower center", ncol=3, fontsize=9.5)
    return fig


def _frase_erros(prev, acerto):
    """O que a grade de celulas mostra dos erros, para o subtitulo."""
    erros = prev[~acerto]
    perto = ((erros[ALVO] - FIM_DE_VIDA).abs() < PERTO_DO_LIMIAR).mean() if len(erros) else 0
    return (f"Acima da linha de {FIM_DE_VIDA:.0f}% o erro é alarme falso; abaixo, fim de vida "
            f"não detectado. {virg(100 * perto, 0)}% dos {len(erros)} erros ficam a menos de "
            f"{virg(PERTO_DO_LIMIAR, 0)} p.p. do limiar.")


def fig_celulas(mods, plt, prev, k):
    acerto = prev.acerto.to_numpy()
    fig = _grade_celulas(plt, prev, acerto, "erro do kNN")
    sub = (f"Cada painel é uma célula de teste numa condição de ensaio, com o kNN de k = {k}. "
           + _frase_erros(prev, acerto))
    titulo_figura(plt, fig, "Onde o kNN erra", sub)
    salvar(plt, fig, "07_teste_por_celula.png")


def fig_celulas_por_modelo(mods, plt, prev, ordem):
    """A 07 para cada algoritmo, em teste_por_modelo/<algoritmo>_por_celula.png.

    O eixo de SOH de cada celula so depende do medido, entao ja e o mesmo nas
    imagens de todos os algoritmos, e elas se comparam lado a lado.
    """
    for nome in ordem:
        knn = nome == ordem[0]
        prevista = prev.previsto if knn else prev[f"previsto_{SLUG[nome]}"]
        acerto = (prevista == prev.fim_de_vida).to_numpy()
        fig = _grade_celulas(plt, prev, acerto, "classificada errado")
        sub = ("Cada painel é uma célula de teste numa condição de ensaio, com o algoritmo "
               "ajustado nas 25 células de treino, com os atributos relativos ao início de vida. "
               + _frase_erros(prev, acerto))
        titulo_figura(plt, fig, f"{ROTULO_MODELO.get(nome, nome)}: erros em cada célula de teste",
                      sub)
        salvar(plt, fig, f"teste_por_modelo/{'knn' if knn else SLUG[nome]}_por_celula.png")


def fig_roc(mods, plt, y, escores, res):
    """Curvas ROC no teste: a ordem dos escores em todos os limiares de decisao."""
    from sklearn.metrics import roc_curve
    t = res.set_index("modelo")
    nomes = list(t.index)        # o kNN e depois as referencias, sempre na mesma ordem
    # A cor segue o modelo, nao a posicao: slots 1 a 5 da paleta, em ordem fixa.
    cor = {n: PAL[i] for i, n in enumerate(nomes)}
    nome_knn = nomes[0]
    fig, ax = plt.subplots(figsize=(7.2, 6.6))
    ax.plot([0, 100], [0, 100], color=INK2, linestyle=":", linewidth=1, zorder=1)
    ax.text(70, 66, "acaso", fontsize=9, color=INK2, rotation=45, rotation_mode="anchor")
    for n in nomes:
        fpr, tpr, _ = roc_curve(y, escores[n])
        ax.plot(100 * fpr, 100 * tpr, color=cor[n], linewidth=2.6 if n == nome_knn else 1.6,
                zorder=3 if n == nome_knn else 2,
                label=f"{ROTULO_MODELO.get(n, n)}: AUC {virg(t.auc[n], 2)}")
    r = t.loc[nome_knn]
    ax.scatter(100 * (1 - r.especificidade), 100 * r.sensibilidade, s=80, marker="D",
               color=PAL[0], edgecolors=SURF, linewidths=1.5, zorder=4,
               label="kNN no limiar de 50%, a decisão avaliada")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_aspect("equal")
    ax.set_xlabel("alarmes falsos (% das descargas saudáveis)")
    ax.set_ylabel("fim de vida detectado (%)")
    ax.legend(fontsize=9, loc="lower right")
    sub = (f"As 8 células de teste ({len(y)} descargas). Cada ponto de uma curva é um limiar de "
           f"decisão; a AUC resume a curva inteira e não depende do limiar. O losango é o kNN no "
           f"limiar de 50%, a decisão que a acurácia balanceada avalia. AUC do kNN: "
           f"{virg(r.auc, 2)} (IC 95% por reamostragem de células: {virg(r.auc_ic95_inferior, 2)} "
           f"a {virg(r.auc_ic95_superior, 2)}).")
    titulo_figura(plt, fig, "Curvas ROC no teste", sub)
    salvar(plt, fig, "05_curvas_roc.png")


def fig_variante(mods, plt, curva, resumo):
    from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator
    k_base, k_var = resumo["k_base"], resumo["k_var"]
    fig, ax = plt.subplots(figsize=(9.5, 5.0))
    # Azul e laranja: o par passa o validador de daltonismo (pior dE 24,7), e a
    # forma repete a distincao para impressao em preto e branco.
    series = (("sem_restricao", "vizinhos de qualquer célula (o modelo avaliado no teste)",
               PAL[0], "D", k_base),
              ("mesmo_grupo", "vizinhos só do mesmo grupo de comportamento (variante)",
               PAL[1], "o", k_var))
    for col, rotulo, cor, mk, k in series:
        ax.plot(curva.index, 100 * curva[col], color=cor, marker=mk, markersize=6.5,
                markeredgecolor=SURF, markeredgewidth=1.4, label=rotulo, zorder=3)
        if k in curva.index:
            v = 100 * curva.loc[k, col]
            ax.annotate(f"k = {k}: {virg(v)}%", (k, v), xytext=(6, 9),
                        textcoords="offset points", fontsize=9.5, color=INK)
    ax.set_xscale("log")
    ax.xaxis.set_major_locator(FixedLocator([1, 3, 5, 9, 15, 25, 41, 61, 101, 201]))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}"))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.set_xlabel("k, número de vizinhos consultados (escala log)")
    ax.set_ylabel("acurácia balanceada (%)")
    ax.legend(fontsize=9, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=1,
              borderaxespad=0.4)
    pior = int((curva.mesmo_grupo < curva.sem_restricao).sum())
    sub = ("Variante pós-hoc, avaliada só na validação nas 25 células de treino, porque surgiu "
           "da análise dos erros no teste. O agrupamento do módulo 2 é refeito a cada rodada sem "
           f"a célula avaliada. Restringir a vizinhança ao grupo piora em {pior} dos "
           f"{len(curva)} valores de k; no k escolhido pela mesma regra, a acurácia balanceada "
           f"vai de {virg(100 * resumo['sem restricao'])}% para "
           f"{virg(100 * resumo['mesmo grupo'])}%. Cada grupo oferece em mediana "
           f"{resumo['oferta_mediana']:.0f} células como vizinhas, contra 24 sem a restrição.")
    titulo_figura(plt, fig, "Vizinhos só do mesmo grupo de comportamento", sub)
    salvar(plt, fig, "08_variante_mesmo_grupo.png")


ROTULO_PASSO = {"artigo": "a do artigo", "C menor": "+ regularização mais forte",
                "idade no par": "+ idade no par", "media movel": "+ média móvel causal"}


def fig_escolha_c(mods, plt, tab, c_final):
    from matplotlib.ticker import FuncFormatter, NullLocator
    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    # Azul, violeta e laranja passam o validador de daltonismo em todos os pares, e
    # a forma repete a distincao para impressao em preto e branco.
    series = (("artigo", "atributos da logística do artigo", PAL[0], "D"),
              ("idade no par", "com a idade no par", PAL[6], "s"),
              ("media movel", "com a idade no par e a média móvel", PAL[1], "o"))
    for col, rotulo, cor, mk in series:
        ax.plot(tab.index, 100 * tab[col], color=cor, marker=mk, markersize=6.5,
                markeredgecolor=SURF, markeredgewidth=1.4, label=rotulo, zorder=3)
    for c, col, texto, desloc in ((C_PADRAO, "artigo", "a do artigo", (4, -16)),
                                  (c_final, "media movel", "a melhorada", (8, 7))):
        v = 100 * tab.loc[c, col]
        ax.annotate(f"{texto}: {virg(v)}%", (c, v), xytext=desloc,
                    textcoords="offset points", fontsize=9.5, color=INK)
    ax.axvline(c_final, color=INK2, linestyle="--", linewidth=1.2, zorder=1)
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}".replace(".", ",")))
    ax.set_xticks([1e-4, 1e-3, 1e-2, 0.1, 1, 10])
    ax.xaxis.set_minor_locator(NullLocator())
    ax.set_ylim(50, 85)
    ax.set_xlabel("C, inverso da regularização (escala log; à esquerda, mais regularizado)")
    ax.set_ylabel("acurácia balanceada (%)")
    ax.legend(fontsize=9, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3,
              borderaxespad=0.4)
    melhor = (tab["media movel"] >= tab["artigo"]).sum()
    sub = ("Validação nas 25 células de treino, deixando uma de fora por vez. Vence o menor C a "
           f"até {virg(100 * TOLERANCIA_K, 0)} p.p. do melhor, a regra do k do kNN: "
           f"C\u00a0=\u00a0{f'{c_final:g}'.replace('.', ',')}. Com as duas trocas de atributos a curva fica "
           f"acima da do artigo em {melhor} dos {len(tab)} valores de C.")
    titulo_figura(plt, fig, "Quanto regularizar a regressão logística", sub)
    salvar(plt, fig, "09_logistica_escolha_de_c.png")


def _tres_avaliacoes(np, ax, piv, rotulos, limites, ligar=False):
    """Uma linha por modelo (ou passo) e um marcador por avaliacao, com o valor escrito."""
    ys = np.arange(len(piv))[::-1]
    # O rotulo da validacao vai embaixo do marcador: o das 33 celulas fica colado nele.
    marcas = (("validacao", "validação (25 células)", -0.17, "top",
               dict(marker="o", markersize=8, markerfacecolor=SURF, markeredgecolor=INK2,
                    markeredgewidth=1.6)),
              ("33 celulas", "as 33 células", 0.17, "bottom",
               dict(marker="s", markersize=8, markerfacecolor=PAL[1], markeredgecolor=SURF,
                    markeredgewidth=1.4)),
              ("teste", "teste (8 células)", 0.17, "bottom",
               dict(marker="D", markersize=8.5, markerfacecolor=PAL[0], markeredgecolor=SURF,
                    markeredgewidth=1.4)))
    for alvo, rotulo, dy, va, marca in marcas:
        v = 100 * piv[alvo].to_numpy()
        if ligar:
            ax.plot(v, ys, linestyle="-", color=GRID, linewidth=1.6, zorder=1)
        ax.plot(v, ys, linestyle="", zorder=3, label=rotulo, **marca)
        for x, y in zip(v, ys):
            ax.text(x, y + dy, virg(x), fontsize=9, color=INK2, ha="center", va=va)
    ax.set_yticks(ys, rotulos)
    ax.set_ylim(-0.5, len(piv) - 0.4)
    ax.set_xlim(*limites)
    ax.set_xlabel("acurácia balanceada (%)")
    ax.grid(axis="y", visible=False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.legend(fontsize=9, loc="lower left", bbox_to_anchor=(0, 1.0), ncol=3,
              borderaxespad=0.4, handletextpad=0.2, columnspacing=1.2)


def fig_logistica(mods, plt, res):
    """Cada troca nas tres avaliacoes, e a matriz de confusao do teste antes e depois."""
    np = mods["numpy"]
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("seq", SEQ)
    piv = res.pivot(index="passo", columns="avaliacao", values="acuracia_balanceada")
    passos = list(ROTULO_PASSO)
    fig, axes = plt.subplots(1, 3, figsize=(13, 5.6),
                             gridspec_kw={"width_ratios": [2.1, 1, 1]})
    _tres_avaliacoes(np, axes[0], piv.loc[passos], [ROTULO_PASSO[n] for n in passos],
                     (65, 91), ligar=True)

    t = res[res.avaliacao == "teste"].set_index("passo")
    for j, (nome, titulo) in enumerate((("artigo", "a do artigo, no teste"),
                                        ("media movel", "a melhorada, no teste"))):
        _matriz(np, axes[j + 1], t.loc[nome], cmap, j == 0)
        axes[j + 1].set_title(titulo, fontsize=11, color=INK, pad=10)
    fim = res[res.passo == "media movel"].set_index("avaliacao")
    ic = lambda a: (f"{sinal(100 * fim.diferenca_para_artigo[a])}\u00a0p.p. "
                    f"({sinal(100 * fim.dif_ic95_inferior[a])} a "
                    f"{sinal(100 * fim.dif_ic95_superior[a])})")
    sub = ("À esquerda, cada linha mantém as trocas das anteriores; na validação e nas 33 células, "
           "uma célula fica de fora por vez. Diferença da melhorada para a "
           f"do artigo, com o intervalo de 95% pareado por células: {ic('33 celulas')} nas 33 "
           f"células e {ic('teste')} no teste. À direita, as linhas são a classe real, as colunas "
           "a prevista, e o percentual é sobre a classe real. As trocas foram feitas depois de o "
           "teste ser visto: o número do teste não é avaliação independente.")
    titulo_figura(plt, fig, "A regressão logística melhorada, troca por troca", sub)
    salvar(plt, fig, "10_logistica_melhorada.png")


def fig_celulas_pos_hoc(mods, plt, prev, nome, descricao):
    acerto = (prev[f"previsto_{SLUG[nome]}"] == prev.fim_de_vida).to_numpy()
    fig = _grade_celulas(plt, prev, acerto, "classificada errado")
    sub = (f"Cada painel é uma célula de teste numa condição de ensaio, com {descricao} "
           "nas 25 células de treino. " + _frase_erros(prev, acerto))
    titulo_figura(plt, fig, f"{ROTULO_MODELO.get(nome, nome)}: erros em cada célula de teste", sub)
    salvar(plt, fig, f"teste_por_modelo/{SLUG[nome]}_por_celula.png")


def fig_ensemble(mods, plt, res, tipo, escolhidos):
    """O ensemble, os membros e as referencias, e a matriz do ensemble no teste."""
    np = mods["numpy"]
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("seq", SEQ)
    piv = res.pivot(index="modelo", columns="avaliacao", values="acuracia_balanceada")
    ordem = list(res[res.avaliacao == "teste"].sort_values("acuracia_balanceada",
                                                           ascending=False).modelo)
    fig, axes = plt.subplots(1, 2, figsize=(13, 0.62 * len(ordem) + 3.2),
                             gridspec_kw={"width_ratios": [2.6, 1]})
    _tres_avaliacoes(np, axes[0], piv.loc[ordem], [ROTULO_MODELO.get(n, n) for n in ordem],
                     (65, 91))
    for tk in axes[0].get_yticklabels():
        if tk.get_text() == ENSEMBLE:
            tk.set_fontweight("bold")
            tk.set_color(INK)
    r = res[(res.modelo == ENSEMBLE) & (res.avaliacao == "teste")].iloc[0]
    _matriz(np, axes[1], r, cmap, True)
    axes[1].set_title("o ensemble, no teste", fontsize=11, color=INK, pad=10)
    d = res.set_index(["modelo", "avaliacao"])
    ic = lambda m, a: (f"{sinal(100 * d.ensemble_menos_modelo[(m, a)])}\u00a0p.p. "
                       f"({sinal(100 * d.dif_ic95_inferior[(m, a)])} a "
                       f"{sinal(100 * d.dif_ic95_superior[(m, a)])})")
    voto = "majoritário" if tipo == "majoritario" else "suave"
    rot = [ROTULO_MODELO.get(n, n) for n in escolhidos]
    sub = (f"Voto {voto} de {lista(rot)}; a composição e o tipo de voto saíram da validação. Na "
           "validação e nas 33 células, uma célula fica de fora por vez. Diferença do ensemble, "
           f"pareada por células: para a logística melhorada, {ic(MELHORADA, '33 celulas')} nas "
           f"33 células e {ic(MELHORADA, 'teste')} no teste; para o SVM do artigo, "
           f"{ic('SVM (RBF)', '33 celulas')} nas 33 células. O ensemble veio depois de o teste "
           "ser visto: o número do teste não é avaliação independente.")
    titulo_figura(plt, fig, "O ensemble, os membros e as referências", sub)
    salvar(plt, fig, "11_ensemble.png")


# ---------------------------------------------------------------------------
# graficos por algoritmo: as referencias com o mesmo detalhe do kNN
# ---------------------------------------------------------------------------
def ordem_modelos(piv, nome_knn):
    """O kNN e depois as referencias pela acuracia balanceada na validacao, como em 02 e 03."""
    return [nome_knn] + [m for m in piv.sort_values("relativas", ascending=False).index
                         if m != nome_knn]


def validacao_relativas(comp, nome_knn):
    """As linhas de comparacao.csv com os atributos relativos, uma celula de fora por vez."""
    v = comp[(comp.atributos == "relativas") & (comp.validacao == "uma celula de fora")]
    return v.assign(modelo=v.modelo.replace({"kNN": nome_knn})).set_index("modelo")


def lista(itens):
    """['a', 'b', 'c'] -> 'a, b e c'."""
    return itens[0] if len(itens) == 1 else ", ".join(itens[:-1]) + " e " + itens[-1]


def _matriz(np, ax, r, cmap, rotulos_y):
    """Uma matriz de confusao: contagem e fracao da classe real em cada casa."""
    rotulos = ["saudável", "fim de vida"]
    m = np.array([[r.vn, r.fp], [r.fn, r.vp]], dtype=float)
    frac = m / m.sum(axis=1, keepdims=True)
    ax.imshow(frac, cmap=cmap, vmin=0, vmax=1)
    for a in range(2):
        for b in range(2):
            ax.text(b, a, f"{int(m[a, b])}\n{virg(100 * frac[a, b], 0)}%",
                    ha="center", va="center", fontsize=10.5,
                    color=_tinta(cmap(frac[a, b])),
                    fontweight="bold" if a == b else "normal", linespacing=1.3)
    ax.set_xticks([0, 1], rotulos, fontsize=9)
    ax.set_yticks([0, 1], rotulos if rotulos_y else ["", ""], fontsize=9)
    ax.set_xticks([0.5], minor=True)
    ax.set_yticks([0.5], minor=True)
    ax.grid(which="minor", color=SURF, linewidth=3)
    ax.grid(which="major", visible=False)
    ax.tick_params(which="both", length=0)
    for lado in ax.spines.values():
        lado.set_visible(False)
    ax.set_xlabel(f"acurácia balanceada {virg(100 * r.acuracia_balanceada)}%",
                  fontsize=9.5, color=INK, labelpad=7)


def fig_matrizes(mods, plt, comp, res, ordem):
    """A matriz de confusao de cada algoritmo, na validacao e no teste."""
    np = mods["numpy"]
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("seq", SEQ)
    nome_knn = ordem[0]
    etapas = (("validação", validacao_relativas(comp, nome_knn).loc[ordem]),
              ("teste", res.set_index("modelo").loc[ordem]))
    n = len(ordem)
    fig, axes = plt.subplots(2, n, figsize=(2.45 * n + 1.2, 8.0), squeeze=False)
    for i, (etapa, t) in enumerate(etapas):
        for j, nome in enumerate(ordem):
            ax = axes[i, j]
            _matriz(np, ax, t.loc[nome], cmap, j == 0)
            if i == 0:
                ax.set_title(ROTULO_MODELO.get(nome, nome), fontsize=11, color=INK, pad=10,
                             fontweight="bold" if nome == nome_knn else "normal")
        axes[i, 0].text(-0.66, 0.5, etapa, transform=axes[i, 0].transAxes, rotation=90,
                        ha="center", va="center", fontsize=12.5, fontweight="bold", color=INK)
    v, t = etapas[0][1], etapas[1][1]
    muda = t.sensibilidade - v.sensibilidade
    rot = lambda m: ROTULO_MODELO.get(m, m)
    pc = lambda s, m: f"{virg(100 * s[m], 0)}%"
    # Ponto como separador de milhar, como manda a norma brasileira: 2.001.
    total = lambda d: f"{int(d.iloc[0][['vp', 'fn', 'fp', 'vn']].sum()):,}".replace(",", ".")
    sub = ("Atributos relativos ao início de vida. Em cada matriz, as linhas são a classe real e "
           "as colunas a prevista; o percentual é sobre a classe real, e a diagonal é a taxa de "
           "acerto de cada classe: especificidade em cima, sensibilidade embaixo. Validação: as "
           f"{total(v)} descargas das 25 células de treino, cada célula prevista por um modelo "
           f"que não a viu. Teste: as {total(t)} descargas das 8 células nunca vistas.")
    if n > 1:
        cai, sobe = muda.idxmin(), muda.idxmax()
        sub += (f" Sensibilidade, da validação para o teste: {rot(cai)}, de "
                f"{pc(v.sensibilidade, cai)} para {pc(t.sensibilidade, cai)}; {rot(sobe)}, de "
                f"{pc(v.sensibilidade, sobe)} para {pc(t.sensibilidade, sobe)}.")
    titulo_figura(plt, fig, "A matriz de confusão de cada algoritmo", sub)
    salvar(plt, fig, "03_matrizes_de_confusao.png")


def fig_metricas(mods, plt, comp, res, ordem):
    """Todas as metricas de cada algoritmo: da validacao ao teste, com o intervalo do teste."""
    np = mods["numpy"]
    from matplotlib.lines import Line2D
    from matplotlib.ticker import FixedLocator, FuncFormatter
    nome_knn = ordem[0]
    val = validacao_relativas(comp, nome_knn).loc[ordem]
    te = res.set_index("modelo").loc[ordem]
    # coluna, prefixo do intervalo em teste.csv, titulo, nome curto, escala, acaso
    paineis = [("acuracia_balanceada", "", "acurácia balanceada (%)", "acurácia balanceada",
                100, 50),
               ("sensibilidade", "sensibilidade_", "sensibilidade: fim de vida detectado (%)",
                "sensibilidade", 100, None),
               ("especificidade", "especificidade_", "especificidade: saudável reconhecida (%)",
                "especificidade", 100, None),
               ("precisao", "precisao_", "precisão: alarmes que eram fim de vida (%)",
                "precisão", 100, None),
               ("f1_fim_de_vida", "f1_", "F1 do fim de vida", "F1", 1, None),
               ("auc", "auc_", "AUC", "AUC", 1, 0.5)]
    valid = dict(marker="o", markersize=7.5, markerfacecolor=SURF, markeredgecolor=INK2,
                 markeredgewidth=1.5)
    teste = dict(marker="D", markersize=8, markerfacecolor=PAL[0], markeredgecolor=SURF,
                 markeredgewidth=1.3)
    n = len(ordem)
    fig, axes = plt.subplots(2, 3, figsize=(13, 0.95 * n + 4.6), sharey=True)
    ys = np.arange(n)[::-1]
    setas = []
    for ax, (col, pre, titulo, _c, escala, acaso) in zip(axes.flat, paineis):
        # Uma linha por algoritmo: a faixa e o intervalo do teste, e a seta vai
        # da validacao ao teste. Quem cai, quem sobe, e quanto a faixa deixa
        # afirmar, sem um marcador fora da linha do seu algoritmo.
        ax.hlines(ys, escala * te[f"{pre}ic95_inferior"], escala * te[f"{pre}ic95_superior"],
                  color=FAIXA, linewidth=9, capstyle="butt", zorder=1)
        ax.plot(escala * val[col], ys, linestyle="", zorder=3, clip_on=False, **valid)
        ax.plot(escala * te[col], ys, linestyle="", zorder=4, clip_on=False, **teste)
        setas += [(ax, escala * v, escala * t, y) for v, t, y in zip(val[col], te[col], ys)]
        if acaso is not None:
            ax.axvline(acaso, color=INK2, linewidth=1, linestyle=":", zorder=0)
            ax.text(acaso + 0.012 * escala, -0.62, "acaso", fontsize=8.5, color=INK2,
                    va="bottom", ha="left")
        ax.set_xlim(0, escala)
        ax.xaxis.set_major_locator(FixedLocator([escala * v for v in (0, 0.25, 0.5, 0.75, 1)]))
        if escala == 1:
            ax.xaxis.set_major_formatter(
                FuncFormatter(lambda v, _: virg(v, 2).rstrip("0").rstrip(",")))
        ax.set_title(titulo, fontsize=10, color=INK, loc="left")
        ax.set_ylim(-0.7, n - 0.3)
        ax.grid(axis="y", visible=False)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
    for ax in axes[:, 0]:
        ax.set_yticks(ys, [ROTULO_MODELO.get(m, m) for m in ordem])
        for tk in ax.get_yticklabels():
            if tk.get_text() == nome_knn:
                tk.set_fontweight("bold")
                tk.set_color(INK)
    alcas = [Line2D([], [], linestyle="", label="validação: 25 células de treino, uma de fora por vez",
                    **valid),
             Line2D([], [], linestyle="", label="teste: 8 células nunca vistas", **teste),
             Line2D([], [], color=FAIXA, linewidth=9, solid_capstyle="butt",
                    label="IC 95% do teste, reamostrando células inteiras")]
    fig.legend(handles=alcas, loc="lower center", ncol=3, fontsize=9.5,
               bbox_to_anchor=(0.5, -0.01))
    rot = lambda m: ROTULO_MODELO.get(m, m)
    # Faixas que nao se cruzam: o unico caso em que o grafico, sozinho, separa
    # dois algoritmos. A diferenca pareada de teste.csv e mais sensivel.
    separadas = []
    for col, pre, _t, nome_curto, _e, _a in paineis:
        lo, hi = te[f"{pre}ic95_inferior"], te[f"{pre}ic95_superior"]
        frente = [f"{rot(a)} à frente de {lista([rot(b) for b in ordem if lo[a] > hi[b]])}"
                  for a in ordem if (lo[a] > hi).any()]
        if frente:
            separadas.append(f"em {nome_curto}, {lista(frente)}")
    sub = ("Atributos relativos ao início de vida. Cada seta vai da validação, nas 25 células de "
           "treino com uma de fora por vez, ao teste, nas 8 células nunca vistas; a faixa é o "
           "intervalo de 95% do teste, de reamostrar células inteiras. Com 8 células as faixas "
           "são largas: " + ("só não se cruzam " + "; ".join(separadas) if separadas
                             else "todas se cruzam") + ".")
    pv = val.acuracia_balanceada.rank(ascending=False, method="min").astype(int)
    pt = te.acuracia_balanceada.rank(ascending=False, method="min").astype(int)
    a, b = pv.idxmin(), pt.idxmin()
    if a != b:
        sub += (f" A ordem também muda: em acurácia balanceada, {rot(a)} é o 1º na validação e o "
                f"{pt[a]}º no teste, e {rot(b)}, o 1º no teste, era o {pv[b]}º na validação.")
    titulo_figura(plt, fig, "Todas as métricas, algoritmo por algoritmo", sub)
    fig.subplots_adjust(bottom=0.11)
    _setas(fig, setas)
    salvar(plt, fig, "04_metricas_por_algoritmo.png")


def fig_erro_celulas(mods, plt, por, res, ordem):
    """A fracao de erro de cada algoritmo em cada celula de teste, e nas 8 juntas."""
    np = mods["numpy"]
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("erro", SEQ_ERRO)
    nome_knn = ordem[0]
    t = por.set_index(["modelo", "battery_id", "test_condition"])
    base = por[por.modelo == nome_knn].reset_index(drop=True)
    tot = res.set_index("modelo")
    # (fracao de erro, alarmes falsos, fins de vida nao detectados) por par e modelo
    pares = [[(1 - t.loc[(m, r.battery_id, r.test_condition), "acuracia"],
               int(t.loc[(m, r.battery_id, r.test_condition), "alarmes_falsos"]),
               int(t.loc[(m, r.battery_id, r.test_condition), "nao_detectados"]))
              for m in ordem] for r in base.itertuples()]
    total = [(1 - tot.loc[m, "acuracia"], int(tot.loc[m, "fp"]), int(tot.loc[m, "fn"]))
             for m in ordem]
    n_lin, n_col = len(pares), len(ordem)
    # O conjunto das 8 celulas fica embaixo, separado dos pares por uma faixa vazia.
    folga = 0.45
    bordas_y = list(range(n_lin + 1)) + [n_lin + folga, n_lin + folga + 1]
    erro = np.array([[e for e, _a, _n in lin] for lin in pares]
                    + [[np.nan] * n_col] + [[e for e, _a, _n in total]])
    vmax = max(0.5, float(np.ceil(10 * np.nanmax(erro)) / 10))
    fig, ax = plt.subplots(figsize=(1.95 * n_col + 3.4, 0.56 * (n_lin + 1) + 2.9))
    ax.pcolormesh(np.arange(n_col + 1), bordas_y, np.ma.masked_invalid(erro), cmap=cmap,
                  vmin=0, vmax=vmax, edgecolors=SURF, linewidth=2.5)
    centros = [i + 0.5 for i in range(n_lin)] + [n_lin + folga + 0.5]
    for yc, lin in zip(centros, pares + [total]):
        for j, (e, af, nd) in enumerate(lin):
            # Sem erro, o zero fica apagado: o olho vai para onde ha erro.
            if not (af or nd):
                ax.text(j + 0.5, yc, "0%", ha="center", va="center", fontsize=10, color=INK2)
                continue
            tinta = _tinta(cmap(e / vmax))
            ax.text(j + 0.5, yc - 0.12, f"{virg(100 * e, 0)}%", ha="center", va="center",
                    fontsize=10.5, color=tinta, fontweight="bold")
            ax.text(j + 0.5, yc + 0.24, f"{af} AF · {nd} ND", ha="center", va="center",
                    fontsize=8, color=tinta)
    ax.set_xlim(0, n_col)
    ax.set_ylim(bordas_y[-1], 0)
    ax.xaxis.tick_top()
    ax.set_xticks(np.arange(n_col) + 0.5, [ROTULO_MODELO.get(m, m) for m in ordem], fontsize=10)
    for tk in ax.get_xticklabels():
        if tk.get_text() == nome_knn:
            tk.set_fontweight("bold")
            tk.set_color(INK)
    rotulos = [f"{r.battery_id} · {condicao(r.test_condition)}\n"
               f"{r.fim_de_vida_real} de {r.descargas} em fim de vida" for r in base.itertuples()]
    rotulos.append(f"as 8 células\n{int(base.fim_de_vida_real.sum())} de "
                   f"{int(base.descargas.sum())} em fim de vida")
    ax.set_yticks(centros, rotulos, fontsize=9)
    ax.tick_params(length=0)
    ax.grid(False)
    for lado in ax.spines.values():
        lado.set_visible(False)
    media = erro[:n_lin].mean(axis=1)
    piores = np.argsort(media)[::-1][:3]
    sub = ("Cada linha é uma célula de teste numa condição de ensaio, e cada coluna um algoritmo "
           "ajustado nas 25 células de treino, com os atributos relativos. A cor e o número são a "
           "fração das descargas do par classificadas errado; embaixo, quantas viraram alarme falso "
           "(AF, saudável prevista como fim de vida) e quantas são fim de vida não detectado (ND). "
           "Na média dos algoritmos, os pares com mais erro são "
           + lista([f"{base.battery_id[i]} a {condicao(base.test_condition[i])} "
                    f"({virg(100 * media[i], 0)}%)" for i in piores]) + ".")
    titulo_figura(plt, fig, "Onde cada algoritmo erra", sub)
    salvar(plt, fig, "06_erro_por_celula.png")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--k", type=int, default=None,
                    help="forca k (por padrao, o menor equivalente ao melhor na validacao)")
    ap.add_argument("--tolerancia", type=float, default=TOLERANCIA_K,
                    help="distancia ao maximo, em acuracia balanceada, que ainda conta "
                         f"como equivalente (padrao {TOLERANCIA_K})")
    ap.add_argument("--sem-referencias", action="store_true",
                    help="so o kNN, sem as familias dos trabalhos relacionados")
    ap.add_argument("--sem-graficos", action="store_true")
    ap.add_argument("--com-grupo", action="store_true",
                    help="com baterias_por_condicao entre os atributos, em "
                         "saida_nasa/baterias_por_condicao/classificacao/")
    a = ap.parse_args()

    global SAIDA, FIGURAS, TABELAS, NOTA
    if a.com_grupo:
        SAIDA, NOTA = SAIDA_COM_GRUPO, NOTA_COM_GRUPO
        FIGURAS, TABELAS = SAIDA / "figuras", SAIDA / "tabelas"
    mods = checar()
    TABELAS.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    p("Classificacao de fim de vida com kNN"
      + (", com baterias_por_condicao" if a.com_grupo else ""))
    p("=" * 60)
    df = carregar(mods)
    conj = conjuntos(df)
    tr = df[df.split == "treino"].reset_index(drop=True)
    te = df[df.split == "teste"].reset_index(drop=True)
    cod = None
    if a.com_grupo:
        from baterias_por_condicao import Codificacao
        cod = Codificacao(mods, tr, te)
        cod.relatar(tr, te)
        conj = {n: cols + cod.colunas for n, cols in conj.items()}
    for nome, d in (("treino", tr), ("teste", te)):
        p(f"  {nome:<6} {len(d):>4} descargas, {d.battery_id.nunique():>2} celulas, "
          f"{d.fim_de_vida.mean():.1%} em fim de vida (SOH < {FIM_DE_VIDA:.0f}%)")
    for n, cols in conj.items():
        p(f"  atributos {n:<9} {len(cols):>2}: {', '.join(cols)}")

    p("")
    p("1. escolha de k, uma celula de treino de fora por vez:")
    tab, k_conj = etapa_k(mods, tr, conj, a.tolerancia, a.k, cod)
    k = k_conj["relativas"]

    p("")
    p("2. protocolo, atributos e algoritmo (so treino):")
    refs = {} if a.sem_referencias else referencias()
    comp, piv, por_cel, nome_knn = etapa_comparacao(mods, tr, conj, k_conj, refs, cod)

    p("")
    p("3. teste: 8 celulas, avaliadas uma vez:")
    res, prev, por, escores, y_te = etapa_teste(mods, tr, te, conj, k, refs, nome_knn)

    p("")
    variante = None
    if a.com_grupo:
        p("4. variante pulada: com --com-grupo o grupo de comportamento ja e atributo")
    elif CURVAS.exists() and GRUPOS.exists():
        p("4. variante pos-hoc, vizinhos so do mesmo grupo de comportamento (so validacao):")
        variante = etapa_variante(mods, tr, conj, tab, k, a.tolerancia)
        por_cel = por_cel.merge(variante[1].reset_index(), on="battery_id", how="left")
    else:
        p("4. variante pulada: falta o agrupamento. Rode antes: python src/curvas.py "
          "e python src/grupos.py")

    p("")
    melhorada = None
    if a.com_grupo:
        # Nelas o agrupamento nao e refeito a cada rodada: o grupo vazaria na validacao.
        p("5 e 6. logistica melhorada e ensemble pulados: --com-grupo")
    elif refs:
        p("5. logistica melhorada, pos-hoc (C sai so da validacao):")
        melhorada = etapa_logistica(mods, tr, te, conj, a.tolerancia)
        prev = prev.assign(**melhorada[5])
        p("")
        p("6. ensemble, pos-hoc (composicao e tipo de voto so da validacao):")
        ensemble = etapa_ensemble(mods, tr, te, conj, melhorada[1], refs)
        prev = prev.assign(**ensemble[3])
    else:
        p("5 e 6. logistica melhorada e ensemble pulados: --sem-referencias")

    arquivos = {"escolha_de_k.csv": tab, "comparacao.csv": comp,
                "validacao_por_celula.csv": por_cel, "teste.csv": res,
                "teste_por_celula.csv": por, "predicoes_teste.csv": prev}
    if variante:
        arquivos["variante_mesmo_grupo.csv"] = variante[0]
    if melhorada:
        arquivos.update({"logistica_escolha_de_c.csv": melhorada[0],
                         "logistica_melhorada.csv": melhorada[2],
                         "logistica_coeficientes.csv": melhorada[3],
                         "logistica_por_celula.csv": melhorada[4],
                         "ensemble_composicao.csv": ensemble[0], "ensemble.csv": ensemble[1],
                         "ensemble_por_celula.csv": ensemble[2]})
    p("")
    for nome, tabela in arquivos.items():
        tabela.round(4).to_csv(TABELAS / nome, index=nome in ("escolha_de_k.csv",
                                                              "variante_mesmo_grupo.csv",
                                                              "logistica_escolha_de_c.csv"))
        p(f"  {(TABELAS / nome).relative_to(RAIZ)}")

    if not a.sem_graficos:
        p("")
        p("graficos:")
        plt = estilo(mods)
        # Na ordem do artigo: validacao, teste de todos os algoritmos, o kNN em
        # detalhe, a variante pos-hoc, a logistica melhorada e o ensemble. Sem
        # referencias, os graficos por algoritmo saem so com o kNN.
        ordem = ordem_modelos(piv, nome_knn)
        fig_escolha_k(mods, plt, tab, k, a.tolerancia)
        fig_hierarquia(mods, plt, piv, nome_knn)
        fig_matrizes(mods, plt, comp, res, ordem)
        fig_metricas(mods, plt, comp, res, ordem)
        fig_roc(mods, plt, y_te, escores, res)
        fig_erro_celulas(mods, plt, por, res, ordem)
        fig_celulas(mods, plt, prev, k)
        fig_celulas_por_modelo(mods, plt, prev, ordem)
        if variante:
            fig_variante(mods, plt, variante[0], variante[2])
        if melhorada:
            fig_escolha_c(mods, plt, melhorada[0], melhorada[1])
            fig_logistica(mods, plt, melhorada[2])
            fig_celulas_pos_hoc(mods, plt, prev, MELHORADA, "a logística melhorada ajustada")
            fig_ensemble(mods, plt, ensemble[1], ensemble[4], ensemble[5])
            fig_celulas_pos_hoc(mods, plt, prev, ENSEMBLE, "o ensemble ajustado")
    p("")
    p(f"  tempo total: {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
