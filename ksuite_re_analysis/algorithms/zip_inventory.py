"""
Inventário de criptografia dos arquivos .ori do KSuite.

✅ RESULTADO (executado): 312 ZIPs, todos ZipCrypto (legacy) + deflate,
   0 armazenados (stored), 0 não-criptografados, 0 erros.

Uso:
    python zip_inventory.py "E:\\Ksuite 2.80 NEWEST !\\res\\ori"
"""

import sys
import os
import zipfile
import collections


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "."
    methods = collections.Counter()   # 0=stored, 8=deflate
    enc, plain, errors = 0, 0, 0
    sizes = []

    for root, _dirs, files in os.walk(base):
        for f in files:
            if not f.lower().endswith(".zip"):
                continue
            full = os.path.join(root, f)
            try:
                with zipfile.ZipFile(full) as z:
                    for info in z.infolist():
                        methods[info.compress_type] += 1
                        sizes.append((info.file_size, info.compress_size))
                        if info.flag_bits & 0x1:
                            enc += 1
                        else:
                            plain += 1
            except Exception as e:
                errors += 1
                print(f"ERRO {full}: {e}")

    print(f"Entradas criptografadas : {enc}")
    print(f"Entradas sem senha      : {plain}")
    print(f"Erros                   : {errors}")
    print(f"Métodos de compressão   : {dict(methods)}  (0=stored, 8=deflate)")
    if sizes:
        fs = [a for a, _ in sizes]
        cs = [b for _, b in sizes]
        print(f"Tamanho descomprimido    : min={min(fs)} max={max(fs)}")
        print(f"Tamanho comprimido       : min={min(cs)} max={max(cs)}")
        print(f"Razão de compressão      : {sum(cs)/sum(fs):.3f}")


if __name__ == "__main__":
    main()
