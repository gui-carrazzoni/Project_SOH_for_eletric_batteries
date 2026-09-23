#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Roda a cadeia inteira, pulando o que ja esta feito.

    python main.py                  # roda o que falta
    python main.py --listar         # so mostra o estado de cada etapa
    python main.py --forcar         # refaz tudo (menos o download)
    python main.py --refazer curvas # refaz essa etapa e todas as seguintes
    python main.py --so carga       # roda so essa etapa

**Como ele decide o que ja foi feito.** Cada etapa declara um arquivo-alvo: se
ele existe, a etapa esta feita. Nao e data de modificacao — e existencia, que e
o criterio que nao mente quando os relogios do sistema de arquivos discordam.

**Uma etapa que roda dispara todas as seguintes.** Se `curvas.py` precisou
rodar, o cache que ele deixa mudou, e `grupos.py`, `capacidade.py` e os demais
estao trabalhando sobre dado velho. Pular por "o arquivo existe" nesse caso
produziria uma saida internamente inconsistente, que e o pior resultado
possivel — pior que refazer. Por isso a cascata.

**Quando uma etapa e refeita e nao apenas rodada pela primeira vez**, ela recebe
o proprio argumento de invalidacao (`--remontar` nos tres scripts que tem cache
em disco). Sem isso, `curvas.py` releria o cache e a cascata nao serviria para
nada.

**O download fica de fora da cascata.** `preparar_dados.py` baixa 586 MB da
NASA e so roda se `cleaned_nasa_dataset/` nao existir — nem `--forcar` o
dispara. Para refazer o download, chame o script direto:

    python src/preparar_dados.py --forcar

Dependencias: nenhuma alem da biblioteca padrao. Cada etapa roda como processo
proprio, entao os argparse de cada script continuam valendo quando chamados a
mao.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
SRC = RAIZ / "src"

# nome, script, argumentos, alvo que prova que rodou, argumento de invalidacao
ETAPAS = [
    ("preparar_dados", "preparar_dados.py", [],
     "cleaned_nasa_dataset/metadata.csv", [],
     "baixa da NASA e reconstroi o dataset limpo"),
    ("graficos_nasa", "graficos_nasa.py", [],
     "saida_nasa/metricas_descargas.csv", [],
     "metricas por ensaio e os sete graficos gerais"),
    ("correlacao_soh", "correlacao_soh.py", [],
     "saida_nasa/correlacao/tabela_modelagem.csv", ["--remontar"],
     "tabela da Tabela 2 e relevancia dos atributos"),
    ("limpeza", "limpeza.py", [],
     "saida_nasa/preprocessado/dados_modelagem.csv", [],
     "limpeza, faltantes e redundancia"),
    ("descritiva", "descritiva.py", [],
     "saida_nasa/descritiva/estatisticas_numericas.csv", [],
     "analise descritiva: distribuicoes e graficos"),
    ("normalizar", "normalizar.py", [],
     "saida_nasa/normalizado/dados_normalizados.csv", [],
     "divisao por bateria, referencia de vida e escala"),
    ("curvas", "curvas.py", [],
     "saida_nasa/curvas/features_curvas.csv", ["--remontar"],
     "areas sob a curva e forma da descarga"),
    ("grupos", "grupos.py", ["--grupos", "5"],
     "saida_nasa/cluster/agrupamento/grupos_comportamento.csv", [],
     "agrupamento por comportamento medido"),
    ("capacidade", "capacidade.py", [],
     "saida_nasa/cluster/grupo_corrente_temperatura/capacidade/resumo_por_grupo.csv", [],
     "capacidade por ciclo e taxa de fade, nos dois esquemas"),
    ("modelos_area", "modelos_area.py", [],
     "saida_nasa/cluster/grupo_corrente_temperatura/modelos_area/carga/vencedores.csv", [],
     "modelos para a area ao longo dos ciclos"),
    ("comparacao", "comparacao.py", [],
     "saida_nasa/cluster/comparacao/visao_geral.csv", [],
     "confronta os dois esquemas de grupo"),
    ("mapa_calor", "mapa_calor.py", [],
     "saida_nasa/curvas/correlacao/ranking_vs_soh.csv", [],
     "mapa de calor com as areas e a forma"),
    ("carga", "carga.py", [],
     "saida_nasa/carga/features_carga.csv", ["--remontar"],
     "a carga como processo proprio"),
]

NOMES = [e[0] for e in ETAPAS]


