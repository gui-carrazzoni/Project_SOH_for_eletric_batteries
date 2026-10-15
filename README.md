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
src/                       os 14 scripts, cada um executável sozinho
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
├── classificacao/         fim de vida por kNN, contra as famílias da literatura
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

Os sete scripts de `curvas.py` a `carga.py` vieram de uma revisão com um
profissional de baterias. Seis deles formam um encadeamento: `curvas.py` lê as
descargas brutas uma vez e os outros trabalham sobre o cache que ele deixa.
`carga.py` é independente — tem cache próprio e lê os ensaios de carga, que
nenhum outro script toca. `classificacao.py` fecha a cadeia: lê só a saída de
`normalizar.py`, mas fica por último para que nada que rode depois dela precise
ser refeito.

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

Escreve `saida_nasa/classificacao/`, em 1 a 2 min (quase tudo Random Forest e
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
   da mesma célula em 90% dos casos (`vazamento.csv`). O modelo reconhece a
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

| | |
|---|---|
| `escolha_de_k.csv` | acurácia balanceada por k, nos três conjuntos de atributos |
| `comparacao.csv` | modelo × atributos × validação (por célula e aleatória): acurácia balanceada, sensibilidade, especificidade, F1, AUC e o k do kNN |
| `vazamento.csv` | de onde vêm os vizinhos na partição aleatória |
| `validacao_por_celula.csv` | o acerto do kNN em cada célula de treino, quando ela é a deixada de fora, com e sem a restrição ao grupo |
| `variante_mesmo_grupo.csv` | acurácia balanceada por k, com e sem a restrição ao grupo de comportamento |
| `teste.csv` | métricas no teste, IC por reamostragem de células e diferença pareada para o kNN em acurácia balanceada, AUC e F1, com e sem Bonferroni |
| `teste_por_celula.csv` | acertos, alarmes falsos e fins de vida não detectados por célula |
| `predicoes_teste.csv` | cada descarga de teste com a previsão, o voto e os três vizinhos que a decidiram |
| `01_escolha_de_k.png` | a curva de k nos três conjuntos, com a faixa de equivalência |
| `02_protocolo_atributos_algoritmo.png` | o efeito do protocolo, dos atributos e do algoritmo na validação |
| `03_teste_comparacao.png` | o teste com IC ao lado da validação, por algoritmo |
| `04_matriz_confusao.png` | a matriz de confusão do kNN no teste |
| `05_teste_por_celula.png` | SOH contra ciclo em cada célula de teste, com os erros marcados |
| `06_variante_mesmo_grupo.png` | a variante pós-hoc contra o modelo avaliado, em toda a grade de k |
| `07_curvas_roc.png` | as curvas ROC dos cinco modelos no teste, com a AUC e o ponto de operação do kNN |


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
