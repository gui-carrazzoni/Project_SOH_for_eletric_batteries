#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A variavel baterias_por_condicao: o grupo de comportamento como atributo.

    python baterias_por_condicao.py                # correlacao com o SOH e efeito nos modelos
    python baterias_por_condicao.py --sem-graficos # so as tabelas

Escreve saida_nasa/baterias_por_condicao/: correlacao/ e comparacao/, cada uma
com tabelas/ e figuras/. As pastas classificacao/ e regressao/ ao lado sao de
classificacao.py --com-grupo e regressao.py --com-grupo.

**O que e a variavel.** O grupo de comportamento medido de grupos.py — os 6
grupos de k=6 mais o dos pares extremos, G1 a G7 — de cada par bateria x
condicao. E nominal: G3 nao fica entre G2 e G4. Nos modelos entra como sete
indicadores, `baterias_por_condicao_G1` a `_G7`, um por grupo, e nao como um
numero so, que inventaria uma ordem.

**Sem vazamento: o agrupamento so ve o treino.** Os grupos de grupos.py foram
ajustados com todas as celulas, as de teste inclusive. Como atributo, isso
deixaria a celula avaliada pesar no proprio rotulo. Codificacao refaz o
agrupamento com grupos.ajustar — os mesmos atributos, extremos a parte, PCA e
Ward com o k de grupos.py — so nas celulas de treino, e os pares de teste
entram no grupo de centroide mais proximo. Na validacao deixando uma celula de
fora, o agrupamento e refeito a cada rodada sem ela. Os rotulos de cada ajuste
sao renomeados para os de grupos.py pelo pareamento de maior concordancia
(algoritmo hungaro), para que G4 seja o mesmo grupo em toda parte.

**A correlacao com o SOH e a razao de correlacao (eta)**, a parte da variancia
do SOH explicada pela media de cada grupo, na raiz: eta^2 = SQ entre grupos /
SQ total. E o analogo do |r| de Pearson para uma variavel nominal, e sai ao
lado do |r| agrupado dos atributos de correlacao_soh.py, na mesma tabela de
descargas. Por construcao eta >= |r| de qualquer codificacao numerica dos
grupos. Cada indicador ganha a correlacao ponto-bisserial com o SOH: o sinal diz
se o grupo fica acima ou abaixo da media. A condicao nominal, test_condition,
entra como referencia.

**Nao existe correlacao intracelula.** A variavel e constante dentro de cada
par, como a temperatura ambiente. Ela so pode dizer ao modelo em que regime a
celula esta, nao quanto ela degradou dentro dele. O teste de Kruskal-Wallis e
feito com uma media de SOH por par, e nao por descarga: descargas da mesma
celula nao sao independentes.

**O efeito nos modelos e medido em pares.** As mesmas descargas de teste,
previstas com e sem a variavel, passam pelas mesmas reamostragens de celulas,
e o intervalo da diferenca diz se a variavel muda algo que 8 celulas consigam
distinguir.

Dependencias: numpy, pandas, scipy, matplotlib
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# A raiz do projeto e a pasta acima de src/: e la que ficam
# cleaned_nasa_dataset/ e saida_nasa/.
RAIZ = Path(__file__).resolve().parent.parent
CURVAS = RAIZ / "saida_nasa" / "curvas" / "tabelas" / "features_curvas.csv"
GRUPOS = (RAIZ / "saida_nasa" / "cluster" / "agrupamento" / "tabelas"
          / "grupos_comportamento.csv")
TABELA = RAIZ / "saida_nasa" / "correlacao" / "tabelas" / "tabela_modelagem.csv"
RANKING = RAIZ / "saida_nasa" / "correlacao" / "tabelas" / "ranking_vs_soh.csv"
SAIDA = RAIZ / "saida_nasa" / "baterias_por_condicao"
# Sem e com a variavel: as saidas de classificacao.py e regressao.py.
SEM = {"classificacao": RAIZ / "saida_nasa" / "classificacao" / "tabelas",
       "regressao": RAIZ / "saida_nasa" / "regressao" / "tabelas"}
COM = {t: SAIDA / t / "tabelas" for t in SEM}

PAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
       "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e3e2de"
MUTED = "#898781"
FAIXA = "#cfe0f5"          # intervalo de confianca: o azul do teste, lavado
RECUO_SETA = 6.5           # pt: a seta para antes do centro do marcador, sem cobri-lo

NOME = "baterias_por_condicao"
ALVO = "SOH"
FIM_DE_VIDA = 80.0
N_BOOT = 2000              # reamostragens de celulas, como em classificacao.py e regressao.py
SEMENTE = 0

