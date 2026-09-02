#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Converte um Oxford Battery Degradation Dataset (.mat) para CSV + Excel + graficos.

Roda em qualquer maquina (Linux/macOS/Windows, Python 3.9+). Sem caminhos fixos:
o arquivo .mat e a pasta de saida vem da linha de comando, ou sao descobertos
automaticamente no diretorio atual.

Uso:
    python converter_oxford_mat.py
    python converter_oxford_mat.py -e dados/Oxford_1.mat -s resultados/
    python converter_oxford_mat.py --sem-csv          # so a planilha e os PNGs
    python converter_oxford_mat.py -c Cell1 Cell2     # so algumas celulas

Dependencias: numpy, scipy, pandas, xlsxwriter  (matplotlib e opcional, so p/ PNGs)
    python -m pip install -r requirements.txt
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

VERSAO = "1.0"
LIMITE_LINHAS_EXCEL = 1_048_576

# --------------------------------------------------------------------------
# impressao segura em consoles que nao sao UTF-8 (cmd.exe antigo, por exemplo)
# --------------------------------------------------------------------------
def p(msg: str = "") -> None:
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "ascii"
        print(msg.encode(enc, "replace").decode(enc), flush=True)


# --------------------------------------------------------------------------
# dependencias
# --------------------------------------------------------------------------
def checar_dependencias():
    faltando = []
    mods = {}
    for nome, pacote in (("numpy", "numpy"), ("scipy", "scipy"),
                         ("pandas", "pandas"), ("xlsxwriter", "XlsxWriter")):
        try:
            mods[nome] = __import__(nome)
        except ImportError:
            faltando.append(pacote)
    if faltando:
        p("ERRO: faltam dependencias: " + ", ".join(faltando))
        p("")
        p("Instale com:")
        p(f"    {Path(sys.executable).name} -m pip install " + " ".join(faltando))
        p("")
        p("Se o sistema bloquear a instalacao (externally-managed-environment),")
        p("crie um ambiente virtual primeiro:")
        p(f"    {Path(sys.executable).name} -m venv venv")
        p("    # Linux/macOS:  source venv/bin/activate")
        p("    # Windows:      venv\\Scripts\\activate")
        p("    python -m pip install numpy scipy pandas XlsxWriter matplotlib")
        sys.exit(1)
    return mods


# --------------------------------------------------------------------------
# paleta (categorica validada p/ daltonismo, modo claro) e estilo
# --------------------------------------------------------------------------
PAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
       "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
SEQ = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7",
       "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e3e2de"

DESC_ENSAIO = {
    "C1ch":  "Carga a 1C (caracterizacao)",
    "C1dc":  "Descarga a 1C (caracterizacao)",
    "OCVch": "Carga lenta C/18 (pseudo-OCV)",
    "OCVdc": "Descarga lenta C/18 (pseudo-OCV)",
}


def datenum_para_datetime(d: float) -> dt.datetime:
    """datenum do MATLAB -> datetime do Python."""
    return dt.datetime.fromordinal(int(d)) + dt.timedelta(days=d % 1) - dt.timedelta(days=366)


# --------------------------------------------------------------------------
# descoberta do arquivo de entrada
# --------------------------------------------------------------------------
def achar_mat(entrada) -> Path:
    if entrada:
        cam = Path(entrada).expanduser()
        if not cam.is_file():
            p(f"ERRO: arquivo nao encontrado: {cam}")
            sys.exit(1)
        return cam.resolve()

    candidatos = sorted(Path.cwd().glob("*.mat"))
    if not candidatos:
        p("ERRO: nenhum arquivo .mat no diretorio atual.")
        p("Informe o caminho:  python converter_oxford_mat.py -e caminho/arquivo.mat")
        sys.exit(1)
    if len(candidatos) > 1:
        preferido = [c for c in candidatos if "oxford" in c.name.lower()]
        if len(preferido) == 1:
            candidatos = preferido
        else:
            p("Varios .mat encontrados; escolha um com -e:")
            for c in candidatos:
                p(f"    {c.name}")
            sys.exit(1)
    return candidatos[0].resolve()


def checar_versao_mat(caminho: Path) -> None:
    """MAT v7.3 e HDF5 e o scipy nao le. Avisa com clareza em vez de estourar."""
    with open(caminho, "rb") as fh:
        cabecalho = fh.read(128)
    if cabecalho[:8] == b"\x89HDF\r\n\x1a\n":
        p("ERRO: este .mat foi salvo no formato v7.3 (HDF5), que o scipy nao le.")
        p("No MATLAB, reexporte com:  save('arquivo.mat', '-v7')")
        p("Ou converta antes usando a biblioteca h5py / mat73.")
        sys.exit(1)
    if b"MATLAB 5.0 MAT-file" not in cabecalho:
        p("AVISO: cabecalho nao reconhecido como MAT-file v5; tentando mesmo assim.")


# --------------------------------------------------------------------------
# leitura da estrutura
# --------------------------------------------------------------------------
def listar_celulas(sio, caminho: Path):
    """Le so os cabecalhos do .mat para descobrir as variaveis de topo."""
    nomes = [nome for nome, _forma, _tipo in sio.whosmat(str(caminho))
             if not nome.startswith("__")]

    def chave(s):
        digitos = "".join(ch for ch in s if ch.isdigit())
        return (0, int(digitos)) if digitos else (1, 0), s

    return sorted(nomes, key=chave)


