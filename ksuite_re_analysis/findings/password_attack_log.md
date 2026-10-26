# Log do ataque à senha dos `.ori`

## ✅ RESOLVIDO (via engenharia reversa, não força bruta)

```
Senha: -%7B5-FA45+48DA7+72F5-8E9C5%4F5A68%+
```

Aberta em **312/312 ZIPs**. A senha é **decifrada em runtime** por XOR na função
RVA `0x0000A160`. Detalhes completos em `password_discovery.md`.

> As tabelas abaixo ficam como registro histórico das tentativas que falharam.

---

## Alvo

`res\ori\<protocolo>\<CODIGO>.zip` → contém 1 arquivo `.ori`, **ZipCrypto + deflate**.
Todos os 312 usam o mesmo esquema; a senha provavelmente é a mesma para todos.

## Tentativas e resultados

| # | Ataque | Candidatos | Resultado |
|---|---|---|---|
| 1 | Senhas públicas de fóruns (`ardayunus68`, `mhh3001mhh`, `v93vhe`, `i4cwgr`, `g311lg`, `laura168`) | ~20 | ❌ |
| 2 | Strings extraídas dos binários (Ksuite + DLLs) | 33.035 | ❌ |
| 3 | SecLists `Pwdb_top-100000` + `xato_10k` | ~110.000 | ❌ |
| 4 | Total dicionário (dedup) | **133.362** | ❌ |
| 5 | Força bruta numérica 1–8 dígitos | **111.111.110** | ❌ |
| 6 | Derivados de constantes/ID (prefixos K/KESSV2/KSUITE, sufixos SEED/999, hex/dec do PRO.INI) | 9.558 | ❌ |
| 7 | Strings de seed diretas (`KESSV2GOSKSUITESEED`, `C9313`, `KSUITEDB`, `KTAGGOSKSUITE11`, 32×`x`) | ~65 | ❌ |
| 8 | Nome do arquivo/variações (`A142_275`, `A142_275.ori`, etc.) | ~50 | ❌ |

### ID do cliente (PRO.INI)

```
[CUSTOMER]
ID=0x0CABAC1F     → decimal 212.577.311 (hex 0CABAC1F)
```
Testado em hex/dec, com prefixos/sufixos e separadores: ❌.

## ⚠️ LIÇÃO CRÍTICA — falso positivo de check-byte

Houve um falso positivo (`kessv2.0CAA1F1FSEED`) causado por **bug na verificação**:

```python
# ERRADO — trata erro de zlib como sucesso:
except Exception as e:
    return "encrypted" not in str(e).lower()
```

O erro real era `zlib.error: invalid distance too far back` (decriptação
parcialmente válida, mas inflate falhou). Como a palavra "encrypted" não estava
na mensagem, o código retornou **sucesso**.

**Correto:**

```python
except Exception:
    return False          # QUALQUER exceção = senha errada
```

**Regra:** só aceite a senha se a **descompressão completa** (CRC) passar.
O check-byte tem 1/256 de falso positivo — com 133 mil candidatos, ~520 falsos
positivos de check-byte são esperados e devem ser descartados pela verificação.

## O que se sabe

- Senha **não** é numérica pura (1–8 testado exaustivamente).
- Senha **não** é um literal simples extraível por strings (33k testados).
- Senha **não** corresponde a nenhuma senha pública conhecida do pacote.
- O binário **constrói a senha em runtime** (ver `reverse_engineering.md`):
  `IntToHex(valor_runtime, 8)` + `"K"` + `"KESSV2"` + seeds.

## Caminhos restantes (alta certeza)

1. **Emulação** da função `0x125C90` (Unicorn/Qiling) capturando a string.
2. **Debugger** (x64dbg) com breakpoint em `0x126A41` / `0x3b1c58`.
3. Localizar o **setter da propriedade `Password` do ZipForge** e o caller.
4. Se a senha depender de serial de hardware, ela pode ser **específica da
   máquina** — nesse caso os `.ori` de `res\ori\` (distribuídos) teriam de usar
   uma chave fixa em outro ponto do código.
