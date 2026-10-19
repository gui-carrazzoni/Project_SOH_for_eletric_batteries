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

python main.py              # roda a cadeia inteira, pulando o que já está feito
```

Na primeira vez são ~6 min, quase tudo download. Depois, `main.py` só roda o que
falta.

## Organização

```
main.py                    orquestrador: roda a cadeia, pula o que já está feito
src/                       os 15 scripts, cada um executável sozinho
cleaned_nasa_dataset/      os dados (não versionados, reconstruídos pelo script)
manifesto_nasa.csv.gz      as impressões digitais que verificam os dados
saida_nasa/                tudo que a análise produz
├── geral/                 métricas por ensaio e os sete gráficos gerais
├── correlacao/            tabela da Tabela 2 e relevância dos atributos
├── preprocessado/         a tabela limpa, pronta para modelar
├── descritiva/            distribuições do alvo e da condição
├── normalizado/           divisão por bateria, referência de vida, escala
├── curvas/                áreas e forma da descarga, mais o mapa de calor
├── carga/                 a carga como processo próprio
├── classificacao/         fim de vida: kNN e as famílias da literatura, lado a lado
├── regressao/             SOH: GAM e as famílias da literatura, e o RUL
└── cluster/               tudo que é agrupamento
    ├── agrupamento/                          grupos descobertos no dado
    ├── grupo_corrente_temperatura/           esquema sem a tensão de corte
    ├── grupo_corrente_temperatura_corte/     esquema com a tensão de corte
    └── comparacao/                           qual dos dois esquemas ganha
```

**Dentro de cada pasta, tabelas e figuras ficam separadas**: os CSVs em
`tabelas/`, os PNGs em `figuras/`. Uma pasta sem gráfico só tem `tabelas/`.
As figuras de classificação e regressão são numeradas na ordem do artigo —
validação, teste de todos os algoritmos, o modelo proposto em detalhe e, na
regressão, o RUL. Algumas tabelas não são resultado, e sim a entrada da etapa
seguinte; ficam em `tabelas/` como as outras:

| tabela | quem gera | quem lê |
|---|---|---|
| `geral/tabelas/metricas_descargas.csv` | `graficos_nasa.py` | `correlacao_soh.py`, `curvas.py`, `carga.py` |
| `correlacao/tabelas/tabela_modelagem.csv` | `correlacao_soh.py` | `limpeza.py`, `descritiva.py` |
| `preprocessado/tabelas/dados_modelagem.csv` | `limpeza.py` | `descritiva.py`, `normalizar.py`, `classificacao.py`, `regressao.py` |
| `normalizado/tabelas/dados_normalizados.csv` | `normalizar.py` | `classificacao.py`, `regressao.py` |
| `normalizado/tabelas/parametros_escala.csv` | `normalizar.py` | `regressao.py` |
| `curvas/tabelas/features_curvas.csv` | `curvas.py` | `grupos.py`, `capacidade.py`, `modelos_area.py`, `mapa_calor.py`, `classificacao.py` |
| `cluster/agrupamento/tabelas/grupos_comportamento.csv` | `grupos.py` | `classificacao.py` |
| `cluster/<esquema>/capacidade/tabelas/` e `modelos_area/<área>/tabelas/` | `capacidade.py`, `modelos_area.py` | `comparacao.py` |

### `main.py`

```bash
python main.py                  # roda o que falta
python main.py --listar         # estado de cada etapa
python main.py --listar --alvos # e o arquivo que prova que cada uma rodou
python main.py --forcar         # refaz tudo (menos o download)
python main.py --refazer curvas # refaz essa etapa e todas as seguintes
python main.py --so carga       # roda só essa
```

Cada etapa declara um **arquivo-alvo**: se ele existe, a etapa está feita. Não é
data de modificação — é existência, que é o critério que não mente quando os
relógios do sistema de arquivos discordam.

**Uma etapa que roda dispara todas as seguintes.** Se `curvas.py` precisou
rodar, o cache mudou e quem vem depois está trabalhando sobre dado velho; pular
por "o arquivo existe" produziria uma saída internamente inconsistente, que é
pior que refazer. E quando uma etapa é **refeita** em vez de rodada pela
primeira vez, ela recebe o próprio argumento de invalidação (`--remontar` nos
três scripts que têm cache em disco) — sem isso a cascata não serviria de nada.

**O download fica fora da cascata.** `preparar_dados.py` baixa 586 MB e só roda
se `cleaned_nasa_dataset/` não existir; nem `--forcar` o dispara. Para refazer,
chame o script direto.

Cada script continua rodando sozinho, com os próprios argumentos:

```bash
python src/curvas.py --remontar
python src/capacidade.py --sem-corte
```

Os sete scripts de `curvas.py` a `carga.py` vieram de uma revisão com um
profissional de baterias. Seis deles formam um encadeamento: `curvas.py` lê as
descargas brutas uma vez e os outros trabalham sobre o cache que ele deixa.
`carga.py` é independente — tem cache próprio e lê os ensaios de carga, que
nenhum outro script toca. `classificacao.py` e `regressao.py` fecham a cadeia:
leem só a saída de `normalizar.py`, mas ficam por último para que nada que rode
depois delas precise ser refeito.

## `preparar_dados.py`

```bash
python src/preparar_dados.py                     # baixa e prepara
python src/preparar_dados.py --verificar         # não baixa; confere o que já existe
python src/preparar_dados.py --gerar-manifesto   # (re)cria o manifesto de verificação
python src/preparar_dados.py --forcar            # refaz mesmo se já estiver na pasta
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

Gera `saida_nasa/geral/` com três tabelas de métricas, em `tabelas/`, e sete
gráficos, em `figuras/`:

| | |
|---|---|
| `metricas_descargas.csv` | uma linha por descarga: condição, capacidade, SoH, duração, tensão final, temperatura máxima |
| `metricas_impedancia.csv` | uma linha por ensaio de impedância: Re, Rct, SoH da descarga mais próxima |
| `resumo_baterias.csv` | uma linha por bateria, incluindo a correlação entre resistência e SoH |
| `figuras/01…07` | capacidade por condição, SoH, efeito da condição, resistência, predição de SoH, curvas de descarga, espectro |

## `correlacao_soh.py`

```bash
python src/correlacao_soh.py                # monta, correlaciona, plota
python src/correlacao_soh.py --sem-graficos  # so as tabelas
python src/correlacao_soh.py --remontar      # ignora o cache e rele as 2.794 curvas
```

Monta `saida_nasa/correlacao/tabelas/tabela_modelagem.csv` **no esquema da Tabela 2 do
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
python src/limpeza.py                   # politica padrao
python src/limpeza.py --teto-falta 0.3  # mais rigoroso com coluna esburacada
python src/limpeza.py --grupo-minimo 5  # aceita grupos mais curtos
python src/limpeza.py --podar           # remove tambem os pares redundantes
```

Transforma a tabela da Tabela 2 em `saida_nasa/preprocessado/tabelas/dados_modelagem.csv`
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
python src/descritiva.py                # tabelas e graficos
python src/descritiva.py --sem-graficos  # so as tabelas
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
python src/normalizar.py                     # politica padrao
python src/normalizar.py --ciclos-referencia 10
python src/normalizar.py --fracao-teste 0.3
python src/normalizar.py --so-relativas      # descarta as colunas brutas
```

Escreve `saida_nasa/normalizado/tabelas/dados_normalizados.csv` — 2.719 x 27, com as
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

## `curvas.py`

```bash
python src/curvas.py              # usa cache
python src/curvas.py --remontar   # relê as 2.794 curvas
python src/curvas.py --amostra 50 # teste rápido
```

Lê as curvas de descarga **uma única vez** e escreve
`saida_nasa/curvas/tabelas/features_curvas.csv` — 2.794 × 87. Daqui saem as três áreas,
a carga integrada e os descritores de forma que os scripts seguintes consomem.

**Três áreas, porque a curva de descarga admite três integrais:** `carga_Ah`
(∫I·dt, que é a capacidade), `tensao_Vs` (∫V·dt, a leitura geométrica do gráfico
de descarga) e `energia_Wh` (∫V·I·dt, a energia entregue). Em corrente constante
as três andam juntas; nas quatro baterias de carga pulsada, não.

