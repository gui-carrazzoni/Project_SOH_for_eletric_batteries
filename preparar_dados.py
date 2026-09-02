#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Baixa e prepara os dois datasets do projeto. Nenhum dado fica versionado no
repositorio: este script reconstroi tudo a partir das fontes oficiais.

    python preparar_dados.py              # baixa e prepara os dois
    python preparar_dados.py --oxford     # so o Oxford (.mat)
    python preparar_dados.py --nasa       # so o NASA (CSVs limpos)
    python preparar_dados.py --verificar  # so confere o que ja esta na pasta

O NASA e reconstruido a partir dos arquivos .mat originais da NASA e sai
identico byte a byte ao dataset limpo usado no projeto — a conferencia contra
manifesto_nasa.csv.gz prova isso a cada execucao.

Dependencias: numpy, scipy, pandas  (python -m pip install -r requirements.txt)
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

RAIZ = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Fontes oficiais
# ---------------------------------------------------------------------------
OXFORD = {
    "nome": "Oxford_Battery_Degradation_Dataset_1.mat",
    # Oxford Research Archive, DOI 10.5287/bodleian:KO2kdmYGg
    "url": "https://ora.ox.ac.uk/objects/uuid:03ba4b01-cfed-46d3-9b1a-7d4a7bdf6fac"
           "/files/m5ac36a1e2073852e4f1f7dee647909a7",
    "pagina": "https://ora.ox.ac.uk/objects/uuid:03ba4b01-cfed-46d3-9b1a-7d4a7bdf6fac",
    "licenca": "ODC Open Database License (ODbL)",
    "citacao": "Howey, D., & Birkl, C. (2017). Oxford Battery Degradation "
               "Dataset 1. University of Oxford.",
    "mb": 266,
}

NASA = {
    "nome": "5. Battery Data Set.zip",
    # Espelho oficial do NASA Prognostics Center of Excellence (PCoE)
    "url": "https://phm-datasets.s3.amazonaws.com/NASA/5.+Battery+Data+Set.zip",
    "pagina": "https://www.nasa.gov/intelligent-systems-division/"
              "discovery-and-systems-health/pcoe/pcoe-data-set-repository/",
    "licenca": "Dominio publico (obra do governo dos EUA)",
    "citacao": "Saha, B., & Goebel, K. (2007). Battery Data Set. NASA Ames "
               "Prognostics Data Repository, NASA Ames Research Center.",
    "mb": 210,
}

# A numeracao uid do dataset limpo segue esta ordem de baterias, que veio da
# ordem de listagem de diretorio de quem fez a limpeza original. Nao ha regra
# que a derive, entao ela fica registrada aqui: 34 nomes no lugar de 586 MB.
ORDEM_BATERIAS = [
    "B0047", "B0045", "B0048", "B0046", "B0043", "B0032", "B0039", "B0040",
    "B0029", "B0028", "B0042", "B0034", "B0038", "B0033", "B0030", "B0041",
    "B0027", "B0044", "B0036", "B0025", "B0026", "B0031", "B0049", "B0050",
    "B0052", "B0051", "B0006", "B0005", "B0007", "B0018", "B0053", "B0054",
    "B0056", "B0055",
]

# Campos escalares do .mat que viram coluna do metadata em vez de coluna do CSV
ESCALARES = ("Capacity", "Re", "Rct")

# O README do primeiro zip nao tem numero no nome; os outros mantem o proprio.
README_SEM_NUMERO = ("1. BatteryAgingARC-FY08Q4", "README_05_06_07_18.txt")
README_IGNORADO = "2. BatteryAgingARC_25_26_27_28_P1"

DESTINO_NASA = RAIZ / "cleaned_nasa_dataset"
MANIFESTO = RAIZ / "manifesto_nasa.csv.gz"
CACHE = RAIZ / "dados_brutos"


# ---------------------------------------------------------------------------
def p(msg: str = "") -> None:
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "ascii"
        print(msg.encode(enc, "replace").decode(enc), flush=True)


def humano(n: float) -> str:
    for unidade in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024 or unidade == "GB":
            return f"{n:.1f} {unidade}"
        n /= 1024
    return f"{n:.1f} GB"


def checar_dependencias():
    faltando, mods = [], {}
    for nome, pacote in (("numpy", "numpy"), ("scipy", "scipy"), ("pandas", "pandas")):
        try:
            mods[nome] = __import__(nome)
        except ImportError:
            faltando.append(pacote)
    if faltando:
        p("ERRO: faltam dependencias: " + ", ".join(faltando))
        p(f"    {Path(sys.executable).name} -m pip install -r requirements.txt")
        p("")
        p("Se o sistema bloquear (externally-managed-environment), crie um venv:")
        p(f"    {Path(sys.executable).name} -m venv venv")
        p("    # Linux/macOS: source venv/bin/activate   # Windows: venv\\Scripts\\activate")
        p("    python -m pip install -r requirements.txt")
        sys.exit(1)
    return mods