# Modelo, coluna da previsao em predicoes_teste.csv. O kNN e o GAM primeiro,
# depois as referencias na ordem de classificacao.py e regressao.py.
MODELOS = {
    "classificacao": [("kNN", "previsto"),
                      ("Regressao logistica", "previsto_regressao_logistica"),
                      ("SVM (RBF)", "previsto_svm"),
                      ("Random Forest", "previsto_random_forest"),
                      ("Gradient Boosting", "previsto_gradient_boosting")],
    "regressao": [("GAM", "soh_gam"),
                  ("Regressao linear", "soh_regressao_linear"),
                  ("SVR (RBF)", "soh_svr"),
                  ("Random Forest", "soh_random_forest"),
                  ("Processo gaussiano", "soh_processo_gaussiano")],
}
ROTULO_MODELO = {"Regressao logistica": "Regressão logística",
                 "Regressao linear": "Regressão linear"}


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


# ---------------------------------------------------------------------------
# a variavel como atributo: o que classificacao.py e regressao.py importam
# ---------------------------------------------------------------------------
class Codificacao:
    """baterias_por_condicao em indicadores, sem que o agrupamento veja quem e avaliado.

    Ao ser criada, escreve em `tr` e `te` a coluna `baterias_por_condicao` (o
    grupo, 1 a 7; 0 para par sem perfil de comportamento) e os indicadores de
    `colunas`, com o agrupamento ajustado so nas celulas de treino: e o que o
    modelo final e o teste usam. `rodada` troca os indicadores na validacao.
    """

    def __init__(self, mods, tr, te):
        import grupos
        pd = mods["pandas"]
        for f, etapa in ((CURVAS, "curvas.py"), (GRUPOS, "grupos.py")):
            if not f.exists():
                p(f"ERRO: {f.relative_to(RAIZ)} nao existe.")
                p(f"    Rode antes: python src/{etapa}")
                sys.exit(1)
        self.mods = mods
        glob = pd.read_csv(GRUPOS)
        self.k = int(glob.query("not extremo").grupo.nunique())
        self.de_grupos = dict(zip(zip(glob.battery_id, glob.condicao), glob.grupo))
        self.niveis = sorted(int(g) for g in glob.grupo.unique())
        self.nomes = dict(zip(glob.grupo, glob.grupo_comportamento))
        self.colunas = [f"{NOME}_G{g}" for g in self.niveis]
        self.perfil = grupos.perfis(mods, pd.read_csv(CURVAS))
        self.pares_tr = list(zip(tr.battery_id, tr.test_condition))
        self.celulas_tr = set(tr.battery_id)
        self._sem = {}

        self.final = self.rotular(self.celulas_tr)
        for d in (tr, te):
            g = [self.final.get(par, 0) for par in zip(d.battery_id, d.test_condition)]
            d[NOME] = g
            for c, v in zip(self.colunas, self._indicadores(g).T):
                d[c] = v

    def rotular(self, celulas):
        """Grupo de cada par, com o agrupamento ajustado so nos pares de `celulas`.

        Os demais pares entram pelo encaixe de grupos.ajustar. Os rotulos voltam
        com os numeros de grupos.py: o extremo (0 em ajustar) e o ultimo nivel, e
        os outros sao pareados aos de grupos.py pela maior concordancia nos pares
        ajustados.
        """
        np = self.mods["numpy"]
        import grupos
        from scipy.optimize import linear_sum_assignment
        dentro = self.perfil.battery_id.isin(celulas).to_numpy()
        pt = self.perfil[dentro].reset_index(drop=True)
        pn = self.perfil[~dentro].reset_index(drop=True)
        rot, encaixar = grupos.ajustar(self.mods, pt, self.k)
        ref = np.array([self.de_grupos.get(par, -1) for par in zip(pt.battery_id, pt.condicao)])
        conta = np.array([[np.sum((rot == a) & (ref == b)) for b in range(1, self.k + 1)]
                          for a in range(1, self.k + 1)])
        lin, col = linear_sum_assignment(-conta)
        mapa = {0: self.k + 1, **{int(a) + 1: int(b) + 1 for a, b in zip(lin, col)}}
        pares = list(zip(pt.battery_id, pt.condicao)) + list(zip(pn.battery_id, pn.condicao))
        rotulos = np.r_[rot, encaixar(pn) if len(pn) else []].astype(int)
        return {par: mapa[int(g)] for par, g in zip(pares, rotulos)}

    def _indicadores(self, g):
        np = self.mods["numpy"]
        g = np.asarray(g)
        return (g[:, None] == np.array(self.niveis)[None]).astype(float)

    def sem(self, celula):
        """Indicadores de cada descarga de treino, com o agrupamento ajustado sem `celula`."""
        if celula not in self._sem:
            g = self.rotular(self.celulas_tr - {celula})
            self._sem[celula] = self._indicadores([g.get(par, 0) for par in self.pares_tr])
        return self._sem[celula]

    def rodada(self, cols, celulas):
        """Funcao (X, te) -> X da rodada em que as descargas `te` ficam de fora.

        `cols` sao as colunas de X e `celulas` a celula de cada linha, ambas de
        treino. Os indicadores de X sao trocados pelos do agrupamento ajustado
        sem a celula de fora. Devolve None quando `cols` nao tem a variavel.
        """
        np = self.mods["numpy"]
        idx = [i for i, c in enumerate(cols) if c in self.colunas]
        if not idx:
            return None
        ordem = [self.colunas.index(cols[i]) for i in idx]

        def trocar(X, te):
            fora = np.unique(celulas[te])
            if len(fora) != 1:
                raise ValueError("a troca dos indicadores pede uma celula de fora por rodada")
            X = np.array(X, dtype=float)
            X[:, idx] = self.sem(fora[0])[:, ordem]
            return X
        return trocar

    def relatar(self, tr, te):
        """Quanto o agrupamento so com o treino concorda com o de grupos.py."""
        np = self.mods["numpy"]
        import grupos
        p(f"  {NOME}: agrupamento de grupos.py (k={self.k} + extremos) refeito so com as "
          f"{len(self.celulas_tr)} celulas de treino;")
        p("  os pares de teste entram no grupo de centroide mais proximo, e na validacao o")
        p("  agrupamento e refeito a cada rodada sem a celula deixada de fora")
        for nome, d in (("treino", tr), ("teste", te)):
            pares = d[["battery_id", "test_condition", NOME]].drop_duplicates()
            ref = np.array([self.de_grupos.get(par, -1)
                            for par in zip(pares.battery_id, pares.test_condition)])
            igual = int((ref == pares[NOME].to_numpy()).sum())
            p(f"    {nome:<6} {igual} de {len(pares)} pares no mesmo grupo de grupos.py "
              f"(ARI {grupos.ari(self.mods, ref, pares[NOME].to_numpy()):+.2f})")
        # Quanto o agrupamento depende de cada celula: sem ela, quantos dos
        # outros pares de treino mudam de grupo.
        pares = sorted(set(self.pares_tr))
        mudam = []
        for c in sorted(self.celulas_tr):
            g = self.rotular(self.celulas_tr - {c})
            mudam.append(sum(g.get(par, 0) != self.final.get(par, 0)
                             for par in pares if par[0] != c))
        p(f"    validacao: sem a celula de fora, mudam de grupo em mediana {np.median(mudam):.0f} "
          f"dos outros pares de treino (de {min(mudam)} a {max(mudam)})")
        p(f"  entra como {len(self.colunas)} indicadores: {', '.join(self.colunas)}")