**Duas janelas, e é a parte que importa.** Cada bateria tem seu próprio corte de
descarga, de 2,0 a 2,7 V. Integrar até o corte de cada uma produz áreas que **não
se comparam** — uma célula cortada em 2,0 V descarrega mais fundo, e a diferença
é protocolo, não saúde. Então cada área sai duas vezes, e só a versão `_comum`,
que para num piso de 2,7 V igual para todas, se compara entre células.

O piso de 2,7 V não foi escolhido a esmo, e sim descoberto no dado:

| integrando até | erro mediano vs `Capacity` da NASA | casos com \|erro\| > 5% |
|---|---|---|
| o corte de cada célula | +1,13% | 35,9% |
| o piso comum de 2,7 V | **−0,28%** | **6,5%** |

Ou seja, **o campo `Capacity` da NASA já é medido numa janela comum de ~2,7 V**,
e não no corte de cada célula. O que também quer dizer que o SoH do projeto,
derivado dele, já estava numa base comparável entre cortes.

## `grupos.py`

```bash
python src/grupos.py              # k por silhueta + estabilidade
python src/grupos.py --grupos 6   # força k
```

Agrupamento hierárquico (Ward) por **comportamento medido**, para confrontar com
o rótulo nominal de `test_condition`. Escreve `saida_nasa/cluster/agrupamento/`.

A unidade agrupada é a bateria × condição, descrita pela mediana dos 10
primeiros ciclos naquele regime — com todos os ciclos, uma célula degradada num
regime brando pareceria uma célula nova num regime severo. Corrente,
temperatura **e tensão de corte** ficam fora dos atributos: incluí-las faria o
cluster reproduzir o protocolo por construção.

**Tudo vem da janela comum de 2,7 V.** A versão anterior usava a curva até o
corte de cada célula, e o último ponto dela (`v49`) *é* a tensão de corte
(r = 0,98); `queda_V` também (r = −0,79). Com isso o cluster "descobria" o
corte que recebia como atributo — em `2 A / 4 C` as oito células se partiam
exatamente por corte. Na janela comum (`c00`..`c49` e as grandezas `_comum` de
`curvas.py`) as oito caem no mesmo grupo, e o ARI contra o corte vai a ≈ 0.

O pipeline:

1. **Extremos à parte.** Escore-z modificado (mediana/MAD) > 3,5 no log das
   áreas separa 5 pares — os quatro de `4 A / 4 C` e B0039 a `4 A / 24 C`, que
   chegam a 2,7 V em menos de 7 min. Dentro do agrupamento eles inflavam a
   silhueta e faziam ela escolher k=2.
2. **Redundância fora.** `carga_Ah_comum` sai por r = 0,99 com
   `energia_Wh_comum`; sem isso a mesma grandeza contaria duas vezes.
3. **PCA** retém 95% da variância em 3 componentes (75%, 16%, 5%).
4. **k por dois critérios.** Candidatos: estabilidade bootstrap (ARI médio,
   200 reamostragens) ≥ 0,75 e nenhum grupo unitário. Vence o **menor**
   candidato — a silhueta cresce quase sem parar com k e não tem pico, então o
   máximo dela é fragmentação. Resultado: **k = 6**.

| k=6 | valor |
|---|---|
| silhueta | 0,48 |
| estabilidade bootstrap | 0,80 ± 0,15 |
| ARI Ward × k-means | 0,94 |
| ARI contra a condição nominal | 0,49 (NMI 0,76) |
| ARI contra a tensão de corte | −0,04 (NMI 0,08) |

**O que ele encontrou de fato foi a carga pulsada.** B0025–B0027 estão rotuladas
`4 A / 24 C`, mas descarregam em onda quadrada de 50% de duty — 2 A em média.
O agrupamento, que nunca viu a corrente, as colocou junto das células de 2 A em
temperatura ambiente, e não com as de 4 A contínuo (B0033, B0034). É o rótulo
nominal escondendo um regime, agora sem vazamento. As outras fusões seguem a
física: `2 A / 22 C`, `2 A / 24 C` e `2 A / 44 C` formam um grupo só (a
temperatura entre 22 e 44 °C pouco muda a descarga a 2 A), enquanto 4 °C separa
sempre.

Ressalvas. B0039 a `4 A / 24 C` virou extremo com 1,34 Wh — muito abaixo das
irmãs B0038 e B0040 (2,3 e 3,2 Wh), mas nove vezes acima de `4 A / 4 C`: o MAD
das áreas é pequeno e o limiar de 3,5 o pega. E B0041 e B0045 (`1 A / 4 C`)
ficam com `2 A / 4 C`, não com as outras de 1 A. Em B0041 há explicação: ela
chega a `1 A / 4 C` depois de 42 ciclos a `4 A / 4 C`, já gasta. B0045 entra
nova, e o agrupamento não explica por que ela destoa.

`ajustar()` refaz esse agrupamento com k fixo usando só parte dos pares e
encaixa os demais no grupo de centroide mais próximo. É o que `classificacao.py`
usa na variante pós-hoc; as saídas deste script não mudam.

## `capacidade.py` e `modelos_area.py`

```bash
python src/capacidade.py                # os dois esquemas de grupo
python src/modelos_area.py --area energia
```

Escrevem em árvores paralelas com **os mesmos nomes de arquivo**, que é o que
torna a comparação direta:

```
saida_nasa/cluster/grupo_corrente_temperatura/
    capacidade/  modelos_area/{carga,tensao,energia}/

saida_nasa/cluster/grupo_corrente_temperatura_corte/
    capacidade/  modelos_area/{carga,tensao,energia}/
```

Cada uma dessas pastas tem as suas `tabelas/` e `figuras/`; a correlação das
áreas com o SOH fica em `modelos_area/tabelas/`.

`capacidade.py` dá a taxa de fade em Ah/ciclo, os ciclos até 80% e o joelho de
cada célula. `modelos_area.py` ajusta quatro famílias à série área × ciclo de
cada célula — linear, exponencial, potência e exponencial duplo — comparadas por
**AIC**, e não por R²: o R² sempre melhora quando se acrescenta parâmetro, e o
exponencial duplo tem quatro contra dois do linear.

O ajuste é **por célula, nunca por grupo empilhado**, porque empilhar
reproduziria o paradoxo de Simpson que o projeto já documenta.

| família | vence em |
|---|---|
| potência | 53% das séries |
| linear | 23% |
| exponencial duplo | 16% |
| exponencial | 7% |

**As três áreas são vazamento para o SoH**, e isso não é defeito do cálculo: a
carga integrada *é* a capacidade, e o SoH é a capacidade normalizada. A
correlação intra-célula dá +1,0000 em 100% das séries. Elas não entram num
modelo de SoH como atributo — mesma regra que `correlacao_soh.py` aplica a
`capacity` e `time`. Entram como **objeto modelado**: ajustar como a área cai ao
longo dos ciclos é descrever a curva de degradação, não prevê-la. O r = +1,0000
tem um uso legítimo, porém — é a confirmação de que a integração está correta.

## `comparacao.py`

Confronta os dois esquemas de grupo e escreve `saida_nasa/cluster/comparacao/`. O veredito
tem duas metades que apontam para lados diferentes, e nenhuma resolve sozinha.

**Contra dividir por corte:** 59% dos grupos ficam com uma célula só. A NASA
atribui um corte diferente a cada bateria do mesmo README, então condição × corte
quase identifica a célula e o agrupamento vira `battery_id` — rótulo de
instância, que não existe para uma célula nova.

**A favor:** onde pode ser medido, funciona. O desvio da taxa de fade caiu em 3
das 4 condições avaliáveis, e em `4 A / 24 C` foi de 1,302 para 0,047. Nas outras
quatro condições todo subgrupo ficou unitário e não há desvio interno para
comparar.

**O que não muda:** o R² dos ajustes fica em 0,6619 contra 0,6619. Partir os
grupos não tornou as séries mais fáceis de modelar, porque o ajuste já é por
célula — o grupo nunca entrou na conta.

**A recomendação é `grupo_corrente_temperatura` — o esquema sem o corte —, com a
área na janela comum.** A janela comum
não depende do corte, então o efeito que motivaria a divisão já foi removido na
origem. O que sobra correlacionado ao corte troca de sinal entre condições (+0,68
em `1 A / 4 C`, −0,84 em `1 A / 44 C`), e efeito físico real não troca de sinal:
é confundimento com a identidade da célula, que dividir por corte não corrige —
só ajusta ruído. Com mais células por corte a divisão teria mérito; é limitação
do dataset, não da ideia.

