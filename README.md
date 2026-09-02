# Project_SOH_for_eletric_batteries

Estimativa de estado de saúde (SoH) de baterias de íon-lítio a partir do **NASA
Li-ion Battery Aging Dataset**: 34 células, 7.565 ensaios de carga, descarga e
espectroscopia de impedância.

## Os dados não estão no repositório

São 586 MB em 7.575 arquivos, públicos e reconstruíveis bit a bit. O repositório
guarda o código que os obtém e os prepara — não os dados.

## Como começar

```bash
python -m venv venv

# Linux / macOS
source venv/bin/activate
# Windows (PowerShell)
venv\Scripts\Activate.ps1

python -m pip install -r requirements.txt

python preparar_dados.py    # baixa da NASA e reconstrói (~5 min)
python graficos_nasa.py     # gera saida_nasa/ com métricas e gráficos (~1 min)
```

## `preparar_dados.py`

```bash
python preparar_dados.py                     # baixa e prepara
python preparar_dados.py --verificar         # não baixa; confere o que já existe
python preparar_dados.py --gerar-manifesto   # (re)cria o manifesto de verificação
python preparar_dados.py --forcar            # refaz mesmo se já estiver na pasta
```

O download é retomável: se cair no meio, rode de novo.

### Os CSVs são reconstruídos, não baixados prontos

O script baixa os 34 arquivos `.mat` originais da NASA e refaz a limpeza — um
CSV por ensaio, mais `metadata.csv` e `extra_infos/`. O resultado é **idêntico
byte a byte** ao dataset limpo usado no projeto, e o script prova isso a cada
execução conferindo os 7.575 arquivos contra `manifesto_nasa.csv.gz`.

Esse manifesto é a única parte dos dados que fica versionada: uma tabela com o
caminho, o tamanho e o `sha256` de cada arquivo. Não contém dado nenhum — só as
impressões digitais, em 337 KB no lugar de 586 MB. **Sem ele a verificação não
roda**, e o script avisa em vez de fingir que passou.

A ordem das baterias que define a numeração `uid` é arbitrária, herdada da
listagem de diretório de quem fez a limpeza original. Está registrada em
`ORDEM_BATERIAS`, dentro do script: 34 nomes no lugar de 586 MB.

## `graficos_nasa.py`

Gera `saida_nasa/` com três tabelas de métricas e sete gráficos:

| | |
|---|---|
| `metricas_descargas.csv` | uma linha por descarga: condição, capacidade, SoH, duração, tensão final, temperatura máxima |
| `metricas_impedancia.csv` | uma linha por ensaio de impedância: Re, Rct, SoH da descarga mais próxima |
| `resumo_baterias.csv` | uma linha por bateria, incluindo a correlação entre resistência e SoH |
| `graficos/01…07` | capacidade por condição, SoH, efeito da condição, resistência, predição de SoH, curvas de descarga, espectro |

## O que os dados exigem cuidado

**A capacidade só é comparável dentro da mesma condição de ensaio.** A mesma
célula a 4 A entrega 1,42 Ah a 24 °C e **0,06 Ah a 4 °C** — 23 vezes menos. São
11 combinações de corrente × temperatura no dataset, e 9 das 34 baterias mudam
de condição no meio da vida. Plotar capacidade contra ciclo sem separar por
condição produz um degrau que parece morte súbita e é troca de protocolo. Por
isso o SoH aqui é normalizado pela capacidade máxima da bateria **naquela
condição**, e o eixo x conta ciclos dentro da condição.

**Normalizar pelo primeiro ciclo não funciona neste dataset.** Várias baterias
começam com uma descarga que não mede a capacidade cheia, o que produziria SoH
de até 1.900%.

**A impedância prevê o SoH, mas só dentro da mesma célula.** Juntando as 34, a
correlação entre `Re` e SoH é de apenas −0,17. Nas três células com histórico
longo, tomadas uma a uma, é de **−0,87 a −0,95**. Cada célula tem seu próprio
nível de resistência, então um modelo de SoH por impedância precisa de
calibração por célula.

**Ruído que precisa ser filtrado:**

- **14 dos 1.956** ensaios de impedância têm `Re`/`Rct` fisicamente impossíveis,
  chegando a 10¹⁵ Ω (a mediana é 0,07 Ω). Concentram-se em B0050 e B0052.
- **44 descargas** têm capacidade ausente ou exatamente zero.
- **18 dos 4.080** valores de `Re`/`Rct` são complexos, com parte imaginária de
  até 0,039 — comparável ao próprio valor. Ler a coluna como float perde
  informação real.
- **19 `Capacity` são inteiro `0`** (medição que falhou), e **25 são `[]`**
  (array vazio) — diferente de célula em branco.

As marcações ficam na coluna `alerta` das tabelas de métricas. Nada é apagado.

## Fonte e licença

[NASA PCoE Data Repository](https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/) — domínio público (obra do governo dos EUA).

> Saha, B., & Goebel, K. (2007). *Battery Data Set*. NASA Ames Prognostics Data
> Repository, NASA Ames Research Center.