# ---------------------------------------------------------------------------
# correlacao com o SOH
# ---------------------------------------------------------------------------
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
    for f, etapa in ((TABELA, "correlacao_soh.py"), (RANKING, "correlacao_soh.py"),
                     (GRUPOS, "grupos.py")):
        if not f.exists():
            p(f"ERRO: {f.relative_to(RAIZ)} nao existe.")
            p(f"    Rode antes: python src/{etapa}")
            sys.exit(1)
    return mods


def eta(np, rotulo, y):
    """Razao de correlacao: raiz da fracao da variancia de y explicada pela media de cada rotulo."""
    rotulo, y = np.asarray(rotulo), np.asarray(y, dtype=float)
    sst = ((y - y.mean()) ** 2).sum()
    sse = sum(((y[rotulo == g] - y[rotulo == g].mean()) ** 2).sum() for g in np.unique(rotulo))
    return float(np.sqrt(1 - sse / sst)) if sst > 0 else float("nan")


def carregar(mods):
    """As descargas de correlacao_soh.py, com o filtro de qualidade dele, e o grupo de cada par."""
    pd = mods["pandas"]
    df = pd.read_csv(TABELA, usecols=["battery_id", "test_condition", ALVO, "quality_flag"])
    df = df[df.quality_flag.isna() | (df.quality_flag == "")].dropna(subset=[ALVO])
    g = pd.read_csv(GRUPOS)
    df = df.merge(g[["battery_id", "condicao", "grupo", "grupo_comportamento"]].rename(
        columns={"condicao": "test_condition", "grupo": NOME}),
        on=["battery_id", "test_condition"], how="left", validate="many_to_one")
    sem = df[NOME].isna()
    if sem.any():
        p(f"  {int(sem.sum())} descargas de pares sem grupo ficam de fora: "
          + ", ".join(f"{b} {c}" for b, c in
                      df.loc[sem, ["battery_id", "test_condition"]].drop_duplicates().to_numpy()))
    df = df[~sem].copy()
    df[NOME] = df[NOME].astype(int)
    return df.reset_index(drop=True)


