#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analise e graficos do NASA Li-ion Battery Aging Dataset.

    python graficos_nasa.py                # tudo
    python graficos_nasa.py --sem-graficos # so as tabelas de metricas

Escreve em saida_nasa/: metricas por ensaio, resumo por bateria e os PNGs.

O ponto central: neste dataset a capacidade **so e comparavel dentro da mesma
condicao de ensaio**. A mesma bateria descarregada a 4 A entrega 1,42 Ah a 24 C
e 0,06 Ah a 4 C — 23 vezes menos. Sete das 34 baterias mudam de condicao no meio
da vida, e quem plotar capacidade contra ciclo sem separar por condicao vera um
despencar que e troca de protocolo, nao degradacao.

Dependencias: numpy, pandas, matplotlib
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
DADOS = RAIZ / "cleaned_nasa_dataset"
SAIDA = RAIZ / "saida_nasa"

# Paleta categorica validada para daltonismo (modo claro), slots 1..8 em ordem fixa
PAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
       "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
# Rampa sequencial azul, para magnitude (numero do ciclo)
SEQ = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7",
       "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e3e2de"

# Resistencias fisicamente plausiveis para estas celulas: a mediana e 0,07 ohm e
# 99,3% dos ensaios ficam abaixo de 0,3. Os 14 restantes chegam a 1e15 ohm — lixo
# de ajuste numerico. O corte e insensivel: 0,5, 1 ou 2 ohm marcam os mesmos 14.
LIMITE_RESISTENCIA = 1.0


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
    return mods


def para_real(serie, np, pd):
    """Le colunas que podem trazer complexo em texto, como '(0.05-0.03j)'."""
    def um(v):
        if pd.isna(v):
            return np.nan
        texto = str(v).strip()
        if texto.startswith("("):
            try:
                return complex(texto).real
            except ValueError:
                return np.nan
        try:
            return float(texto)
        except ValueError:
            return np.nan
    return serie.map(um)


# ---------------------------------------------------------------------------
# metricas
# ---------------------------------------------------------------------------
def montar_metricas(mods):
    """Uma linha por descarga e uma por ensaio de impedancia, com a condicao."""
    np, pd = mods["numpy"], mods["pandas"]
    meta = pd.read_csv(DADOS / "metadata.csv")

    # ---- descargas
    d = meta[meta.type == "discharge"].copy()
    d["Capacity"] = pd.to_numeric(d.Capacity, errors="coerce")
    correntes, duracoes, v_final, t_max = [], [], [], []
    for arquivo in d.filename:
        c = pd.read_csv(DADOS / "data" / arquivo)
        i = c.Current_load.abs()
        correntes.append(round(float(i[i > 0.1].median()), 1) if (i > 0.1).any() else np.nan)
        duracoes.append(float(c.Time.max()) / 60.0)
        v_final.append(float(c.Voltage_measured.iloc[-1]))
        t_max.append(float(c.Temperature_measured.max()))
    d["corrente_A"] = correntes
    d["duracao_min"] = duracoes
    d["V_final"] = v_final
    d["T_max_C"] = t_max
    d["ciclo"] = d.groupby("battery_id").cumcount()
    d["condicao"] = (d.corrente_A.map(lambda x: f"{x:g} A")
                     + " / " + d.ambient_temperature.astype(str) + " C")
    # Contagem dentro da condicao: somar ciclos de protocolos diferentes no mesmo
    # eixo cria degraus que parecem degradacao subita e sao troca de ensaio.
    d["ciclo_na_condicao"] = d.groupby(["battery_id", "condicao"]).cumcount()

    # A capacidade so e comparavel dentro da mesma condicao, entao o SoH e
    # normalizado pelo maximo da bateria NAQUELA condicao. Normalizar pelo
    # primeiro ciclo daria SoH acima de 1900% aqui, porque varias baterias
    # comecam com uma descarga que nao mede a capacidade cheia.
    chave = ["battery_id", "condicao"]
    d["cap_ref_Ah"] = d.groupby(chave).Capacity.transform("max")
    d["SoH_%"] = d.Capacity / d.cap_ref_Ah * 100.0
    d["alerta"] = np.where(d.Capacity.isna(), "capacidade_ausente",
                  np.where(d.Capacity <= 0, "capacidade_zero", ""))

    # ---- impedancia
    z = meta[meta.type == "impedance"].copy()
    z["Re_ohm"] = para_real(z.Re, np, pd)
    z["Rct_ohm"] = para_real(z.Rct, np, pd)
    z["ciclo"] = z.groupby("battery_id").cumcount()
    fora = (~z.Re_ohm.between(0, LIMITE_RESISTENCIA, inclusive="right")
            | ~z.Rct_ohm.between(0, LIMITE_RESISTENCIA, inclusive="right"))
    z["alerta"] = np.where(fora, "resistencia_implausivel", "")

    # SoH da descarga mais proxima, para cruzar resistencia com saude
    z["SoH_%"] = np.nan
    for bateria, gz in z.groupby("battery_id"):
        gd = d[(d.battery_id == bateria) & (d.alerta == "")]
        if gd.empty:
            continue
        idx = np.abs(gz.test_id.to_numpy()[:, None] - gd.test_id.to_numpy()[None, :]).argmin(axis=1)
        z.loc[gz.index, "SoH_%"] = gd["SoH_%"].to_numpy()[idx]
    return d, z


