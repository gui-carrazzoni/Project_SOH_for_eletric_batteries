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
python correlacao_soh.py    # relevância dos atributos para o SoH (~10 s)
python limpeza.py           # limpeza, faltantes e redundância (~2 s)
python descritiva.py        # análise descritiva: distribuições e gráficos (~5 s)
python normalizar.py        # divisão, referência de vida e escala (~3 s)
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

## `correlacao_soh.py`

```bash
python correlacao_soh.py                # monta, correlaciona, plota
python correlacao_soh.py --sem-graficos  # so as tabelas
python correlacao_soh.py --remontar      # ignora o cache e rele as 2.794 curvas
```

Monta `saida_nasa/correlacao/tabela_modelagem.csv` **no esquema da Tabela 2 do
artigo** — uma coluna por variavel do dicionario de dados, sem acrescimo — e
correlaciona tudo contra `SOH`.

O dicionario do artigo mistura tres niveis de medicao: `voltage_measured` e por
instante (~490 linhas por ensaio), `capacity` e por descarga, e
`re`/`rct`/`rectified_impedance` sao por ensaio de impedancia. **Nenhuma linha do
dataset tem as tres juntas.** A tabela de modelagem tem que morar num nivel so, e
o nivel do alvo e a descarga — e ali que `SOH` existe. Entao cada coluna por
instante vira a media daquela descarga, e as de impedancia vem do ensaio mais
proximo da mesma bateria.

A media e tomada **so no trecho sob carga**: toda descarga termina com um rabo em
repouso, corrente zero e tensao subindo de volta, e incluir isso mede a bateria
descansando em vez de descarregando.

**`charge_type` e `discharge_type` nao sao colunas do dataset.** Estao em texto
corrido nos README de `extra_infos/`, um por grupo de baterias. A tabela
`PROTOCOLO`, no topo do script, transcreve os nove. `charge_type` e identico nas
34 (CC 1,5 A ate 4,2 V mais CV ate 20 mA); `discharge_type` traz perfil e corte
juntos, ex. `CC ate 2.5V`: o perfil separa as quatro de **carga pulsada** — B0025
a B0028, onda quadrada de 0,05 Hz e 50% de duty — das trinta de corrente
constante, e o corte vai de 2,0 a 2,7 V conforme a bateria. Numa coluna so porque
a Tabela 2 nao tem coluna de corte, e porque o corte e constante dentro da
bateria: como numero separado ele zera ao centrar e nao mede degradacao nenhuma.

`dicionario_tabela2.csv` reproduz o dicionario com a origem de cada coluna e a
forca que ela teve contra o SOH.

**Vazamento.** `capacity` e `time` estao na Tabela 2, mas o SOH e `capacity`
dividido pela capacidade de referencia, e a corrente constante torna a duracao a
propria capacidade (Ah = I·t). Ficam marcadas com `is_leakage` no ranking e fora
do topo da lista. Para o RUL mais adiante sao atributo legitimo; para o SOH sao a
resposta.

**Agrupada contra intra-celula.** Toda correlacao sai nas duas versoes. A
agrupada mistura diferenca entre celulas com degradacao e engana: `voltage_load`
da 0,10 juntando tudo e **0,63** centrando por bateria x condicao. O ranking se
ordena por `within_cell_correlation`, e
`per_cell_correlation_p10`/`_p90`/`same_sign_fraction` dizem se o sinal se
sustenta celula a celula — e o caso de `re` e `rectified_impedance`, fortes na
media (−0,62 e −0,59) e estaveis em so 58% e 60% das celulas.

`04_agrupada_vs_intra.png` mostra a divergencia sobre o mesmo dado, sem filtrar
nada entre um painel e outro: cada bateria x condicao e uma reta propria e
inclinada, mas cada uma num nivel de tensao diferente — `voltage_load` fica em
0,67 V a 4 A / 4 C e em 2,88 V a 1 A / 4 C. Juntando tudo, essa diferenca de
nivel ocupa 2,2 V contra os 0,2 V que a degradacao mexe dentro de uma celula, e a
reta agrupada acaba medindo protocolo. E o paradoxo de Simpson na pratica.

