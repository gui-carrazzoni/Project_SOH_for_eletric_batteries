#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Modelos matematicos para a area sob a curva de descarga ao longo dos ciclos.

    python modelos_area.py                 # as tres areas, nos dois agrupamentos
    python modelos_area.py --area energia  # so uma
    python modelos_area.py --sem-corte
    python modelos_area.py --sem-graficos

Escreve nas duas arvores de esquema de grupo:

    saida_nasa/cluster/grupo_corrente_temperatura/modelos_area/
    saida_nasa/cluster/grupo_corrente_temperatura_corte/modelos_area/

**As tres areas.** `carga_Ah_comum` (integral da corrente, em Ah), `tensao_Vs_comum`
(integral da tensao, em V.s) e `energia_Wh_comum` (integral da potencia, em Wh).
Todas na janela comum ate 2.7 V — a unica base que se compara entre celulas de
corte diferente.

**As tres sao vazamento para o SOH, e isso nao e defeito do calculo.** Em
descarga a corrente constante a carga integrada *e* a capacidade, e as outras
duas sao proporcionais a ela; como o SOH e a capacidade sobre a capacidade
maxima, a correlacao intra-celula da +1.0000 em 100% das series. Elas nao
entram num modelo de SOH como atributo — e a mesma regra que
correlacao_soh.py aplica a `capacity` e `time`. Entram aqui como **objeto
modelado**: ajustar como a area cai ao longo dos ciclos e descrever a curva de
degradacao, nao preve-la. `correlacao_com_soh.csv` registra o vazamento em vez
de esconde-lo, com a coluna `is_leakage`.

A diferenca entre as tres, entao, nao esta em poder preditivo mas em qual
delas rende o ajuste mais limpo, e nas quatro baterias de carga pulsada
(B0025-B0028), onde `tensao_Vs` deixa de ser proporcional as outras porque
metade do tempo nao sai corrente.

**Os quatro modelos**, ajustados a serie area x ciclo de cada celula:

| modelo | forma | leitura |
|---|---|---|
| linear | a.x + b | perda constante por ciclo |
| exponencial | a.exp(b.x) + c | perda proporcional ao que resta |
| potencia | a.x^b + c | perda que desacelera, tipica de difusao |
| exp. duplo | a.exp(b.x) + c.exp(d.x) | dois mecanismos em ritmos diferentes |

Comparados por R2, RMSE e **AIC**. O AIC e quem decide: R2 sempre melhora quando
se acrescenta parametro, e o exponencial duplo tem quatro contra dois do linear.
Sem penalizar complexidade, o duplo venceria por construcao e nao por ajuste.

**O ajuste e feito em escala normalizada.** x vai para [0, 1] e y e dividido
pelo valor inicial. Sem isso o `curve_fit` recebe ciclos na casa das centenas
dentro de uma exponencial e estoura; e os parametros publicados sao devolvidos a
escala original depois.

**Por celula, nunca por grupo inteiro.** Empilhar as celulas de um grupo e
ajustar uma curva so reproduziria o paradoxo de Simpson que o projeto ja
documenta: cada celula cai, e a reta sobre o monte pode subir. Cada serie e uma
celula dentro de um grupo, e o que se reporta e a distribuicao dos ajustes.

Dependencias: numpy, pandas, scipy, matplotlib
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

# A raiz do projeto e a pasta acima de src/: e la que ficam
# cleaned_nasa_dataset/ e saida_nasa/.
RAIZ = Path(__file__).resolve().parent.parent
ENTRADA = RAIZ / "saida_nasa" / "curvas" / "features_curvas.csv"

PAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
       "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e3e2de"

