# 🔑 Descoberta da senha dos `.ori` — RESOLVIDO

## Resultado

```
Senha: -%7B5-FA45+48DA7+72F5-8E9C5%4F5A68%+
```

- **Abre 312/312 ZIPs** de `res\ori\` (verificado, CRC OK, 0 falhas).
- Extrai firmware `.ori` válido (458 KB – 2 MB, padrões de flash `FF`/`00`).
- O `res\file\LastFiles.dev` usa **outra** senha (backup de usuário, gerada em
  runtime pelo serial do hardware).

## Como foi encontrada

Não foi força bruta — foi **leitura do algoritmo** no binário (99,3% legível).

### 1. Localização da classe `CAlienZip`

Detecção de VMT Delphi pelo auto-ponteiro (`vmtSelfPtr` em `VMT-88`):

```
CAlienZip VMT @ VA 0x00A41CC0
```

### 2. Construtor `CAlienZip.Create` (RVA `0x0012BCBC`)

Cria um `TZipForge` (slot `TZipForge` VMT `0x006F9FE0`) e registra o handler
`OnProgress` (`RVA 0x0052CDB8`, recebe `Double`).

### 3. Função que abre os `.ori` (RVA `0x0000A160`)

1. Copia 36 bytes estáticos de `VA 0x7C0326` (seção `.rsrc`).
2. Lê a palavra-chave de 16 bits em `VA 0x7C0324` = `0x7CD7`.
3. **Decifra o blob com XOR**:

```
first  = word & 0xFF          # 0xD7
second = (word >> 8) & 0xFF   # 0x7C
out[i] = raw[i] ^ (((first + i) * i + second) & 0xFF)   # i = 0..35
```

Desmontagem original (Capstone):

```asm
0040A19D  mov   dx, word [0x7c0324]
0040A1A4  mov   [ebp-0x86], dx
0040A1AB  mov   esi, 0x7c0326
0040A1B0  lea   edi, [ebp-0xac]
0040A1B6  mov   ecx, 9
0040A1BB  rep movsd
0040A1BD  movsb
...
0040A2DC  xor   eax, eax
0040A2DE  mov   al, [ebp-0x86]
0040A2E4  add   eax, [ebp-0xb0]     ; + i
0040A2EA  imul  dword [ebp-0xb0]    ; * i
0040A2F0  add   al, [ebp-0x85]      ; + second
0040A2F6  mov   edx, [ebp-0xb0]
0040A2FC  xor   [ebp+edx-0xac], al  ; blob[i] ^= al
0040A303  inc   dword [ebp-0xb0]
0040A309  cmp   dword [ebp-0xb0], 0x24
0040A310  jl    0x40a2dc
```

4. O resultado é usado como argumento da chamada ao método `CAlienZip`
   (`RVA 0x0052CC60`) junto com o nome do `.ori`.

### 4. Cálculo

```
raw    = 51711948dde5eccf40696d06185443c1c7d3ec9cedf5e29bddafc327246607076a4cab81
word   = 0x7CD7  (first=0xD7, second=0x7C)
senha  = -%7B5-FA45+48DA7+72F5-8E9C5%4F5A68%+
```

## Por que a força bruta nunca acharia

- 36 caracteres, com `-`, `+`, `%` e maiúsculas — espaço astronômico.
- Não é nenhuma senha pública de fórum (essas são do RAR de instalação).
- Não está como literal no binário: é **decifrada em runtime**.

## Reprodução

```bash
python algorithms/ksuite_ori_decrypt.py "E:\Ksuite 2.80 NEWEST !"
```

O script deriva a senha do próprio `Ksuite_2.80.exe` e decifra todos os `.ori`.

> Observação: `LastFiles.dev` (backups do usuário) NÃO usa essa senha —
> usa a derivação por serial (`IntToHex(serial,8)` + `"KESSV2"`, ver
> `reverse_engineering.md`). Só faz sentido decifrá-lo na máquina de origem.
