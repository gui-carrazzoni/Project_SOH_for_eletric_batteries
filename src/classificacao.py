#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Classificacao de fim de vida com k vizinhos mais proximos (kNN).

    python classificacao.py                    # escolhe k na validacao, avalia no teste
    python classificacao.py --k 25             # forca k
    python classificacao.py --sem-referencias  # so o kNN, sem as familias da literatura
    python classificacao.py --sem-graficos     # so as tabelas

Le saida_nasa/normalizado/dados_normalizados.csv e escreve em
saida_nasa/classificacao/.

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
celula. vazamento.csv registra quanto.

**Familias da literatura como referencia.** Regressao logistica, SVM, Random
Forest e Gradient Boosting rodam no mesmo protocolo e com o mesmo preparo, com
os hiperparametros padrao do scikit-learn. Nao decidem nada: dizem onde o kNN
fica. Sao o motivo de o scikit-learn entrar no projeto — o kNN caberia em numpy,
as quatro nao.

**Variante pos-hoc: vizinhos so do mesmo grupo de comportamento.** Na analise
dos erros do teste, mais da metade dos vizinhos que enganaram B0018 vinha de
outros grupos do agrupamento do modulo 2. A variante restringe a vizinhanca ao
grupo da descarga, com o agrupamento refeito a cada rodada so com as celulas de
treino (grupos.ajustar) e a celula de fora encaixada no grupo mais proximo.
Como surgiu de olhar o teste, so a validacao a avalia. Precisa das saidas de
curvas.py e grupos.py; sem elas, e pulada.

Dependencias: numpy, pandas, scipy, scikit-learn, matplotlib
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# A raiz do projeto e a pasta acima de src/: e la que ficam
# cleaned_nasa_dataset/ e saida_nasa/.
RAIZ = Path(__file__).resolve().parent.parent
ENTRADA = RAIZ / "saida_nasa" / "normalizado" / "dados_normalizados.csv"
# So pelo numero do ciclo: a tabela normalizada traz o ciclo escalonado, e o
# eixo dos graficos e o CSV de previsoes precisam do ciclo de verdade.
BRUTA = RAIZ / "saida_nasa" / "preprocessado" / "dados_modelagem.csv"
# So a variante pos-hoc le o agrupamento do modulo 2: os perfis de
# comportamento saem das curvas, e o k e o que grupos.py escolheu.
CURVAS = RAIZ / "saida_nasa" / "curvas" / "features_curvas.csv"
GRUPOS = RAIZ / "saida_nasa" / "cluster" / "agrupamento" / "grupos_comportamento.csv"
SAIDA = RAIZ / "saida_nasa" / "classificacao"

# Paleta categorica validada para daltonismo (modo claro), slots 1..8 em ordem fixa
PAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
       "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e3e2de"
MUTED = "#898781"          # o que o kNN acertou: fundo, para o erro aparecer
SEQ = ["#f0efec", "#cfe0f5", "#9dc3ea", "#6d9fe4", "#2a78d6", "#104281"]

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
ROTULO_MODELO = {"Regressao logistica": "Regressão logística"}

# k impar: no voto por maioria entre duas classes nao ha empate.
GRADE_K = [1, 3, 5, 7, 9, 11, 15, 21, 25, 31, 41, 51, 61, 81, 101, 151, 201]
TOLERANCIA_K = 0.01        # acuracia balanceada; com 25 celulas, menos que isso e ruido
N_VIZINHOS_CSV = 3         # vizinhos listados por previsao em predicoes_teste.csv
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
    return df


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


def condicao(c):
    """'2 A / 24 C' -> '2 A / 24 °C', para os graficos."""
    return c[:-1] + "°C" if c.endswith(" C") else c


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


def referencias():
    """As familias dos trabalhos relacionados, com os hiperparametros padrao.

    max_iter da logistica e a unica excecao: com os pares colineares o padrao
    de 100 iteracoes nao converge.
    """
    from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.svm import SVC
    return {
        "Regressao logistica": make_pipeline(preparo(), LogisticRegression(max_iter=2000)),
        "SVM (RBF)": make_pipeline(preparo(), SVC()),
        "Random Forest": make_pipeline(preparo(), RandomForestClassifier(random_state=SEMENTE)),
        "Gradient Boosting": make_pipeline(
            preparo(), HistGradientBoostingClassifier(random_state=SEMENTE)),
    }


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


