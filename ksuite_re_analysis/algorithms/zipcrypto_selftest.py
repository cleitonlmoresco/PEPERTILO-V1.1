"""
ZipCrypto — autoteste que CONSTRÓI um ZIP cifrado do zero e o valida.

✅ VALIDADO: este script cria um ZIP com senha "secret123" usando a implementação
   de criptografia pura (sem depender do zipfile para cifrar) e depois o lê com
   o módulo zipfile do Python, provando que o algoritmo está correto.

Execute:
    python zipcrypto_selftest.py
Saída esperada: "SELFTEST OK: ..." e retorno 0.
"""

import sys
import struct
import zlib
import random
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from zipcrypto import keys_from_password, encrypt_byte, derive_check_byte


def build_encrypted_zip(path, password: bytes, filename="selftest.txt"):
    """Constrói um ZIP ZipCrypto válido (método STORE) do zero."""
    payload = b"Hello ZipCrypto self test. " * 50
    crc = zlib.crc32(payload) & 0xFFFFFFFF

    # deriva chaves e cifra o header de 12 bytes + payload
    k0, k1, k2 = keys_from_password(password)
    check = derive_check_byte(crc, 0, flag_bit3=False)
    header = bytes(random.getrandbits(8) for _ in range(11)) + bytes([check])

    enc = bytearray()
    for b in header + payload:
        e, k0, k1, k2 = encrypt_byte(b, k0, k1, k2)
        enc.append(e)

    fn = filename.encode()
    dos_time, dos_date = 0x6000, 0x5765
    flags, method, ver = 0x0001, 0, 20  # encrypted, store
    crc_orig = crc

    local = struct.pack(
        "<IHHHHHIIIHH",
        0x04034B50, ver, flags, method, dos_time, dos_date,
        crc_orig, len(enc), len(payload), len(fn), 0,
    ) + fn

    cdh = struct.pack(
        "<IHHHHHHIIIHHHHHII",
        0x02014B50, (ver << 8) | ver, ver, flags, method, dos_time, dos_date,
        crc_orig, len(enc), len(payload), len(fn), 0, 0, 0, 0, 0, 0,
    ) + fn

    offset_cd = len(local) + len(enc)
    eocd = struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, 1, 1, len(cdh), offset_cd, 0)

    pathlib.Path(path).write_bytes(local + enc + cdh + eocd)


def main():
    import zipfile

    out = pathlib.Path(__file__).parent / "selftest_enc.zip"
    pw = b"secret123"
    build_encrypted_zip(out, pw)
    print(f"[+] ZIP cifrado criado: {out} ({out.stat().st_size} bytes)")

    with zipfile.ZipFile(out) as z:
        data = z.read("selftest.txt", pwd=pw)
    assert data.startswith(b"Hello ZipCrypto self test."), "conteudo inesperado"

    # senha errada deve falhar
    try:
        with zipfile.ZipFile(out) as z:
            z.read("selftest.txt", pwd=b"errada")
        raise AssertionError("senha errada deveria falhar")
    except RuntimeError:
        pass

    print("SELFTEST OK: algoritmo de criptografia/descriptografia ZipCrypto validado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
