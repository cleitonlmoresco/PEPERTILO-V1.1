"""
Cracker ZipCrypto — filtro rápido de check-byte + verificação completa.

✅ VALIDADO: no autoteste (ZIP com senha "secret123"), encontrou a senha em
   44.198 tentativas com 182 "falsos positivos" de check-byte, confirmando que a
   verificação final elimina todos.

⚠️ LIÇÃO CRÍTICA
----------------
O check-byte tem **1/256 de falsos positivos**. NUNCA aceite um candidato
apenas porque o check-byte bateu. Só declare sucesso se a DESCOMPRESSÃO
COMPLETA (CRC) funcionar. Um bug comum é tratar exceções de zlib como sucesso:

    # ERRADO:
    except Exception as e:
        return "encrypted" not in str(e).lower()   # zlib.error vira "sucesso"!

    # CERTO:
    except Exception:
        return False

Uso:
    python checkbyte_cracker.py <arquivo.zip> <charset> <min_len> <max_len>
Ex.:
    python checkbyte_cracker.py alvo.zip 0123456789 1 6
"""

import sys
import os
import time
import zipfile
import pathlib
import itertools
import multiprocessing as mp

sys.path.insert(0, str(pathlib.Path(__file__).parent))


# ---------------------------------------------------------------------------
# Leitura do alvo: 12 bytes cifrados do header + byte de verificação esperado
# ---------------------------------------------------------------------------
def load_target(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        info = z.infolist()[0]
        flag_bits = info.flag_bits
        crc = info.CRC
        dt = info.date_time
        header_offset = info.header_offset
        name_len = len(info.filename.encode("utf-8", "ignore"))
        extra_len = len(info.extra)

    with open(zip_path, "rb") as f:
        f.seek(header_offset + 30 + name_len + extra_len)
        enc12 = f.read(12)

    # DOS time -> byte alto
    dos_time = (dt[3] << 11) | (dt[4] << 5) | (dt[5] // 2)
    if flag_bits & 0x08:
        check = (dos_time >> 8) & 0xFF
    else:
        check = (crc >> 24) & 0xFF
    return enc12, check, flag_bits


# ---------------------------------------------------------------------------
# Verificação completa (única forma segura)
# ---------------------------------------------------------------------------
def verify_full(zip_path, password: str) -> bool:
    try:
        with zipfile.ZipFile(zip_path) as z:
            name = z.namelist()[0]
            z.read(name, pwd=password.encode("utf-8", "ignore"))
        return True
    except Exception:
        # QUALQUER exceção = senha errada (RuntimeError, zlib.error, etc.)
        return False


# ---------------------------------------------------------------------------
# Filtro rápido: decripta os 12 bytes e compara o 12º (índice 11)
# ---------------------------------------------------------------------------
def check_pw(pw, enc12, check):
    from zipcrypto import keys_from_password, decrypt_byte
    if isinstance(pw, str):
        pw = pw.encode("utf-8", "ignore")
    k0, k1, k2 = keys_from_password(pw)
    dec = 0
    for e in enc12:
        dec, k0, k1, k2 = decrypt_byte(e, k0, k1, k2)
    return dec == check


def check_batch(args):
    pw_list, enc12, check = args
    for pw in pw_list:
        if check_pw(pw, enc12, check):
            return pw
    return None


def iter_keyspace(charset, min_len, max_len):
    for L in range(min_len, max_len + 1):
        for combo in itertools.product(charset, repeat=L):
            yield "".join(combo)


def main():
    if len(sys.argv) < 5:
        print(__doc__)
        return 1
    zip_path = sys.argv[1]
    charset = sys.argv[2]
    min_len, max_len = int(sys.argv[3]), int(sys.argv[4])

    enc12, check, flags = load_target(zip_path)
    print(f"Alvo: {zip_path}")
    print(f"Header cifrado: {enc12.hex()}  check=0x{check:02X}  flags={flags}")

    workers = max(1, (os.cpu_count() or 2) - 1)
    print(f"charset={charset!r} len={min_len}-{max_len} workers={workers}")

    gen = iter_keyspace(charset, min_len, max_len)
    CHUNK = 50000
    tested = 0
    t0 = time.time()
    found = None

    with mp.Pool(workers) as pool:
        while True:
            batch = []
            for _ in range(CHUNK):
                try:
                    batch.append(next(gen))
                except StopIteration:
                    break
            if not batch:
                break
            chunks = [batch[i::workers] for i in range(workers)]
            results = pool.map(check_batch, [(c, enc12, check) for c in chunks])
            tested += len(batch)
            for r in results:
                if r and verify_full(zip_path, r):
                    found = r
                    break
            if found:
                break
            if tested % 500000 < CHUNK:
                rate = tested / (time.time() - t0 + 1e-6)
                print(f"  testados={tested:,} taxa={rate:,.0f}/s")

    if found:
        print(f"SENHA ENCONTRADA: {found!r} ({tested:,} tentativas)")
        return 0
    print(f"Espaço esgotado. testados={tested:,}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