AREAS = {
    "carga": ("carga_Ah_comum", "Ah", "carga integrada"),
    "tensao": ("tensao_Vs_comum", "V.s", "integral da tensao"),
    "energia": ("energia_Wh_comum", "Wh", "energia entregue"),
}
MIN_CICLOS = 10        # abaixo disso o ajuste de 4 parametros nao tem graus
CICLOS_REF = 5


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
# os modelos
# ---------------------------------------------------------------------------
def familias(np):
    """Nome -> (funcao, chute inicial, n de parametros).

    Os chutes valem na escala normalizada: x em [0,1] e y perto de 1 no inicio,
    caindo. Por isso `b` negativo nas exponenciais e `a` perto de 1.
    """
    return {
        "linear": (lambda x, a, b: a * x + b, [-0.2, 1.0], 2),
        "exponencial": (lambda x, a, b, c: a * np.exp(b * x) + c,
                        [0.3, -1.0, 0.7], 3),
        "potencia": (lambda x, a, b, c: a * np.power(np.clip(x, 1e-6, None), b) + c,
                     [-0.2, 0.5, 1.0], 3),
        "exp_duplo": (lambda x, a, b, c, d: a * np.exp(b * x) + c * np.exp(d * x),
                      [0.5, -0.5, 0.5, -3.0], 4),
    }


def ajustar_um(mods, x, y, nome, func, chute, k):
    """Ajusta uma familia a uma serie normalizada. Devolve None se nao converge."""
    np = mods["numpy"]
    from scipy.optimize import curve_fit
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            par, _ = curve_fit(func, x, y, p0=chute, maxfev=20000)
        prev = func(x, *par)
        if not np.all(np.isfinite(prev)):
            return None
    except Exception:
        return None

    res = y - prev
    sse = float(np.sum(res ** 2))
    sst = float(np.sum((y - y.mean()) ** 2))
    n = len(x)
    r2 = 1 - sse / sst if sst > 0 else float("nan")
    rmse = float(np.sqrt(sse / n))
    # AIC de minimos quadrados, com a constante omitida: so a diferenca importa.
    aic = n * np.log(sse / n) + 2 * k if sse > 0 else float("-inf")
    return {"modelo": nome, "r2": r2, "rmse": rmse, "aic": float(aic),
            "n_par": k, "parametros": ";".join(f"{v:.6g}" for v in par)}


def ajustar_serie(mods, x_cru, y_cru):
    """Todas as familias numa serie. Normaliza, ajusta, devolve uma linha cada."""
    np = mods["numpy"]
    if len(x_cru) < MIN_CICLOS:
        return []
    y0 = float(np.median(y_cru[:CICLOS_REF]))
    xmax = float(x_cru.max())
    if not (y0 > 0 and xmax > 0):
        return []
    x = x_cru / xmax
    y = y_cru / y0

    saida = []
    for nome, (f, chute, k) in familias(np).items():
        r = ajustar_um(mods, x, y, nome, f, chute, k)
        if r:
            r["escala_x"] = xmax
            r["escala_y"] = y0
            saida.append(r)
    return saida


def rodar_area(mods, d, rotulos, col, nome_grupo):
    np, pd = mods["numpy"], mods["pandas"]
    d = d.assign(grupo=rotulos)
    linhas = []
    for (grupo, bat), b in d.groupby(["grupo", "battery_id"]):
        b = b.sort_values("ciclo_na_condicao")
        x = b.ciclo_na_condicao.to_numpy(float)
        y = b[col].to_numpy(float)
        ok = np.isfinite(x) & np.isfinite(y) & (y > 0)
        for r in ajustar_serie(mods, x[ok], y[ok]):
            linhas.append({"grupo": grupo, "battery_id": bat,
                           "ciclos": int(ok.sum()), **r})
    return pd.DataFrame(linhas)


def vencedores(mods, aj):
    """Por serie, o modelo de menor AIC."""
    pd = mods["pandas"]
    if aj.empty:
        return aj
    idx = aj.groupby(["grupo", "battery_id"]).aic.idxmin()
    return aj.loc[idx].copy()


# ---------------------------------------------------------------------------
# relatorio
# ---------------------------------------------------------------------------
def relatar(mods, aj, venc, rotulo):
    pd = mods["pandas"]
    p("")
    p(f"    {rotulo}: {venc.shape[0]} series ajustadas")
    cont = venc.modelo.value_counts()
    for m, n in cont.items():
        r2 = venc[venc.modelo == m].r2.median()
        p(f"      vence {m:<12} em {n:>3} series ({n/len(venc)*100:>4.0f}%), "
          f"R2 mediano {r2:.4f}")
    p(f"      R2 mediano de todas as familias:")
    for m, g in aj.groupby("modelo"):
        p(f"        {m:<12} {g.r2.median():.4f}   "
          f"(p10 {g.r2.quantile(.1):.3f}, p90 {g.r2.quantile(.9):.3f})")


