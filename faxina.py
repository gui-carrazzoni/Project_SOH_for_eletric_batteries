#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Remove de saida_nasa/ as sobras do layout antigo.

    python faxina.py            # apaga as copias e as versoes antigas
    python faxina.py --orfaos   # apaga tambem o que nao tem par

**O que e sobra.** No layout atual, todo arquivo de saida_nasa/ mora numa pasta
`figuras/` ou `tabelas/`. O layout antigo gravava direto na pasta da etapa
(`carga/features_carga.csv`), com os graficos gerais em `graficos/` e as
metricas soltas na raiz de saida_nasa/. Como `main.py` decide pelo arquivo-alvo
do layout novo, ele refaz tudo no lugar novo e deixa o antigo para tras.

**Cada sobra cai em uma de tres classes**, pelo arquivo que a substitui no
layout novo (mesma pasta + `tabelas/` ou `figuras/`, com `graficos/` e a raiz
remapeadas para `geral/`):

    copia    o par existe e e identico byte a byte
    antiga   o par existe mas difere: e a versao que o codigo atual refez
    orfa     nao ha par: saida que o codigo atual nao produz mais, ou etapa
             que ainda nao rodou no layout novo

As duas primeiras sempre saem, porque o conteudo delas esta garantido no lugar
novo. A orfa so sai com `--orfaos`: se a etapa ainda nao rodou, rode
`python main.py` antes, e ela vira copia ou antiga.

Pastas que ficarem vazias depois da faxina tambem saem. Dependencias: nenhuma
alem da biblioteca padrao.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
SAIDA = RAIZ / "saida_nasa"
LAYOUT = {"figuras", "tabelas"}

# pasta do layout antigo -> pasta que a substituiu. "" e a raiz de saida_nasa/.
RENOMEADAS = {"": "geral", "graficos": "geral"}


def p(msg: str = "") -> None:
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "ascii"
        print(msg.encode(enc, "replace").decode(enc), flush=True)
    except BrokenPipeError:
        try:
            sys.stdout.close()
        except BrokenPipeError:
            pass
        sys.exit(0)


def tamanho(n: float) -> str:
    for un in ("B", "KB", "MB"):
        if n < 1024:
            return f"{n:.0f} {un}"
        n /= 1024
    return f"{n:.1f} GB"


def fora_do_layout() -> list[Path]:
    """Arquivos de saida_nasa/ que nao estao sob figuras/ nem tabelas/."""
    if not SAIDA.exists():
        return []
    return sorted(f for f in SAIDA.rglob("*")
                  if f.is_file() and not LAYOUT & set(f.relative_to(SAIDA).parts[:-1]))


def resumo(f: Path) -> str:
    h = hashlib.sha256()
    with open(f, "rb") as arq:
        for bloco in iter(lambda: arq.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def par(f: Path) -> Path | None:
    """O arquivo que substitui f no layout novo, se existir."""
    pasta = f.parent.relative_to(SAIDA).as_posix()
    pasta = SAIDA / RENOMEADAS.get("" if pasta == "." else pasta, pasta)
    for sub in ("tabelas", "figuras"):
        if (pasta / sub / f.name).exists():
            return pasta / sub / f.name
    return None


def classificar(sobras: list[Path]) -> dict[str, list[tuple[Path, Path | None]]]:
    classes = {"copia": [], "antiga": [], "orfa": []}
    for f in sobras:
        novo = par(f)
        if novo is None:
            classes["orfa"].append((f, None))
        elif resumo(f) == resumo(novo):
            classes["copia"].append((f, novo))
        else:
            classes["antiga"].append((f, novo))
    return classes


def pastas_vazias() -> list[Path]:
    """De baixo para cima, para que a pasta-mae esvazie depois das filhas."""
    vazias = []
    for d in sorted((d for d in SAIDA.rglob("*") if d.is_dir()),
                    key=lambda d: len(d.parts), reverse=True):
        if all(c in vazias for c in d.iterdir()):
            vazias.append(d)
    return vazias


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__.split("\n")[1],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--orfaos", action="store_true",
                    help="apaga tambem as sobras sem par no layout novo")
    ap.add_argument("--detalhar", action="store_true",
                    help="lista cada arquivo, nao so a contagem por pasta")
    a = ap.parse_args()

    p("Faxina de saida_nasa/")
    p("=" * 72)
    sobras = fora_do_layout()
    if not sobras:
        p("  nada a fazer: tudo ja esta em figuras/ ou tabelas/.")
        return 0

    classes = classificar(sobras)
    rotulos = {
        "copia": "copias identicas ao arquivo do layout novo",
        "antiga": "versoes antigas de um arquivo que o layout novo refez",
        "orfa": "sem par no layout novo",
    }
    for classe, itens in classes.items():
        if not itens:
            continue
        total = sum(f.stat().st_size for f, _ in itens)
        p("")
        p(f"  {classe}: {len(itens)} arquivo(s), {tamanho(total)} — {rotulos[classe]}")
        if a.detalhar:
            for f, novo in itens:
                destino = f"  ->  {novo.relative_to(SAIDA)}" if novo else ""
                p(f"      {f.relative_to(SAIDA)}{destino}")
        else:
            por_pasta: dict[str, int] = {}
            for f, _ in itens:
                chave = f.parent.relative_to(SAIDA).as_posix()
                por_pasta[chave] = por_pasta.get(chave, 0) + 1
            for pasta, n in sorted(por_pasta.items()):
                p(f"      {n:>3}  saida_nasa/{'' if pasta == '.' else pasta + '/'}")

    alvo = classes["copia"] + classes["antiga"]
    if a.orfaos:
        alvo += classes["orfa"]

    p("")
    p("=" * 72)
    liberado = 0
    for f, _ in alvo:
        liberado += f.stat().st_size
        f.unlink()
    vazias = pastas_vazias()
    for d in vazias:
        d.rmdir()
    p(f"  apagados {len(alvo)} arquivo(s) ({tamanho(liberado)}) e {len(vazias)} pasta(s) vazia(s).")
    if classes["orfa"] and not a.orfaos:
        p(f"  ficaram {len(classes['orfa'])} orfa(s): rode python main.py antes e, se ainda")
        p("  sobrarem, use --orfaos para apaga-las tambem.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