def resumir(mods, d, z):
    np, pd = mods["numpy"], mods["pandas"]
    linhas = []
    for bateria, g in d.groupby("battery_id"):
        bons = g[g.alerta == ""]
        principal = g.condicao.mode().iloc[0] if not g.condicao.mode().empty else ""
        gp = bons[bons.condicao == principal]
        gz = z[(z.battery_id == bateria) & (z.alerta == "")]
        linhas.append({
            "battery_id": bateria,
            "descargas": len(g),
            "descargas_validas": len(bons),
            "condicoes": g.condicao.nunique(),
            "condicao_principal": principal,
            "cap_max_Ah": bons.Capacity.max() if len(bons) else np.nan,
            "cap_final_Ah": gp.Capacity.iloc[-1] if len(gp) else np.nan,
            "SoH_final_%": gp["SoH_%"].iloc[-1] if len(gp) else np.nan,
            "T_max_C": bons.T_max_C.max() if len(bons) else np.nan,
            "ensaios_impedancia": int((z.battery_id == bateria).sum()),
            "Re_inicial_ohm": gz.Re_ohm.iloc[0] if len(gz) else np.nan,
            "Re_final_ohm": gz.Re_ohm.iloc[-1] if len(gz) else np.nan,
            "Rct_inicial_ohm": gz.Rct_ohm.iloc[0] if len(gz) else np.nan,
            "Rct_final_ohm": gz.Rct_ohm.iloc[-1] if len(gz) else np.nan,
            "r_Re_vs_SoH": (gz.Re_ohm.corr(gz["SoH_%"]) if len(gz.dropna(
                subset=["SoH_%", "Re_ohm"])) >= 10 else np.nan),
            "r_Rct_vs_SoH": (gz.Rct_ohm.corr(gz["SoH_%"]) if len(gz.dropna(
                subset=["SoH_%", "Rct_ohm"])) >= 10 else np.nan),
        })
    return pd.DataFrame(linhas)


# ---------------------------------------------------------------------------
# graficos
# ---------------------------------------------------------------------------
def estilo(plt):
    plt.rcParams.update({
        "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
        "font.size": 11, "text.color": INK, "axes.labelcolor": INK2,
        "xtick.color": INK2, "ytick.color": INK2, "axes.edgecolor": GRID,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 2.0,
        "legend.frameon": False, "figure.dpi": 150,
    })


