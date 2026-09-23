#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Areas sob a curva de descarga e descritores de forma, uma linha por descarga.

    python curvas.py              # usa cache se existir
    python curvas.py --remontar   # ignora o cache e rele as 2.794 curvas
    python curvas.py --amostra 50 # so as 50 primeiras, para teste rapido

Escreve saida_nasa/curvas/features_curvas.csv.

Este e o passo 0: le as curvas brutas **uma unica vez** e entrega o que os tres
estudos seguintes precisam — as areas (item 4), a carga integrada em Ah (item 3)
e os descritores de forma que definem os grupos de comportamento (item 1). Ler
575 MB tres vezes seria desperdicio, entao tudo sai do mesmo passe e vai para
cache.

**As tres areas.** A curva de descarga admite tres integrais, e elas medem
coisas diferentes:

- `carga_Ah` = integral de |I| dt / 3600. E a capacidade: quanta carga saiu.
- `tensao_Vs` = integral de V dt. A leitura literal e geometrica do grafico de
  descarga que se ve nos artigos, com tensao no eixo y e tempo no x.
- `energia_Wh` = integral de |V.I| dt / 3600. Quanta energia a celula entregou.
  Captura queda de tensao e perda de carga no mesmo numero.

Em corrente constante as tres andam juntas, e `tensao_Vs` vira proporcional a
`energia_Wh`. Nas quatro baterias de carga pulsada (B0025-B0028) nao: a corrente
e onda quadrada de 0,05 Hz com 50% de duty, entao integrar a tensao ignora que
metade do tempo nao saiu corrente nenhuma. Por isso as tres ficam na tabela e o
ranking contra o SOH decide qual serve.

**A integracao e so no trecho sob carga.** Mesma convencao de correlacao_soh.py:
toda descarga termina com um rabo em repouso, corrente zero e tensao subindo de
volta. Integrar isso soma area de bateria descansando, o que infla `tensao_Vs`
sem corresponder a energia entregue nenhuma.

**Duas correntes.** `Current_measured` e a corrente da celula e `Current_load` e
a da carga; elas diferem por perdas e pelo transitorio inicial. A integral sai
nas duas versoes porque a comparacao contra o `Capacity` da NASA, no passo
seguinte, precisa saber qual delas a NASA usou.

**Duas janelas, e essa e a parte que importa.** Cada bateria tem seu proprio
corte de descarga, de 2.0 a 2.7 V. Integrar ate o corte de cada uma produz
areas que **nao se comparam**: uma celula cortada em 2.0 V descarrega bem mais
fundo que uma cortada em 2.7 V, e a diferenca e protocolo, nao saude. E o
mesmo erro que o projeto ja evita ao normalizar a capacidade dentro da
condicao, so que num eixo que `test_condition` nao registra.

Entao cada area sai duas vezes: `carga_Ah` integra o trecho sob carga inteiro,
ate o corte da propria celula, e `carga_Ah_comum` para em PISO_COMUM volts,
igual para todas. So a segunda se compara entre celulas.

O piso de 2.7 V nao foi escolhido a esmo: e o que o proprio dataset usa.
Integrando ate o corte de cada celula, a carga diverge do campo `Capacity` da
NASA em mais de 5% num terco das descargas; integrando ate 2.7 V, a divergencia
cai para 7,8% dos casos e a mediana vai a -0,32%. Ou seja, o `Capacity` da NASA
ja e medido numa janela comum de ~2.7 V, e nao no corte de cada celula — o que
tambem quer dizer que o SOH do projeto, derivado dele, ja esta numa base
comparavel. 2.7 V e ainda o maior corte entre as 34 baterias, o unico piso que
todas alcancam.

**A curva reamostrada.** As colunas `v00`..`v49` sao a tensao em 50 pontos de
tempo normalizado (0 = inicio da carga, 1 = fim). Normalizar o tempo separa a
**forma** da descarga da sua duracao: e o que permite comparar uma descarga de
6.400 s a 1 A com uma de 240 s a 4 A pelo formato, sem que a diferenca de
duracao domine tudo. E a materia-prima do agrupamento por comportamento.

Dependencias: numpy, pandas
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# A raiz do projeto e a pasta acima de src/: e la que ficam
# cleaned_nasa_dataset/ e saida_nasa/.
RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "cleaned_nasa_dataset"
SAIDA = RAIZ / "saida_nasa" / "curvas"

N_REAMOSTRA = 50           # pontos da curva de tensao em tempo normalizado
MIN_PONTOS_CARGA = 5       # abaixo disso a descarga nao rende agregacao
LIMIAR_CARGA = 0.1         # A; define o trecho sob carga em Current_load