def campos(estrutura) -> list:
    nomes = estrutura.dtype.names
    return list(nomes) if nomes else []


def extrair_sinais(np, ensaio):
    """Devolve (t, v, q, T) alinhados, ou None se o ensaio estiver vazio."""
    disponiveis = campos(ensaio)
    saida = []
    for chave in ("t", "v", "q", "T"):
        if chave not in disponiveis:
            return None
        saida.append(np.asarray(ensaio[chave], dtype=float).ravel())
    n = min(len(a) for a in saida)
    if n == 0:
        return None
    return [a[:n] for a in saida]


# --------------------------------------------------------------------------
# etapa 1: percorrer o .mat, escrever CSVs e montar as metricas
# --------------------------------------------------------------------------
def processar(mods, caminho_mat: Path, dir_csv, celulas, escrever_csv, pontos_curva):
    np, sio, pd = mods["numpy"], mods["scipy"], mods["pandas"]
    import scipy.io as scipy_io

    metricas, curvas = [], {}
    total_linhas = 0

    # Uma celula por vez: no MAT v5 cada variavel e comprimida separadamente,
    # entao ler so a que interessa nao custa tempo a mais e segura a RAM baixa.
    for cel in celulas:
        p(f"Lendo {cel}...")
        bruto = scipy_io.loadmat(str(caminho_mat), variable_names=[cel])[cel]

        estrutura = bruto[0, 0]
        ciclos = campos(estrutura)
        curvas[cel] = {}

        fh = None
        if escrever_csv:
            arq = dir_csv / f"{cel}.csv"
            fh = open(arq, "w", newline="", encoding="utf-8")
            fh.write("celula,ciclo,ensaio,tempo_s,tensao_V,carga_mAh,temperatura_C\n")

        for nome_ciclo in ciclos:
            digitos = "".join(ch for ch in nome_ciclo if ch.isdigit())
            n_ciclo = int(digitos) if digitos else len(metricas)
            ciclo = estrutura[nome_ciclo][0, 0]
            linha = {"celula": cel, "ciclo": n_ciclo}

            for ensaio in campos(ciclo):
                sinais = extrair_sinais(np, ciclo[ensaio][0, 0])
                if sinais is None:
                    continue
                t, v, q, T = sinais
                n = len(t)
                tempo_s = (t - t[0]) * 86400.0

                if fh is not None:
                    prefixo = f"{cel},{n_ciclo},{ensaio},"
                    fh.writelines(
                        prefixo + "%.3f,%.6f,%.6f,%.4f\n" % r
                        for r in zip(tempo_s, v, q, T)
                    )
                total_linhas += n

                linha[f"inicio_{ensaio}"]     = datenum_para_datetime(t[0])
                linha[f"duracao_h_{ensaio}"]  = tempo_s[-1] / 3600.0
                linha[f"cap_mAh_{ensaio}"]    = float(np.ptp(q))
                linha[f"vmin_V_{ensaio}"]     = float(v.min())
                linha[f"vmax_V_{ensaio}"]     = float(v.max())
                linha[f"Tmed_C_{ensaio}"]     = float(T.mean())
                linha[f"Tmax_C_{ensaio}"]     = float(T.max())
                linha[f"n_amostras_{ensaio}"] = int(n)

                if ensaio == ENSAIO_REF[0]:
                    idx = np.linspace(0, n - 1, min(n, pontos_curva)).astype(int)
                    curvas[cel][n_ciclo] = (np.abs(q[idx] - q[idx][0]), v[idx])

            metricas.append(linha)

        if fh is not None:
            fh.close()
            mb = arq.stat().st_size / 1e6
            p(f"  {cel}: {len(ciclos)} ciclos -> {arq.name} ({mb:.1f} MB)")
        else:
            p(f"  {cel}: {len(ciclos)} ciclos")

        del bruto, estrutura

    df = mods["pandas"].DataFrame(metricas).sort_values(["celula", "ciclo"]).reset_index(drop=True)
    return df, curvas, total_linhas


# ENSAIO_REF e definido em tempo de execucao (o dataset pode nomear diferente)
ENSAIO_REF = ["C1dc"]


def escolher_ensaio_referencia(mods, caminho_mat: Path, primeira_celula: str) -> str:
    """O ensaio usado para capacidade/SoH/curvas: C1dc, ou a melhor alternativa."""
    import scipy.io as scipy_io
    estrutura = scipy_io.loadmat(str(caminho_mat), variable_names=[primeira_celula])[primeira_celula][0, 0]
    primeiro_ciclo = campos(estrutura)[0]
    ensaios = campos(estrutura[primeiro_ciclo][0, 0])
    for preferido in ("C1dc", "C1ch"):
        if preferido in ensaios:
            return preferido
    apenas_descarga = [e for e in ensaios if e.lower().endswith("dc")]
    return apenas_descarga[0] if apenas_descarga else ensaios[0]


# --------------------------------------------------------------------------
# controle de qualidade: marca medicoes suspeitas
# --------------------------------------------------------------------------
# Limiares escolhidos a partir da distribuicao do proprio dataset:
#   razao C1dc/OCVdc  -> mediana 0.991, percentil 0.5% em 0.949  => corte em 0.95
#   |OCVch-OCVdc|     -> mediana 0.3%,  percentil 99.5% em 1.6%  => corte em 3%
RAZAO_MIN_1C_OCV = 0.95
DESBALANCO_MAX_OCV = 0.03
DESVIO_MAX_TEMP_C = 5.0