## `limpeza.py`

```bash
python limpeza.py                   # politica padrao
python limpeza.py --teto-falta 0.3  # mais rigoroso com coluna esburacada
python limpeza.py --grupo-minimo 5  # aceita grupos mais curtos
python limpeza.py --podar           # remove tambem os pares redundantes
```

Transforma a tabela da Tabela 2 em `saida_nasa/preprocessado/dados_modelagem.csv`
— 2.719 linhas, 11 atributos, 33 baterias — com o relatorio de cada decisao.

**Nao normaliza e nao imputa**, de proposito: escalonamento e imputacao ajustados
no conjunto inteiro vazam informacao do teste. Ficam para depois da divisao
treino/teste.

| descarte | linhas |
|---|---|
| capacidade ausente ou zero (ja marcadas por `graficos_nasa.py`) | −44 |
| curva curta demais para render agregacao (B0041, 4 A / 4 C) | −3 |
| grupos com menos de 10 descargas | −28 |

O terceiro merece explicacao. O SOH e a capacidade sobre a **maior capacidade da
celula naquela condicao**. Num grupo de 2 descargas essa referencia quase
certamente nao mede a capacidade cheia, e o SOH sai distorcido para o grupo
inteiro — nao e ruido de medicao, e alvo mal definido. Saem 7 grupos.

**Faltantes praticamente nao existem** neste esquema: 15 NaN em 2.719 linhas,
99,8% de casos completos. Vem dos 14 ensaios de impedancia com resistencia
implausivel, que `correlacao_soh.py` zera antes de propagar. O mapa de faltantes
so e desenhado quando alguma coluna passa de 5% de ausencia.

**Redundancia e relatada, nao removida.** Dois pares passam de 0,95:
`current_measured` ~ `voltage_load` (0,960) e `ambient_temperature` ~
`temperature_measured` (0,953). Colinearidade atrapalha modelo linear e nao
atrapalha arvore, entao a decisao pertence a quem escolhe o modelo;
`pares_redundantes.csv` lista a sugestao e `--podar` aplica. A sugestao usa a
correlacao **intra-celula** para decidir quem fica.

## `descritiva.py`

```bash
python descritiva.py                # tabelas e graficos
python descritiva.py --sem-graficos  # so as tabelas
```

Escreve `saida_nasa/descritiva/`: as estatisticas de um atributo numerico, a
distribuicao de um nominal e tres figuras — histograma, boxplot e dispersao.
E a materia da secao 3.3 do artigo.

**O numerico e `SOH`**, porque e o alvo e porque o limiar de fim de vida (80%) e
definido sobre ele. **O nominal e `test_condition`**, corrente x temperatura. Os
outros dois candidatos perdem por motivos diferentes: `charge_type` e identico
nas 34 celulas — variancia zero, nada a descrever — e `discharge_type` explica
8,6% da variancia do SOH contra os 16,0% da condicao. `battery_id` explica 60,6%,
mas e rotulo de instancia: nao existe para uma celula nova.

| | |
|---|---|
| `estatisticas_numericas.csv` | tendencia central, dispersao e forma do SOH e da capacidade |
| `frequencias_condicao.csv` | uma linha por condicao: descargas, celulas, quartis do SOH e as duas correlacoes com o ciclo |
| `01_histograma_soh.png` | o SOH ao lado da capacidade bruta |
| `02_boxplot_soh_condicao.png` | SOH por condicao, ordenado pela mediana |
| `03_dispersao_soh_ciclo.png` | SOH contra ciclo, um painel por condicao |