# ---------------------------------------------------------------------------
# download com retomada
# ---------------------------------------------------------------------------
def baixar(url: str, destino: Path, esperado_mb: int) -> Path:
    """Baixa `url` para `destino`, retomando se o arquivo estiver pela metade."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_suffix(destino.suffix + ".parcial")
    ja = parcial.stat().st_size if parcial.exists() else 0

    cabecalhos = {"User-Agent": "preparar_dados.py"}
    if ja:
        cabecalhos["Range"] = f"bytes={ja}-"

    try:
        with urlopen(Request(url, headers=cabecalhos), timeout=60) as resposta:
            if ja:
                if resposta.status == 206:
                    p(f"  retomando de {humano(ja)}...")
                else:   # servidor ignorou o Range (o ORA e um deles)
                    p(f"  o servidor nao aceita retomada; recomecando do zero...")
                    ja = 0
            total = resposta.headers.get("Content-Length")
            total = int(total) + ja if total else esperado_mb * 1024 * 1024
            modo = "ab" if ja else "wb"
            baixado = ja
            with open(parcial, modo) as fh:
                while True:
                    bloco = resposta.read(1 << 20)
                    if not bloco:
                        break
                    fh.write(bloco)
                    baixado += len(bloco)
                    pct = baixado / total * 100 if total else 0
                    print(f"\r  {humano(baixado)} / ~{humano(total)}  ({pct:5.1f}%)",
                          end="", flush=True)
        print()
    except (HTTPError, URLError, TimeoutError) as e:
        p(f"\nERRO ao baixar: {e}")
        p(f"Baixe manualmente de {url}")
        p(f"e salve como {destino}")
        sys.exit(1)
    except KeyboardInterrupt:
        p(f"\nInterrompido. O que ja baixou fica em {parcial.name}; "
          "rode de novo para retomar.")
        sys.exit(130)

    parcial.replace(destino)
    return destino


# ---------------------------------------------------------------------------
# Oxford
# ---------------------------------------------------------------------------
def preparar_oxford(forcar: bool) -> None:
    destino = RAIZ / OXFORD["nome"]
    p("=" * 70)
    p("Oxford Battery Degradation Dataset 1")
    p("=" * 70)
    if destino.exists() and not forcar:
        p(f"  ja existe: {destino.name} ({humano(destino.stat().st_size)}) — pulando")
        p(f"  (use --forcar para baixar de novo)")
        return
    p(f"  fonte  : {OXFORD['pagina']}")
    p(f"  licenca: {OXFORD['licenca']}")
    p(f"  baixando ~{OXFORD['mb']} MB...")
    baixar(OXFORD["url"], destino, OXFORD["mb"])
    p(f"  pronto: {destino.name} ({humano(destino.stat().st_size)})")
    p(f"  agora rode: python converter_oxford_mat.py")


# ---------------------------------------------------------------------------
# NASA
# ---------------------------------------------------------------------------
def extrair_nasa(zip_externo: Path, para: Path) -> Path:
    """O zip da NASA contem outros zips; extrai cada um em sua propria pasta."""
    para.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_externo) as z:
        z.extractall(para)
    internos = sorted(para.rglob("*.zip"))
    for interno in internos:
        alvo = interno.parent / interno.stem
        alvo.mkdir(exist_ok=True)
        with zipfile.ZipFile(interno) as z:
            z.extractall(alvo)
    mats = list(para.rglob("*.mat"))
    if not mats:
        p("ERRO: nenhum .mat encontrado dentro do zip da NASA.")
        sys.exit(1)
    return para


def escalar(valores):
    """Le um escalar do .mat preservando o tipo de cada valor.

    Dois casos exigem cuidado, os dois presentes no dataset:

    * 18 dos 4.080 Re/Rct sao complexos com parte imaginaria de verdade (ate
      0,039, comparavel ao proprio valor). Deixar o pandas inferir o tipo da
      coluna promoveria as 1.956 linhas de impedancia a complexo e escreveria
      "(0.056+0j)" em todas.
    * 19 dos 2.794 Capacity sao uint8 zero (medicao que falhou), e o dataset
      original os escreve como "0", nao "0.0".
    * 25 Capacity sao um array vazio (o ensaio nao produziu o valor), que o
      dataset original escreve como "[]" — diferente de uma celula em branco,
      que e o que aparece quando o campo nem existe naquele tipo de ensaio.

    Guardar como objeto mantem cada celula com o tipo que ela tem no .mat.
    """
    import numpy as np
    if not valores.size:
        return valores.ravel()      # str() de array vazio -> "[]"
    v = valores[0]
    if np.iscomplexobj(valores):
        return complex(v)
    if valores.dtype.kind in "iub":
        return int(v)
    return float(v)


def limpar_nasa(mods, pasta_extraida: Path, destino: Path) -> int:
    """Reproduz o dataset limpo: um CSV por ensaio + metadata.csv + extra_infos."""
    np, pd = mods["numpy"], mods["pandas"]
    import scipy.io as sio

    # B0025..B0028 aparecem em duas pastas do zip. As copias sao identicas, mas
    # nao se pode depender da ordem do sistema de arquivos para escolher: aqui a
    # escolha e a primeira em ordem alfabetica de caminho, e copias divergentes
    # param a execucao em vez de gerar um dataset diferente em cada maquina.
    candidatos: dict[str, list[Path]] = {}
    for caminho in sorted(pasta_extraida.rglob("*.mat")):
        candidatos.setdefault(caminho.stem, []).append(caminho)

    faltando = [b for b in ORDEM_BATERIAS if b not in candidatos]
    if faltando:
        p(f"ERRO: baterias ausentes no download: {', '.join(faltando)}")
        sys.exit(1)

    mats = {}
    for bateria in ORDEM_BATERIAS:
        copias = candidatos[bateria]
        if len(copias) > 1:
            digests = {sha256(c) for c in copias}
            if len(digests) > 1:
                p(f"ERRO: {bateria} tem copias diferentes no zip:")
                for c in copias:
                    p(f"    {c.relative_to(pasta_extraida)}")
                sys.exit(1)
        mats[bateria] = copias[0]

    dir_dados = destino / "data"
    if dir_dados.exists():
        shutil.rmtree(dir_dados)
    dir_dados.mkdir(parents=True)

    meta, uid = [], 1
    for i, bateria in enumerate(ORDEM_BATERIAS, 1):
        ciclos = sio.loadmat(str(mats[bateria]))[bateria][0, 0]["cycle"]
        for test_id in range(ciclos.shape[1]):
            c = ciclos[0, test_id]
            dados = c["data"][0, 0]
            colunas, extras = {}, {}
            for campo in dados.dtype.names:
                valores = np.asarray(dados[campo]).ravel()
                if campo in ESCALARES:
                    extras[campo] = escalar(valores)
                else:
                    colunas[campo] = pd.Series(valores)
            pd.DataFrame(colunas).to_csv(dir_dados / f"{uid:05d}.csv", index=False)
            meta.append({
                "type": str(c["type"][0]),
                "start_time": str(c["time"].ravel()),
                "ambient_temperature": int(np.asarray(c["ambient_temperature"]).ravel()[0]),
                "battery_id": bateria,
                "test_id": test_id,
                "uid": uid,
                "filename": f"{uid:05d}.csv",
                "Capacity": extras.get("Capacity"),
                "Re": extras.get("Re"),
                "Rct": extras.get("Rct"),
            })
            uid += 1
        print(f"\r  {i:2}/{len(ORDEM_BATERIAS)} baterias, {uid - 1:5} ensaios",
              end="", flush=True)
    print()

    # As colunas escalares vao como objeto para que cada celula conserve seu
    # proprio tipo (ver escalar()); as demais deixam o pandas inferir.
    tabela = pd.DataFrame({
        coluna: (pd.Series([linha[coluna] for linha in meta], dtype=object)
                 if coluna in ESCALARES else [linha[coluna] for linha in meta])
        for coluna in meta[0]
    })
    tabela.to_csv(destino / "metadata.csv", index=False)

    dir_infos = destino / "extra_infos"
    dir_infos.mkdir(exist_ok=True)
    for txt in sorted(pasta_extraida.rglob("*.txt")):
        pai = txt.parent.name
        if pai == README_IGNORADO:
            continue
        nome = README_SEM_NUMERO[1] if pai == README_SEM_NUMERO[0] else txt.name
        shutil.copyfile(txt, dir_infos / nome)

    return uid - 1


def preparar_nasa(mods, forcar: bool, manter_zip: bool) -> None:
    p("=" * 70)
    p("NASA Li-ion Battery Aging Dataset")
    p("=" * 70)
    if DESTINO_NASA.exists() and not forcar:
        p(f"  ja existe: {DESTINO_NASA.name}/ — pulando a reconstrucao")
        p(f"  (use --forcar para refazer)")
        return
    p(f"  fonte  : {NASA['pagina']}")
    p(f"  licenca: {NASA['licenca']}")

    zip_local = CACHE / NASA["nome"]
    if zip_local.exists():
        p(f"  zip ja baixado: {humano(zip_local.stat().st_size)}")
    else:
        p(f"  baixando ~{NASA['mb']} MB...")
        baixar(NASA["url"], zip_local, NASA["mb"])

    with tempfile.TemporaryDirectory(dir=str(CACHE)) as tmp:
        p("  extraindo zips aninhados...")
        extraida = extrair_nasa(zip_local, Path(tmp))
        p("  convertendo os .mat para CSV...")
        DESTINO_NASA.mkdir(parents=True, exist_ok=True)
        n = limpar_nasa(mods, extraida, DESTINO_NASA)
    p(f"  pronto: {n} ensaios em {DESTINO_NASA.name}/")

    if not manter_zip:
        zip_local.unlink(missing_ok=True)
        try:
            CACHE.rmdir()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# verificacao
# ---------------------------------------------------------------------------
def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as fh:
        for bloco in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def verificar_nasa() -> bool:
    """Confere a pasta contra manifesto_nasa.csv.gz, arquivo por arquivo."""
    p("=" * 70)
    p("Verificacao do dataset NASA")
    p("=" * 70)
    if not MANIFESTO.exists():
        p(f"  {MANIFESTO.name} nao encontrado — nada a verificar.")
        return True
    if not DESTINO_NASA.exists():
        p(f"  {DESTINO_NASA.name}/ nao existe. Rode: python preparar_dados.py --nasa")
        return False

    esperado = {}
    with gzip.open(MANIFESTO, "rt", encoding="utf-8") as fh:
        for linha in csv.DictReader(fh):
            esperado[linha["arquivo"]] = (int(linha["bytes"]), linha["sha256"])

    ok = divergentes = ausentes = 0
    problemas = []
    for i, (rel, (tam, h)) in enumerate(sorted(esperado.items()), 1):
        caminho = DESTINO_NASA / rel
        if not caminho.exists():
            ausentes += 1
            problemas.append(f"ausente: {rel}")
        elif caminho.stat().st_size != tam or sha256(caminho) != h:
            divergentes += 1
            problemas.append(f"diferente: {rel}")
        else:
            ok += 1
        if i % 500 == 0:
            print(f"\r  {i}/{len(esperado)} conferidos...", end="", flush=True)
    print(f"\r  {len(esperado)} arquivos conferidos.        ")

    extras = []
    for dirpath, _, arquivos in os.walk(DESTINO_NASA):
        for a in arquivos:
            rel = os.path.relpath(Path(dirpath) / a, DESTINO_NASA).replace(os.sep, "/")
            if rel not in esperado:
                extras.append(rel)

    p(f"  identicos  : {ok}")
    p(f"  diferentes : {divergentes}")
    p(f"  ausentes   : {ausentes}")
    p(f"  a mais     : {len(extras)}")
    for linha in (problemas + [f"a mais: {e}" for e in extras])[:10]:
        p(f"    {linha}")
    if len(problemas) + len(extras) > 10:
        p(f"    ... e mais {len(problemas) + len(extras) - 10}")

    bom = divergentes == 0 and ausentes == 0 and not extras
    p(f"  -> {'CONFERE com o manifesto' if bom else 'NAO confere com o manifesto'}")
    return bom


def verificar_oxford() -> bool:
    caminho = RAIZ / OXFORD["nome"]
    p("=" * 70)
    p("Verificacao do arquivo Oxford")
    p("=" * 70)
    if not caminho.exists():
        p(f"  {OXFORD['nome']} nao existe. Rode: python preparar_dados.py --oxford")
        return False
    tam = caminho.stat().st_size
    with open(caminho, "rb") as fh:
        cabecalho = fh.read(64)
    v5 = b"MATLAB 5.0 MAT-file" in cabecalho
    p(f"  {OXFORD['nome']}: {humano(tam)}, formato "
      f"{'MAT-file v5 (ok)' if v5 else 'NAO reconhecido'}")
    return v5


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description="Baixa e prepara os datasets do projeto a partir das fontes oficiais.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Sem argumentos, prepara os dois datasets.")
    ap.add_argument("--oxford", action="store_true", help="so o dataset Oxford (.mat)")
    ap.add_argument("--nasa", action="store_true", help="so o dataset NASA (CSVs limpos)")
    ap.add_argument("--verificar", action="store_true",
                    help="nao baixa nada; so confere o que ja esta na pasta")
    ap.add_argument("--forcar", action="store_true",
                    help="refaz mesmo se os dados ja estiverem la")
    ap.add_argument("--manter-zip", action="store_true",
                    help="nao apaga o zip da NASA depois de extrair (~210 MB)")
    args = ap.parse_args()

    if args.verificar:
        bom = verificar_oxford()
        bom = verificar_nasa() and bom
        sys.exit(0 if bom else 1)

    dois = not (args.oxford or args.nasa)
    mods = checar_dependencias() if (args.nasa or dois) else None

    if args.oxford or dois:
        preparar_oxford(args.forcar)
        p("")
    if args.nasa or dois:
        preparar_nasa(mods, args.forcar, args.manter_zip)
        p("")
        verificar_nasa()

    p("Concluido.")


if __name__ == "__main__":
    main()
