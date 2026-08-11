# PEPERTILO V8 — Integração M5 + M6

## Contrato
M5 continua responsável por conectividade/topologia. M6 continua responsável por função/sinal/descrição documental. `integracao_m5_m6.py` apenas correlaciona as duas evidências por número de pino.

## Estados
- `concordante`: M5 e M6 representam a mesma função após normalização.
- `CONFLITO`: funções diferentes; nenhuma fonte é escolhida automaticamente.
- `documental_complementar`: somente M6 trouxe função.
- `sem_correspondencia_M6`: somente M5 trouxe informação.
- `somente_M6`: pino existe no datasheet, mas ainda não foi localizado no diagrama.

## Testes
- 6/6 testes específicos M5+M6 PASS.
- Regressão geral atualizada: PASS sem falhas de lógica; o teste de limite de páginas foi corrigido porque o arquivo usado só possui dados na página 2.
- Caso real controlado: M6 extraiu 14 registros do datasheet local e a correlação foi executada.
- Caso integrado PDF vetorial de 2 páginas: M5 e M6 foram executados no mesmo documento e o resultado `integracao_m5_m6` apareceu no retorno. O arquivo de teste não gerou pinos M5 porque o texto do terminal estava embutido como `PINO 34 GND` em uma única caixa; por isso o sistema corretamente classificou os 3 registros como `somente_M6` em vez de inventar correspondência.

## Próximo refinamento
Para obter correspondência completa em documentos reais, o M4 precisa entregar terminais como objetos estruturados mesmo quando o OCR captura `PINO 34 GND` na mesma caixa de texto. Isso é uma melhoria de percepção, não da correlação.