def detectar_anomalias(mods, df, ref):
    """Marca ciclos cuja medicao nao e confiavel. Nada e removido: so sinalizado.

    Tres verificacoes:
      * temperatura media muito longe da mediana do proprio ensaio -> sensor/camara
      * capacidade a 1C muito abaixo da capacidade OCV do mesmo ciclo -> o ensaio
        rapido nao extraiu a carga que o ensaio lento do mesmo ciclo encontrou
      * carga e descarga OCV do mesmo ciclo discordando -> ensaio interrompido
    """
    np, pd = mods["numpy"], mods["pandas"]
    alertas = [[] for _ in range(len(df))]

    ensaios = [c[len("Tmed_C_"):] for c in df.columns if c.startswith("Tmed_C_")]
    for e in ensaios:
        col = f"Tmed_C_{e}"
        fora = (df[col] - df[col].median()).abs() > DESVIO_MAX_TEMP_C
        for pos in np.where(fora.fillna(False).to_numpy())[0]:
            alertas[pos].append(f"temperatura_{e}")

    col_ref, col_ocv = f"cap_mAh_{ref}", "cap_mAh_OCVdc"
    if col_ref in df.columns and col_ocv in df.columns and col_ref != col_ocv:
        baixa = (df[col_ref] / df[col_ocv]) < RAZAO_MIN_1C_OCV
        for pos in np.where(baixa.fillna(False).to_numpy())[0]:
            alertas[pos].append("1C_abaixo_do_OCV")

    if "cap_mAh_OCVch" in df.columns and col_ocv in df.columns:
        media = df[["cap_mAh_OCVch", col_ocv]].mean(axis=1)
        desb = (df["cap_mAh_OCVch"] - df[col_ocv]).abs() / media > DESBALANCO_MAX_OCV
        for pos in np.where(desb.fillna(False).to_numpy())[0]:
            alertas[pos].append("ocv_inconsistente")

    df["alerta"] = ["; ".join(a) for a in alertas]
    return df


def _mascara_suspeitos(tabela, marcados, df):
    """True nas celulas (ciclo x celula) da tabela que tem alerta."""
    mascara = tabela.notna() & False          # mesma forma, tudo False
    for _, r in marcados.iterrows():
        if r["celula"] in mascara.columns and r["ciclo"] in mascara.index:
            mascara.at[r["ciclo"], r["celula"]] = True
    return mascara


def taxa_degradacao(mods, df, celulas, col_cap, janela=3, passo=4):
    """mAh perdidos a cada 100 ciclos, ignorando as medicoes marcadas.

    A diferenca entre duas caracterizacoes vizinhas e dominada pelo ruido de
    medicao (poucos mAh), entao a inclinacao e tomada sobre `passo` pontos
    (~400 ciclos) de uma capacidade previamente suavizada por mediana movel.
    """
    pd = mods["pandas"]
    saida = {}
    for cel in celulas:
        g = df[(df["celula"] == cel) & (df["alerta"] == "")].sort_values("ciclo")
        if len(g) < passo + 1:
            continue
        suave = g[col_cap].rolling(janela, center=True, min_periods=1).median()
        taxa = -suave.diff(passo) / g["ciclo"].diff(passo) * 100.0
        saida[cel] = pd.Series(taxa.to_numpy(), index=g["ciclo"].to_numpy())
    return pd.DataFrame(saida)


