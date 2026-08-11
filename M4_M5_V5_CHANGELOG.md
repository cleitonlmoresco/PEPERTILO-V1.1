# PEPERTILO Bancada V5 — M4 → M5 Terminalização

## Objetivo
Transformar cada terminal de conector em uma unidade semântica explícita antes de entrar no M5.

Contrato:
`CON1 / PINO 410 -> SEGMENTO 123 -> REDE`

## Alterações
- M4 cria `terminais` enriquecidos.
- Cada terminal contém `conector_id`, `numero`, `x`, `y`, `segmento_fio`, candidatos, `cor_fio`, `bitola`, fontes e evidências.
- Cor/bitola vêm exclusivamente do documento nesta etapa.
- Se o texto de cor/bitola estiver longe do terminal, o terminal pode herdar o atributo já associado ao segmento.
- M5 usa o vínculo explícito terminal→segmento como evidência primária.
- O fallback por proximidade recebe score baixo e é identificado como `proximidade_fallback`.
- O M5 divide a aresta real do grafo no ponto de snap do terminal, evitando terminal isolado do segmento.
- Um terminal isolado não é exportado como conexão confirmada apenas por possuir cor/bitola.
- Conexão confirmada exige pelo menos dois pinos ou um destino semântico.
- Cores e bitolas não são mais tratados como periféricos.
- Adicionado `TerminalConector` e `Conector` ao modelo de dados.

## Validação
- Regressão: 12/12 testes PASS.
- Teste dedicado: `CON1/PINO 34 + PINO 46 -> segmento -> rede`, PASS.
- Diagrama ECU real: 2 conectores, 8 terminais; 7 terminais receberam segmento.
- M5 real não fabricou conexões onde não havia evidência suficiente.
- Compilação completa: PASS.
- AST dos módulos críticos: PASS.

## Observação
PaddleOCR/Flask não estão instalados neste ambiente de validação; o pipeline de processamento foi testado com Tesseract e os módulos web foram validados por AST/compilação.