def votos_loco(mods, X, y, celulas, ks):
    """Fracao de vizinhos em fim de vida para cada k, uma celula de fora por vez.

    Os vizinhos de cada rodada sao procurados uma vez so, com o maior k, e o
    voto de cada k sai dos primeiros k da lista ordenada por distancia. Da o
    mesmo resultado que ajustar um KNeighborsClassifier por k, numa fracao do
    tempo.
    """
    np = mods["numpy"]
    from sklearn.neighbors import NearestNeighbors
    ks = np.asarray(ks)
    votos = np.zeros((len(y), len(ks)))
    for c in np.unique(celulas):
        te = celulas == c
        prep = preparo().fit(X[~te])
        nn = NearestNeighbors(n_neighbors=int(ks.max())).fit(prep.transform(X[~te]))
        _, idx = nn.kneighbors(prep.transform(X[te]))
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


def prever_fora(mods, modelo, X, y, grupos):
    """Cada grupo e previsto por um modelo ajustado sem ele: classe e escore."""
    np = mods["numpy"]
    from sklearn.base import clone
    pred, escore = np.zeros_like(y), np.zeros(len(y))
    for g in np.unique(grupos):
        te = grupos == g
        m = clone(modelo).fit(X[~te], y[~te])
        pred[te] = m.predict(X[te])
        escore[te] = pontuar(m, X[te])
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
def etapa_k(mods, tr, conj, tolerancia, k_forcado):
    """Curva de acuracia contra k em cada conjunto, e o k de cada um."""
    np, pd = mods["numpy"], mods["pandas"]
    y, cel = tr.fim_de_vida.to_numpy(), tr.battery_id.to_numpy()
    tab = {}
    for n, cols in conj.items():
        v = votos_loco(mods, tr[cols].to_numpy(), y, cel, GRADE_K)
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