def correlacao_soh(mods, d, rotulos):
    """Correlacao de cada area com o SOH — e a demonstracao de que e vazamento.

    A tabela existe para ser lida como aviso, nao como ranking de preditores. O
    SOH e a capacidade dividida pela capacidade maxima da celula naquele grupo,
    e as tres areas sao a capacidade por outro nome: em descarga a corrente
    constante, `carga_Ah` e a propria capacidade, e `tensao_Vs` e `energia_Wh`
    sao proporcionais a ela. A correlacao intra-celula da +1.0000 em 100% das
    series, o que nao e um achado — e uma identidade.

    E o mesmo caso que correlacao_soh.py ja marca com `is_leakage` para
    `capacity` e `time`. As areas **nao entram num modelo de SOH como
    atributo**. O que elas servem e para serem o objeto modelado: o item 4
    ajusta como a area cai ao longo dos ciclos, e isso e a curva de degradacao,
    nao uma predicao dela.

    O r = +1.0000 tem um uso legitimo, porem: e a confirmacao de que a
    integracao esta correta. Se a area integrada nao reproduzisse a capacidade,
    o erro estaria na integracao.
    """
    np, pd = mods["numpy"], mods["pandas"]
    d = d.assign(grupo=rotulos)
    if "SoH_%" not in d.columns:
        return pd.DataFrame()
    linhas = []
    for chave, col, _u, _r in [(k,) + v for k, v in AREAS.items()]:
        rr = []
        for _, b in d.groupby(["grupo", "battery_id"]):
            if len(b) >= MIN_CICLOS and b[col].notna().sum() >= MIN_CICLOS:
                c = b[col].corr(b["SoH_%"])
                if c == c:
                    rr.append(c)
        if rr:
            rr = np.array(rr)
            linhas.append({
                "area": col,
                "correlacao_intracelula_mediana": float(np.median(rr)),
                "p10": float(np.quantile(rr, .1)),
                "p90": float(np.quantile(rr, .9)),
                "fracao_positiva": float((rr > 0).mean()),
                "series": len(rr),
                # Marca explicita, no mesmo espirito do is_leakage de
                # correlacao_soh.py: |r| ~ 1 aqui significa identidade com o
                # alvo, nao poder preditivo.
                "is_leakage": bool(abs(float(np.median(rr))) > 0.99),
            })
    return pd.DataFrame(linhas).sort_values(
        "correlacao_intracelula_mediana", ascending=False)


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
        "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 1.8,
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


def desenhar(mods, plt, aj, venc, saida, rotulo, area_col, unidade):
    np, pd = mods["numpy"], mods["pandas"]

    # 01 — R2 por familia
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    fam = ["linear", "exponencial", "potencia", "exp_duplo"]
    dados = [aj[aj.modelo == m].r2.dropna().to_numpy() for m in fam]
    manter = [i for i, v in enumerate(dados) if len(v)]
    bp = ax.boxplot([dados[i] for i in manter], patch_artist=True,
                    medianprops=dict(color=INK, linewidth=1.6),
                    flierprops=dict(markersize=3, markerfacecolor=INK2,
                                    markeredgecolor="none"))
    for i, cx in enumerate(bp["boxes"]):
        cx.set_facecolor(PAL[i % len(PAL)]); cx.set_alpha(0.55)
        cx.set_edgecolor(INK2)
    ax.set_xticks(range(1, len(manter) + 1), [fam[i] for i in manter], fontsize=9.5)
    ax.set_ylabel("R2 do ajuste")
    ax.set_ylim(min(0, ax.get_ylim()[0]), 1.02)
    titulo_figura(plt, fig, f"Qualidade do ajuste por familia — {rotulo}",
                  f"Uma observacao por serie (celula dentro de grupo), para {area_col} "
                  f"em {unidade}. R2 alto e necessario mas nao suficiente: quem decide e "
                  f"o AIC, que desconta o numero de parametros.")
    fig.savefig(saida / "01_r2_por_familia.png", bbox_inches="tight")
    plt.close(fig)
    p(f"      01_r2_por_familia.png")

    # 02 — quem vence, por grupo
    tab = pd.crosstab(venc.grupo, venc.modelo)
    fig, ax = plt.subplots(figsize=(max(7, 0.4 * len(tab) + 4),
                                    0.32 * len(tab) + 3))
    base = np.zeros(len(tab))
    for i, m in enumerate([c for c in fam if c in tab.columns]):
        ax.barh(range(len(tab)), tab[m].to_numpy(), left=base,
                color=PAL[i % len(PAL)], label=m, height=0.72)
        base += tab[m].to_numpy()
    ax.set_yticks(range(len(tab)), [str(i) for i in tab.index], fontsize=8)
    ax.set_xlabel("series (celulas)")
    ax.legend(fontsize=9, ncol=4, loc="lower right")
    ax.grid(axis="y", visible=False)
    titulo_figura(plt, fig, f"Modelo vencedor por grupo — {rotulo}",
                  "Vencedor por menor AIC em cada celula. Se um grupo e coerente, suas "
                  "celulas tendem a escolher a mesma familia; barras misturadas sugerem "
                  "que o grupo reune regimes de degradacao diferentes.")
    fig.savefig(saida / "02_modelo_vencedor.png", bbox_inches="tight")
    plt.close(fig)
    p(f"      02_modelo_vencedor.png")


