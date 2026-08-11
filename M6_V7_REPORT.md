# PEPERTILO M6 V7 — DEBUG E TABELAS COMPLEXAS

## Alterações
- descoberta de cabeçalho por pontuação, não por primeira linha;
- suporte a colunas Pino/Sinal/Função/Descrição/Tipo;
- continuação de tabela entre páginas com herança de cabeçalho;
- reconstrução por coordenadas X/Y quando a tabela não possui grade;
- múltiplas estratégias do pdfplumber;
- fallback OCR estruturado para Tesseract quando PaddleOCR não está disponível;
- saída detalhada preservando página, origem, cabeçalho, tipo e evidências;
- compatibilidade mantida com `extrair_datasheet()` retornando `{pino: função}`;
- limite_paginas aplicado em todas as rotas;
- deduplicação por página/pino;
- confiança diferenciada por backend, sem afirmar certeza estatística inexistente.

## Testes
- Datasheet local com 14 registros: PASS
- Tabela multipágina: PASS
- Continuação sem cabeçalho na terceira página: PASS
- Limite de 1 página: PASS
- Tabela rasterizada via Tesseract: PASS (6 registros)
- AST M6 + M7 + roteador + web/app: PASS

## Resultado
M6 deixa de ser apenas `pino -> função` e passa a produzir registros estruturados. A API antiga continua funcionando para não quebrar os módulos existentes.
