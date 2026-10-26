# KSuite 2.80 — Reverse Engineering & Algoritmos

Análise reversa do software **KSuite 2.80 (Alientech / KESS v2 / K-TAG)** e dos arquivos
`.ori` empacotados em `res\ori\*\.zip`.

> Objetivo: documentar os algoritmos usados, registrar o que funcionou e o que não
> funcionou, e preservar as implementações validadas em Python.

---

## 🎯 Resumo executivo — O QUE FUNCIONOU

| # | Algoritmo / Técnica | Status | Onde |
|---|---|---|---|
| 1 | **SENHA dos `.ori` descoberta** | ✅ **312/312 ZIPs abertos** | `findings/password_discovery.md` |
| 2 | **Decriptação XOR do template (0xA160)** | ✅ **VALIDADO** | `algorithms/ksuite_ori_decrypt.py` |
| 3 | **ZipCrypto (PKWARE legacy) — decriptação** | ✅ **VALIDADO** (selftest) | `algorithms/zipcrypto.py` |
| 4 | **Derivação de chaves ZipCrypto a partir da senha** | ✅ **VALIDADO** | `algorithms/zipcrypto.py` |
| 5 | **Criptografia ZipCrypto from-scratch (para selftest)** | ✅ **VALIDADO** | `algorithms/zipcrypto_selftest.py` |
| 6 | **Filtro rápido de check-byte + verificação completa** | ✅ **VALIDADO** | `algorithms/checkbyte_cracker.py` |
| 7 | **Inventário de criptografia dos 312 ZIPs** | ✅ 312 ZipCrypto/deflate, 0 stored | `algorithms/zip_inventory.py` |
| 8 | **Decriptação em lote (senha derivada do exe)** | ✅ **312 arquivos** | `algorithms/ksuite_ori_decrypt.py` |
| 9 | **Análise SQLite do `SystemData.s3d`** | ✅ 3 tabelas, sem credenciais | `findings/sqlite_analysis.md` |
| 10 | **Análise PE: 99,3% do código legível** | ✅ | `findings/reverse_engineering.md` |
| 11 | **Detecção de VMT Delphi (auto-ponteiro)** | ✅ achou `CAlienZip`/`TZipForge` | `findings/reverse_engineering.md` |
| 12 | **Correlação ajuda `.mht` ↔ ZIPs** | ✅ 280/312 por código-base | `findings/help_zip_correlation.md` |

## 🔑 SENHA ENCONTRADA

```
-%7B5-FA45+48DA7+72F5-8E9C5%4F5A68%+
```

Abre **todos os 312 ZIPs** de `res\ori\`. Não é literal: é **decifrada em
runtime** por um XOR (função RVA `0x0000A160`) a partir de um template de 36
bytes em `.rsrc` com chave `0x7CD7`. Ver `findings/password_discovery.md`.


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

Os `.ori` usam **ZipCrypto legacy** (1989) + deflate. A **senha foi descoberta**
por engenharia reversa (não por força bruta):

```
-%7B5-FA45+48DA7+72F5-8E9C5%4F5A68%+
```

Ela é **decifrada em runtime** por um XOR na função RVA `0x0000A160`, a partir de
um template de 36 bytes em `.rsrc` e da palavra-chave `0x7CD7`.

⚠️ **Lição importante registrada**: a validação por *check-byte* do ZipCrypto tem
**falsos positivos de 1/256**. Um candidato só é válido se a **descompressão
completa** funcionar (CRC). Ver `findings/password_attack_log.md`.

---

## 📁 Estrutura

```
ksuite_re_analysis/
├── README.md
├── algorithms/
│   ├── ksuite_ori_decrypt.py   # ✅ deriva a senha do exe + decifra os 312 .ori
│   ├── zipcrypto.py            # ✅ algoritmo validado (decrypt/encrypt/keys)
│   ├── zipcrypto_selftest.py   # ✅ constrói zip cifrado e testa
│   ├── checkbyte_cracker.py    # ✅ filtro check-byte + verificação
│   ├── zip_inventory.py        # ✅ inventário de criptografia
│   └── decrypt_all.py          # ✅ decifra lote dada uma senha
└── findings/
    ├── password_discovery.md   # 🔑 COMO A SENHA FOI DESCOBERTA
    ├── reverse_engineering.md  # PE, VMT, xrefs, função .ori
    ├── sqlite_analysis.md      # SystemData.s3d
    ├── help_zip_correlation.md # ajuda ↔ protocolos
    ├── password_attack_log.md  # tudo que foi tentado
    └── bkcrack_assessment.md   # por que bkcrack não serve aqui
```

## ⚠️ Nota legal

Trabalho de **engenharia reversa para interoperabilidade/estudo** sobre uma cópia
local do software. Não distribua software não licenciado nem firmware protegido.