## `mapa_calor.py`

Mapa de calor da correlação incluindo as áreas e a forma da descarga, em
`saida_nasa/curvas/correlacao/`. Não substitui o de `correlacao_soh.py`, que é
fiel ao dicionário da Tabela 2 sem acréscimo. Três diferenças: todo valor é
anotado, saem as duas leituras (agrupada e intra-célula), e **o vazamento fica
marcado em vermelho na figura** — um mapa que mostrasse r = 1,00 sem dizer que é
identidade convidaria a ler o óbvio como achado.

Fora as vazadas, o que acompanha o SoH dentro da célula:

| variável | agrupada | intra-célula |
|---|---|---|
| `V_medio` | 0,324 | **0,674** |
| `ciclo_na_condicao` | −0,469 | −0,592 |
| `V_inicial` | 0,171 | 0,484 |
| `inclinacao_mV_min` | −0,006 | **0,340** |

`inclinacao_mV_min` é o caso didático: 0,00 agrupada e 0,34 dentro da célula.

## `carga.py`

```bash
python src/carga.py                 # usa cache
python src/carga.py --remontar      # relê os 2.815 ensaios de carga
python src/carga.py --amostra 100   # teste rápido
```

Escreve `saida_nasa/carga/` — `features_carga.csv`, 2.783 × 149, mais o resumo
por condição, as duas matrizes de correlação e sete figuras.

**Todo o resto do projeto olha só para a descarga.** O dataset tem 2.815 ensaios
de carga contra 2.794 de descarga, cobrindo as 34 células, e nenhum script os
tocava: `graficos_nasa.py` filtra `type == "discharge"`, `correlacao_soh.py`
filtra `discharge` e `impedance`, e `charge_type` entrava como string constante.
Metade do dado estava parada.

**E a carga é o ensaio controlado que a descarga não é.** Na descarga o
protocolo varia — 11 combinações de corrente × temperatura, mais o corte de 2,0
a 2,7 V — e essa variação engole a degradação; é o motivo de todo o projeto
normalizar por bateria × condição. Na carga o protocolo é **idêntico nas 34
células**: CC de 1,5 A até 4,2 V, depois CV até a corrente cair a 20 mA. Com o
estímulo fixo, o que muda de um ciclo para o outro é a célula.

**Duas fases, em sentidos opostos.** Na CC a célula aceita 1,5 A e a tensão sobe
até 4,2 V: quanto menos capacidade resta, mais rápido ela sobe e mais curta fica
a fase. Na CV a tensão fica em 4,2 V e a corrente decai: quanto mais degradada a
célula, mais tempo leva. Os dois efeitos se cancelam, e a **duração total da
carga tem r = 0,01 com o SoH** — quem olha só o total não vê nada. A fronteira é
achada no dado: a CC acaba na primeira vez que a corrente cai abaixo de 95% do
seu patamar e *fica* abaixo por 3 amostras seguidas.

**A janela de tensão fixa é a parte que importa.** Cada carga começa na tensão
em que a descarga anterior deixou a célula, e isso varia de 3,1 a 4,4 V entre os
ensaios — comparar `t_cc_s` cru mede sobretudo quão descarregada a célula
estava. A solução é a mesma que `curvas.py` usa para as áreas: medir numa janela
fixa, igual para todos. `t_janela_CC_s` é o tempo para atravessar de 3,9 V a
4,15 V dentro da CC. Como a corrente é constante ali, esse tempo *é* a carga
aceita naquela faixa — uma capacidade parcial, sempre na mesma janela.

| atributo | agrupada | intra-célula | cobertura |
|---|---|---|---|
| `t_janela_CC_s` (3,9–4,15 V) | 0,484 | **0,632** | 75%, 31 células |
| `t_cc_s` | 0,381 | 0,522 | 100%, 34 |
| `Ah_cc` | 0,374 | 0,520 | 100%, 34 |
| `t_janela_CC34_s` (4,0–4,15 V) | 0,265 | 0,498 | 88%, **34** |
| `dqdv_pico` | 0,420 | 0,491 | 94%, 34 |
| `frac_Ah_cv` | −0,329 | −0,444 | 100%, 34 |

Para comparar: o melhor atributo **não vazado** do lado da descarga é `V_medio`,
com 0,674 intra-célula. A carga chega perto disso sem tocar na descarga que está
sendo prevista. As duas janelas ficam na tabela porque a escolha é um troco: a
de 3,9 V correlaciona mais forte, a de 4,0 V alcança as 34 células — B0041 e
parte dos ensaios de B0038 a B0045 começam a carga já acima de 3,9 V.

**dQ/dV.** Na fase CC, a carga acumulada derivada pela tensão tem picos nos
platôs de transição de fase do eletrodo; o pico encolhe e desliza para tensões
mais altas conforme a célula perde material ativo. É o que `dqdv_pico` (0,491) e
`dqdv_V_pico` (−0,384) registram. A curva é reamostrada a 5 mV e suavizada por
média móvel de 9 pontos antes de derivar — sem isso a derivada é ruído de
quantização do conversor.

**O que é quase-capacidade aqui.** `carga_inj_Ah`, a carga total injetada,
correlaciona **0,924** com a capacidade da descarga *anterior*, com excesso
mediano de +1,96% — que é a própria ineficiência coulômbica. Ela é a capacidade
medida pelo outro lado, um ciclo antes. Não é o vazamento que `correlacao_soh.py`
marca, porque não usa a descarga que se quer prever, e para um BMS é atributo
legítimo; mas também não é achado nenhum que acompanhe o SoH, e o ranking marca
ela e `energia_inj_Wh` com `quase_capacidade`. `t_janela_CC_s`, `Ah_cc` e
`dqdv_pico` não caem nessa conta: medem um trecho fixo da carga, não o total
devolvido.

**O pareamento.** Cada carga recebe o rótulo da **descarga seguinte** da mesma
célula — a que ela preparou —, e com ele vêm `condicao`, `ciclo_na_condicao` e
`SoH_%`. A ordem cronológica é a de `uid`: `start_time` tem 1.526 registros
corrompidos (ano "2"), e `uid` concorda com o relógio nas 34 células onde ele é
legível. Dos 2.815 ensaios, 2.783 rendem atributos e 2.754 têm descarga
seguinte.

**O que precisa de cuidado.** O ensaio tem teto de 3 h e 40% das cargas batem
nele; em 16% a corrente ainda não tinha caído aos 50 mA, então `t_cv_s` está
cortado por cima — é a razão de as métricas de CV renderem menos que as de CC
apesar de a física prometer o contrário. E a eficiência coulômbica (mediana
**98,0%**) só significa alguma coisa quando a descarga seguinte esvazia a
célula: em 4 A / 4 C ela entrega 0,077 Ah contra 1,7 Ah das demais condições, e
a razão cai para 5% medindo protocolo, não perda de carga. São 344 casos,
marcados na coluna `alerta`.

| | |
|---|---|
| `01_curva_de_carga.png` | a carga CC-CV envelhecendo, duas células, tensão e corrente |
| `02_ciclo_completo.png` | carga e descarga no mesmo eixo, três idades |
| `03_ah_cc_por_ciclo.png` | Ah aceito na CC ao longo dos ciclos, um painel por grupo |
| `04_janela_CC_por_ciclo.png` | o tempo na janela fixa ao longo dos ciclos, por grupo |
| `05_ranking_vs_soh.png` | agrupada contra intra-célula, quase-capacidade em vermelho |
| `06`, `07` | mapas de calor, agrupado e intra-célula |

## `classificacao.py`

```bash
python src/classificacao.py                    # k na validação, avaliação no teste
python src/classificacao.py --k 25             # força k
python src/classificacao.py --sem-referencias  # só o kNN, sem as famílias da literatura
python src/classificacao.py --sem-graficos     # só as tabelas
```

Escreve `saida_nasa/classificacao/`, em 2 a 3 min (quase tudo Random Forest e
Gradient Boosting; com `--sem-referencias` são poucos segundos). Cada descarga
vira **fim de vida** (SOH < 80%, o limiar do artigo) ou **saudável**, e quem
decide é o **kNN**: as k descargas de treino mais próximas no espaço padronizado
dos atributos, distância euclidiana, voto por maioria, k ímpar para não empatar.