def correlacao(mods, df):
    """eta da variavel e da condicao nominal, e o perfil de SOH de cada grupo."""
    np, pd = mods["numpy"], mods["pandas"]
    from scipy.stats import kruskal
    y = df[ALVO].to_numpy(float)
    e_grupo, e_cond = eta(np, df[NOME], y), eta(np, df.test_condition, y)

    linhas = []
    for gid, b in df.groupby(NOME):
        ind = (df[NOME] == gid).to_numpy(float)
        linhas.append({
            "grupo": gid, "grupo_comportamento": b.grupo_comportamento.iat[0],
            "pares": b.groupby(["battery_id", "test_condition"]).ngroups,
            "descargas": len(b), "soh_medio": b[ALVO].mean(), "soh_mediana": b[ALVO].median(),
            "soh_p10": b[ALVO].quantile(0.10), "soh_p90": b[ALVO].quantile(0.90),
            "fracao_fim_de_vida": (b[ALVO] < FIM_DE_VIDA).mean(),
            "r_ponto_bisserial": float(np.corrcoef(ind, y)[0, 1]),
        })
    por_grupo = pd.DataFrame(linhas)

    # Uma media por par: descargas da mesma celula nao sao observacoes independentes.
    pares = df.groupby(["battery_id", "test_condition", NOME])[ALVO].mean().reset_index()
    kw = kruskal(*[g[ALVO].to_numpy() for _, g in pares.groupby(NOME)])
    e_par = eta(np, pares[NOME], pares[ALVO])
    resumo = pd.DataFrame([
        {"variavel": NOME, "niveis": df[NOME].nunique(), "descargas": len(df),
         "pares": len(pares), "eta": e_grupo, "eta2": e_grupo ** 2, "eta_por_par": e_par,
         "kruskal_H_por_par": float(kw.statistic), "kruskal_p_por_par": float(kw.pvalue),
         "correlacao_intracelula": np.nan},
        {"variavel": "test_condition", "niveis": df.test_condition.nunique(),
         "descargas": len(df), "pares": len(pares), "eta": e_cond, "eta2": e_cond ** 2,
         "eta_por_par": eta(np, pares.test_condition, pares[ALVO]),
         "kruskal_H_por_par": np.nan, "kruskal_p_por_par": np.nan,
         "correlacao_intracelula": np.nan}])

    # Ao lado do |r| agrupado dos atributos de correlacao_soh.py: a mesma tabela
    # de descargas, com o mesmo filtro de qualidade.
    rk = pd.read_csv(RANKING, index_col=0)
    rk = rk[~rk.is_leakage]
    ranking = pd.concat([
        pd.DataFrame({"variavel": rk.index, "tipo": "numerica", "medida": "|r| de Pearson",
                      "correlacao_agrupada": rk.pooled_correlation.to_numpy(),
                      "forca_agrupada": rk.pooled_correlation.abs().to_numpy(),
                      "correlacao_intracelula": rk.within_cell_correlation.to_numpy()}),
        pd.DataFrame({"variavel": [NOME, "test_condition"], "tipo": "categorica",
                      "medida": "eta", "correlacao_agrupada": np.nan,
                      "forca_agrupada": [e_grupo, e_cond], "correlacao_intracelula": np.nan}),
    ], ignore_index=True).sort_values("forca_agrupada", ascending=False)

    p(f"  {len(df)} descargas de {len(pares)} pares, {df[NOME].nunique()} grupos")
    p(f"  eta de {NOME} com o SOH: {e_grupo:.3f} (eta2 = {e_grupo ** 2:.3f}: "
      f"{e_grupo ** 2:.0%} da variancia do SOH)")
    p(f"  eta da condicao nominal (test_condition), para comparar: {e_cond:.3f} "
      f"(eta2 = {e_cond ** 2:.3f})")
    p(f"  com uma media de SOH por par: eta {e_par:.3f}; Kruskal-Wallis H = "
      f"{kw.statistic:.2f}, p = {kw.pvalue:.3g}")
    p("  correlacao intracelula: nao existe, a variavel e constante dentro de cada par")
    p("")
    p(f"  {'grupo':<30} {'pares':>5} {'desc.':>6} {'SOH medio':>10} {'fim de vida':>12} "
      f"{'r pb':>6}")
    for r in por_grupo.itertuples(index=False):
        p(f"  {r.grupo_comportamento:<30} {r.pares:>5} {r.descargas:>6} {r.soh_medio:>9.1f}% "
          f"{r.fracao_fim_de_vida:>11.0%} {r.r_ponto_bisserial:>+6.2f}")
    p("  r pb: correlacao ponto-bisserial do indicador do grupo com o SOH")
    p("")
    p("  forca da associacao com o SOH, todas as descargas juntas (|r| ou eta):")
    for r in ranking.itertuples(index=False):
        marca = "  <-" if r.variavel == NOME else ""
        p(f"    {r.variavel:<24} {r.medida:<15} {r.forca_agrupada:.3f}{marca}")
    return resumo, por_grupo, ranking


# ---------------------------------------------------------------------------
# efeito nos modelos: sem e com a variavel
# ---------------------------------------------------------------------------
def faltam_modelos():
    return [f for t in SEM for f in (SEM[t] / "teste.csv", COM[t] / "teste.csv")
            if not f.exists()]


def acuracia_balanceada(np, y, pred):
    return float(np.mean([np.mean(pred[y == c] == c) for c in (0, 1) if (y == c).any()]))


def rmse(np, y, pred):
    return float(np.sqrt(np.mean((pred - y) ** 2)))


