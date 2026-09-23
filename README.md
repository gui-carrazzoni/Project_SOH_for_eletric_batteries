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
src/                       os 13 scripts, cada um executável sozinho
cleaned_nasa_dataset/      os dados (não versionados, reconstruídos pelo script)
manifesto_nasa.csv.gz      as impressões digitais que verificam os dados
saida_nasa/                tudo que a análise produz
├── graficos/              os sete gráficos gerais
├── correlacao/            tabela da Tabela 2 e relevância dos atributos
├── preprocessado/         a tabela limpa, pronta para modelar
├── descritiva/            distribuições do alvo e da condição
├── normalizado/           divisão por bateria, referência de vida, escala
├── curvas/                áreas e forma da descarga, mais o mapa de calor
├── carga/                 a carga como processo próprio
└── cluster/               tudo que é agrupamento
    ├── agrupamento/                          grupos descobertos no dado
    ├── grupo_corrente_temperatura/           esquema sem a tensão de corte
    ├── grupo_corrente_temperatura_corte/     esquema com a tensão de corte
    └── comparacao/                           qual dos dois esquemas ganha
```

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

Os sete últimos scripts da cadeia vieram de uma revisão com um profissional de
baterias. Seis deles formam um encadeamento: `curvas.py` lê as descargas brutas
uma vez e os outros trabalham sobre o cache que ele deixa. `carga.py` é
independente — tem cache próprio e lê os ensaios de carga, que nenhum outro
script toca.

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

Gera `saida_nasa/` com três tabelas de métricas e sete gráficos:

| | |
|---|---|
| `metricas_descargas.csv` | uma linha por descarga: condição, capacidade, SoH, duração, tensão final, temperatura máxima |
| `metricas_impedancia.csv` | uma linha por ensaio de impedância: Re, Rct, SoH da descarga mais próxima |
| `resumo_baterias.csv` | uma linha por bateria, incluindo a correlação entre resistência e SoH |
| `graficos/01…07` | capacidade por condição, SoH, efeito da condição, resistência, predição de SoH, curvas de descarga, espectro |

## `correlacao_soh.py`

```bash
python src/correlacao_soh.py                # monta, correlaciona, plota
python src/correlacao_soh.py --sem-graficos  # so as tabelas
python src/correlacao_soh.py --remontar      # ignora o cache e rele as 2.794 curvas
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
python src/limpeza.py                   # politica padrao
python src/limpeza.py --teto-falta 0.3  # mais rigoroso com coluna esburacada
python src/limpeza.py --grupo-minimo 5  # aceita grupos mais curtos
python src/limpeza.py --podar           # remove tambem os pares redundantes
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

## `curvas.py`

```bash
python src/curvas.py              # usa cache
python src/curvas.py --remontar   # relê as 2.794 curvas
python src/curvas.py --amostra 50 # teste rápido
```

Lê as curvas de descarga **uma única vez** e escreve
`saida_nasa/curvas/features_curvas.csv` — 2.794 × 87. Daqui saem as três áreas,
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
python src/grupos.py              # k pela silhueta
python src/grupos.py --grupos 5   # força k
```

Agrupamento hierárquico (Ward) das descargas por **comportamento medido**, para
confrontar com o rótulo nominal de `test_condition`. Escreve
`saida_nasa/cluster/agrupamento/`.

A unidade agrupada é a bateria × condição, e só os ciclos de início de vida
entram — com todos os ciclos, uma célula degradada num regime brando pareceria
uma célula nova num regime severo, e o cluster mediria degradação em vez de
regime. Corrente e temperatura ficam **fora** dos atributos de propósito: incluí-
las faria o cluster reproduzir o rótulo nominal por construção.

**O que ele encontrou foi a tensão de corte.** Em 4 das 6 condições nominais que
o agrupamento partiu, a divisão segue exatamente o corte. O caso mais limpo é
`2 A / 4 C`: oito células, mesmo protocolo nominal, todas do ciclo 0.

| células | corte | queda de tensão |
|---|---|---|
| B0049, B0050, B0053, B0054 | 2,0 e 2,2 V | 1,58 – 1,84 V |
| B0051, B0052, B0055, B0056 | 2,5 e 2,7 V | 1,07 – 1,34 V |

Sem sobreposição. `test_condition` é corrente × temperatura e **ignora um
terceiro eixo de protocolo** que muda o comportamento de descarga.

Duas ressalvas honestas. A silhueta escolhe k=2, mas é patologia: `4 A / 4 C`
entrega 0,062 Ah contra 1,7 das demais, e é tão distante que infla a silhueta de
qualquer partição que o isole; k=5 é o último antes de fragmentar em grupos
unitários. E `queda_V` está entre os atributos, sendo quase determinado pelo
corte (r = −0,95) — o cluster em parte descobriu uma variável que lhe foi
entregue.

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
