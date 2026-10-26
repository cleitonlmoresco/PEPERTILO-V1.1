# Correlação documentação `.mht` ↔ arquivos `.ori` (ZIPs)

## Método

- 2.953 arquivos de ajuda em `help\` (`.mht`, em DEU/ENU/FRA).
- 312 ZIPs em `res\ori\<protocolo>\`.
- Extração do texto ASCII dos `.mht` e busca pelos códigos-base dos ZIPs.

## Resultado

| Métrica | Valor |
|---|---|
| Match de nome completo (`A142_275`) | 0 / 312 (nunca aparece literal) |
| Match por código-base (`A142`) | **280 / 312** |
| Sem match | 32 / 312 |

O identificador do `.ori` é o **código-base** (letra + número), não o nome do
arquivo. Ele aparece dentro dos manuais de protocolo `.mht`.

## Exemplos

| `.ori` | Protocolos / manuais que o referenciam |
|---|---|
| `A142_275` | `L_0048`, `L_0184`, `L_0380`, `L_0457`, `L_0606`, `L_0687` |
| `D410_446/511/700` | `144300K201_18/19/20/27/28`, `EDC17_FAL` |
| `Y13_Y896` | `EDC17_DEUTZ`, `SDI6_PORSCHE_TPROT8`, `L_0255`, `L_0329`, `L_0414` |
| `B101_091` | `M17_KTM`, `M17_POLARIS`, `ME17_SUZUKI`, `MED17_MASERATI_GPT` |

## Interpretação

O código-base do arquivo original mapeia para um conjunto de **protocolos ECU**.
Isso confirma o modelo de dados: *arquivo original → protocolo → manual*.
O `.ori` é o backup "virtual read" do firmware stock daquele protocolo.