def etapa_comparacao(mods, tr, conj, k_conj, refs):
    """Protocolo, atributos e algoritmo, so nas celulas de treino."""
    np, pd = mods["numpy"], mods["pandas"]
    y, cel = tr.fim_de_vida.to_numpy(), tr.battery_id.to_numpy()
    aleat = particao_aleatoria(mods, y)
    nome_knn = f"kNN (k = {k_conj['relativas']})"
    modelos = {nome_knn: None, **refs}
    linhas = []
    for nome, modelo in modelos.items():
        t0 = time.time()
        for n, cols in conj.items():
            m = knn(k_conj[n]) if modelo is None else modelo
            X = tr[cols].to_numpy()
            esquemas = [("uma celula de fora", cel)]
            if n == "relativas":
                esquemas.append(("aleatoria por descarga", aleat))
            for esquema, grupos in esquemas:
                pred, escore = prever_fora(mods, m, X, y, grupos)
                if modelo is None and n == "relativas" and grupos is cel:
                    pred_knn = pred
                met = metricas(np, y, pred)
                # No CSV o kNN e "kNN" e o k vai na coluna propria: cada conjunto
                # tem o seu k, e o nome com o k do relativo enganaria.
                linhas.append({"modelo": "kNN" if modelo is None else nome,
                               "atributos": n, "validacao": esquema,
                               "k": k_conj[n] if modelo is None else None,
                               "acuracia_balanceada": met["acuracia_balanceada"],
                               "sensibilidade": met["sensibilidade"],
                               "especificidade": met["especificidade"],
                               "f1_fim_de_vida": met["f1_fim_de_vida"],
                               "auc": auc(np, y, escore)})
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
    vaz = pd.DataFrame([{"k": k_conj["relativas"],
                         "vizinho_mais_proximo_da_mesma_celula": perto,
                         "vizinhos_da_mesma_celula_media": media}])
    p(f"  particao aleatoria: o vizinho mais proximo e da mesma celula em {perto:.1%}")
    p(f"  das descargas, e {media:.1%} dos {k_conj['relativas']} vizinhos tambem, "
      f"em media")

    # Quanto o acerto varia de uma celula para outra: e essa variacao que decide
    # se 8 celulas de teste bastam para ordenar algoritmos.
    por_cel = (pd.DataFrame({"battery_id": cel, "fim_de_vida": y, "acerto": pred_knn == y})
               .groupby("battery_id")
               .agg(descargas=("acerto", "size"), fracao_fim_de_vida=("fim_de_vida", "mean"),
                    acuracia=("acerto", "mean"))
               .reset_index())
    q = por_cel.acuracia.quantile([0, 0.25, 0.5, 1]).to_numpy()
    p(f"  acerto do kNN por celula de treino: de {q[0]:.0%} a {q[3]:.0%} "
      f"(quartil inferior {q[1]:.0%}, mediana {q[2]:.0%})")
    return comp, piv, vaz, por_cel, nome_knn


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

    por = (prev.assign(alarme_falso=(pred == 1) & (y_te == 0),
                       nao_detectado=(pred == 0) & (y_te == 1))
           .groupby(["battery_id", "test_condition"])
           .agg(descargas=("acerto", "size"), fim_de_vida_real=("fim_de_vida", "sum"),
                fim_de_vida_previsto=("previsto", "sum"), acuracia=("acerto", "mean"),
                alarmes_falsos=("alarme_falso", "sum"),
                nao_detectados=("nao_detectado", "sum"), soh_minimo=(ALVO, "min"))
           .reset_index())
    p("")
    p(f"  por celula, kNN (k = {k}):")
    for r in por.itertuples(index=False):
        p(f"    {r.battery_id} {r.test_condition:<11} {r.descargas:>4} descargas, "
          f"{r.fim_de_vida_real:>3} em fim de vida, acerto {r.acuracia:.0%}, "
          f"{r.alarmes_falsos} alarme(s) falso(s), {r.nao_detectados} nao detectado(s)")
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