O histograma traz a capacidade bruta ao lado do alvo de proposito: ela e bimodal
e ele nao. A moda junto de zero sao as 192 descargas a 4 A / 4 C, mediana de
0,062 Ah contra 1,760 Ah a 1 A / 44 C — 28 vezes. Nenhuma degradacao faz isso; e
protocolo, e e o argumento para o alvo ser relativo.

A dispersao mostra o **paradoxo de Simpson** dentro de uma unica condicao. Em
1 A / 4 C o SOH parece subir com o ciclo (r = +0,26); dentro de cada uma das oito
celulas ele cai, com r mediano de −0,91. B0042, B0043 e B0044 entram nessa
condicao ja no ciclo 87 e, renormalizadas pelo maximo do novo grupo, reaparecem
em 100% — trajetorias decrescentes empilhadas no canto alto, sobre as quais a
reta agregada sobe. Nos 43 grupos o r mediano e −0,82, negativo em 37; agrupando
tudo, −0,42.

## `normalizar.py`

```bash
python normalizar.py                     # politica padrao
python normalizar.py --ciclos-referencia 10
python normalizar.py --fracao-teste 0.3
python normalizar.py --so-relativas      # descarta as colunas brutas
```

Escreve `saida_nasa/normalizado/dados_normalizados.csv` — 2.719 x 27, com as
colunas `split` e `fold`. Sao tres coisas que costumam receber o mesmo nome:

**1. Divisao por bateria.** Dividir por descarga poria a mesma celula nos dois
lados, e como cada celula vive num nivel de tensao proprio, o modelo acertaria
por reconhecer a celula. E o vazamento entre celulas que o artigo declara querer
evitar. O teste leva baterias inteiras: **8 baterias, 718 descargas (26%)**,
escolhidas de modo que as 8 condicoes aparecam dos dois lados. As baterias sao
muito desiguais (12 a 197 descargas), entao a escolha equilibra o numero de
descargas, nao o de baterias. As de treino recebem `fold` para validacao cruzada,
tambem por bateria.

**2. Referencia de inicio de vida.** De cada valor subtrai-se a mediana dos 5
primeiros ciclos **daquela** bateria x condicao, gerando as colunas `_rel`. Isso
converte "2,5 V" em "0,35 V abaixo do que esta celula entregava quando nova", e o
numero passa a atravessar celulas:

| variavel | agrupada crua | com referencia | intra-celula (teto) |
|---|---|---|---|
| `voltage_load` | 0,10 | **0,49** | 0,63 |
| `voltage_measured` | 0,32 | **0,51** | 0,65 |
| `re` | −0,23 | **−0,40** | −0,62 |
| `rectified_impedance` | −0,26 | −0,25 | −0,59 |
| `rct` | −0,24 | −0,17 | −0,41 |

Nao e vazamento: usa os primeiros ciclos da propria celula, nunca o alvo, e e
informacao que um BMS tem — voce conhece a celula quando ela e nova. Mas **assume
que a celula de teste tem historico de inicio de vida**; se o cenario for "celula
chega no meio da vida, sem historico", nao vale.

Foram testadas quatro formas: `x-ref` ganhou de `(x-ref)/ref`, de
`(x-ref)/desvio` e de usar 10 ciclos em vez de 5. O ganho nao e uniforme — ajuda
muito as de tensao e o `re`, nao mexe em `rectified_impedance` e piora `rct` —
entao por padrao as colunas brutas ficam ao lado das `_rel` e a escolha fica para
a modelagem. `01_ganho_da_referencia.png` compara as tres leituras.

**3. Escalonamento z-score, ajustado so no treino.** Media e desvio saem das
baterias de treino e sao aplicados aos dois lados. A tabela ja sai escalonada,
o que serve para o fluxo treino/teste simples; para validacao cruzada honesta o
escalonamento tem que ser refeito por fold, e `parametros_escala.csv` traz uma
linha por fold alem da linha do treino inteiro.

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