def titulo(ax, texto, sub=None):
    ax.set_title(texto, fontsize=14, fontweight="bold", color=INK, loc="left",
                 pad=30 if sub else 10)
    if sub:
        ax.text(0, 1.012, sub, transform=ax.transAxes, fontsize=10.5, color=INK2,
                va="bottom")


def titulo_figura(fig, texto, sub):
    """Titulo e subtitulo da figura sem colidir com os paineis."""
    fig.suptitle(texto, fontsize=15, fontweight="bold", color=INK,
                 x=0.007, ha="left", y=0.995)
    fig.text(0.007, 0.945, sub, fontsize=10.5, color=INK2, ha="left", va="top")
    fig.tight_layout(rect=[0, 0, 1, 0.90])


def salvar(fig, nome):
    fig.savefig(SAIDA / "graficos" / nome, bbox_inches="tight")
    p(f"  {nome}")


def desenhar(mods, d, z):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    np, pd = mods["numpy"], mods["pandas"]
    estilo(plt)
    (SAIDA / "graficos").mkdir(parents=True, exist_ok=True)
    bons = d[d.alerta == ""]

    # -- 01 capacidade por corrente, colorida por temperatura ambiente
    correntes = sorted(bons.corrente_A.dropna().unique())
    temps = sorted(bons.ambient_temperature.unique())
    cor_t = {t: PAL[i % len(PAL)] for i, t in enumerate(temps)}
    fig, axes = plt.subplots(1, len(correntes), figsize=(5.2 * len(correntes), 5.0),
                             sharey=True, squeeze=False)
    for ax, corrente in zip(axes[0], correntes):
        sub = bons[bons.corrente_A == corrente]
        for (bat, temp), g in sub.groupby(["battery_id", "ambient_temperature"]):
            ax.plot(g.ciclo_na_condicao, g.Capacity, color=cor_t[temp],
                    linewidth=1.4, alpha=0.85)
        ax.set_title(f"descarga a {corrente:g} A   ({sub.battery_id.nunique()} baterias)",
                     fontsize=12, fontweight="bold", color=INK, loc="left")
        ax.set_xlabel("Ciclo dentro da condição")
        ax.set_axisbelow(True); ax.grid(axis="x", visible=False)
    axes[0][0].set_ylabel("Capacidade (Ah)")
    fig.legend([Line2D([], [], color=cor_t[t], lw=2) for t in temps],
               [f"{t} °C" for t in temps], loc="center right",
               bbox_to_anchor=(1.06, 0.5), labelcolor=INK2, title="ambiente")
    titulo_figura(fig, "Capacidade ao longo do envelhecimento, por condição de ensaio",
                  "Cada linha é uma bateria. A capacidade só é comparável dentro do "
                  "mesmo painel: corrente e temperatura mudam o resultado mais que o "
                  "envelhecimento.")
    salvar(fig, "01_capacidade_por_condicao.png"); plt.close(fig)

    # -- 02 SoH com o limite de fim de vida
    fig, ax = plt.subplots(figsize=(10, 5.6))
    unica = bons.groupby("battery_id").condicao.nunique()
    estaveis = unica[unica == 1].index
    for (bat, temp), g in bons[bons.battery_id.isin(estaveis)].groupby(
            ["battery_id", "ambient_temperature"]):
        ax.plot(g.ciclo_na_condicao, g["SoH_%"], color=cor_t[temp],
                linewidth=1.4, alpha=0.85)
    ax.axhline(80, color=INK2, linewidth=1.25, linestyle=(0, (5, 4)))
    ax.text(ax.get_xlim()[1], 80.8, "fim de vida convencionado (80%)", ha="right",
            va="bottom", fontsize=10, color=INK2)
    ax.set_xlabel("Ciclo de descarga"); ax.set_ylabel("SoH (%)")
    ax.set_axisbelow(True); ax.grid(axis="x", visible=False)
    ax.legend([Line2D([], [], color=cor_t[t], lw=2) for t in temps],
              [f"{t} °C" for t in temps], loc="center left",
              bbox_to_anchor=(1.01, 0.5), labelcolor=INK2, title="ambiente")
    titulo(ax, "Estado de saúde das baterias de condição estável",
           f"{len(estaveis)} das {bons.battery_id.nunique()} baterias mantêm a mesma "
           "corrente e temperatura a vida toda; SoH normalizado pela capacidade máxima de cada uma")
    fig.tight_layout(); salvar(fig, "02_soh_vs_ciclo.png"); plt.close(fig)

    # -- 03 o efeito da condicao sobre a capacidade
    comb = (bons.groupby(["corrente_A", "ambient_temperature"])
                .agg(mediana=("Capacity", "median"), n=("Capacity", "size"))
                .reset_index().sort_values("mediana"))
    fig, ax = plt.subplots(figsize=(10, 5.4))
    rotulos = [f"{r.corrente_A:g} A · {r.ambient_temperature:g} °C" for r in comb.itertuples()]
    ax.barh(rotulos, comb.mediana, color=[cor_t[t] for t in comb.ambient_temperature],
            height=0.68)
    for y, (valor, n) in enumerate(zip(comb.mediana, comb.n)):
        ax.text(valor + 0.02, y, f"{valor:.2f} Ah   (n={n})", va="center",
                fontsize=10, color=INK2)
    ax.set_xlim(0, comb.mediana.max() * 1.35)
    ax.set_xlabel("Capacidade mediana (Ah)")
    ax.set_axisbelow(True); ax.grid(axis="y", visible=False)
    titulo(ax, "A condição de ensaio pesa mais que o envelhecimento",
           "Mediana de todas as descargas de cada combinação corrente × temperatura ambiente")
    fig.tight_layout(); salvar(fig, "03_efeito_da_condicao.png"); plt.close(fig)

    # -- 04 resistencia interna ao longo da vida
    zb = z[z.alerta == ""]
    escolhidas = (zb.groupby("battery_id").size().sort_values(ascending=False)
                    .head(8).index.tolist())
    cor_b = {b: PAL[i] for i, b in enumerate(sorted(escolhidas))}
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2), sharex=True)
    for ax, coluna, nome in zip(axes, ("Re_ohm", "Rct_ohm"),
                                ("Re — resistência ôhmica", "Rct — transferência de carga")):
        for bat in sorted(escolhidas):
            g = zb[zb.battery_id == bat]
            ax.plot(g.ciclo, g[coluna], color=cor_b[bat], linewidth=1.8, label=bat)
        ax.set_title(nome, fontsize=12, fontweight="bold", color=INK, loc="left")
        ax.set_xlabel("Ensaio de impedância"); ax.set_ylabel("Resistência (Ω)")
        ax.set_axisbelow(True); ax.grid(axis="x", visible=False)
    axes[1].legend(loc="center left", bbox_to_anchor=(1.01, 0.5), labelcolor=INK2)
    titulo_figura(fig, "Resistência interna cresce enquanto a capacidade cai",
                  f"As {len(escolhidas)} baterias com mais ensaios de impedância")
    salvar(fig, "04_resistencia_vs_ciclo.png"); plt.close(fig)

    # -- 05 resistencia como preditor de SoH: agregado esconde o que vale
    par = zb.dropna(subset=["SoH_%", "Re_ohm", "Rct_ohm"])
    contagem = par.groupby("battery_id").size().sort_values(ascending=False)
    destaque = contagem.head(3).index.tolist()   # 3 slots validam a paleta em todos os pares
    cor_d = {b: PAL[i] for i, b in enumerate(sorted(destaque))}

    def ajuste(ax, x, y, cor):
        if len(x) > 2:
            a, b = np.polyfit(x, y, 1)
            xs = np.linspace(x.min(), x.max(), 50)
            ax.plot(xs, a * xs + b, color=cor, linewidth=1.8, linestyle=(0, (5, 4)))

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.4), sharey=True)

    r_geral = par.Re_ohm.corr(par["SoH_%"])
    axes[0].scatter(par.Re_ohm, par["SoH_%"], s=13, color=INK2, alpha=0.28,
                    edgecolors="none")
    ajuste(axes[0], par.Re_ohm, par["SoH_%"], INK)
    axes[0].set_title(f"Todas as {par.battery_id.nunique()} baterias juntas    "
                      f"r = {r_geral:+.2f}", fontsize=12, fontweight="bold",
                      color=INK, loc="left")

    rotulos = []
    for bat in sorted(destaque):
        g = par[par.battery_id == bat]
        axes[1].scatter(g.Re_ohm, g["SoH_%"], s=13, color=cor_d[bat], alpha=0.55,
                        edgecolors="none")
        ajuste(axes[1], g.Re_ohm, g["SoH_%"], cor_d[bat])
        rotulos.append(f"{bat}  r = {g.Re_ohm.corr(g['SoH_%']):+.2f}")
    axes[1].set_title("Uma bateria de cada vez", fontsize=12, fontweight="bold",
                      color=INK, loc="left")
    axes[1].legend([Line2D([], [], color=cor_d[b], lw=2) for b in sorted(destaque)],
                   rotulos, loc="lower left", labelcolor=INK2)

    for ax in axes:
        ax.set_xlabel("Re — resistência ôhmica (Ω)")
        ax.set_axisbelow(True); ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("SoH (%) da descarga mais próxima")
    titulo_figura(fig, "A impedância prevê a saúde — mas só dentro da mesma célula",
                  "Cada célula tem seu próprio nível de resistência, então juntar todas "
                  "dilui a relação de r ≈ −0,9 para −0,17. Um modelo de SoH por "
                  "impedância precisa ser calibrado por célula.")
    salvar(fig, "05_soh_vs_resistencia.png"); plt.close(fig)

    # -- 06 curvas de descarga envelhecendo
    longas = (bons.groupby("battery_id").size().sort_values(ascending=False)
                  .head(4).index.tolist())
    fig, axes = plt.subplots(1, 4, figsize=(17, 4.6), sharey=True)
    for ax, bat in zip(axes, longas):
        g = bons[bons.battery_id == bat]
        g = g[g.condicao == g.condicao.mode().iloc[0]]
        escolha = g.iloc[np.linspace(0, len(g) - 1, min(len(g), 10)).astype(int)]
        for i, r in enumerate(escolha.itertuples()):
            c = pd.read_csv(DADOS / "data" / r.filename)
            # O arquivo continua gravando depois do corte de tensao, durante a
            # recuperacao da celula; a curva voltaria a subir. Aqui fica so a
            # descarga em si, ate o minimo de tensao.
            c = c.iloc[:int(c.Voltage_measured.idxmin()) - int(c.index[0]) + 1]
            passo = int(i * (len(SEQ) - 3) / max(1, len(escolha) - 1))
            ax.plot(c.Time / 60, c.Voltage_measured,
                    color=SEQ[min(len(SEQ) - 1, 2 + passo)], linewidth=1.6)
        ax.set_title(f"{bat}  ({g.condicao.iloc[0]})", fontsize=12, fontweight="bold",
                     color=INK, loc="left")
        ax.set_xlabel("Tempo (min)")
        ax.set_axisbelow(True); ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("Tensão (V)")
    fig.legend([Line2D([], [], color=SEQ[2], lw=2), Line2D([], [], color=SEQ[-1], lw=2)],
               ["ciclos iniciais", "ciclos finais"], loc="upper right",
               bbox_to_anchor=(0.995, 0.99), ncol=2, labelcolor=INK2)
    titulo_figura(fig, "A descarga encurta conforme a bateria envelhece",
                  "Quatro baterias com as séries mais longas, na sua condição "
                  "principal. Cada curva vai até o corte de tensão; o trecho de "
                  "recuperação posterior foi omitido.")
    salvar(fig, "06_curvas_descarga.png"); plt.close(fig)

    # -- 07 espectro de impedancia retificada ao longo da vida
    #
    # Um diagrama de Nyquist seria o natural aqui, mas a coluna Battery_impedance
    # traz 2,2% de pontos com parte real negativa (ruido nos extremos da varredura)
    # e sai ilegivel. Rectified_Impedance e limpa (0,041 a 0,079 ohm, sem negativos),
    # so que com parte imaginaria praticamente nula — nao forma arco. Entao o que
    # este grafico mostra e o modulo ao longo da varredura, que e o que o dado
    # sustenta sem curadoria pesada.
    bat = zb.groupby("battery_id").size().idxmax()
    g = zb[zb.battery_id == bat]
    escolha = g.iloc[np.linspace(0, len(g) - 1, min(len(g), 12)).astype(int)]
    fig, ax = plt.subplots(figsize=(9.6, 5.8))
    desenhou = 0
    for i, r in enumerate(escolha.itertuples()):
        c = pd.read_csv(DADOS / "data" / r.filename)
        v = c.Rectified_Impedance.dropna().map(lambda t: complex(str(t)).real)
        if v.empty:
            continue
        passo = int(i * (len(SEQ) - 3) / max(1, len(escolha) - 1))
        ax.plot(range(len(v)), v.to_numpy(),
                color=SEQ[min(len(SEQ) - 1, 2 + passo)], linewidth=1.6)
        desenhou += 1
    ax.set_xlabel("Ponto da varredura de frequência (0,1 Hz a 5 kHz)")
    ax.set_ylabel("Impedância retificada (Ω)")
    ax.set_axisbelow(True); ax.grid(axis="x", visible=False)
    ax.legend([Line2D([], [], color=SEQ[2], lw=2), Line2D([], [], color=SEQ[-1], lw=2)],
              ["ensaios iniciais", "ensaios finais"], loc="upper left", labelcolor=INK2)
    titulo(ax, f"O espectro de impedância sobe com o envelhecimento — {bat}",
           f"{desenhou} ensaios de espectroscopia ao longo da vida da célula")
    fig.tight_layout(); salvar(fig, "07_espectro_impedancia.png"); plt.close(fig)


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description="Analise e graficos do NASA Li-ion Battery Aging Dataset.")
    ap.add_argument("--sem-graficos", action="store_true",
                    help="gera so as tabelas de metricas")
    args = ap.parse_args()

    mods = checar()
    SAIDA.mkdir(exist_ok=True)

    p("Lendo os ensaios...")
    d, z = montar_metricas(mods)
    resumo = resumir(mods, d, z)

    cols_d = ["battery_id", "ciclo", "ciclo_na_condicao", "test_id", "uid", "filename",
              "condicao", "corrente_A", "ambient_temperature", "Capacity", "cap_ref_Ah",
              "SoH_%", "duracao_min", "V_final", "T_max_C", "alerta"]
    d[cols_d].to_csv(SAIDA / "metricas_descargas.csv", index=False)
    z[["battery_id", "ciclo", "test_id", "uid", "filename", "ambient_temperature",
       "Re_ohm", "Rct_ohm", "SoH_%", "alerta"]].to_csv(
        SAIDA / "metricas_impedancia.csv", index=False)
    resumo.to_csv(SAIDA / "resumo_baterias.csv", index=False)

    p(f"  {len(d)} descargas, {len(z)} ensaios de impedancia, "
      f"{resumo.battery_id.nunique()} baterias")
    p(f"  marcados: {int((d.alerta != '').sum())} descargas, "
      f"{int((z.alerta != '').sum())} impedancias")
    p(f"  condicoes de ensaio distintas: {d.condicao.nunique()}")
    p(f"  baterias que mudam de condicao: "
      f"{int((d.groupby('battery_id').condicao.nunique() > 1).sum())}")

    if not args.sem_graficos:
        p("Graficos:")
        desenhar(mods, d, z)

    p(f"\nSaida em {SAIDA.name}/")


if __name__ == "__main__":
    main()