def _tinta(cor):
    """Texto sobre um preenchimento: tinta escura ou clara pela luminancia dele."""
    from matplotlib.colors import to_rgb
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in to_rgb(cor)]
    lum = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    return INK if lum > 0.18 else SURF


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
    refs = [m for m in piv.sort_values("relativas", ascending=False).index if m != nome_knn]
    piv = piv.loc[[nome_knn] + refs]
    n = len(piv)
    fig, ax = plt.subplots(figsize=(10, 0.62 * n + 3.1))
    ys = np.arange(n)[::-1]
    cols = [c for c in CONJUNTOS if c in piv.columns]
    for y, (_, r) in zip(ys, piv.iterrows()):
        ax.plot([100 * r[cols].min(), 100 * r.aleatoria], [y, y], color=GRID,
                linewidth=3, solid_capstyle="round", zorder=1)
    # Bruto e completo saem um pouco da linha: quando dois conjuntos empatam, um
    # marcador cobriria o outro. O relativo e o vazado ficam na linha.
    desvio = {"brutas": 0.14, "todas": -0.14, "relativas": 0.0}
    for c in [c for c in ("brutas", "todas", "relativas") if c in cols]:
        cor, mk = COR_CONJUNTO[c]
        ax.scatter(100 * piv[c], ys + desvio[c], s=80, color=cor, marker=mk,
                   edgecolors=SURF, linewidths=1.5, zorder=3, label=NOME_CONJUNTO[c])
    ax.scatter(100 * piv.aleatoria, ys, s=80, marker="D", facecolors=SURF,
               edgecolors=PAL[0], linewidths=1.8, zorder=3,
               label="relativos, partição aleatória (vazada)")
    ax.axvline(50, color=INK2, linewidth=1, linestyle=":", zorder=0)
    ax.text(50.5, -0.55, "acaso", fontsize=9, color=INK2, va="bottom", ha="left")
    ax.set_yticks(ys, [ROTULO_MODELO.get(m, m) for m in piv.index])
    for t in ax.get_yticklabels():
        if t.get_text() == nome_knn:
            t.set_fontweight("bold")
            t.set_color(INK)
    ax.set_xlim(45, 100)
    ax.set_ylim(-0.7, n - 0.3)
    ax.set_xlabel("acurácia balanceada (%)")
    ax.grid(axis="y", visible=False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.legend(fontsize=9, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2,
              borderaxespad=0.4)

    inflacao = 100 * (piv.aleatoria - piv.relativas)
    sub = ("Acurácia balanceada nas 25 células de treino. Pontos cheios: validação que "
           "deixa uma célula de fora por vez; losango vazado: a mesma conta com partição "
           "aleatória por descarga, que põe a mesma célula dos dois lados. "
           f"A partição aleatória soma de {virg(inflacao.min(), 0)} a "
           f"{virg(inflacao.max(), 0)} p.p.")
    if "brutas" in cols:
        efeito = 100 * (piv.relativas - piv.brutas)
        sub += (f"; trocar atributos brutos por relativos muda de "
                f"{virg(efeito.min(), 0)} a {virg(efeito.max(), 0)} p.p.")
    if refs:
        dif = 100 * (piv.relativas[nome_knn] - piv.relativas[refs].max())
        lado = "acima" if dif >= 0 else "abaixo"
        sub += (f"; com os atributos relativos, o kNN fica {virg(abs(dif), 1)} p.p. {lado} "
                f"da melhor das famílias dos trabalhos relacionados (as demais linhas, com "
                f"hiperparâmetros padrão)")
    titulo_figura(plt, fig, "Protocolo, atributos e algoritmo: o que mais pesa", sub + ".")
    salvar(plt, fig, "02_protocolo_atributos_algoritmo.png")


def fig_teste(mods, plt, res, piv, nome_knn):
    """Teste com intervalo, ao lado da validacao: o ranking se sustenta?"""
    np = mods["numpy"]
    t = res.set_index("modelo")
    refs = [m for m in piv.sort_values("relativas", ascending=False).index if m != nome_knn]
    ordem = [nome_knn] + refs
    t, cv = t.loc[ordem], piv.relativas.loc[ordem]
    n = len(t)
    fig, ax = plt.subplots(figsize=(10, 0.62 * n + 3.1))
    ys = np.arange(n)[::-1]
    ax.hlines(ys, 100 * t.ic95_inferior, 100 * t.ic95_superior, color=PAL[0],
              linewidth=2, zorder=2)
    ax.scatter(100 * t.acuracia_balanceada, ys, s=80, marker="D", color=PAL[0],
               edgecolors=SURF, linewidths=1.5, zorder=3,
               label="teste: 8 células, com IC 95% por reamostragem de células")
    ax.scatter(100 * cv, ys, s=70, marker="o", facecolors=SURF, edgecolors=INK2,
               linewidths=1.6, zorder=3,
               label="validação: 25 células de treino, uma de fora por vez")
    ax.axvline(50, color=INK2, linewidth=1, linestyle=":", zorder=0)
    ax.text(50.5, -0.55, "acaso", fontsize=9, color=INK2, va="bottom", ha="left")
    ax.set_yticks(ys, [ROTULO_MODELO.get(m, m) for m in ordem])
    for tk in ax.get_yticklabels():
        if tk.get_text() == nome_knn:
            tk.set_fontweight("bold")
            tk.set_color(INK)
    ax.set_xlim(45, 100)
    ax.set_ylim(-0.7, n - 0.3)
    ax.set_xlabel("acurácia balanceada (%)")
    ax.grid(axis="y", visible=False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.legend(fontsize=9, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=1,
              borderaxespad=0.4)

    pos_cv = int((cv > cv[nome_knn]).sum()) + 1
    pos_te = int((t.acuracia_balanceada > t.acuracia_balanceada[nome_knn]).sum()) + 1
    sub = ("Acurácia balanceada com os atributos relativos ao início de vida. O losango é o "
           "teste nas 8 células nunca vistas, com o intervalo de 95% de reamostrar células "
           "inteiras; o círculo vazado é a validação nas 25 células de treino. "
           f"O kNN fica em {pos_cv}º de {n} na validação e em {pos_te}º no teste.")
    if refs:
        fora = [r for r in t.iloc[1:].itertuples()
                if r.dif_ic95_inferior > 0 or r.dif_ic95_superior < 0]
        sub += (f" Medida em pares, nas mesmas reamostragens, a diferença para o kNN exclui "
                f"o zero em {len(fora)} das {len(refs)} referências.")
    titulo_figura(plt, fig, "Validação e teste: a ordem dos algoritmos muda", sub)
    salvar(plt, fig, "03_teste_comparacao.png")


def fig_confusao(mods, plt, met, k):
    np = mods["numpy"]
    from matplotlib.colors import LinearSegmentedColormap
    m = np.array([[met["vn"], met["fp"]], [met["fn"], met["vp"]]], dtype=float)
    frac = m / m.sum(axis=1, keepdims=True)
    cmap = LinearSegmentedColormap.from_list("seq", SEQ)
    fig, ax = plt.subplots(figsize=(6.8, 5.6))
    ax.imshow(frac, cmap=cmap, vmin=0, vmax=1)
    rotulos = ["saudável", "fim de vida"]
    for i in range(2):
        for j in range(2):
            ax.text(j, i, f"{int(m[i, j])}\n{virg(100 * frac[i, j], 0)}%", ha="center",
                    va="center", fontsize=14, color=_tinta(cmap(frac[i, j])),
                    fontweight="bold" if i == j else "normal", linespacing=1.4)
    ax.set_xticks([0, 1], rotulos)
    ax.set_yticks([0, 1], rotulos)
    ax.xaxis.tick_top()
    ax.xaxis.set_label_position("top")
    ax.set_xlabel("previsto pelo kNN")
    ax.set_ylabel(f"real (SOH < {FIM_DE_VIDA:.0f}% = fim de vida)")
    ax.set_xticks([0.5], minor=True)
    ax.set_yticks([0.5], minor=True)
    ax.grid(which="minor", color=SURF, linewidth=3)
    ax.grid(which="major", visible=False)
    ax.tick_params(which="both", length=0)
    for lado in ax.spines.values():
        lado.set_visible(False)
    sub = (f"{met['descargas']} descargas de 8 células que não participaram de nenhuma "
           f"escolha; kNN com k = {k} e atributos relativos ao início de vida. Acurácia "
           f"balanceada de {virg(100 * met['acuracia_balanceada'])}% (IC 95% por "
           f"reamostragem de células: {virg(100 * met['ic95_inferior'], 0)} a "
           f"{virg(100 * met['ic95_superior'], 0)}%). Percentuais sobre cada classe real: "
           f"a diagonal é a taxa de acerto de cada uma.")
    titulo_figura(plt, fig, "Teste em células nunca vistas", sub)
    salvar(plt, fig, "04_matriz_confusao.png")


def fig_celulas(mods, plt, prev, k):
    from matplotlib.lines import Line2D
    grupos = list(prev.groupby(["battery_id", "test_condition"], sort=True))
    ncol = 4
    nlin = -(-len(grupos) // ncol)
    fig, axes = plt.subplots(nlin, ncol, figsize=(13, 2.9 * nlin + 1.9), squeeze=False)
    for i, (ax, ((bat, cond), g)) in enumerate(zip(axes.flat, grupos)):
        certo = g.acerto.to_numpy()
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
                    markeredgecolor=SURF, label="erro do kNN"),
             Line2D([], [], color=INK2, linestyle="--", linewidth=1.1,
                    label=f"limiar de fim de vida ({FIM_DE_VIDA:.0f}%)")]
    sobra = list(axes.flat)[len(grupos):]
    for ax in sobra:
        ax.axis("off")
    if sobra:
        sobra[0].legend(handles=alcas, loc="center", fontsize=9.5)
    else:
        fig.legend(handles=alcas, loc="lower center", ncol=3, fontsize=9.5)
    erros = prev[~prev.acerto]
    perto = ((erros[ALVO] - FIM_DE_VIDA).abs() < PERTO_DO_LIMIAR).mean() if len(erros) else 0
    sub = (f"Cada painel é uma célula de teste numa condição de ensaio, com o kNN de k = {k}. "
           f"Acima da linha de {FIM_DE_VIDA:.0f}% o erro é alarme falso; abaixo, fim de vida "
           f"não detectado. {virg(100 * perto, 0)}% dos {len(erros)} erros ficam a menos de "
           f"{virg(PERTO_DO_LIMIAR, 0)} p.p. do limiar.")
    titulo_figura(plt, fig, "Onde o kNN erra", sub)
    salvar(plt, fig, "05_teste_por_celula.png")


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
    salvar(plt, fig, "07_curvas_roc.png")


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
    salvar(plt, fig, "06_variante_mesmo_grupo.png")


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
    a = ap.parse_args()

    mods = checar()
    SAIDA.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    p("Classificacao de fim de vida com kNN")
    p("=" * 60)
    df = carregar(mods)
    conj = conjuntos(df)
    tr = df[df.split == "treino"].reset_index(drop=True)
    te = df[df.split == "teste"].reset_index(drop=True)
    for nome, d in (("treino", tr), ("teste", te)):
        p(f"  {nome:<6} {len(d):>4} descargas, {d.battery_id.nunique():>2} celulas, "
          f"{d.fim_de_vida.mean():.1%} em fim de vida (SOH < {FIM_DE_VIDA:.0f}%)")
    for n, cols in conj.items():
        p(f"  atributos {n:<9} {len(cols):>2}: {', '.join(cols)}")

    p("")
    p("1. escolha de k, uma celula de treino de fora por vez:")
    tab, k_conj = etapa_k(mods, tr, conj, a.tolerancia, a.k)
    k = k_conj["relativas"]

    p("")
    p("2. protocolo, atributos e algoritmo (so treino):")
    refs = {} if a.sem_referencias else referencias()
    comp, piv, vaz, por_cel, nome_knn = etapa_comparacao(mods, tr, conj, k_conj, refs)

    p("")
    p("3. teste: 8 celulas, avaliadas uma vez:")
    res, prev, por, escores, y_te = etapa_teste(mods, tr, te, conj, k, refs, nome_knn)

    p("")
    variante = None
    if CURVAS.exists() and GRUPOS.exists():
        p("4. variante pos-hoc, vizinhos so do mesmo grupo de comportamento (so validacao):")
        variante = etapa_variante(mods, tr, conj, tab, k, a.tolerancia)
        por_cel = por_cel.merge(variante[1].reset_index(), on="battery_id", how="left")
    else:
        p("4. variante pulada: falta o agrupamento. Rode antes: python src/curvas.py "
          "e python src/grupos.py")

    arquivos = {"escolha_de_k.csv": tab, "comparacao.csv": comp, "vazamento.csv": vaz,
                "validacao_por_celula.csv": por_cel, "teste.csv": res,
                "teste_por_celula.csv": por, "predicoes_teste.csv": prev}
    if variante:
        arquivos["variante_mesmo_grupo.csv"] = variante[0]
    p("")
    for nome, tabela in arquivos.items():
        tabela.round(4).to_csv(SAIDA / nome, index=nome in ("escolha_de_k.csv",
                                                            "variante_mesmo_grupo.csv"))
        p(f"  {(SAIDA / nome).relative_to(RAIZ)}")

    if not a.sem_graficos:
        p("")
        p("graficos:")
        plt = estilo(mods)
        fig_escolha_k(mods, plt, tab, k, a.tolerancia)
        fig_hierarquia(mods, plt, piv, nome_knn)
        fig_teste(mods, plt, res, piv, nome_knn)
        fig_confusao(mods, plt, res.iloc[0].to_dict(), k)
        fig_celulas(mods, plt, prev, k)
        fig_roc(mods, plt, y_te, escores, res)
        if variante:
            fig_variante(mods, plt, variante[0], variante[2])
    p("")
    p(f"  tempo total: {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