# --------------------------------------------------------------------------
# etapa 2: planilha Excel
# --------------------------------------------------------------------------
def montar_excel(mods, df, curvas, celulas, caminho_xlsx: Path, total_linhas, nome_mat, ref):
    np, pd = mods["numpy"], mods["pandas"]
    cor = {cel: PAL[i % len(PAL)] for i, cel in enumerate(celulas)}
    col_cap = f"cap_mAh_{ref}"

    linhas_resumo = []
    for cel in celulas:
        g = df[df["celula"] == cel]
        cols_inicio = [c for c in g.columns if c.startswith("inicio_")]
        inicio = g[cols_inicio].min().min() if cols_inicio else None
        fim = g[cols_inicio].max().max() if cols_inicio else None
        cols_n = [c for c in g.columns if c.startswith("n_amostras_")]
        item = {
            "celula": cel,
            "ciclos_caracterizados": len(g),
            "ciclo_inicial": int(g["ciclo"].min()),
            "ciclo_final": int(g["ciclo"].max()),
            "inicio_ensaio": inicio,
            "fim_ensaio": fim,
            "duracao_dias": (fim - inicio).days if inicio is not None and fim is not None else None,
            "capacidade_inicial_mAh": g[col_cap].iloc[0],
            "capacidade_final_mAh": g[col_cap].iloc[-1],
            "perda_mAh": g[col_cap].iloc[0] - g[col_cap].iloc[-1],
            "SoH_final_%": g["SoH_%"].iloc[-1],
            "linhas_brutas": int(g[cols_n].sum().sum()) if cols_n else 0,
        }
        col_tmed, col_tmax = f"Tmed_C_{ref}", f"Tmax_C_{ref}"
        if col_tmed in g:
            item["temperatura_media_C"] = g[col_tmed].mean()
            item["temperatura_max_C"] = g[col_tmax].max()
        linhas_resumo.append(item)
    resumo_cel = pd.DataFrame(linhas_resumo)

    def pivot(coluna):
        if coluna not in df.columns:
            return None
        tab = df.pivot(index="ciclo", columns="celula", values=coluna)
        return tab[[c for c in celulas if c in tab.columns]]

    leiame = [
        ("Gerado por", f"converter_oxford_mat.py v{VERSAO} — {dt.date.today().isoformat()}"),
        ("Arquivo original", nome_mat),
        ("Conteudo", f"{len(celulas)} celulas ({', '.join(celulas[:4])}...), "
                     f"caracterizadas periodicamente ao longo do envelhecimento"),
        ("Ensaios por ciclo", " | ".join(f"{k} = {v}" for k, v in DESC_ENSAIO.items())),
        ("Sinais", "t = tempo (datenum MATLAB) | v = tensao (V) | q = carga (mAh) | T = temperatura (C)"),
        ("Ensaio de referencia", f"{ref} — base das colunas de capacidade, do SoH e das curvas"),
        ("", ""),
        ("POR QUE OS DADOS BRUTOS NAO ESTAO NESTA PLANILHA",
         f"O .mat contem {total_linhas:,} linhas de serie temporal. O limite do Excel e "
         f"{LIMITE_LINHAS_EXCEL:,} por aba, entao os dados ponto a ponto vao para CSV em "
         "csv_dados_brutos/ (um arquivo por celula). Esta planilha traz as metricas derivadas."),
        ("", ""),
        ("Resumo_Celulas", "Uma linha por celula: janela de ensaio, capacidade inicial/final, SoH, temperatura"),
        ("Metricas_por_Ciclo", "Uma linha por (celula, ciclo), com todos os ensaios: capacidade, "
                               "duracao, faixa de tensao, temperatura media/maxima, n de amostras"),
        ("Capacidade_Descarga", "Tabela dinamica ciclo x celula (capacidade, mAh) + grafico"),
        ("SoH", "Idem, normalizado pelo primeiro ciclo de cada celula (%) + grafico"),
        ("Capacidade_OCV", "Idem, capacidade da descarga lenta C/18 (mAh) + grafico"),
        ("Temperatura_Media", "Temperatura media durante o ensaio de referencia (C) + grafico"),
        ("Curva_<celula>", "Tensao x capacidade descarregada, um par de colunas por ciclo + grafico"),
        ("Anomalias", "Ciclos cuja medicao nao e confiavel, com o motivo. Nenhum dado foi "
                      "removido — os alertas apenas sinalizam o que nao se deve usar cru."),
        ("", ""),
        ("alerta = temperatura_<ensaio>",
         f"Temperatura media a mais de {DESVIO_MAX_TEMP_C:.0f} C da mediana daquele ensaio: "
         "sensor solto ou camara termica fora de regime."),
        ("alerta = 1C_abaixo_do_OCV",
         f"A capacidade medida a 1C ficou abaixo de {RAZAO_MIN_1C_OCV:.0%} da capacidade "
         "medida no ensaio lento (OCV) do MESMO ciclo. Como o ensaio lento encontrou mais "
         "carga na celula, o valor a 1C nao representa a capacidade dela. O instrumento "
         "gravou corretamente o que aconteceu; foi o ensaio que nao mediu o que deveria. "
         "A causa nao e identificavel so com estes dados — ver a coluna diagnostico."),
        ("alerta = ocv_inconsistente",
         f"Carga e descarga OCV do mesmo ciclo discordam em mais de {DESBALANCO_MAX_OCV:.0%}: "
         "ensaio interrompido."),
        ("", ""),
        ("Definicoes", "capacidade = max(q) - min(q) dentro do ensaio; "
                       "SoH = capacidade / capacidade do primeiro ciclo da celula x 100"),
        ("Datas", "Convertidas de datenum MATLAB para data/hora real"),
        ("tempo_s nos CSVs", "Segundos desde o inicio daquele ensaio; o instante absoluto "
                             "de inicio esta na aba Metricas_por_Ciclo"),
    ]

    opcoes = {"engine_kwargs": {"options": {"nan_inf_to_errors": True}}}
    with pd.ExcelWriter(caminho_xlsx, engine="xlsxwriter", **opcoes) as xl:
        wb = xl.book
        f_tit = wb.add_format({"bold": True, "font_size": 14, "font_color": INK})
        f_hdr = wb.add_format({"bold": True, "bg_color": "#f0efec", "font_color": INK,
                               "border": 1, "border_color": GRID, "text_wrap": True, "valign": "top"})
        f_key = wb.add_format({"bold": True, "font_color": INK, "valign": "top"})
        f_txt = wb.add_format({"font_color": INK2, "text_wrap": True, "valign": "top"})
        f_dat = wb.add_format({"num_format": "yyyy-mm-dd hh:mm"})

        ws = wb.add_worksheet("Leia-me")
        xl.sheets["Leia-me"] = ws
        ws.hide_gridlines(2)
        ws.set_column("A:A", 26)
        ws.set_column("B:B", 105)
        ws.write("A1", "Oxford Battery Degradation Dataset — conversao para Excel", f_tit)
        for i, (k, v) in enumerate(leiame):
            ws.write(i + 2, 0, k, f_key)
            ws.write(i + 2, 1, v, f_txt)

        def escreve(nome, tabela, indice=False, largura=16, primeira=22):
            if len(tabela) + 1 > LIMITE_LINHAS_EXCEL:
                p(f"AVISO: aba {nome} truncada no limite do Excel.")
                tabela = tabela.iloc[:LIMITE_LINHAS_EXCEL - 1]
            tabela.to_excel(xl, sheet_name=nome, index=indice,
                            freeze_panes=(1, 1 if indice else 0))
            w = xl.sheets[nome]
            cols = ([tabela.index.name or ""] if indice else []) + [str(c) for c in tabela.columns]
            for j, c in enumerate(cols):
                w.write(0, j, c, f_hdr)
            w.set_column(0, 0, primeira)
            w.set_column(1, max(1, len(cols) - 1), largura)
            w.hide_gridlines(2)
            return w

        def arredonda(tabela):
            num = tabela.select_dtypes("number").columns
            return tabela.assign(**{c: tabela[c].round(4) for c in num})

        w = escreve("Resumo_Celulas", arredonda(resumo_cel), largura=20, primeira=10)
        for nome_col in ("inicio_ensaio", "fim_ensaio"):
            if nome_col in resumo_cel.columns:
                j = list(resumo_cel.columns).index(nome_col)
                w.set_column(j, j, 19, f_dat)

        escreve("Metricas_por_Ciclo", arredonda(df), largura=15, primeira=10)

        def aba_pivot(nome, tabela, titulo, eixo_y, fmt="0.0"):
            if tabela is None or tabela.empty:
                return
            w = escreve(nome, arredonda(tabela), indice=True, largura=13, primeira=10)
            ch = wb.add_chart({"type": "line"})
            n = len(tabela)
            for i, cel in enumerate(tabela.columns):
                if cel in cor:
                    linha_fmt = {"color": cor[cel], "width": 2.0}
                else:   # serie de referencia (ex.: limite de fim de vida)
                    linha_fmt = {"color": INK2, "width": 1.25, "dash_type": "dash"}
                ch.add_series({
                    "name":       [nome, 0, i + 1],
                    "categories": [nome, 1, 0, n, 0],
                    "values":     [nome, 1, i + 1, n, i + 1],
                    "line": linha_fmt,
                })
            ch.set_title({"name": titulo, "name_font": {"size": 13, "color": INK, "bold": True}})
            ch.set_x_axis({"name": "Ciclo de envelhecimento", "num_font": {"color": INK2},
                           "line": {"color": GRID}, "major_gridlines": {"visible": False}})
            ch.set_y_axis({"name": eixo_y, "num_font": {"color": INK2}, "num_format": fmt,
                           "line": {"none": True},
                           "major_gridlines": {"visible": True, "line": {"color": GRID}}})
            ch.set_legend({"position": "right", "font": {"color": INK2}})
            ch.set_chartarea({"border": {"none": True}, "fill": {"color": SURF}})
            ch.set_plotarea({"fill": {"color": SURF}})
            ch.set_size({"width": 900, "height": 460})
            w.insert_chart(2, len(tabela.columns) + 3, ch)

        aba_pivot("Capacidade_Descarga", pivot(col_cap),
                  f"Capacidade ({ref}) ao longo do envelhecimento", "Capacidade (mAh)")

        # O SoH e a capacidade reescalada por celula, entao a curva tem a mesma
        # forma. A linha de 80% e o que faz esta aba responder outra pergunta:
        # em que ciclo cada celula cruza o fim de vida convencionado.
        tab_soh = pivot("SoH_%")
        if tab_soh is not None and not tab_soh.empty:
            tab_soh = tab_soh.copy()
            tab_soh["fim_de_vida_80%"] = 80.0
        aba_pivot("SoH", tab_soh,
                  "Estado de saude (SoH) e o limite de fim de vida (80%)", "SoH (%)")
        aba_pivot("Capacidade_OCV", pivot("cap_mAh_OCVdc"),
                  "Capacidade da descarga lenta C/18 (pseudo-OCV)", "Capacidade (mAh)")
        aba_pivot("Temperatura_Media", pivot(f"Tmed_C_{ref}"),
                  f"Temperatura media durante o ensaio {ref}", "Temperatura (C)", fmt="0.00")

        marcados = df[df["alerta"] != ""]
        if len(marcados):
            cols = ["celula", "ciclo", "alerta", col_cap, "cap_mAh_OCVdc",
                    "cap_mAh_OCVch", f"Tmed_C_{ref}", f"duracao_h_{ref}"]
            cols = [c for c in cols if c in marcados.columns]
            tabela_anom = marcados[cols].copy()
            # Capacidade recuperou no proximo ciclo? Capacidade perdida nao volta,
            # entao recuperar e a prova de que a medicao e que estava errada.
            tabela_anom.insert(len(cols), "cap_proximo_ciclo", pd.NA)
            tabela_anom.insert(len(cols) + 1, "diagnostico", "")
            for i, r in tabela_anom.iterrows():
                g = df[(df["celula"] == r["celula"]) & (df["ciclo"] > r["ciclo"])] \
                      .sort_values("ciclo")
                if not len(g):
                    tabela_anom.at[i, "diagnostico"] = (
                        "ultimo ciclo da celula: sem medicao posterior para comparar")
                    continue
                prox = g.iloc[0][col_cap]
                tabela_anom.at[i, "cap_proximo_ciclo"] = prox
                if "temperatura" in r["alerta"] and "1C_abaixo" not in r["alerta"]:
                    tabela_anom.at[i, "diagnostico"] = (
                        "so a temperatura: tensao e capacidade normais no mesmo ciclo")
                elif prox > r[col_cap] * 1.02:
                    tabela_anom.at[i, "diagnostico"] = (
                        f"capacidade voltou a {prox:.0f} mAh no ciclo seguinte: "
                        "a medicao estava errada, a celula nao")
                else:
                    tabela_anom.at[i, "diagnostico"] = (
                        "nao recuperou no ciclo seguinte: pode ser a celula, nao a medicao")
            escreve("Anomalias", arredonda(tabela_anom), largura=17, primeira=10)

        for cel in celulas:
            if not curvas.get(cel):
                continue
            sel = selecionar_ciclos(sorted(curvas[cel]))
            blocos, cabec = [], []
            for c in sel:
                q, v = curvas[cel][c]
                blocos += [pd.Series(q), pd.Series(v)]
                cabec += [f"cap_mAh_cic{c}", f"tensao_V_cic{c}"]
            tab = pd.concat(blocos, axis=1)
            tab.columns = cabec
            nome = f"Curva_{cel}"[:31]
            w = escreve(nome, arredonda(tab), largura=15, primeira=15)
            ch = wb.add_chart({"type": "scatter", "subtype": "straight"})
            n = len(tab)
            passo = max(1, (len(SEQ) - 1) // max(1, len(sel) - 1))
            for i, c in enumerate(sel):
                ch.add_series({
                    "name":       f"ciclo {c}",
                    "categories": [nome, 1, 2 * i,     n, 2 * i],
                    "values":     [nome, 1, 2 * i + 1, n, 2 * i + 1],
                    "line": {"color": SEQ[min(len(SEQ) - 1, i * passo)], "width": 1.75},
                    "marker": {"type": "none"},
                })
            ch.set_title({"name": f"{cel} — {ref}: tensao x capacidade, por ciclo",
                          "name_font": {"size": 13, "color": INK, "bold": True}})
            ch.set_x_axis({"name": "Capacidade descarregada (mAh)", "num_font": {"color": INK2},
                           "line": {"color": GRID}, "major_gridlines": {"visible": False}})
            ch.set_y_axis({"name": "Tensao (V)", "num_font": {"color": INK2},
                           "line": {"none": True},
                           "major_gridlines": {"visible": True, "line": {"color": GRID}}})
            ch.set_legend({"position": "right", "font": {"color": INK2}})
            ch.set_chartarea({"border": {"none": True}, "fill": {"color": SURF}})
            ch.set_plotarea({"fill": {"color": SURF}})
            ch.set_size({"width": 880, "height": 460})
            w.insert_chart(2, 2 * len(sel) + 2, ch)


def selecionar_ciclos(ciclos, alvo=10):
    """Escolhe ~alvo ciclos bem espacados, sempre com o primeiro e o ultimo.

    Prefere numeros redondos (1000, 500, 200...) quando o dataset os oferece,
    porque rotulo "ciclo 3000" se le melhor que "ciclo 2917"; se a numeracao
    nao for regular, cai no espacamento por indice.
    """
    if len(ciclos) <= alvo:
        return list(ciclos)
    sel = None
    for redondo in (1000, 500, 200, 100):
        candidatos = [c for c in ciclos if c % redondo == 0]
        if alvo * 0.6 <= len(candidatos) <= alvo * 1.6:
            sel = candidatos
            break
    if sel is None:
        passo = max(1, len(ciclos) // alvo)
        sel = list(ciclos[::passo])
    if ciclos[0] not in sel:
        sel.insert(0, ciclos[0])
    if ciclos[-1] not in sel:
        sel.append(ciclos[-1])
    return sel


# --------------------------------------------------------------------------
# etapa 3: PNGs (opcional — so se matplotlib estiver instalado)
# --------------------------------------------------------------------------
def montar_graficos(mods, df, curvas, celulas, dir_graficos: Path, ref):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.lines import Line2D
    except ImportError:
        p("AVISO: matplotlib nao instalado — PNGs ignorados "
          "(instale com: python -m pip install matplotlib).")
        return

    pd = mods["pandas"]
    cor = {cel: PAL[i % len(PAL)] for i, cel in enumerate(celulas)}

    plt.rcParams.update({
        "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
        "font.size": 11, "text.color": INK, "axes.labelcolor": INK2,
        "xtick.color": INK2, "ytick.color": INK2,
        "axes.edgecolor": GRID, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 2.0,
        "legend.frameon": False, "figure.dpi": 150,
    })

    def pivot(coluna):
        if coluna not in df.columns:
            return None
        tab = df.pivot(index="ciclo", columns="celula", values=coluna)
        return tab[[c for c in celulas if c in tab.columns]]

    marcados = df[df["alerta"] != ""] if "alerta" in df.columns else df.iloc[:0]

    def linhas(tabela, titulo, sub, ylabel, arquivo, coluna=None, filtro_alerta=None):
        """Uma linha por celula.

        `coluna` + `filtro_alerta` ligam a marcacao de qualidade: so entram os
        alertas cujo texto casa com `filtro_alerta`, para nao marcar um ponto do
        C1dc por causa de um problema que aconteceu no ensaio OCV do mesmo ciclo.
        Os pontos marcados saem da linha (que fica com uma falha visivel) e da
        escala do eixo, para que um sensor quebrado nao achate o grafico inteiro.
        """
        if tabela is None or tabela.empty:
            return

        sus = marcados.iloc[:0]
        if coluna is not None and filtro_alerta is not None and len(marcados):
            casa = marcados["alerta"].str.contains(filtro_alerta, regex=False)
            sus = marcados[casa & marcados[coluna].notna()]

        plotavel = tabela
        if len(sus):
            plotavel = tabela.mask(_mascara_suspeitos(tabela, sus, df))

        fig, ax = plt.subplots(figsize=(10, 5.6))
        # A legenda e ordenada pelo valor final de cada linha, para que a ordem
        # de cima para baixo na legenda seja a mesma ordem em que as linhas
        # aparecem na borda direita do grafico. Sem isso e facil trocar duas
        # cores vizinhas ao procurar qual celula e qual.
        entradas = []
        for cel in plotavel.columns:
            serie = plotavel[cel]
            (handle,) = ax.plot(serie.index, serie.values, color=cor[cel], label=cel,
                                solid_capstyle="round")
            ultimo = serie.dropna()
            entradas.append((ultimo.iloc[-1] if len(ultimo) else float("-inf"), cel, handle))
        entradas.sort(key=lambda e: -e[0])

        fora_da_escala = []
        if len(sus):
            lim = ax.get_ylim()
            for _, r in sus.iterrows():
                if r["celula"] not in tabela.columns:
                    continue
                y = r[coluna]
                if lim[0] <= y <= lim[1]:
                    ax.plot(r["ciclo"], y, marker="o", markersize=9, markerfacecolor="none",
                            markeredgecolor=INK2, markeredgewidth=1.6, linestyle="none",
                            zorder=5)
                else:
                    fora_da_escala.append(f"{r['celula']} ciclo {int(r['ciclo'])} "
                                          f"= {y:.1f} ({r['alerta']})")
            ax.set_ylim(lim)
            (marca,) = ax.plot([], [], marker="o", markersize=9, markerfacecolor="none",
                               markeredgecolor=INK2, markeredgewidth=1.6, linestyle="none",
                               label="medicao suspeita")
            entradas.append((float("-inf"), "medicao suspeita", marca))

        ax.set_xlabel("Ciclo de envelhecimento")
        ax.set_ylabel(ylabel)
        ax.set_axisbelow(True)
        ax.grid(axis="x", visible=False)
        ax.legend([e[2] for e in entradas], [e[1] for e in entradas],
                  loc="center left", bbox_to_anchor=(1.01, 0.5), labelcolor=INK2)
        ax.set_title(titulo, fontsize=14, fontweight="bold", color=INK, loc="left", pad=18)
        ax.text(0, 1.02, sub, transform=ax.transAxes, fontsize=10.5, color=INK2, va="bottom")
        if fora_da_escala:
            ax.text(0, -0.16, "Removido da escala — " + "; ".join(fora_da_escala),
                    transform=ax.transAxes, fontsize=9.5, color=INK2, va="top")
        fig.tight_layout()
        fig.savefig(dir_graficos / arquivo, bbox_inches="tight")
        plt.close(fig)
        p(f"  {arquivo}")

    linhas(pivot(f"cap_mAh_{ref}"), f"Perda de capacidade das {len(celulas)} celulas",
           f"Ensaio {ref}, medido a cada caracterizacao", "Capacidade (mAh)",
           "01_capacidade_vs_ciclo.png", coluna=f"cap_mAh_{ref}",
           filtro_alerta="1C_abaixo_do_OCV")

    # O SoH e a capacidade dividida pelo primeiro ciclo da propria celula: como
    # todas partem quase da mesma capacidade, a curva sai identica a de cima.
    # A taxa de perda mostra o que aquela nao mostra — onde a degradacao acelera.
    linhas(taxa_degradacao(mods, df, celulas, f"cap_mAh_{ref}"),
           "Velocidade da degradacao",
           "Inclinacao sobre ~400 ciclos da capacidade suavizada, "
           "sem as medicoes marcadas",
           "Perda (mAh / 100 ciclos)", "02_taxa_degradacao.png")

    linhas(pivot(f"Tmed_C_{ref}"), f"Temperatura media durante o ensaio {ref}",
           "Media por ensaio de caracterizacao", "Temperatura (°C)",
           "04_temperatura_vs_ciclo.png", coluna=f"Tmed_C_{ref}",
           filtro_alerta=f"temperatura_{ref}")

    com_curva = [c for c in celulas if curvas.get(c)]
    if not com_curva:
        return
    ncol = min(4, len(com_curva))
    nlin = -(-len(com_curva) // ncol)
    fig, axes = plt.subplots(nlin, ncol, figsize=(4 * ncol, 3.8 * nlin),
                             sharex=True, sharey=True, squeeze=False)
    planos = axes.ravel()
    for ax, cel in zip(planos, com_curva):
        sel = selecionar_ciclos(sorted(curvas[cel]))
        for i, c in enumerate(sel):
            q, v = curvas[cel][c]
            passo = int(i * (len(SEQ) - 3) / max(1, len(sel) - 1))
            ax.plot(q, v, color=SEQ[min(len(SEQ) - 1, 2 + passo)], linewidth=1.6)
        ax.set_title(cel, fontsize=12, fontweight="bold", color=INK, loc="left")
        ax.set_axisbelow(True)
        ax.grid(axis="x", visible=False)
    for ax in planos[len(com_curva):]:
        ax.set_visible(False)
    for ax in axes[-1]:
        ax.set_xlabel("Capacidade descarregada (mAh)")
    for ax in axes[:, 0]:
        ax.set_ylabel("Tensao (V)")
    guia = [Line2D([], [], color=SEQ[2], lw=2), Line2D([], [], color=SEQ[-1], lw=2)]
    fig.legend(guia, ["ciclos iniciais", "ciclos finais"], loc="upper right",
               bbox_to_anchor=(0.995, 0.995), ncol=2, labelcolor=INK2)
    fig.suptitle(f"Curvas de {ref} encolhendo com o envelhecimento",
                 fontsize=15, fontweight="bold", color=INK, x=0.007, ha="left", y=0.995)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(dir_graficos / "03_curvas_descarga_por_celula.png", bbox_inches="tight")
    plt.close(fig)
    p("  03_curvas_descarga_por_celula.png")


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description="Converte um Oxford Battery Degradation Dataset (.mat) "
                    "para CSV, Excel e graficos.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Exemplo:  python converter_oxford_mat.py -e dados/Oxford_1.mat -s resultados/")
    ap.add_argument("-e", "--entrada", help="caminho do .mat (padrao: procura no diretorio atual)")
    ap.add_argument("-s", "--saida", default="saida_oxford", help="pasta de saida (padrao: saida_oxford)")
    ap.add_argument("-c", "--celulas", nargs="+", help="processar so estas celulas (ex: Cell1 Cell2)")
    ap.add_argument("--sem-csv", action="store_true", help="nao gerar os CSVs brutos (economiza ~800 MB)")
    ap.add_argument("--sem-graficos", action="store_true", help="nao gerar os PNGs")
    ap.add_argument("--pontos-curva", type=int, default=250,
                    help="amostras por curva tensao x capacidade no Excel (padrao: 250)")
    ap.add_argument("-V", "--version", action="version", version=f"converter_oxford_mat {VERSAO}")
    args = ap.parse_args()

    mods = checar_dependencias()
    caminho_mat = achar_mat(args.entrada)
    checar_versao_mat(caminho_mat)

    dir_saida = Path(args.saida).expanduser().resolve()
    dir_csv = dir_saida / "csv_dados_brutos"
    dir_graficos = dir_saida / "graficos"
    dir_saida.mkdir(parents=True, exist_ok=True)
    if not args.sem_csv:
        dir_csv.mkdir(exist_ok=True)
    if not args.sem_graficos:
        dir_graficos.mkdir(exist_ok=True)

    import scipy.io as scipy_io
    p(f"Arquivo:  {caminho_mat}  ({caminho_mat.stat().st_size / 1e6:.0f} MB)")
    p(f"Saida:    {dir_saida}")

    celulas = listar_celulas(scipy_io, caminho_mat)
    if args.celulas:
        pedidas = [c for c in args.celulas if c in celulas]
        faltantes = [c for c in args.celulas if c not in celulas]
        if faltantes:
            p(f"AVISO: nao encontradas no arquivo: {', '.join(faltantes)}")
        if not pedidas:
            p(f"ERRO: nenhuma celula valida. Disponiveis: {', '.join(celulas)}")
            sys.exit(1)
        celulas = pedidas
    p(f"Celulas:  {', '.join(celulas)}")

    ENSAIO_REF[0] = escolher_ensaio_referencia(mods, caminho_mat, celulas[0])
    p(f"Ensaio de referencia: {ENSAIO_REF[0]}")
    p("")

    df, curvas, total_linhas = processar(
        mods, caminho_mat, dir_csv, celulas,
        escrever_csv=not args.sem_csv, pontos_curva=args.pontos_curva)

    np = mods["numpy"]
    col_cap = f"cap_mAh_{ENSAIO_REF[0]}"
    df["SoH_%"] = np.nan
    for cel in celulas:
        m = df["celula"] == cel
        base = df.loc[m, col_cap].dropna()
        if len(base):
            df.loc[m, "SoH_%"] = df.loc[m, col_cap] / base.iloc[0] * 100.0

    df = detectar_anomalias(mods, df, ENSAIO_REF[0])
    n_alertas = int((df["alerta"] != "").sum())

    p(f"\nLinhas de serie temporal lidas: {total_linhas:,}")
    if n_alertas:
        p(f"Controle de qualidade: {n_alertas} de {len(df)} ciclos marcados "
          f"(veja a aba Anomalias).")
        for _, r in df[df["alerta"] != ""].iterrows():
            p(f"  {r['celula']} ciclo {r['ciclo']:>5}: {r['alerta']}")

    caminho_xlsx = dir_saida / (caminho_mat.stem + ".xlsx")
    montar_excel(mods, df, curvas, celulas, caminho_xlsx, total_linhas,
                 caminho_mat.name, ENSAIO_REF[0])
    p(f"Excel:    {caminho_xlsx}  ({caminho_xlsx.stat().st_size / 1e6:.1f} MB)")

    if not args.sem_graficos:
        p("Graficos:")
        montar_graficos(mods, df, curvas, celulas, dir_graficos, ENSAIO_REF[0])

    p("\nConcluido.")


if __name__ == "__main__":
    main()
