"""
KSuite 2.80 — decriptação dos .ori (SENHA DESCOBERTA ✅)

Como a senha foi obtida
-----------------------
A senha NÃO é um literal simples: o binário a **decifra em runtime** a partir de
um template estático de 36 bytes na seção `.rsrc`, usando um XOR com chave
derivada de uma palavra de 16 bits. A rotina está na função RVA `0x0000A160`.

Algoritmo (reproduzido fielmente)
---------------------------------
    W      = uint16 little-endian em VA 0x7C0324  (= 0x7CD7)
    first  = W & 0xFF          # 0xD7
    second = (W >> 8) & 0xFF   # 0x7C
    raw    = 36 bytes em VA 0x7C0326
    out[i] = raw[i] ^ (((first + i) * i + second) & 0xFF)   para i = 0..35

    -> senha = out (36 caracteres ASCII)

Senha resultante:
    -%7B5-FA45+48DA7+72F5-8E9C5%4F5A68%+

Essa senha abre **todos os 312 ZIPs** de `res\\ori\\` (ZipCrypto + deflate).
O arquivo `res\\file\\LastFiles.dev` (backup do usuário) usa OUTRA senha,
gerada em runtime a partir do serial (ver findings/reverse_engineering.md).

Uso:
    python ksuite_ori_decrypt.py "E:\\Ksuite 2.80 NEWEST !" [saida]
"""

import sys
import pathlib
import zipfile

# --- constantes extraídas do binário ---
IMAGE_BASE = 0x00400000
VA_WORD = 0x7C0324       # palavra de 16 bits (chave)
VA_BLOB = 0x7C0326       # 36 bytes cifrados
BLOB_LEN = 36


def derive_password(exe_path: pathlib.Path) -> str:
    """Reproduz o laço XOR de 0x0000A160 e devolve a senha."""
    data = exe_path.read_bytes()
    off_w = VA_WORD - IMAGE_BASE
    off_b = VA_BLOB - IMAGE_BASE

    w = int.from_bytes(data[off_w:off_w + 2], "little")
    first, second = w & 0xFF, (w >> 8) & 0xFF
    raw = data[off_b:off_b + BLOB_LEN]

    out = bytearray(raw)
    for i in range(BLOB_LEN):
        out[i] ^= ((first + i) * i + second) & 0xFF
    return out.decode("ascii", "strict")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    root = pathlib.Path(sys.argv[1])
    outdir = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else root / "ori_decrypted"

    exe = root / "Ksuite_2.80.exe"
    if not exe.exists():
        print(f"ERRO: {exe} nao encontrado")
        return 1

    pw = derive_password(exe)
    print(f"Senha derivada: {pw!r}")

    ori_base = root / "res" / "ori"
    outdir.mkdir(parents=True, exist_ok=True)

    ok = fail = 0
    for zp in sorted(ori_base.rglob("*.zip")):
        rel = zp.relative_to(ori_base).parent
        try:
            with zipfile.ZipFile(zp) as z:
                for name in z.namelist():
                    data = z.read(name, pwd=pw.encode())
                    dest = outdir / rel / name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(data)
                    ok += 1
        except Exception as e:
            fail += 1
            print(f"[FAIL] {zp.name}: {type(e).__name__}: {e}")

    print(f"\nOK: {ok} arquivos .ori decifrados | falhas: {fail}")
    print(f"Saida: {outdir}")
    return 0 if ok and not fail else 2


if __name__ == "__main__":
    sys.exit(main())
