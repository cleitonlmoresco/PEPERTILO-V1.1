# PEPERTILO V9 — Consolidação de bancada

## Objetivo
Unificar M5 + M6 + MPU PRO + base de programadores em uma ficha operacional, preservando todas as evidências.

## Regras
- M5 continua sendo fonte de topologia.
- M6 continua sendo fonte documental de tabelas.
- MPU PRO continua sendo fonte do pin-map documental do MCU.
- Programadores só são marcados como documentados quando existe evidência explícita no cadastro.
- Conflitos M5/M6 bloqueiam a indicação operacional automática.
- Ausência de pin-map documental bloqueia operação de programação.

## Saída
`ficha_bancada` contém:
- componente: part number, família, encapsulamento, maskset e orientação;
- pinagem consolidada;
- programadores e cabos documentados;
- resumo de correlação;
- fontes brutas M5/M6/MPU.

## Testes
`debug_ficha_bancada.py`: 8/8 PASS.
`consolidacao_bancada.py` e `roteador.py`: compilação OK.
