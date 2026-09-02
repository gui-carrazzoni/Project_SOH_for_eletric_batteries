# Project_SOH_for_eletric_batteries

Estimativa de estado de saúde (SoH) de baterias de íon-lítio a partir de dois
conjuntos públicos de dados de envelhecimento: o **Oxford Battery Degradation
Dataset 1** e o **NASA Li-ion Battery Aging Dataset**.

## Os dados não estão no repositório

São 1,6 GB de dados públicos. O repositório guarda o código que os obtém e os
prepara — não os dados em si:

| | tamanho | por quê não versionar |
|---|---|---|
| `Oxford_..._Dataset_1.mat` | 266 MB | acima do limite de 100 MB por arquivo do GitHub |
| `cleaned_nasa_dataset/` | 586 MB em 7.575 arquivos | público, e reconstruível bit a bit |
| `saida_oxford/` | 833 MB | saída gerada; o conversor a refaz em ~1 min |

## Como começar

```bash
python -m venv venv

# Linux / macOS
source venv/bin/activate
# Windows (PowerShell)
venv\Scripts\Activate.ps1

python -m pip install -r requirements.txt

python preparar_dados.py        # baixa e prepara os dois datasets (~10 min)
python converter_oxford_mat.py  # gera saida_oxford/ (planilha, CSVs e gráficos)
```

## `preparar_dados.py`

```bash
python preparar_dados.py              # os dois datasets
python preparar_dados.py --oxford     # só o .mat do Oxford
python preparar_dados.py --nasa       # só os CSVs limpos da NASA
python preparar_dados.py --verificar  # não baixa nada; confere o que já existe
python preparar_dados.py --forcar     # refaz mesmo se já estiver na pasta
```

O download é retomável: se cair no meio, rode de novo.

### O NASA é reconstruído, não baixado pronto

O script baixa os 34 arquivos `.mat` originais da NASA e refaz a limpeza —
um CSV por ensaio, mais `metadata.csv` e `extra_infos/`. O resultado é
**idêntico byte a byte** ao dataset limpo usado no projeto, e o script prova
isso a cada execução conferindo os 7.575 arquivos contra
`manifesto_nasa.csv.gz` (337 KB, versionado).

Três detalhes do dado original que a reconstrução precisa respeitar, e que
valem como aviso para quem for analisar:

- **18 dos 4.080 valores de `Re`/`Rct` são complexos**, com parte imaginária de
  até 0,039 — comparável ao próprio valor. Tratar a coluna como float perde
  informação real.
- **19 dos 2.794 `Capacity` são inteiro zero**, e não 0.0: são medições que
  falharam, não capacidade nula medida.
- **25 `Capacity` são `[]`** (array vazio), diferente de célula em branco — o
  ensaio existiu mas não produziu o valor.

A ordem das baterias que define a numeração `uid` é arbitrária (herdada da
listagem de diretório de quem fez a limpeza original). Ela está registrada em
`ORDEM_BATERIAS`, dentro do script: 34 nomes no lugar de 586 MB.

## `converter_oxford_mat.py`

Converte o `.mat` do Oxford em planilha Excel, CSVs e gráficos, com controle de
qualidade das medições. Documentação completa em [COMO_USAR.md](COMO_USAR.md).

## Fontes e licenças

| dataset | fonte | licença |
|---|---|---|
| Oxford Battery Degradation Dataset 1 | [ORA, DOI 10.5287/bodleian:KO2kdmYGg](https://ora.ox.ac.uk/objects/uuid:03ba4b01-cfed-46d3-9b1a-7d4a7bdf6fac) | ODC Open Database License (ODbL) |
| NASA Li-ion Battery Aging Dataset | [NASA PCoE Data Repository](https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/) | domínio público (obra do governo dos EUA) |

Citações:

> Howey, D., & Birkl, C. (2017). *Oxford Battery Degradation Dataset 1*.
> University of Oxford.

> Saha, B., & Goebel, K. (2007). *Battery Data Set*. NASA Ames Prognostics Data
> Repository, NASA Ames Research Center.
