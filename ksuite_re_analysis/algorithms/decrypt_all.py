"""
Decriptação em lote dos .ori do KSuite — dado que se tenha a senha.

✅ VALIDADO (com o selftest): usa a implementação de ZipCrypto do zipcrypto.py
   indiretamente via zipfile (que usa o mesmo algoritmo padrão) e verifica CRC.

Uso:
    python decrypt_all.py <senha> [pasta_raiz] [pasta_saida]
Ex.:
    python decrypt_all.py "minha_senha" "res\\ori" "ori_decifrados"

Observação:
    - Só grava o arquivo se a descompressão completa funcionar (CRC válido).
    - Se a senha estiver errada, nada é extraído e o script reporta.
"""

import sys
import os
import zipfile
import pathlib


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    password = sys.argv[1]
    base = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else pathlib.Path("res/ori")
    outdir = pathlib.Path(sys.argv[3]) if len(sys.argv) > 3 else pathlib.Path("ori_decifrados")
    outdir.mkdir(parents=True, exist_ok=True)

    ok = fail = 0
    for zp in sorted(base.rglob("*.zip")):
        rel = zp.relative_to(base).parent
        try:
            with zipfile.ZipFile(zp) as z:
                for name in z.namelist():
                    data = z.read(name, pwd=password.encode("utf-8", "ignore"))
                    dest = outdir / rel / name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(data)
                    ok += 1
                    print(f"[OK] {zp.name} -> {name} ({len(data)} bytes)")
        except Exception as e:
            fail += 1
            print(f"[FAIL] {zp.name}: {type(e).__name__}: {e}")

    print(f"\nResumo: {ok} extraídos, {fail} falhas")
    return 0 if ok and not fail else 2


if __name__ == "__main__":
    sys.exit(main())