# Piso comum de tensao para a janela comparavel. E 2.7 V porque esse e o maior
# corte entre as 34 baterias: qualquer piso mais baixo ficaria fora do alcance
# das celulas cortadas em 2.7 V, e a area delas nao existiria. Ver a docstring.
PISO_COMUM = 2.7


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
    if not (RAIZ / "saida_nasa" / "metricas_descargas.csv").exists():
        p("ERRO: saida_nasa/metricas_descargas.csv nao existe.")
        p("    Rode antes: python graficos_nasa.py")
        sys.exit(1)
    if not DADOS.exists():
        p(f"ERRO: {DADOS.name}/ nao existe. Rode antes: python preparar_dados.py")
        sys.exit(1)
    return mods


def integrar(np, y, t):
    """Trapezio, tolerante ao numpy 2.x (np.trapz virou np.trapezoid)."""
    f = getattr(np, "trapezoid", None) or np.trapz
    return float(f(y, t))


def extrair(c, np):
    """Uma curva de descarga -> areas e descritores de forma.

    Devolve {} quando a curva nao tem trecho sob carga utilizavel: acontece em
    B0041 a 4 A / 4 C, onde a descarga termina antes de render 5 pontos.
    """
    il = np.abs(c.Current_load.to_numpy(float))
    carga = il > LIMIAR_CARGA
    if carga.sum() < MIN_PONTOS_CARGA:
        return {}
    k0 = int(carga.argmax())
    k1 = int(len(carga) - 1 - carga[::-1].argmax())
    faixa = slice(k0, k1 + 1)

    t = c.Time.to_numpy(float)[faixa]
    v = c.Voltage_measured.to_numpy(float)[faixa]
    im = np.abs(c.Current_measured.to_numpy(float)[faixa])
    ilo = np.abs(c.Current_load.to_numpy(float)[faixa])
    temp = c.Temperature_measured.to_numpy(float)[faixa]

    dur = float(t[-1] - t[0])
    if dur <= 0:
        return {}

    # As tres areas. A carga sai nas duas correntes: o passo seguinte precisa
    # saber qual delas reproduz o Capacity da NASA.
    r = {
        "carga_Ah": integrar(np, im, t) / 3600.0,
        "carga_load_Ah": integrar(np, ilo, t) / 3600.0,
        "tensao_Vs": integrar(np, v, t),
        "energia_Wh": integrar(np, v * im, t) / 3600.0,
        "duracao_s": dur,
        "n_pontos": int(k1 - k0 + 1),
    }

    # As mesmas tres areas na janela comum, ate PISO_COMUM volts. Sem isso as
    # areas nao se comparam entre celulas: uma cortada em 2.0 V descarrega bem
    # mais fundo que uma cortada em 2.7 V, e a diferenca e protocolo, nao saude.
    abaixo = np.where(v <= PISO_COMUM)[0]
    kp = int(abaixo[0]) if len(abaixo) else len(v) - 1
    if kp >= 1:
        tp, vp, ip = t[:kp + 1], v[:kp + 1], im[:kp + 1]
        r["carga_Ah_comum"] = integrar(np, ip, tp) / 3600.0
        r["tensao_Vs_comum"] = integrar(np, vp, tp)
        r["energia_Wh_comum"] = integrar(np, vp * ip, tp) / 3600.0
        r["duracao_s_comum"] = float(tp[-1] - tp[0])
        # Falso quando a celula nunca chega ao piso: a janela comum ficou
        # truncada no fim da descarga e a area nao e comparavel as demais.
        r["atingiu_piso"] = bool(len(abaixo))
    else:
        for c in ("carga_Ah_comum", "tensao_Vs_comum", "energia_Wh_comum",
                  "duracao_s_comum"):
            r[c] = float("nan")
        r["atingiu_piso"] = False

    # Forma da descarga, em grandezas que um engenheiro le direto.
    r["V_inicial"] = float(v[0])
    # V_final_carga, e nao V_final: metricas_descargas.csv ja tem um V_final que
    # e a ultima tensao do ensaio inteiro, medida depois do rabo em repouso e
    # portanto ja recuperada. Este aqui e o fim do trecho sob carga, que e outra
    # grandeza. Nomes iguais colidiriam no merge e virariam V_final_x/_y.
    r["V_final_carga"] = float(v[-1])
    r["V_medio"] = float(v.mean())
    r["queda_V"] = float(v[0] - v[-1])
    r["I_medio"] = float(im.mean())
    r["T_inicial"] = float(temp[0])
    r["T_max"] = float(temp.max())
    r["T_subida"] = float(temp.max() - temp[0])

    # Inclinacao media da descarga, em mV/min: o quanto a tensao cede por minuto
    # sob carga. Em regimes severos ela e varias vezes maior.
    r["inclinacao_mV_min"] = float((v[-1] - v[0]) / dur * 1000.0 * 60.0)

    # Tensao normalizada por tempo normalizado: a forma, sem a duracao.
    tn = (t - t[0]) / dur
    grade = np.linspace(0.0, 1.0, N_REAMOSTRA)
    vq = np.interp(grade, tn, v)
    for i, val in enumerate(vq):
        r[f"v{i:02d}"] = float(val)

    # Energia acumulada a meio caminho: distingue curva que despenca cedo de
    # curva que segura o plato e cai no fim. Duas descargas com a mesma area
    # total podem ter perfis opostos, e esse numero separa os dois casos.
    meio = len(t) // 2
    if meio > 1:
        e_meio = integrar(np, (v * im)[:meio + 1], t[:meio + 1]) / 3600.0
        r["fracao_energia_1a_metade"] = (
            e_meio / r["energia_Wh"] if r["energia_Wh"] > 0 else float("nan"))
    else:
        r["fracao_energia_1a_metade"] = float("nan")
    return r


