# Engenharia Reversa — KSuite 2.80

## Alvo

- **Arquivo:** `Ksuite_2.80.exe`
- **SHA-256:** `BAE8D39700E052CC0C8362F8B3D940A38EBECC3DDF925A1D6D0716B7B2DE9F3E`
- **Arquitetura:** x86 (32 bits), Delphi
- **Timestamp PE:** `0x5AB5046C` (2018-03-23)
- **ImageBase:** `0x00400000` · **SizeOfImage:** `0x1EC2000`

## Seções PE

| Seção | VA | RawOff | RawSize | Característica |
|---|---|---|---|---|
| (sem nome) | 0x00001000 | 0x00001000 | 0x00753000 | código (1:1 com raw) |
| `.rsrc` | 0x00754000 | 0x00754000 | 0x00178000 | recursos/DFM |
| `Tut4you` | 0x008CC000 | 0x008CC000 | 0x00045000 | **protetor** |
| `.idata` | 0x00911000 | 0x00911000 | 0x00003000 | imports |
| `.idata` | 0x00914000 | 0x00914000 | 0x00001000 | imports |
| `.upx` | 0x00D2E000 | 0x00915000 | 0x002B1000 | nome enganoso |
| `BP` | 0x01EB0000 | 0x00BC6000 | 0x0001176D | stub do packer |

- **Entry point** `0x01EB1600` (seção `BP`) começa com `60` (`pushad`) → stub de packer.
- **Não há magic `UPX!`** — o `.upx` é falso; o protetor é o **"Tut4you"** (Delphi).

## 🔓 Achado principal — o código NÃO está criptografado

Apesar do protetor, a seção de código está **legível**:

```
8.819 prologues Delphi ('push ebp; mov ebp,esp') na seção principal
3.974 / 4.000 blocos de amostra desmontaram limpos  → 99,3% legível
```

Isso permitiu **análise estática do algoritmo real** sem desempacotar.

## Imports notáveis

| DLL | Funções | Relevância |
|---|---|---|
| `gmp.dll` | `__gmpz_powm_ui`, `__gmpz_mul_ui`, `__gmpz_root`... | **cripto bigint / RSA** |
| `advapi32.dll` | `RegOpenKeyExW`, `RegQueryValueExW`... | registro |
| `kernel32/mfc80/msvcr80` | padrão | — |

## Exports (649) — RTTI Delphi

Classes identificadas nas strings de RTTI:

- **`CAlienZip`** — wrapper próprio sobre o ZipForge (onde a senha é usada)
- `TZipForge`, `TZFBaseArchiver`, `TAESCryptoTransform`, `TZFCryptoTransform`
- `TPBKDF2`, `TCipher` — derivação de chave
- Formulários: `_KessMainForm`, `_FLoaderPswDlg`, `_KessBackupDlg`, `_LoaderMainForm`...

## VMT da CAlienZip

Detecção robusta pelo **auto-ponteiro Delphi** (`vmtSelfPtr` em `VMT-88` == VA da VMT):

```
CAlienZip VMT = 0x00A41CC0 (file 0x00641CC0)
  vmtClassName (VMT-56) -> "CAlienZip"
  vmtSelfPtr   (VMT-88) -> 0x00A41CC0  ✔
```

- `vmtMethodTable` (VMT-64) = 0 → **sem métodos publicados**
- Sem slots virtuais no intervalo → métodos são **não-virtuais** (chamada direta)

## 🔑 Strings de seed encontradas

Localizadas no binário (região de código legível):

```
KESSV2GOSKSUITESEED      (0x0061944F, 0x0063E5AC)
KESSV2GOSKSUITE          (0x0061943E)
C9313                    (0x00619463)
KSUITE / KSUITEDB
KTAGGOSKSUITE11
"xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"  (32 x's — buffer/placeholder)
\res\ori\   (0x0063E618)
Original.ori (0x0063E65A)
```

**Testadas como senha direta: ❌ não são a senha.** São entradas de um gerador
em runtime.

## Função que lida com `.ori` — `0x00125C90`

- Legível (98% desmontada).
- Referencia `\res\ori\` (0x1266EA), `Original.ori` (0x126EA2), `KESSV2` (3×),
  e a string de 32 `x` (`push 0xa3e624` em 0x126926).
- Em `0x126A41` faz:
  ```
  mov edx, [0xb38a58] ; mov ebx, [edx+0x1070]
  mov eax, [ebx+0x894]      ; valor de runtime (serial/ID)
  mov edx, 8
  call 0x1e742c             ; IntToHex(valor, 8)  ✅ confirmado
  ...
  mov eax, 0xa3e643         ; "K"
  call 0x3b1c58             ; operação de string
  ```
  Ou seja: **monta uma string com `IntToHex` + "K" + "KESSV2"** — derivada de um
  valor de runtime.

## Função `0x0000A160` (usa CAlienZip)

- Copia um **template estático de 37 bytes** de `0x7C0324` (seção `.rsrc`) para
  um buffer local, depois usa a classe.
- Chama métodos via `[0xa41c68]` (campo `vmtSelfPtr` da CAlienZip).

## Interpretação

O protetor "Tut4you" protegeu o entry point e **algumas** funções, mas deixou a
maior parte do código legível. A senha dos `.ori` **não é um literal simples**:
é **construída em runtime** combinando `IntToHex(serial, 8)` + `"K"` + `"KESSV2"`
e/ou os seeds. Como a entrada (`[ebx+0x894]`) é de runtime, a extração 100%
estática exigiria emular a função com os valores corretos.

## Próximos passos possíveis

1. **Emular** a função `0x125C90` com Unicorn/Qiling e capturar a string montada.
2. **Debugger** (x64dbg) rodando o app, breakpoint em `0x126A41`/`0x3b1c58`,
   ler a senha em memória.
3. Localizar o **setter da propriedade Password do ZipForge** e rastrear o caller.