def diferenca_pareada(mods, y, sem, com, celulas, metrica, alfa=0.05):
    """com - sem em N_BOOT reamostragens de celulas inteiras, as mesmas para os dois.

    Devolve os limites do intervalo de 1 - alfa.
    """
    np = mods["numpy"]
    rng = np.random.default_rng(SEMENTE)
    unicas = np.unique(celulas)
    linhas = {c: np.flatnonzero(celulas == c) for c in unicas}
    dif = []
    for _ in range(N_BOOT):
        idx = np.concatenate([linhas[c] for c in rng.choice(unicas, len(unicas))])
        if len(np.unique(y[idx])) < 2 and metrica is acuracia_balanceada:
            continue
        dif.append(metrica(np, y[idx], com[idx]) - metrica(np, y[idx], sem[idx]))
    return np.percentile(dif, [100 * alfa / 2, 100 * (1 - alfa / 2)])


def efeito(mods):
    """Cada modelo, sem e com a variavel, na validacao e no teste."""
    np, pd = mods["numpy"], mods["pandas"]
    chave = ["battery_id", "test_condition", "ciclo"]
    linhas = []
    for tarefa, modelos in MODELOS.items():
        classif = tarefa == "classificacao"
        # Validacao: atributos relativos, uma celula de fora por vez, como nos graficos.
        val = {}
        for lado, pasta in (("sem", SEM[tarefa]), ("com", COM[tarefa])):
            c = pd.read_csv(pasta / "comparacao.csv")
            c = c[(c.atributos == "relativas") & (c.validacao == "uma celula de fora")]
            if not classif:
                c = c[c.rotulos_no_treino == "pares avaliaveis"]
            val[lado] = c.set_index("modelo")
        prev = pd.read_csv(SEM[tarefa] / "predicoes_teste.csv").merge(
            pd.read_csv(COM[tarefa] / "predicoes_teste.csv"), on=chave, suffixes=("", "_com"),
            validate="one_to_one")
        if not classif:
            prev = prev[prev.avaliavel]
        y = prev["fim_de_vida" if classif else ALVO].to_numpy(float)
        cel = prev.battery_id.to_numpy()
        metrica = acuracia_balanceada if classif else rmse
        nome_met = "acuracia_balanceada" if classif else "rmse"
        escala = 100 if classif else 1
        # Bonferroni: uma comparacao por algoritmo em cada tarefa.
        alfa = 0.05 / len(modelos)
        for modelo, coluna in modelos:
            s, c = prev[coluna].to_numpy(float), prev[f"{coluna}_com"].to_numpy(float)
            lo, hi = diferenca_pareada(mods, y, s, c, cel, metrica)
            blo, bhi = diferenca_pareada(mods, y, s, c, cel, metrica, alfa)
            lin = {"tarefa": tarefa, "modelo": modelo, "metrica": nome_met,
                   "validacao_sem": escala * val["sem"].loc[modelo, nome_met],
                   "validacao_com": escala * val["com"].loc[modelo, nome_met],
                   "teste_sem": escala * metrica(np, y, s), "teste_com": escala * metrica(np, y, c)}
            lin["validacao_diferenca"] = lin["validacao_com"] - lin["validacao_sem"]
            lin["teste_diferenca"] = lin["teste_com"] - lin["teste_sem"]
            lin["teste_dif_ic95_inferior"], lin["teste_dif_ic95_superior"] = escala * lo, escala * hi
            lin["teste_dif_bonferroni_inferior"] = escala * blo
            lin["teste_dif_bonferroni_superior"] = escala * bhi
            # As outras metricas do teste, como sairam de teste.csv.
            outras = ("f1_fim_de_vida", "auc") if classif else ("mae", "r2")
            for lado, pasta in (("sem", SEM[tarefa]), ("com", COM[tarefa])):
                t = pd.read_csv(pasta / "teste.csv")
                t["modelo"] = t.modelo.where(~t.modelo.str.startswith("kNN"), "kNN")
                t = t.set_index("modelo")
                for m in outras:
                    lin[f"teste_{m}_{lado}"] = t.loc[modelo, m]
            if not classif:
                for lado, pasta in (("sem", SEM[tarefa]), ("com", COM[tarefa])):
                    r = pd.read_csv(pasta / "rul_resumo.csv")
                    r = r[(r.conjunto == "teste")].set_index("fonte")
                    lin[f"teste_rul_mae_ciclos_{lado}"] = r.loc[modelo, "mae_ciclos"]
            linhas.append(lin)
    tab = pd.DataFrame(linhas)

    for tarefa, unidade, melhor in (("classificacao", "acuracia balanceada (%)", "maior"),
                                    ("regressao", "RMSE do SOH (p.p.)", "menor")):
        p(f"  {tarefa}: {unidade}, {melhor} e melhor")
        p(f"    {'':<22} {'validacao':>21}   {'teste':>21}   {'diferenca no teste':>24}")
        p(f"    {'':<22} {'sem':>6} {'com':>6} {'dif':>7}   {'sem':>6} {'com':>6} {'dif':>7}   "
          f"{'IC 95% (celulas)':>24}")
        for r in tab[tab.tarefa == tarefa].itertuples(index=False):
            exclui = ("exclui o zero" if r.teste_dif_ic95_inferior > 0
                      or r.teste_dif_ic95_superior < 0 else "inclui o zero")
            bonf = ("exclui" if r.teste_dif_bonferroni_inferior > 0
                    or r.teste_dif_bonferroni_superior < 0 else "inclui")
            p(f"    {r.modelo:<22} {r.validacao_sem:>6.2f} {r.validacao_com:>6.2f} "
              f"{r.validacao_diferenca:>+7.2f}   {r.teste_sem:>6.2f} {r.teste_com:>6.2f} "
              f"{r.teste_diferenca:>+7.2f}   [{r.teste_dif_ic95_inferior:+.2f}, "
              f"{r.teste_dif_ic95_superior:+.2f}] {exclui}; com Bonferroni "
              f"[{r.teste_dif_bonferroni_inferior:+.2f}, {r.teste_dif_bonferroni_superior:+.2f}] "
              f"{bonf}")
        p("")
    r = tab[tab.tarefa == "regressao"]
    p("  RUL no teste, MAE em ciclos: " + ", ".join(
        f"{m} {a:.1f} -> {b:.1f}" for m, a, b in
        zip(r.modelo, r.teste_rul_mae_ciclos_sem, r.teste_rul_mae_ciclos_com)))
    return tab


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


