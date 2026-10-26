# KSuite 2.80 — Reverse Engineering & Algoritmos

Análise reversa do software **KSuite 2.80 (Alientech / KESS v2 / K-TAG)** e dos arquivos
`.ori` empacotados em `res\ori\*\.zip`.

> Objetivo: documentar os algoritmos usados, registrar o que funcionou e o que não
> funcionou, e preservar as implementações validadas em Python.

---

## 🎯 Resumo executivo — O QUE FUNCIONOU

| # | Algoritmo / Técnica | Status | Onde |
|---|---|---|---|
| 1 | **ZipCrypto (PKWARE legacy) — decriptação** | ✅ **VALIDADO** (selftest) | `algorithms/zipcrypto.py` |
| 2 | **Derivação de chaves ZipCrypto a partir da senha** | ✅ **VALIDADO** | `algorithms/zipcrypto.py` |
| 3 | **Criptografia ZipCrypto from-scratch (para selftest)** | ✅ **VALIDADO** | `algorithms/zipcrypto_selftest.py` |
| 4 | **Filtro rápido de check-byte + verificação completa** | ✅ **VALIDADO** (achou `secret123` em 44.198 tentativas) | `algorithms/checkbyte_cracker.py` |
| 5 | **Inventário de criptografia dos 312 ZIPs** | ✅ 312 ZipCrypto/deflate, 0 stored, 0 erros | `algorithms/zip_inventory.py` |
| 6 | **Decriptação em lote (dado a senha)** | ✅ pronto | `algorithms/decrypt_all.py` |
| 7 | **Análise SQLite do `SystemData.s3d`** | ✅ 3 tabelas, sem credenciais | `findings/sqlite_analysis.md` |
| 8 | **Análise PE: 99,3% do código legível** | ✅ (protetor não criptografou o código) | `findings/reverse_engineering.md` |
| 9 | **Detecção de VMT Delphi (auto-ponteiro)** | ✅ achou `CAlienZip` @ 0xA41CC0 | `findings/reverse_engineering.md` |
| 10 | **Xrefs de strings + leitura do algoritmo** | ✅ `IntToHex(v,8)`, seed strings, função 0x125C90 | `findings/reverse_engineering.md` |
| 11 | **Correlação ajuda `.mht` ↔ ZIPs** | ✅ 280/312 por código-base | `findings/help_zip_correlation.md` |

## ❌ O QUE NÃO FUNCIONOU

| Tentativa | Candidatos | Resultado |
|---|---|---|
| Dicionário (strings do binário + SecLists) | 133.362 | ❌ |
| Força bruta numérica 1–8 dígitos | 111.111.110 | ❌ |
| Senhas públicas da comunidade (RAR de instalação) | ~20 | ❌ |
| Candidatos derivados de constantes/ID | 9.558 | ❌ (1 falso positivo) |
| bkcrack (known-plaintext) | — | ❌ impraticável (tudo deflate) |
| Extração estática da senha | — | ❌ senha construída em runtime / ofuscada |

## 🔑 Conclusão principal

Os `.ori` usam **ZipCrypto legacy** (algoritmo de 1989, totalmente documentado).
O **algoritmo de decriptação foi recriado e validado**. O que falta **não é o
algoritmo — é a senha/chave**, que o binário constrói em runtime (buffer de 32 `x`,
`IntToHex`, strings de seed `KESSV2GOSKSUITESEED` / `C9313` / `KSUITE`).

⚠️ **Lição importante registrada**: a validação por *check-byte* do ZipCrypto tem
**falsos positivos de 1/256**. Um candidato só é válido se a **descompressão
completa** funcionar (CRC). Ver `findings/password_attack_log.md`.

---

## 📁 Estrutura

```
ksuite_re_analysis/
├── README.md
├── algorithms/
│   ├── zipcrypto.py            # ✅ algoritmo validado (decrypt/encrypt/keys)
│   ├── zipcrypto_selftest.py   # ✅ constrói zip cifrado e testa
│   ├── checkbyte_cracker.py    # ✅ filtro check-byte + verificação
│   ├── zip_inventory.py        # ✅ inventário de criptografia
│   └── decrypt_all.py          # ✅ decripta lote dado a senha
└── findings/
    ├── reverse_engineering.md  # PE, VMT, xrefs, função .ori
    ├── sqlite_analysis.md      # SystemData.s3d
    ├── help_zip_correlation.md # ajuda ↔ protocolos
    ├── password_attack_log.md  # tudo que foi tentado
    └── bkcrack_assessment.md   # por que bkcrack não serve aqui
```

## ⚠️ Nota legal

Trabalho de **engenharia reversa para interoperabilidade/estudo** sobre uma cópia
local do software. Não distribua software não licenciado nem firmware protegido.