**Por que kNN.** O kNN não tem parâmetro treinado, e cada
previsão vem com os vizinhos que a decidiram: `predicoes_teste.csv` lista os três
mais próximos de cada descarga de teste, com célula, ciclo e SOH, para quem
conhece bateria conferir.

**O que entra.** Os atributos relativos ao início de vida de `normalizar.py` (as
colunas `_rel`), mais temperatura ambiente, corrente e ciclo. Os conjuntos bruto
e completo rodam ao lado, para medir o efeito. As classes já vêm quase
equilibradas — 43,7% de fim de vida no treino, 47,4% no teste —, e a métrica é a
acurácia balanceada, em que o acaso vale 50%.

**Validação deixando uma célula de fora**, nas 25 de treino. A coluna `fold` de
`normalizar.py` fica de lado: o contador de folds recomeça a cada condição, e os
cinco folds saíram com 8, 7, 6, 3 e 1 células — o último com 24 descargas, 96%
delas em fim de vida. Imputação e escala são refeitas a cada rodada, só com as
células que ficaram no treino.

**k = 25: o menor equivalente ao melhor.** Com os atributos relativos a curva
forma um platô — de k = 15 a k = 101 fica tudo entre 78% e 80% — e cai depois
de k ≈ 100 (73% em k = 201), quando a vizinhança vira média regional. O máximo,
80,0% em k = 101, é um pico isolado na borda da queda. Vence o menor k a até
1 p.p. do máximo, a mesma lógica de `grupos.py`, que fica com o menor candidato.

### Validação: protocolo, atributos e algoritmo

| acurácia balanceada | brutos | relativos | todos | relativos, partição aleatória |
|---|---|---|---|---|
| **kNN** | 72,0% (k = 15) | **79,4%** (k = 25) | 76,5% (k = 5) | 92,1% |
| SVM (RBF) | 74,0% | 79,0% | 73,1% | 92,9% |
| Gradient Boosting | 67,2% | 76,3% | 76,5% | 96,6% |
| Random Forest | 60,0% | 73,6% | 67,3% | 95,8% |
| Regressão logística | 69,2% | 67,9% | 62,1% | 85,9% |

1. **Protocolo.** A partição aleatória por descarga, que põe a mesma célula dos
   dois lados, soma de 13 a 22 p.p. e leva todos para 86% a 97%. No kNN
   o mecanismo fica à vista: com ela, o vizinho mais próximo de uma descarga é
   da mesma célula em 90% dos casos. O modelo reconhece a
   célula em vez de medir a degradação — é o vazamento que o artigo aponta em
   [13].
2. **Atributos.** Trocar brutos por relativos soma de 5 a 14 p.p. aos modelos
   não lineares; a logística perde 1.
3. **Algoritmo.** Com os atributos relativos, kNN e SVM ficam a 0,5 p.p. um do
   outro.

### Teste: as 8 células, avaliadas uma vez

| teste | acurácia balanceada | IC 95% | sensibilidade | especificidade | diferença para o kNN (IC 95% pareado) |
|---|---|---|---|---|---|
| **kNN (k = 25)** | 73,6% | 52–85% | 51,2% | 96,0% | — |
| Regressão logística | 84,1% | 75–94% | 90,6% | 77,5% | +10,4 p.p. (−2,6 a +36,7) |
| SVM (RBF) | 80,3% | 67–88% | 64,1% | 96,6% | +6,7 p.p. (−0,7 a +23,4) |
| Random Forest | 76,8% | 69–87% | 64,7% | 88,9% | +3,2 p.p. (−10,0 a +26,6) |
| Gradient Boosting | 83,2% | 73–90% | 77,1% | 89,4% | +9,6 p.p. (+1,7 a +25,6) |

Os intervalos vêm de reamostrar células inteiras, não descargas: descargas
seguidas da mesma célula são quase cópias, e reamostrá-las uma a uma daria um
intervalo estreito demais. Todos os modelos passam pelas mesmas reamostragens,
então a diferença para o kNN é medida em pares.

**No teste o kNN fica em último**, e a fraqueza é a sensibilidade: deixa passar
49% das descargas em fim de vida. Os erros se concentram em três células — em
B0018 (2 A / 24 °C) as 58 descargas abaixo de 80% passam como saudáveis, em
B0054 (2 A / 4 °C) 45 de 50, em B0042 a 4 A / 4 °C 19 de 23 —, e 65% dos 181
erros ficam a menos de 5 p.p. do limiar. São descargas logo abaixo de 80% que o
kNN ainda vê como saudáveis.

**A ordem dos algoritmos não se sustenta entre validação e teste.** O kNN é o
1º de 5 na validação e o 5º no teste; a logística faz o caminho inverso, de
último (67,9%) a primeiro (84,1%). Na validação o kNN tinha a *melhor*
sensibilidade (71,6%) e a logística a pior (51,4%); no teste, 51,2% e 90,6%. O
que muda é quais células estão sendo avaliadas: o acerto do kNN por célula de
treino vai de 33% a 100%. Com 8 células de teste, a variação entre células pesa
mais que a diferença entre algoritmos.

**Medida em pares, só a diferença para o Gradient Boosting exclui o zero**
(+9,6 p.p.), e continua excluindo com a correção de Bonferroni para as quatro
comparações (+0,6 a +29,0 p.p.). Para as outras três referências o teste não
separa os modelos.

**O que isso diz para o artigo.** A hierarquia da validação — protocolo (13 a
22 p.p.) > atributos (até 14 p.p.) > algoritmo — sai mais forte, não mais fraca:
o efeito do protocolo é sistemático, e o do algoritmo nem mantém a ordem de um
conjunto de células para outro. O kNN não é o melhor classificador para células
novas: empata com as famílias da literatura na validação e fica abaixo do
Gradient Boosting no teste.

### AUC: a ordem dos escores, em todos os limiares

A acurácia balanceada avalia a decisão, com o voto cortado em 50%. A AUC avalia
se o escore põe as descargas em fim de vida acima das saudáveis, qualquer que
seja o limiar. O escore é a fração de vizinhos em fim de vida no kNN, a
probabilidade na logística, no Random Forest e no Gradient Boosting, e a função
de decisão no SVM. Na validação, os escores das 25 rodadas são juntados antes
do cálculo, porque a AUC de uma célula sozinha não existe quando ela tem uma
classe só. A AUC entrou depois do teste e não escolhe nada.

| AUC | validação, relativos | validação, partição aleatória | teste (IC 95% por células) | diferença para o kNN no teste (IC 95% pareado) |
|---|---|---|---|---|
| **kNN (k = 25)** | 0,834 | 0,984 | 0,826 (0,66–0,92) | — |
| Regressão logística | 0,696 | 0,919 | 0,870 (0,79–0,97) | +0,045 (−0,084 a +0,260) |
| SVM (RBF) | 0,853 | 0,975 | 0,950 (0,91–0,98) | +0,125 (+0,026 a +0,308) |
| Random Forest | 0,824 | 0,994 | 0,902 (0,83–0,97) | +0,076 (−0,031 a +0,294) |
| Gradient Boosting | 0,828 | 0,995 | 0,909 (0,86–0,96) | +0,083 (+0,006 a +0,235) |

- **O kNN também ordena pior.** No teste, a AUC dele é a menor. Só a diferença
  para o SVM resiste à correção de Bonferroni (+0,004 a +0,360); a do Gradient
  Boosting exclui o zero sem a correção, mas não com ela.
- **O SVM ordena bem e decide mal.** Tem a melhor AUC no teste (0,95), mas no
  limiar padrão detecta só 64% do fim de vida: o que o segura é o limiar, não a
  ordem. No kNN são as duas coisas. Na validação, o SVM já ficava à frente na
  AUC (0,853 contra 0,834), embora empatasse na acurácia balanceada.
- **O protocolo continua dominando.** Com a partição aleatória, a AUC de todos
  sobe para 0,92 a 0,995.

### F1: a qualidade do alarme de fim de vida

O F1 é a média harmônica entre a precisão (dos alarmes, quantos eram fim de
vida) e a sensibilidade (do fim de vida, quanto foi detectado). Sai com o mesmo
intervalo por células e a mesma comparação em pares da acurácia balanceada.