def salvar(plt, fig, pasta, nome):
    (pasta / "figuras").mkdir(parents=True, exist_ok=True)
    fig.savefig(pasta / "figuras" / nome, bbox_inches="tight")
    plt.close(fig)
    p(f"  {(pasta / 'figuras' / nome).relative_to(RAIZ)}")


def condicao(c):
    """'2 A / 24 C' -> '2 A / 24 °C', para os graficos."""
    return c[:-1] + "°C" if c.endswith(" C") else c


def nome_grupo(nome):
    """'G4: 2-4 A / 22-44 C' -> 'G4: 2–4 A / 22–44 °C', para os graficos."""
    return (condicao(nome.replace(" (extremo)", "")).replace("-", "–")
            + (" (extremo)" if "extremo" in nome else ""))


def fig_soh_por_grupo(mods, plt, df, resumo, por_grupo):
    """O SOH de cada descarga, por grupo: a distribuicao e a media que eta compara."""
    np = mods["numpy"]
    rng = np.random.default_rng(SEMENTE)
    ordem = por_grupo.sort_values("soh_medio").reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(10, 0.62 * len(ordem) + 3.2))
    media_geral = df[ALVO].mean()
    ax.axvline(FIM_DE_VIDA, color=INK2, linestyle="--", linewidth=1.1, zorder=1)
    ax.axvline(media_geral, color=INK2, linestyle=":", linewidth=1.1, zorder=1)
    for y, r in enumerate(ordem.itertuples(index=False)):
        s = df.loc[df[NOME] == r.grupo, ALVO].to_numpy(float)
        ax.scatter(s, y + rng.uniform(-0.22, 0.22, len(s)), s=7, color=MUTED, alpha=0.35,
                   linewidths=0, zorder=2)
        q1, q3 = np.percentile(s, [25, 75])
        ax.hlines(y, q1, q3, color=PAL[0], linewidth=5, zorder=3, capstyle="round")
        ax.plot(r.soh_medio, y, marker="D", markersize=8.5, color=PAL[0],
                markeredgecolor=SURF, markeredgewidth=1.5, zorder=4, linestyle="")
        ax.text(1.005, y, f"{r.pares} pares · {r.descargas} desc. · r {sinal(r.r_ponto_bisserial, 2)}",
                transform=ax.get_yaxis_transform(), fontsize=8.5, color=INK2, va="center",
                ha="left")
    ax.set_yticks(range(len(ordem)), [nome_grupo(n) for n in ordem.grupo_comportamento],
                  fontsize=9.5)
    ax.set_ylim(-0.7, len(ordem) - 0.3)
    ax.set_xlim(max(0, df[ALVO].quantile(0.002) - 3), 103)
    ax.set_xlabel("SOH da descarga (%)")
    ax.grid(axis="y", visible=False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    topo = ax.get_ylim()[1]
    # As duas linhas ficam a poucos p.p. uma da outra: um rotulo de cada lado.
    esq, dir_ = sorted([(FIM_DE_VIDA, f"fim de vida ({FIM_DE_VIDA:.0f}%) "),
                        (media_geral, f" média geral ({virg(media_geral, 0)}%)")])
    ax.text(esq[0], topo, esq[1].strip() + " ", fontsize=8.5, color=INK2, va="bottom", ha="right")
    ax.text(dir_[0], topo, " " + dir_[1].strip(), fontsize=8.5, color=INK2, va="bottom",
            ha="left")
    r = resumo.set_index("variavel")
    g, c = r.loc[NOME], r.loc["test_condition"]
    sub = (f"Cada ponto cinza é uma descarga, o losango é a média do grupo e a barra vai do 1º ao "
           f"3º quartil. A razão de correlação de {NOME} com o SOH é η = {virg(g.eta, 2)}: os "
           f"grupos explicam {virg(100 * g.eta2, 0)}% da variância do SOH, contra "
           f"{virg(100 * c.eta2, 0)}% da condição nominal (η = {virg(c.eta, 2)}). Com uma média "
           f"por par, Kruskal-Wallis dá p = {virg(g.kruskal_p_por_par, 3)}. À direita, r é a "
           "correlação ponto-bisserial do indicador do grupo com o SOH. Dentro de um par a "
           "variável não muda, então não há correlação intracélula.")
    titulo_figura(plt, fig, f"O SOH em cada grupo de {NOME}", sub)
    fig.subplots_adjust(right=0.80)
    salvar(plt, fig, SAIDA / "correlacao", "01_soh_por_grupo.png")


def fig_ranking(mods, plt, ranking):
    """A forca da associacao com o SOH: |r| dos atributos, eta das categoricas."""
    np = mods["numpy"]
    r = ranking.iloc[::-1].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(9, 0.42 * len(r) + 2.8))
    cor = [PAL[1] if v == NOME else (INK2 if t == "categorica" else PAL[0])
           for v, t in zip(r.variavel, r.tipo)]
    ax.barh(np.arange(len(r)), r.forca_agrupada, color=cor, height=0.62, zorder=2)
    for y, (v, f) in enumerate(zip(r.variavel, r.forca_agrupada)):
        ax.text(f + 0.008, y, virg(f, 2), fontsize=9, color=INK, va="center", ha="left",
                fontweight="bold" if v == NOME else "normal")
    rot = [f"{v} (η)" if t == "categorica" else v for v, t in zip(r.variavel, r.tipo)]
    ax.set_yticks(np.arange(len(r)), rot, fontsize=9.5)
    for tk in ax.get_yticklabels():
        if tk.get_text().startswith(NOME):
            tk.set_fontweight("bold")
            tk.set_color(INK)
    from matplotlib.ticker import FuncFormatter
    ax.set_xlim(0, float(r.forca_agrupada.max()) * 1.15)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: virg(v, 1)))
    ax.set_xlabel("força da associação com o SOH, todas as descargas juntas")
    ax.grid(axis="y", visible=False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    pos = int((ranking.variavel.tolist()).index(NOME)) + 1
    sub = ("Atributos numéricos pelo |r| de Pearson agrupado de correlacao_soh.py, sem capacidade e "
           "tempo, que são o próprio SOH; as variáveis categóricas pela razão de correlação η, o "
           "análogo para grupos sem ordem. η nunca é menor que o |r| de qualquer número atribuído "
           f"aos grupos, o que favorece as categóricas. {NOME} fica em {pos}º de {len(ranking)}. "
           "Nenhuma das duas categóricas tem correlação intracélula, que é a que mede degradação: "
           "são constantes dentro de cada par.")
    titulo_figura(plt, fig, f"{NOME} entre os atributos", sub)
    salvar(plt, fig, SAIDA / "correlacao", "02_ranking_vs_soh.png")


def _setas(fig, setas):
    """Setas horizontais (ax, x0, x1, y), desenhadas depois do layout.

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


def fig_efeito(mods, plt, tab):
    """Sem -> com a variavel, por modelo, na validacao e no teste das duas tarefas."""
    np = mods["numpy"]
    from matplotlib.lines import Line2D
    from matplotlib.ticker import FuncFormatter
    sem = dict(marker="o", markersize=8, markerfacecolor=SURF, markeredgecolor=INK2,
               markeredgewidth=1.6)
    com = dict(marker="D", markersize=8, markerfacecolor=PAL[1], markeredgecolor=SURF,
               markeredgewidth=1.3)
    paineis = [("classificacao", "validacao", "Classificação, validação"),
               ("classificacao", "teste", "Classificação, teste"),
               ("regressao", "validacao", "Regressão, validação"),
               ("regressao", "teste", "Regressão, teste")]
    eixo = {"classificacao": "acurácia balanceada (%), maior é melhor",
            "regressao": "RMSE do SOH (p.p.), menor é melhor"}
    n = len(MODELOS["classificacao"])
    fig, axes = plt.subplots(2, 2, figsize=(12.5, 1.25 * n + 5.6))
    ys = np.arange(n)[::-1]
    setas = []
    for ax, (tarefa, etapa, titulo) in zip(axes.flat, paineis):
        t = tab[tab.tarefa == tarefa].reset_index(drop=True)
        a, b = t[f"{etapa}_sem"].to_numpy(), t[f"{etapa}_com"].to_numpy()
        if etapa == "teste":
            # O intervalo da diferenca, ancorado no resultado sem a variavel.
            ax.hlines(ys, a + t.teste_dif_ic95_inferior, a + t.teste_dif_ic95_superior,
                      color=FAIXA, linewidth=9, capstyle="butt", zorder=1)
        ax.plot(a, ys, linestyle="", zorder=3, clip_on=False, **sem)
        ax.plot(b, ys, linestyle="", zorder=4, clip_on=False, **com)
        for y, va, vb in zip(ys, a, b):
            setas.append((ax, va, vb, y))
            ax.text((va + vb) / 2, y + 0.2, sinal(vb - va, 1 if tarefa == "classificacao" else 2),
                    fontsize=9, color=INK2, ha="center", va="bottom")
        valores = np.r_[a, b]
        if etapa == "teste":
            valores = np.r_[valores, a + t.teste_dif_ic95_inferior, a + t.teste_dif_ic95_superior]
        folga = 0.08 * (valores.max() - valores.min()) + 0.5
        ax.set_xlim(valores.min() - folga, valores.max() + folga)
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: virg(v, 1).replace(",0", "")))
        ax.set_title(titulo, loc="left", fontsize=11, color=INK)
        ax.set_xlabel(eixo[tarefa], fontsize=9.5)
        ax.set_ylim(-0.7, n - 0.2)
        ax.set_yticks(ys, [ROTULO_MODELO.get(m, m) for m in t.modelo], fontsize=9.5)
        ax.grid(axis="y", visible=False)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
        for tk in ax.get_yticklabels():
            if tk.get_text() in ("kNN", "GAM"):
                tk.set_fontweight("bold")
                tk.set_color(INK)
    alcas = [Line2D([], [], linestyle="", label="sem a variável", **sem),
             Line2D([], [], linestyle="", label=f"com {NOME}", **com),
             Line2D([], [], color=FAIXA, linewidth=9, solid_capstyle="butt",
                    label="teste: IC 95% da diferença, reamostrando células")]
    fig.legend(handles=alcas, loc="lower center", ncol=3, fontsize=9.5,
               bbox_to_anchor=(0.5, -0.01))
    rot = lambda m: ROTULO_MODELO.get(m, m)
    claros = [f"{rot(r.modelo)} na {'classificação' if r.tarefa == 'classificacao' else 'regressão'} "
              f"({sinal(r.teste_diferenca, 1 if r.tarefa == 'classificacao' else 2)})"
              for r in tab.itertuples(index=False)
              if r.teste_dif_ic95_inferior > 0 or r.teste_dif_ic95_superior < 0]
    sub = (f"Os mesmos algoritmos e o mesmo protocolo, com e sem {NOME} entre os atributos "
           "relativos ao início de vida. Validação: as células de treino, uma de fora por vez, "
           "com o agrupamento refeito sem ela. Teste: as 8 células nunca vistas, que nem o "
           "agrupamento viu. A seta vai do resultado sem a variável ao resultado com ela, e a "
           "faixa no teste é o intervalo de 95% da diferença, pareada nas mesmas reamostragens "
           "de células. ")
    sub += ("O intervalo exclui o zero só em " + "; ".join(claros) + "."
            if claros else "Em todos os algoritmos o intervalo da diferença inclui o zero.")
    bonf = [r for r in tab.itertuples(index=False)
            if r.teste_dif_bonferroni_inferior > 0 or r.teste_dif_bonferroni_superior < 0]
    if claros:
        sub += (" Com Bonferroni, pelos cinco algoritmos de cada tarefa, "
                + (f"continua excluindo em {len(bonf)}." if bonf else "nenhum exclui."))
    titulo_figura(plt, fig, f"O que {NOME} muda nos modelos", sub)
    fig.subplots_adjust(bottom=0.10, hspace=0.55)
    _setas(fig, setas)
    salvar(plt, fig, SAIDA / "comparacao", "01_efeito_nos_modelos.png")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--sem-graficos", action="store_true")
    a = ap.parse_args()

    mods = checar()
    p(f"A variavel {NOME}")
    p("=" * 60)
    p("1. correlacao com o SOH:")
    df = carregar(mods)
    resumo, por_grupo, ranking = correlacao(mods, df)
    pasta = SAIDA / "correlacao" / "tabelas"
    pasta.mkdir(parents=True, exist_ok=True)
    arquivos = {pasta / "correlacao_soh.csv": resumo, pasta / "soh_por_grupo.csv": por_grupo,
                pasta / "ranking_vs_soh.csv": ranking}

    p("")
    tab = None
    falta = faltam_modelos()
    if falta:
        p("2. efeito nos modelos pulado: faltam " + ", ".join(
            str(f.relative_to(RAIZ)) for f in falta))
        p("    Rode antes: python src/classificacao.py --com-grupo e "
          "python src/regressao.py --com-grupo")
    else:
        p("2. efeito nos modelos, sem e com a variavel:")
        tab = efeito(mods)
        pasta = SAIDA / "comparacao" / "tabelas"
        pasta.mkdir(parents=True, exist_ok=True)
        arquivos[pasta / "efeito_nos_modelos.csv"] = tab

    p("")
    for f, t in arquivos.items():
        t.round(4).to_csv(f, index=False)
        p(f"  {f.relative_to(RAIZ)}")

    if not a.sem_graficos:
        p("")
        p("graficos:")
        plt = estilo(mods)
        fig_soh_por_grupo(mods, plt, df, resumo, por_grupo)
        fig_ranking(mods, plt, ranking)
        if tab is not None:
            fig_efeito(mods, plt, tab)


if __name__ == "__main__":
    main()