def montar(mods, remontar=False, amostra=None):
    np, pd = mods["numpy"], mods["pandas"]
    cache = SAIDA / "features_curvas.csv"
    if cache.exists() and not remontar and amostra is None:
        p(f"  cache: {cache.relative_to(RAIZ)}")
        return pd.read_csv(cache)

    # metricas_descargas.csv ja traz condicao, ciclo e SoH por descarga: e a
    # espinha da tabela, e daqui so acrescentamos o que exige ler a curva.
    m = pd.read_csv(RAIZ / "saida_nasa" / "metricas_descargas.csv")
    if amostra:
        m = m.head(amostra)
    p(f"  lendo {len(m)} curvas de descarga...")

    linhas, vazias = [], 0
    for i, lin in enumerate(m.itertuples(index=False), 1):
        if i % 250 == 0:
            p(f"    {i}/{len(m)}")
        arq = DADOS / "data" / lin.filename
        if not arq.exists():
            vazias += 1
            continue
        f = extrair(pd.read_csv(arq), np)
        if not f:
            vazias += 1
            continue
        f["filename"] = lin.filename
        linhas.append(f)

    feats = pd.DataFrame(linhas)
    df = m.merge(feats, on="filename", how="left",
                 suffixes=("_metricas", "_curva"))
    if vazias:
        p(f"  {vazias} curvas sem trecho sob carga utilizavel (sem features)")

    SAIDA.mkdir(parents=True, exist_ok=True)
    if amostra is None:
        df.to_csv(cache, index=False)
        p(f"  {cache.relative_to(RAIZ)}  ({len(df)} x {df.shape[1]})")
    return df


def resumir(mods, df):
    """Confere as areas contra o Capacity da NASA e resume por condicao."""
    pd = mods["pandas"]
    ok = df[df.carga_Ah.notna()]
    p("")
    p(f"  descargas com features: {len(ok)} de {len(df)}")

    val = ok[ok.Capacity.notna() & (ok.Capacity > 0)]
    if len(val):
        for col in ("carga_Ah", "carga_load_Ah"):
            erro = (val[col] - val.Capacity) / val.Capacity * 100.0
            p(f"  {col} vs Capacity da NASA: erro mediano {erro.median():+.2f}%"
              f"  (p10 {erro.quantile(.1):+.2f}%, p90 {erro.quantile(.9):+.2f}%)")

    g = ok.groupby("condicao").agg(
        descargas=("carga_Ah", "size"),
        carga_Ah=("carga_Ah", "median"),
        energia_Wh=("energia_Wh", "median"),
        tensao_Vs=("tensao_Vs", "median"),
        duracao_min=("duracao_s", lambda s: s.median() / 60.0),
    ).sort_values("descargas", ascending=False)
    p("")
    p("  medianas por condicao nominal:")
    for lin in g.reset_index().itertuples(index=False):
        p(f"    {lin.condicao:<14} n={lin.descargas:>4}  "
          f"{lin.carga_Ah:>6.3f} Ah  {lin.energia_Wh:>6.3f} Wh  "
          f"{lin.tensao_Vs:>8.0f} V.s  {lin.duracao_min:>6.1f} min")
    g.to_csv(SAIDA / "resumo_areas_por_condicao.csv")
    p(f"\n  {(SAIDA / 'resumo_areas_por_condicao.csv').relative_to(RAIZ)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--remontar", action="store_true",
                    help="ignora o cache e rele as curvas")
    ap.add_argument("--amostra", type=int, default=None,
                    help="le so as N primeiras descargas (teste rapido)")
    a = ap.parse_args()

    mods = checar()
    p("Areas sob a curva de descarga e descritores de forma")
    p("=" * 60)
    df = montar(mods, remontar=a.remontar, amostra=a.amostra)
    resumir(mods, df)


if __name__ == "__main__":
    main()
