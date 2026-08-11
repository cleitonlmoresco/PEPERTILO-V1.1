# PEPERTILO Bancada V2 — base de refatoração

Esta versão preserva M0–M11 e acrescenta uma camada semântica/bancada sem fingir compatibilidade de programador que não foi comprovada.

## O que foi integrado
- `core/modelos.py`: modelos Pino, Fio, Conexao, Evidencia, MCU, Programador, Cabo, Medicao e ServicoBancada.
- `core/evidencias.py`: normalização semântica, aliases e agrupamento de conexões.
- `base_programadores.py`: aproveita os programadores que já existiam no projeto.
- `bancada_db.py`: SQLite local para serviços, medições e notas.
- `bancada.py`: APIs e tela inicial da bancada.
- `web/templates/bancada.html`: tela de registro de serviço e listagem de programadores.

## Regra de segurança
A base de programadores é tratada como catálogo. `cadastrado` não significa `compatibilidade confirmada` para um MCU específico.

## Próxima refatoração do núcleo
1. M5: topologia por ponto-segmento e snap hierárquico.
2. M6/M9/M10: reconstrução de tabelas por posição X/Y.
3. M11: parser semântico para separar fio, MCU, máscara, instrução e pino.
4. MPU: abandonar numeração geométrica genérica e exigir pin-map do componente/package.
5. M12: correlacionador de evidências.
6. M13: validador e detecção de conflito.
7. M16: biblioteca de programador + cabo/adaptador + interface + evidência.
8. M7: saída agrupada no formato `34, 46, 88 / GND / BROWN`, mantendo os pinos individualizados internamente.

## Limitação conhecida mantida nesta etapa
O módulo `modo_mpu.py` ainda contém uma estimativa geométrica de 100 pinos. Ela deve ser considerada **não validada** e não deve ser usada como pinagem definitiva até a implementação de um banco de pin-maps por MCU/encapsulamento.

## Smoke test realizado em 11/08/2026
- `01_diagrama_eletrico_vetorial.pdf`: M1 => `pdf_vetorial`; M2 extraiu 14 linhas/64 textos/1 retângulo; M5 passou a construir o grafo e rastrear conexões.
- `02_datasheet_mcu_tabela.pdf`: M1 => `manual` após heurística de tabela vetorial.
- `03_manual_carprog_texto_imagens.pdf`: M1 => `manual`; M11 separa 5 fios, 2 MCUs e 2 máscaras sem transformar cor em pino.
- `05_teste_integrado_4_paginas.pdf`: M1 => `manual` como documento misto/textual.
- O M2 não depende mais de `pdfplumber`/`y0` para a geometria vetorial.

## Limitações ainda abertas
- M5 ainda precisa de topologia de cruzamentos/junções e continuidade multi-página mais sofisticada.
- O modo MPU não deve ser usado como pinagem definitiva enquanto o pin-map por MCU/package não estiver implementado.
- A base de programadores contém registros existentes no projeto, mas cabos/compatibilidades específicas ainda precisam de evidência documental.
