# PEPERTILO V1.1

Pipeline de leitura de diagramas elétricos, datasheets e manuais de bancada.
A versão V1.1 usa **PyMuPDF** para extrair a geometria de PDFs vetoriais e
**NetworkX** para reconstruir a topologia (pinos, fios, periféricos e ECU).

## Requisitos

- Python 3.10 ou superior
- Tesseract OCR instalado e disponível no `PATH` (fallback de OCR para imagens)
- Opcional: PaddleOCR/PaddlePaddle para OCR de maior qualidade

## Instalação

```powershell
cd C:\Users\globaltec\github\PEPERTILO-V1.1
python -m venv ..\.venv-pepertilo
..\.venv-pepertilo\Scripts\python.exe -m pip install --upgrade pip
..\.venv-pepertilo\Scripts\python.exe -m pip install -r requirements.txt
```

## Uso pela linha de comando

```powershell
..\.venv-pepertilo\Scripts\python.exe roteador.py <arquivo> [limite_paginas]
```

Exemplos:

```powershell
# PDF vetorial (a ECU é detectada mesmo quando desenhada como path fechado)
..\.venv-pepertilo\Scripts\python.exe roteador.py 03_teste_vetorial_local.pdf

# Limitar a leitura às 5 primeiras páginas
..\.venv-pepertilo\Scripts\python.exe roteador.py manual.pdf 5
```

O classificador escolhe automaticamente a rota: PDF vetorial, PDF rasterizado,
imagem limpa, foto de celular ou manual/datasheet.

## Interface web

```powershell
..\.venv-pepertilo\Scripts\python.exe web\app.py
```

Variáveis de ambiente:

| Variável | Padrão | Descrição |
| --- | --- | --- |
| `FLASK_HOST` | `0.0.0.0` | Endereço de escuta |
| `FLASK_PORT` | `5000` | Porta HTTP |
| `FLASK_DEBUG` | `false` | Ativa o modo debug do Flask |

## Desenvolvimento

- `requirements.txt`: runtime completo (inclui o OCR opcional com Paddle).
- `requirements-ci.txt`: dependências leves usadas no CI, sem Paddle/Tesseract.
- `requirements-dev.txt`: runtime + Ruff.
- Lint: `ruff check .`
- Testes: `python -m unittest discover -s tests -v`

O código usa `import pymupdf as fitz` (PyMuPDF >= 1.24). O alias `fitz` é mantido
para preservar a API usada pelo projeto; o nome antigo do módulo está depreciado
no PyMuPDF 2.x.

Nunca versione `.env`, chaves ou PDFs de clientes. Em produção, defina
`SECRET_KEY` forte e mantenha `FLASK_DEBUG` desligado.

O workflow de CI pronto está em `ci/github-actions.yml`. Para ativá-lo, copie
para `.github/workflows/ci.yml`; o token do GitHub precisa do escopo `workflow`.

## Testes

```powershell
..\.venv-pepertilo\Scripts\python.exe -m unittest discover -s tests -v
```

A suíte cobre o diagrama sintético de 30 pinos (`A1`..`A30`), rótulos
compostos (`PINO 20 - INJ1`), ECU como path fechado, agrupamento de palavras e
o limite de páginas.

## Correções desta branch (`fix/estabilidade`)

- **ECU em path fechado**: caixas desenhadas como 4 retas + fechamento agora
  são reconstruídas como retângulo, além dos itens `re`.
- **Pinos alfanuméricos**: `A1`, `A30`, `PIN 3` e `PINO 20 - INJ1` são
  reconhecidos (antes só dígitos puros).
- **Rótulos com espaço**: `SENSOR 1` e `PINO 1` eram separados pelo
  `get_text('words')`; agora são agrupados por proximidade horizontal.
- **Fios desenhados como curvas**: curvas de Bézier são amostradas em
  segmentos de reta; antes eram descartadas e o grafo ficava sem fios.
- **BFS pino→periférico**: o rastreamento usava o nó local no grafo global
  (prefixado por página) e nunca encontrava o ponto de partida.
- **Limite de páginas** propagado até a extração vetorial.
- **Sem conexões duplicadas**: redes com periférico identificado não são
  contadas duas vezes.

## Estrutura

| Módulo | Arquivo | Função |
| --- | --- | --- |
| M0 | `logger_erros.py` | Logging e tratamento de erros |
| M1 | `classificador.py` | Classificação do arquivo de entrada |
| M2 | `extracao_vetorial.py` | Extração de linhas, textos e retângulos (PyMuPDF) |
| M3 | `restauracao_img.py` | Restauração de imagens |
| M4 | `deteccao_simbolos.py` | Detecção de conectores e terminais |
| M5 | `grafo_rastreador.py` | Grafo topológico e rastreamento de conexões |
| M6 | `extracao_datasheet.py`, `extracao_manual.py` | Tabelas de pinos e manuais |
| — | `roteador.py` | Orquestra o pipeline |
| — | `web\app.py` | Interface Flask |

## Limitações

- O OCR Paddle pode falhar em algumas máquinas; nesse caso o pipeline usa o
  Tesseract automaticamente.
- A extração vetorial depende da camada de desenho do PDF. PDFs que são apenas
  imagem devem usar a rota rasterizada/foto.