| F1 (fim de vida) | validação, relativos | validação, partição aleatória | teste (IC 95% por células) | precisão no teste | diferença para o kNN no teste (IC 95% pareado) |
|---|---|---|---|---|---|
| **kNN (k = 25)** | 0,762 | 0,912 | 0,658 (0,09–0,85) | 0,921 | — |
| Regressão logística | 0,599 | 0,841 | 0,840 (0,65–0,94) | 0,784 | +0,183 (−0,005 a +0,722) |
| SVM (RBF) | 0,755 | 0,923 | 0,764 (0,51–0,87) | 0,944 | +0,106 (−0,012 a +0,562) |
| Random Forest | 0,680 | 0,954 | 0,731 (0,58–0,85) | 0,840 | +0,073 (−0,115 a +0,620) |
| Gradient Boosting | 0,721 | 0,963 | 0,816 (0,61–0,90) | 0,868 | +0,158 (+0,022 a +0,597) |

- **O alarme do kNN é preciso, mas raro.** Quando dispara, acerta 92% das
  vezes; mas só dispara para 51% do fim de vida. O F1 dele, 0,66, é o menor do
  teste. Na validação, o padrão é o da acurácia balanceada: kNN e SVM empatam
  (0,762 e 0,755).
- **Com 8 células, o F1 é a métrica menos estável.** O intervalo do kNN vai de
  0,09 a 0,85. O F1 ignora as saudáveis reconhecidas e depende de quais células
  com fim de vida caem na reamostragem: sem B0018 e B0054, o F1 do kNN no teste
  seria 0,82; nas reamostragens em que elas se repetem, cai abaixo de 0,1.
  Nenhuma diferença de F1 resiste à
  correção de Bonferroni; só a do Gradient Boosting exclui o zero sem ela.
- **Por isso o F1 complementa a acurácia balanceada, mas não a substitui**: ele
  também muda com a proporção de fim de vida, que difere entre treino (44%) e
  teste (47%).

### Os cinco algoritmos lado a lado: matriz de confusão e métricas

As quatro referências saem com o mesmo detalhe do kNN: a matriz de confusão na
validação e no teste (`03_matrizes_de_confusao.png`), todas as métricas com o
intervalo por células (`04_metricas_por_algoritmo.png`) e o erro de cada
algoritmo em cada célula de teste (`06_erro_por_celula.png`). Os intervalos de
acurácia, sensibilidade, especificidade e precisão saem das mesmas
reamostragens de células das outras métricas. Nada disso escolhe nada.

| teste: 718 descargas, 340 em fim de vida | detectado (VP) | não detectado (FN) | alarme falso (FP) | saudável reconhecida (VN) | sensibilidade (IC 95%) | especificidade (IC 95%) | precisão (IC 95%) |
|---|---|---|---|---|---|---|---|
| **kNN (k = 25)** | 174 | 166 | 15 | 363 | 51,2% (5–79) | 96,0% (90–99) | 92,1% (68–97) |
| SVM (RBF) | 218 | 122 | 13 | 365 | 64,1% (37–81) | 96,6% (93–99) | 94,4% (83–98) |
| Gradient Boosting | 262 | 78 | 40 | 338 | 77,1% (56–90) | 89,4% (81–98) | 86,8% (62–97) |
| Random Forest | 220 | 120 | 42 | 336 | 64,7% (53–79) | 88,9% (81–96) | 84,0% (65–95) |
| Regressão logística | 308 | 32 | 85 | 293 | 90,6% (84–96) | 77,5% (61–95) | 78,4% (52–95) |

| validação: 2.001 descargas, 874 em fim de vida | VP | FN | FP | VN | sensibilidade | especificidade | precisão |
|---|---|---|---|---|---|---|---|
| **kNN (k = 25)** | 626 | 248 | 144 | 983 | 71,6% | 87,2% | 81,3% |
| SVM (RBF) | 615 | 259 | 140 | 987 | 70,4% | 87,6% | 81,5% |
| Gradient Boosting | 583 | 291 | 160 | 967 | 66,7% | 85,8% | 78,5% |
| Random Forest | 525 | 349 | 144 | 983 | 60,1% | 87,2% | 78,5% |
| Regressão logística | 449 | 425 | 176 | 951 | 51,4% | 84,4% | 71,8% |

- **Na validação os cinco erram do mesmo jeito; no teste, cada um troca um
  erro pelo outro.** Nas 25 células de treino a especificidade fica entre 84% e
  88% em todos, e o que os separa é quanto fim de vida cada um detecta (de 51%
  a 72%). No teste, kNN e SVM quase não dão alarme falso (15 e 13) e deixam
  passar 166 e 122 descargas em fim de vida; a regressão logística faz o
  contrário, com 32 não detectadas e 85 alarmes falsos; o Gradient Boosting
  fica no meio (78 e 40).
- **Nenhum algoritmo lidera todas as métricas** (`04_metricas_por_algoritmo.png`).
  No teste, a logística tem a maior acurácia balanceada, sensibilidade e F1; o
  SVM, a maior especificidade, precisão e AUC. Os intervalos se sobrepõem, menos
  na sensibilidade: o da logística (84–96%) fica todo acima dos de kNN, SVM e
  Random Forest.
- **O intervalo da sensibilidade do kNN vai de 5% a 79%.** Quem decide é quais
  células com fim de vida caem na reamostragem: B0018 e B0054 têm juntas 108
  das 340 descargas em fim de vida do teste, e o kNN deixa passar 103 delas.
- **Os erros se concentram nas mesmas células** (`06_erro_por_celula.png`).
  B0042 a 4 A / 4 °C é a pior na média dos cinco (50% de erro, de 39% a 61%), e
  B0054 a 2 A / 4 °C vem em seguida (de 19% a 46%). Em B0039 a 4 A / 24 °C os
  cinco erram as mesmas duas descargas: as leituras isoladas de 25% e 34% de
  SOH.
- **E cada algoritmo tem a sua célula difícil.** O kNN deixa passar as 58
  descargas em fim de vida de B0018, em que a logística erra 2. A logística dá
  20 alarmes falsos nas 25 descargas de B0042 a 1 A / 4 °C, um par sem nenhum
  fim de vida em que kNN e SVM não erram nada. É o par renormalizado no ciclo
  87: na regressão, os cinco algoritmos estimam o SOH dele de 8 a 11 p.p.
  abaixo do medido.
- **O acerto por célula de treino varia em todos, não só no kNN**
  (`validacao_por_celula.csv`): de 2% a 100% na logística, de 39% a 100% no
  Gradient Boosting e de 43% a 100% no SVM e no Random Forest, contra 33% a
  100% no kNN. É essa variação entre células que impede 8 células de teste de
  ordenar os algoritmos.

### Variante pós-hoc: vizinhos só do mesmo grupo de comportamento

Na análise dos erros do teste, mais da metade dos vizinhos que enganaram B0018
vinha de outros grupos do agrupamento do módulo 2. A variante restringe a
vizinhança ao grupo da descarga. Para que nem os grupos vejam a célula
avaliada, `grupos.ajustar()` refaz o agrupamento a cada rodada só com as
células de treino — mesmos atributos, extremos à parte, PCA e Ward com o k = 6
do módulo 2 —, e os pares da célula deixada de fora entram no grupo de
centroide mais próximo. Ajustado em todos os pares, `ajustar()` reproduz
exatamente os grupos de `grupos.py`; o encaixe pelo centroide discorda do Ward
em 1 dos 47 pares (B0040 a 2 A / 44 °C, na fronteira entre dois grupos).

Como a ideia surgiu de olhar o teste, só a validação a avalia, e ela **piora em
todos os 17 valores de k**. No k escolhido pela mesma regra (k = 3), a acurácia
balanceada cai de 79,4% para 66,3%, e a sensibilidade de 71,6% para 46,8%. O
motivo é o tamanho dos grupos: dentro do grupo, cada descarga encontra em
mediana só 7 células como vizinhas (de 1 a 8), contra 24 sem a restrição, e o
kNN passa a depender do comportamento de poucas irmãs — o mesmo mecanismo que
derrubou B0054 no teste. A maior queda é de B0036, de 89% para 13% de acerto:
dentro do grupo os vizinhos dela são saudáveis, e o kNN passa a contrariar o
rótulo dela, que é o artificial.

A variante não entra no modelo e não foi avaliada no teste.

**Cuidados:**

- **Ajustar o kNN agora contamina o teste.** Peso por distância ou limiar de voto
  abaixo de 50% atacariam a sensibilidade, mas qualquer mudança feita depois de
  ver o teste deixa de ser avaliação independente, e isso teria de ir declarado
  no artigo.
