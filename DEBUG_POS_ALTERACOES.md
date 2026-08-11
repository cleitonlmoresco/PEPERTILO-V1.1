# DEBUG PEPERTILO-BANCADA-V4

Data: 2026-08-11

## Resultado
- 10/10 testes de regressão automatizados passaram.
- Compilação Python completa passou.
- AST de M4/M5/MPU/M6/roteador/app passou.

## Correções aplicadas após o debug
1. M5 não trata `curvas` como `emendas`. Curvas gráficas não podem criar junção elétrica.
2. M5 não duplica terminais de conectores como `PIN:n`.
3. M4 reconhece conectores sem moldura fechada por agrupamento de terminais numéricos.
4. M6 agora aplica `limite_paginas` também no caminho pdfplumber/OCR.
5. M4 publica `emendas` separadamente para o M5.
6. Foi adicionado `debug_pipeline.py` com regressão de topologia, conectores, MPU, M6, M11 e contrato do roteador.

## Testes reais
- Delphi MT20U: 2 grupos de conectores e 8 terminais foram reconhecidos pelo fallback OCR. O M5 construiu 1076 arestas e identificou 65 junções / 21 cruzamentos sem conexão. Ainda não há conexões semânticas suficientes para declarar a pinagem final.
- MC68HC912BC32: 80 pinos documentais identificados; orientação detectada no teste; programadores retornados pela base.
- Manual CarProg: 5 fios, 2 MCUs e 2 máscaras extraídos.
- Datasheet de teste: limite de páginas validado.

## Limitações do ambiente de debug
- PaddleOCR não está instalado no ambiente de teste; M4/M6 fizeram fallback para Tesseract.
- Flask não está instalado no ambiente de teste; por isso o `web/app.py` foi validado por AST/compilação, mas não foi iniciado por HTTP.

## Próximos gargalos
- Reconhecimento de bitola/cor no diagrama real com OCR localizado.
- Associação terminal -> fio -> rede.
- Ponte gráfica real como evidência negativa de conexão.
- Continuidade entre páginas por identificadores de rede.
- M6 com reconstrução de tabela por coordenadas/grade.