def rodar(mods, d, rotulos, nome, area_chave, graficos):
    pd = mods["pandas"]
    col, unidade, _desc = AREAS[area_chave]
    saida = RAIZ / "saida_nasa" / "cluster" / nome / "modelos_area" / area_chave
    saida.mkdir(parents=True, exist_ok=True)

    aj = rodar_area(mods, d, rotulos, col, nome)
    if aj.empty:
        p(f"    {nome}/{area_chave}: nenhuma serie com {MIN_CICLOS}+ ciclos")
        return
    venc = vencedores(mods, aj)
    relatar(mods, aj, venc, f"{nome}/{area_chave}")

    aj.to_csv(saida / "ajustes.csv", index=False)
    venc.to_csv(saida / "vencedores.csv", index=False)
    venc.groupby("grupo").agg(
        series=("modelo", "size"),
        modelo_mais_comum=("modelo", lambda s: s.mode().iat[0]),
        r2_mediano=("r2", "median"),
        rmse_mediano=("rmse", "median"),
    ).to_csv(saida / "resumo_por_grupo.csv")

    if graficos:
        desenhar(mods, estilo(mods), aj, venc, saida, f"{nome}/{area_chave}",
                 col, unidade)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--area", choices=list(AREAS), default=None,
                    help="ajusta so uma das tres areas")
    ap.add_argument("--sem-corte", action="store_true")
    ap.add_argument("--sem-graficos", action="store_true")
    a = ap.parse_args()

    mods = checar()
    pd = mods["pandas"]
    p("Modelos para a area sob a curva de descarga")
    p("=" * 60)

    from capacidade import preparar
    d, esquemas = preparar(mods, a.sem_corte)
    p(f"  {len(d)} descargas, {d.battery_id.nunique()} baterias")

    chaves = [a.area] if a.area else list(AREAS)
    for nome, rot in esquemas.items():
        for ch in chaves:
            rodar(mods, d, rot, nome, ch, not a.sem_graficos)

        cs = correlacao_soh(mods, d, rot)
        if not cs.empty:
            alvo = RAIZ / "saida_nasa" / "cluster" / nome / "modelos_area"
            alvo.mkdir(parents=True, exist_ok=True)
            cs.to_csv(alvo / "correlacao_com_soh.csv", index=False)
            p("")
            p(f"    {nome}: correlacao das areas com o SOH (intra-celula)")
            for r in cs.itertuples(index=False):
                marca = "  <- VAZAMENTO" if r.is_leakage else ""
                p(f"      {r.area:<20} r mediano {r.correlacao_intracelula_mediana:+.4f}"
                  f"   positiva em {r.fracao_positiva*100:>5.1f}% das "
                  f"{r.series} series{marca}")
            if cs.is_leakage.any():
                p("      As areas sao a capacidade por outro nome, e o SOH deriva dela.")
                p("      Servem como objeto modelado no item 4, nao como atributo de SOH.")
    p("")
    p("  ok")


if __name__ == "__main__":
    main()