- **Parte dos erros é do rótulo, não do kNN.** As descargas 0 e 2 de B0039 a
  4 A / 24 °C marcam SOH de 25% e 34% numa célula que entrega 86% a 100% nas
  outras — leituras isoladas, como as que a análise descritiva já aponta. Em
  B0042 a 4 A / 4 °C o SOH salta de uma descarga para a seguinte (de 80% para
  88%, de 90% para 78%): nessa condição a capacidade mediana é de 0,062 Ah, e o
  SOH vira razão entre capacidades minúsculas.
- **Na validação o kNN leva uma pequena vantagem**, porque o k foi escolhido nela
  e as referências usam o padrão. No teste isso não favorece ninguém: o k saiu
  só do treino.

Em `saida_nasa/classificacao/tabelas/`:

| | |
|---|---|
| `escolha_de_k.csv` | acurácia balanceada por k, nos três conjuntos de atributos |
| `comparacao.csv` | modelo × atributos × validação (por célula e aleatória): acurácia balanceada, sensibilidade, especificidade, F1, AUC, precisão, acurácia, a matriz de confusão (VP, FN, FP, VN) e o k do kNN |
| `validacao_por_celula.csv` | o acerto de cada algoritmo em cada célula de treino, quando ela é a deixada de fora, e o do kNN com a restrição ao grupo |
| `variante_mesmo_grupo.csv` | acurácia balanceada por k, com e sem a restrição ao grupo de comportamento |
| `teste.csv` | métricas no teste, com a matriz de confusão, IC por reamostragem de células de todas elas e diferença pareada para o kNN em acurácia balanceada, AUC e F1, com e sem Bonferroni |
| `teste_por_celula.csv` | acertos, alarmes falsos e fins de vida não detectados por célula, de cada algoritmo |
| `predicoes_teste.csv` | cada descarga de teste com a previsão, o voto e os três vizinhos que a decidiram, e a classe e o escore de cada referência |

Em `saida_nasa/classificacao/figuras/`, na ordem do artigo:

| | |
|---|---|
| `01_escolha_de_k.png` | a curva de k nos três conjuntos, com a faixa de equivalência |
| `02_protocolo_atributos_algoritmo.png` | o efeito do protocolo, dos atributos e do algoritmo na validação |
| `03_matrizes_de_confusao.png` | a matriz de confusão de cada algoritmo, na validação e no teste |
| `04_metricas_por_algoritmo.png` | acurácia balanceada, sensibilidade, especificidade, precisão, F1 e AUC de cada algoritmo, no teste com IC e na validação |
| `05_curvas_roc.png` | as curvas ROC dos cinco modelos no teste, com a AUC e o ponto de operação do kNN |
| `06_erro_por_celula.png` | a fração de erro de cada algoritmo em cada célula de teste, com os alarmes falsos e os fins de vida não detectados |
| `07_teste_por_celula.png` | SOH contra ciclo em cada célula de teste, com os erros do kNN marcados |
| `08_variante_mesmo_grupo.png` | a variante pós-hoc contra o modelo avaliado, em toda a grade de k |

## `regressao.py`

```bash
python src/regressao.py                    # λ na validação, avaliação no teste
python src/regressao.py --lam 10000        # força λ
python src/regressao.py --sem-referencias  # só o GAM, sem as famílias da literatura
python src/regressao.py --sem-graficos     # só as tabelas
```

Escreve `saida_nasa/regressao/`, em cerca de 2,5 min (quase tudo Random Forest e
Gradient Boosting). Estima o **SOH de cada descarga** a partir do que se mede
nela — tensão, corrente, temperatura, impedância —, sem a capacidade, que é o
próprio SOH, e converte a estimativa em **vida útil remanescente (RUL)**, em
ciclos:

    RUL = (SOH estimado − 80) / perda de SOH por ciclo da condição

**Por que um GAM.** A regra é a da classificação: um algoritmo fora das famílias
dos trabalhos relacionados. O modelo aditivo generalizado escreve o SOH como uma
soma de funções suaves, uma por atributo, e cada uma é uma P-spline: base
B-spline cúbica com 20 nós e penalidade nas segundas diferenças dos coeficientes
(Eilers e Marx, 1996). Um parâmetro só, λ, vai de curvas que seguem o ruído
(λ → 0) a retas (λ → ∞), quando o GAM vira regressão linear. A forma de cada
função sai dos dados e pode ser desenhada na unidade física do atributo
(`07_efeitos_gam.png`). **Fora da faixa de 1% a 99% do treino, cada função fica
constante**: prolongar a curva, como faz a regressão linear, explode numa
condição que o treino nunca viu.

**Quais pares entram.** Em 8 dos 43 pares célula × condição a referência do SOH
é uma leitura isolada, e o SOH já começa abaixo de 80%: B0036 marca 99% das
descargas em fim de vida, B0049 a B0051 começam entre 30% e 60%. Na
classificação isso troca alguns rótulos; na regressão o erro é quadrático, e um
par desses pesa no RMSE mais que células inteiras. Entram só os pares cujo SOH
**começa saudável** — mediana das 5 primeiras descargas, a janela da referência
de `normalizar.py`, acima de 80%. Saem 7 pares do treino (5 células inteiras:
B0033, B0036, B0049, B0050 e B0051) e 1 do teste (B0042 a 4 A / 4 °C). Ficam
1.447 descargas de 20 células no treino e 672 de 8 no teste. A regra vale igual
dos dois lados e foi fixada antes de qualquer previsão.

**Atributos.** Os relativos ao início de vida, a temperatura ambiente, a
corrente e os **ciclos desde o início do par**, no lugar do ciclo da célula que
a classificação usa: o SOH é relativo à referência do par, e nas células que
mudam de condição (B0041 a B0044) o ciclo da célula segue contando enquanto o
SOH recomeça em 100%. Na validação, a troca baixa o RMSE do GAM de 7,09 para
6,49 p.p. Temperatura e corrente são o protocolo, com poucos valores distintos,
e entram como reta.

**λ = 3×10⁴: o mais suave equivalente ao melhor.** Validação deixando uma
célula de fora nas 20 de treino, com imputação e escala refeitas a cada rodada.
O RMSE contra λ forma um platô de 3×10³ a 3×10⁴, e vence o maior λ a até 2% do
menor RMSE (6,37 em λ = 10⁴) — a lógica do k do kNN e do agrupamento. O GAM
final usa **13,9 graus de liberdade efetivos**, contra 12 da regressão linear:
as funções saem quase retas, e o que mais o separa da regressão linear é a borda
constante.

### Validação: protocolo, rótulos, atributos e algoritmo

| RMSE (p.p.) | relativos | brutos | todos | relativos, partição aleatória | relativos, com os pares artificiais no treino |
|---|---|---|---|---|---|
| **GAM (λ = 3×10⁴)** | **6,49** | 6,88 | 6,61 | 4,98 | 7,39 |
| Regressão linear | 11,67 | 7,03 | 8,83 | 5,18 | 8,92 |
| SVR (RBF) | 6,29 | 5,82 | 5,78 | 4,23 | 5,93 |
| Random Forest | 4,99 | 5,78 | 5,95 | 1,83 | 7,99 |
| Gradient Boosting | 5,01 | 5,88 | 6,01 | 1,80 | 8,50 |

Prever a média do SOH do treino dá 11,48.

1. **Protocolo.** A partição aleatória por descarga baixa o RMSE de 1,5 a
   6,5 p.p. Nas árvores ele cai de 5,0 para 1,8: é o modelo reconhecendo a
   célula, o mesmo vazamento que a classificação mediu.
2. **Rótulos.** Os 7 pares de SOH artificial de volta ao treino pioram o
   Random Forest em 3,0 p.p., o Gradient Boosting em 3,5 e o GAM em 0,9. A
   regressão linear melhora 2,8, e não pelo rótulo: eles devolvem ao treino a
   condição 4 A / 4 °C (B0043 e B0044). Sem ela, quando B0041 — a única célula
   avaliável nessa condição — fica de fora, a regressão linear prolonga a reta
   até um RMSE de 59,7 p.p. nela.
3. **Atributos.** Sem padrão único: os relativos ajudam o GAM (0,4 p.p.) e as
   árvores (0,8 e 0,9) e atrapalham o SVR (0,5) e a regressão linear (4,6, pela
   explosão em B0041).