def p(msg: str = "") -> None:
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "ascii"
        print(msg.encode(enc, "replace").decode(enc), flush=True)
    except BrokenPipeError:
        # `python main.py --listar | head` fecha o pipe no meio da lista. Sair
        # calado e o comportamento certo; o traceback padrao so polui a tela.
        try:
            sys.stdout.close()
        except BrokenPipeError:
            pass
        sys.exit(0)


def duracao(seg: float) -> str:
    return f"{seg:.0f}s" if seg < 60 else f"{seg / 60:.1f}min"


def listar() -> None:
    p("Etapas da cadeia")
    p("=" * 72)
    p(f"  {'#':<3} {'etapa':<16} {'estado':<10} o que faz")
    for i, (nome, _s, _a, alvo, _f, desc) in enumerate(ETAPAS, 1):
        estado = "feito" if (RAIZ / alvo).exists() else "pendente"
        p(f"  {i:<3} {nome:<16} {estado:<10} {desc}")
    p("")
    p("  'feito' quer dizer que o arquivo-alvo da etapa existe. Para ver qual:")
    p("      python main.py --listar --alvos")


def listar_alvos() -> None:
    p("")
    p("  alvos:")
    for nome, _s, _a, alvo, _f, _d in ETAPAS:
        marca = "ok  " if (RAIZ / alvo).exists() else "--  "
        p(f"    {marca}{nome:<16} {alvo}")


def rodar(nome, script, args, refazendo) -> bool:
    """Chama um script como processo proprio. Devolve True se deu certo."""
    cmd = [sys.executable, str(SRC / script), *args]
    rotulo = "refazendo" if refazendo else "rodando"
    p("")
    p("-" * 72)
    p(f"  {rotulo}: {nome}   ({' '.join(cmd[1:])})")
    p("-" * 72)
    t0 = time.time()
    r = subprocess.run(cmd, cwd=RAIZ)
    dt = time.time() - t0
    if r.returncode != 0:
        p("")
        p(f"  FALHOU: {nome} terminou com codigo {r.returncode} depois de {duracao(dt)}")
        return False
    p(f"  {nome} ok em {duracao(dt)}")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__.split("\n")[1],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--listar", action="store_true",
                    help="mostra o estado de cada etapa e sai")
    ap.add_argument("--alvos", action="store_true",
                    help="com --listar, mostra tambem o arquivo-alvo de cada etapa")
    ap.add_argument("--forcar", action="store_true",
                    help="refaz tudo, menos o download")
    ap.add_argument("--refazer", metavar="ETAPA", choices=NOMES,
                    help="refaz essa etapa e todas as seguintes")
    ap.add_argument("--so", metavar="ETAPA", choices=NOMES,
                    help="roda so essa etapa, independente do estado")
    a = ap.parse_args()

    if a.listar:
        listar()
        if a.alvos:
            listar_alvos()
        return 0

    if not SRC.exists():
        p(f"ERRO: {SRC.name}/ nao existe. Os scripts deveriam estar ali.")
        return 1

    p("Cadeia de analise do SoH")
    p("=" * 72)

    if a.so:
        nome, script, args, alvo, forcar_args, _d = ETAPAS[NOMES.index(a.so)]
        extra = forcar_args if (RAIZ / alvo).exists() else []
        return 0 if rodar(nome, script, args + extra, bool(extra)) else 1

    inicio = NOMES.index(a.refazer) if a.refazer else len(ETAPAS)
    disparado = False
    feitos, pulados = [], []
    t0 = time.time()

    for i, (nome, script, args, alvo, forcar_args, _d) in enumerate(ETAPAS):
        existe = (RAIZ / alvo).exists()

        # O download nunca entra na cascata: 586 MB nao se refazem por engano.
        if nome == "preparar_dados":
            if existe:
                pulados.append(nome)
                continue
            if not rodar(nome, script, args, False):
                return 1
            feitos.append(nome)
            disparado = True
            continue

        refazer = a.forcar or disparado or i >= inicio
        if existe and not refazer:
            pulados.append(nome)
            continue

        extra = forcar_args if existe else []
        if not rodar(nome, script, args + extra, existe):
            return 1
        feitos.append(nome)
        disparado = True

    p("")
    p("=" * 72)
    if pulados:
        p(f"  pulados ({len(pulados)}, ja estavam feitos): {', '.join(pulados)}")
    if feitos:
        p(f"  rodados ({len(feitos)}): {', '.join(feitos)}")
    else:
        p("  nada a fazer: a cadeia inteira ja estava feita.")
        p("  Use --forcar para refazer, ou --refazer <etapa> a partir de um ponto.")
    p(f"  tempo total: {duracao(time.time() - t0)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
