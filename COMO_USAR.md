# Conversor do Oxford Battery Degradation Dataset

`converter_oxford_mat.py` transforma o `.mat` do dataset em:

- **CSVs** com a série temporal completa (um arquivo por célula);
- **uma planilha Excel** com métricas por ciclo e gráficos nativos;
- **PNGs** com os gráficos de degradação.

Roda em Linux, macOS e Windows, com Python 3.9 ou mais novo. Não há caminho
fixo no código: o `.mat` e a pasta de saída vêm da linha de comando.

## Instalação

```bash
python -m venv venv

# Linux / macOS
source venv/bin/activate
# Windows (PowerShell)
venv\Scripts\Activate.ps1

python -m pip install -r requirements.txt
```

O ambiente virtual evita o erro `externally-managed-environment` que aparece em
Arch, Debian/Ubuntu recentes e Fedora quando se instala pacote direto no sistema.

## Uso

```bash
# procura um .mat no diretório atual e escreve em ./saida_oxford/
python converter_oxford_mat.py

# caminhos explícitos
python converter_oxford_mat.py -e dados/Oxford_1.mat -s resultados/

# só a planilha e os gráficos (pula os ~800 MB de CSV)
python converter_oxford_mat.py --sem-csv

# só algumas células
python converter_oxford_mat.py -c Cell1 Cell2 Cell3

# sem os PNGs (dispensa o matplotlib)
python converter_oxford_mat.py --sem-graficos
```

`python converter_oxford_mat.py --help` lista todas as opções.

## Requisitos de máquina

Medido no dataset completo de 266 MB (8 células, 15,2 milhões de linhas):

| Recurso | Conversão completa | Com `--sem-csv` |
|---|---|---|
| RAM (pico) | 0,22 GB | 0,18 GB |
| Disco | ~800 MB | ~1 MB |
| Tempo | ~30-70 s (varia com o disco) | ~5 s |

O script lê uma célula de cada vez. Como o MAT v5 comprime cada variável
separadamente, isso não custa tempo a mais e mantém a memória baixa — roda
tranquilo em qualquer máquina com 2 GB de RAM livre.

## Saída

```
saida_oxford/
├── <nome_do_mat>.xlsx        # Leia-me, Resumo_Celulas, Metricas_por_Ciclo,
│                             # 4 abas dinâmicas, Anomalias, 1 aba de curvas
│                             # por célula — com gráfico nativo do Excel
├── csv_dados_brutos/
│   └── Cell1.csv ...         # celula,ciclo,ensaio,tempo_s,tensao_V,carga_mAh,temperatura_C
└── graficos/
    ├── 01_capacidade_vs_ciclo.png
    ├── 02_taxa_degradacao.png
    ├── 03_curvas_descarga_por_celula.png
    └── 04_temperatura_vs_ciclo.png
```

Os dados ponto a ponto ficam em CSV, e não no Excel, porque o dataset tem
15,2 milhões de linhas — o limite do Excel é 1.048.576 por aba.

## Controle de qualidade

O dataset tem defeitos de medição reais. O script os detecta e os registra na
coluna `alerta` da aba `Metricas_por_Ciclo` e na aba `Anomalias`. **Nada é
apagado** — os pontos marcados apenas saem das linhas e da escala dos gráficos,
com nota de rodapé dizendo o que foi removido e por quê.

| alerta | critério | o que costuma ser |
|---|---|---|
| `temperatura_<ensaio>` | média a mais de 5 °C da mediana daquele ensaio | termopar solto ou câmara térmica fora de regime |
| `1C_abaixo_do_OCV` | capacidade a 1C abaixo de 95 % da capacidade OCV do mesmo ciclo | o ensaio lento do mesmo ciclo achou mais carga na célula, então o valor a 1C não é a capacidade dela — mas a causa física não sai destes dados |
| `ocv_inconsistente` | carga e descarga OCV do mesmo ciclo discordam mais de 3 % | ensaio interrompido |

A aba `Anomalias` traz, para cada ponto marcado, a capacidade do **ciclo
seguinte** e um diagnóstico. Esse é o teste que separa os dois casos: capacidade
perdida não volta. Se o valor seguinte se recupera, o problema estava na medição;
se não se recupera, pode ser a célula.

Os limiares saem da distribuição do próprio dataset (a razão 1C/OCV tem mediana
0,991 e percentil 0,5 % em 0,949, daí o corte em 0,95), e estão no topo do
script como constantes, caso você queira apertá-los ou afrouxá-los.

## Sobre os gráficos

O SoH é a capacidade dividida pelo primeiro ciclo da própria célula. Como as
oito partem de capacidades quase idênticas (727 a 739 mAh), a curva de SoH tem
**exatamente a mesma forma** da curva de capacidade — a correlação entre as duas
é 1,000 para todas as células. Por isso não há um PNG de SoH: no lugar dele vai
a **taxa de degradação**, que mostra o que a curva de capacidade não mostra
(onde a degradação acelera). Na planilha o SoH continua, com a linha de 80 %,
que responde a outra pergunta: em que ciclo cada célula cruza o fim de vida.

A legenda dos gráficos é ordenada pela posição final de cada linha, e não em
ordem alfabética, para que a ordem na legenda seja a mesma ordem em que as
linhas aparecem na borda direita.

## Observações

- **Formato do `.mat`**: o script lê MAT-file v5 (o formato do dataset). Se o
  arquivo tiver sido salvo como **v7.3**, que é HDF5, o script detecta e avisa —
  reexporte no MATLAB com `save('arquivo.mat', '-v7')`.
- **Nomes das células e dos ensaios** são lidos do próprio arquivo, não estão
  fixos no código, então os outros datasets Oxford (2 a 9) também funcionam.
- **Ensaio de referência**: usa `C1dc` (descarga a 1C) para capacidade, SoH e
  curvas; se não existir, escolhe automaticamente outro ensaio de descarga.
- **`matplotlib` é opcional** — sem ele o script gera CSV e Excel normalmente e
  avisa que pulou os PNGs.