4. **Algoritmo.** Random Forest e Gradient Boosting ficam à frente, com 5,0; o
   GAM é o 4º de 5.

### Teste: as 8 células, avaliadas uma vez

| teste | RMSE (p.p.) | IC 95% | MAE | R² | viés | diferença de RMSE para o GAM (IC 95% pareado) |
|---|---|---|---|---|---|---|
| **GAM (λ = 3×10⁴)** | **6,88** | 4,82–9,04 | 5,08 | 0,57 | −2,2 | — |
| Regressão linear | 7,29 | 5,03–9,67 | 5,47 | 0,52 | −2,4 | +0,41 (+0,02 a +0,80) |
| SVR (RBF) | 6,28 | 3,26–8,50 | 4,30 | 0,64 | +2,5 | −0,60 (−3,44 a +1,33) |
| Random Forest | 8,45 | 4,34–11,11 | 6,14 | 0,35 | +4,0 | +1,57 (−2,64 a +4,60) |
| Gradient Boosting | 7,72 | 4,12–10,03 | 5,52 | 0,46 | +3,4 | +0,83 (−2,91 a +3,46) |

Prever a média do treino dá 10,69. Diferença positiva: a referência erra mais
que o GAM. Os intervalos vêm de reamostrar células inteiras, como na
classificação.

**A ordem dos algoritmos se inverte de novo.** Random Forest e Gradient
Boosting, os melhores na validação, são os piores no teste; o GAM sobe de 4º
para 2º, atrás do SVR. Só a diferença para a regressão linear exclui o zero, e
não resiste à correção de Bonferroni. Com 8 células o teste não separa os
modelos — o mesmo que a classificação encontrou.

**Onde o GAM erra** (`06_teste_por_celula.png`):

- **B0042 a 1 A / 4 °C**, viés de −10,3 p.p.: renormalizada no ciclo 87, como
  B0043 e B0044 na validação. A célula chega à condição já usada, e o SOH
  recomeça em 100%.
- **B0039 a 4 A / 24 °C**, RMSE de 24,4 p.p. em 12 descargas: duas delas são
  leituras isoladas de 25% e 34% numa célula que entrega de 86% a 100%.
- **B0054 a 2 A / 4 °C**, viés de −7,6 p.p. e estimativa serrilhada: tensão e
  temperatura alternam de uma descarga para a seguinte (3,01 V e 14,5 °C contra
  3,23 V e 12,0 °C) enquanto a capacidade quase não se mexe. Todos os modelos
  herdam a alternância.

**O que o GAM aprendeu** (`07_efeitos_gam.png`), em efeito típico (distância
entre os quantis de 5% e 95% de cada função nas descargas de treino): a tensão
medida na bateria, relativa ao início, move o SOH em 22,5 p.p.; a idade no par,
em 18,0; a temperatura ambiente, em 12,1 (+0,31 p.p. por °C). Re e Rct derrubam
o SOH quando sobem, como a física pede; a impedância retificada sai com o sinal
trocado, porque divide a informação com Re. A tensão na carga quase não pesa
(1,0 p.p.): o que ela diz já está na tensão medida.

### RUL: a conversão

A **perda de SOH por ciclo** de cada condição é a mediana, entre os pares de
treino dela, da inclinação de Theil–Sen do SOH medido contra o ciclo — robusta
aos saltos de regeneração que as células da NASA têm depois das pausas. Entram
todos os pares da condição, cheguem ou não a 80%: tirar a taxa só dos que
chegaram escolheria as células pelo desfecho.

| condição | 1 A / 4 °C | 2 A / 22 °C | 4 A / 43 °C | 2 A / 24 °C | 4 A / 24 °C | 2 A / 4 °C | 1 A / 44 °C |
|---|---|---|---|---|---|---|---|
| p.p. de SOH por ciclo | −0,52 | −0,35 | −0,30 | −0,21 | −0,14 | −0,12 | −0,02 |

O **fim de vida real** é a primeira de 3 descargas seguidas abaixo de 80%. As
previsões começam na 5ª descarga do par, quando a referência de início de vida
dos atributos já está fechada. Chegam a 80% 9 dos 25 pares de treino e 4 dos 10
de teste (B0018 no ciclo 74, B0034 no 9, B0046 no 21, B0054 no 56). Os demais
são censurados: deles só se pode cobrar que a previsão não anuncie o fim de vida
antes do fim da observação (alarme antecipado).

**A conversão foi escolhida na validação**, contra a tendência da própria
célula — uma reta nas últimas W estimativas, prolongada até 80% —, nos mesmos
358 instantes de 7 pares de treino:

| erro absoluto médio do RUL (ciclos) | SOH medido (oráculo) | SOH do GAM |
|---|---|---|
| **taxa da condição** | **13,3** | **28,3** |
| tendência da célula, W = 10 | 51,8 | 54,3 |
| tendência da célula, W = 20 | 34,7 | 47,2 |
| tendência da célula, W = 30 | 32,1 | 46,2 |
| tendência da célula, W = 50 | 38,5 | 50,3 |
| tendência da célula, todas as estimativas | 39,4 | 51,9 |

A taxa da condição vence com todos os modelos. A tendência erra mais no começo
da vida, quando a célula quase não perdeu capacidade e a reta prolongada passa
longe dos 80% (`08_rul_conversoes.png`).

**O oráculo** é a mesma conversão aplicada ao SOH medido: separa o erro da
conversão do erro da estimativa. Pela taxa da condição os dois se somam,
enquanto a previsão não é cortada em zero: o erro do RUL é o do oráculo mais o
erro do SOH dividido pela perda por ciclo. Numa condição que perde 0,12 p.p. por
ciclo, 5 p.p. de SOH são 40 ciclos.

### RUL no teste

| teste: 143 instantes de 4 pares | MAE (ciclos) | mediana do erro absoluto | viés | dentro de ±20% | alarme antecipado (148 instantes censurados) |
|---|---|---|---|---|---|
| oráculo (SOH medido) | 14,6 | 11,8 | +12,2 | 17% | 0% |
| **GAM** | **17,1** | **7,6** | +1,5 | 31% | 14% |
| Regressão linear | 18,4 | 7,1 | +2,6 | 36% | 14% |
| SVR (RBF) | 16,6 | 15,0 | +14,5 | 21% | 8% |
| Random Forest | 23,7 | 21,0 | +14,9 | 9% | 13% |
| Gradient Boosting | 21,8 | 20,2 | +12,3 | 13% | 11% |

| par de teste | fim de vida | MAE do GAM | MAE do oráculo | viés do SOH do GAM | o mesmo, em ciclos |
|---|---|---|---|---|---|
| B0018 · 2 A / 24 °C | ciclo 74 | 5,5 | 12,1 | −3,5 p.p. | −16,9 |
| B0046 · 1 A / 4 °C | ciclo 21 | 3,3 | 5,1 | +2,0 p.p. | +3,8 |
| B0054 · 2 A / 4 °C | ciclo 56 | 32,4 | 21,0 | −5,4 p.p. | −44,2 |
| B0034 · 4 A / 24 °C | ciclo 9 | 64,6 | 14,5 | +6,9 p.p. | +50,4 |

- **Onde a célula se degrada como as de treino, a conversão funciona.** Em
  B0018, 60% das previsões do GAM caem no cone de ±20% (`09_rul_teste_por_algoritmo.png`); em
  B0046 o erro médio é de 3,3 ciclos, num cone que ali é estreito (a vida toda
  tem 21 ciclos). Em B0018 o GAM chega a errar menos que o oráculo, mas por
  compensação: o viés do SOH (−16,9 ciclos) cancela o da taxa da condição
  (+11,8).
- **Onde a condição perde SOH devagar, o erro do SOH se multiplica.** Em
  2 A / 4 °C cada p.p. de SOH vale 8 ciclos, e a alternância de B0054 vira
  previsões que pulam entre 0 e mais de 80 ciclos.
- **B0034 tem fim de vida artificial.** A referência do SOH é uma leitura de
  100% no ciclo 45, entre vizinhas de 83% a 88%, e o par cruza 80% no ciclo 9.
  O critério de entrada só pega a leitura isolada quando o SOH já começa abaixo
  de 80%; aqui ele começa em 89%.
- **A mediana conta outra história que a média.** O GAM e a regressão linear
  têm as menores medianas do erro absoluto (7,6 e 7,1 ciclos, contra 11,8 do
  oráculo). O MAE do GAM é puxado por B0034 e B0054.
- **O alarme antecipado é o ponto fraco.** Nos pares censurados o GAM anuncia o
  fim de vida antes da hora em 14% dos instantes do teste e 34% da validação,
  contra 0% e 8% do oráculo.

**Cuidados:**

- **Ajustar agora contaminaria o teste.** A ideia natural para B0054 é converter
  a média das últimas estimativas, e não a última. Como surgiu de olhar o teste,
  ela roda como variante pós-hoc, só na validação, e lá quase não muda nada: o
  erro do GAM vai de 28,3 para 27,7 ciclos com a média de 10, e o alarme
  antecipado de 34% para 33%. Não entra no modelo e não foi avaliada no teste.
- **O RUL do teste se apoia em 4 pares.** Não há intervalo de confiança que
  valha com isso; os resultados por par dizem mais que a média.
- **Vale para células com histórico de início de vida**, como os atributos
  relativos de `normalizar.py`, e para condições que o treino conhece: a taxa de
  perda vem das células de treino na mesma condição.

### Os cinco algoritmos lado a lado

As quatro referências saem com o mesmo detalhe do GAM: todas as métricas com o
intervalo por células (`03_metricas_por_algoritmo.png`), o SOH estimado contra o
medido (`04_previsto_vs_real_por_algoritmo.png`), o erro em cada par de teste
(`05_erro_por_par.png`) e o RUL nos pares que chegam a 80%
(`09_rul_teste_por_algoritmo.png`). Cortado em 80%, o SOH estimado vira uma
classificação de fim de vida, com a mesma matriz de confusão da classificação:

| teste: 672 descargas, 317 em fim de vida | detectado | não percebido | alarme falso | saudável reconhecida | viés do SOH (IC 95%) |
|---|---|---|---|---|---|
| **GAM (λ = 3×10⁴)** | 278 | 39 | 45 | 310 | −2,2 p.p. (−5,1 a +0,4) |
| Random Forest | 112 | 205 | 28 | 327 | +4,0 (−1,2 a +8,4) |
| Gradient Boosting | 128 | 189 | 34 | 321 | +3,4 (−1,2 a +7,3) |
| SVR (RBF) | 177 | 140 | 3 | 352 | +2,5 (−0,6 a +4,9) |
| Regressão linear | 277 | 40 | 48 | 307 | −2,4 (−5,4 a +0,4) |

- **Menor RMSE não quer dizer melhor alarme.** O SVR tem o menor RMSE (6,28
  p.p.) e não percebe 140 das 317 descargas em fim de vida (44%); Random Forest
  e Gradient Boosting não percebem 65% e 60%. Os três veem, em média, as células
  mais saudáveis do que estão (+2,5 a +4,0 p.p.). GAM e regressão linear erram
  para o outro lado (−2,2 e −2,4 p.p.): deixam passar 12% e 13% do fim de vida,
  ao custo de 45 e 48 alarmes falsos. Com 8 células nenhum desses vieses é
  firme — todos os intervalos incluem o zero —, então a diferença nos fins de
  vida não percebidos é destas células de teste, não uma regra dos algoritmos.
- **Os pares difíceis são os mesmos para os cinco** (`05_erro_por_par.png`). Em
  B0039 a 4 A / 24 °C o RMSE fica entre 24 e 26 p.p. em todos, pelas duas
  leituras isoladas de 25% e 34%; em B0042 a 1 A / 4 °C, o par renormalizado,
  todos estimam o SOH de 8 a 11 p.p. abaixo do medido. Em 7 dos 10 pares os
  cinco erram para o mesmo lado: o lado do erro depende mais do par que do
  algoritmo.
- **Onde eles se separam.** A alternância de tensão e temperatura de B0054 pesa
  muito mais no GAM e na regressão linear (RMSE de 10,0 e 11,2 p.p.) que no SVR
  e nas árvores (de 4,4 a 5,2). Em B0034 é o contrário: Random Forest e
  Gradient Boosting superestimam o SOH em 12,0 e 10,5 p.p. (RMSE de 12,5 e
  10,9), e o GAM erra 5,8, com viés de +0,4.
- **No RUL, SVR e GAM ficam próximos na média, por caminhos opostos**
  (`09_rul_teste_por_algoritmo.png`). Nos 4 pares, o SVR erra 16,6 ciclos e o
  GAM 17,1, mas o GAM acerta B0018 (5,5 ciclos, contra 18,2 do SVR) e erra
  B0054 (32,4 contra 12,6); a regressão linear se parece com o GAM nos dois.
  Random Forest e Gradient Boosting erram 21,3 e 20,0 ciclos em B0018, onde o
  viés positivo do SOH vira vida remanescente longa demais. Em B0034, de fim de
  vida artificial, todos erram de 56 a 100 ciclos.

Em `saida_nasa/regressao/tabelas/`:

| | |
|---|---|
| `escolha_de_lambda.csv` | RMSE por λ nos três conjuntos de atributos e com o ciclo da célula no lugar da idade no par |
| `comparacao.csv` | modelo × atributos × validação × rótulos no treino: RMSE, MAE, viés e R² |
| `validacao_por_par.csv` | erro de cada modelo em cada par de treino, quando a célula dele é a deixada de fora |
| `teste.csv` | métricas no teste, IC por reamostragem de células (o do viés também), as quatro casas do limiar de 80% e diferença pareada para o GAM, com e sem Bonferroni |
| `teste_por_par.csv` | RMSE e viés de cada modelo em cada par de teste, inclusive o que fica fora das métricas |
| `predicoes_teste.csv` | cada descarga de teste com o SOH medido, as estimativas dos cinco modelos, o RUL real e o RUL de cada modelo e do oráculo |
| `efeitos_gam.csv`, `efeitos_resumo.csv` | as funções do GAM final na unidade física, e o efeito típico de cada uma |
| `taxas_por_condicao.csv` | a inclinação de Theil–Sen de cada par de treino e a taxa da condição |
| `fins_de_vida.csv` | o ciclo do fim de vida de cada par avaliável, ou censurado |
| `rul_conversoes_validacao.csv` | as conversões comparadas na validação, por fonte do SOH e por fração da vida |
| `rul_variante_media_movel.csv` | a variante pós-hoc, média das últimas M estimativas antes de converter, só na validação |
| `rul_resumo.csv` | o erro do RUL por fonte, na validação e no teste |
| `rul_teste_por_par.csv` | o erro do RUL por par e algoritmo no teste, com o viés do SOH convertido em ciclos |

Em `saida_nasa/regressao/figuras/`, na ordem do artigo:

| | |
|---|---|
| `01_escolha_de_lambda.png` | o RMSE contra λ, com a faixa de equivalência |
| `02_protocolo_rotulos_atributos_algoritmo.png` | o efeito do protocolo, dos rótulos, dos atributos e do algoritmo na validação |
| `03_metricas_por_algoritmo.png` | RMSE, MAE, R² e viés de cada algoritmo, no teste com IC e na validação |
| `04_previsto_vs_real_por_algoritmo.png` | SOH estimado contra medido de cada algoritmo, com as casas do limiar de 80% |
| `05_erro_por_par.png` | o RMSE e o viés de cada algoritmo em cada par de teste |
| `06_teste_por_celula.png` | o SOH medido e o estimado pelo GAM em cada par de teste |
| `07_efeitos_gam.png` | o que move o SOH segundo o GAM, atributo por atributo |
| `08_rul_conversoes.png` | taxa da condição contra tendência da célula, por fração da vida |
| `09_rul_teste_por_algoritmo.png` | o RUL de cada algoritmo nos pares de teste que chegam a 80%, com o oráculo |


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
- **1.526 dos 7.565 `start_time`** estão corrompidos, com ano `2` no lugar de
  `2008`. A ordem cronológica confiável é a de `uid`, que concorda com o relógio
  em todas as 34 células onde o relógio é legível. `carga.py` depende disso para
  parear cada carga com a descarga seguinte.
- **32 dos 2.815 ensaios de carga** não têm trecho sob carga utilizável.

As marcações ficam na coluna `alerta` das tabelas de métricas. Nada é apagado.

## Fonte e licença

[NASA PCoE Data Repository](https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/) — domínio público (obra do governo dos EUA).

> Saha, B., & Goebel, K. (2007). *Battery Data Set*. NASA Ames Prognostics Data
> Repository, NASA Ames Research Center.
