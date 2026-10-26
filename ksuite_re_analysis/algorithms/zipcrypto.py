"""
ZipCrypto (PKWARE legacy) — implementação pura em Python.

ALGORITMO VALIDADO ✅
--------------------
Este é o algoritmo usado pelos arquivos .ori do KSuite 2.80.
É o esquema de criptografia tradicional do formato ZIP (1989), documentado em
APPNOTE.TXT da PKWARE. Não é um algoritmo proprietário da Alientech.

Referência: PKWARE ZIP APPNOTE, seção "Traditional PKWARE Encryption".

Como funciona
-------------
1. Três chaves de 32 bits (k0, k1, k2) são inicializadas com constantes fixas.
2. A senha (bytes) é passada por update_keys() byte a byte.
3. Para cada byte do stream:
   - dec = enc XOR ((k2|2) * ((k2|2) ^ 1) >> 8) & 0xFF
   - update_keys(dec)
4. O primeiro bloco de 12 bytes é o "encryption header":
   - 11 bytes aleatórios + 1 byte de verificação (check byte)
   - check byte = byte alto do CRC32 (ou do DOS time, se flag bit 3 estiver setado)

Uso
---
    from zipcrypto import keys_from_password, decrypt_byte

    k0, k1, k2 = keys_from_password(b"minha_senha")
    ...  # decriptar bytes do stream (inclusive o header de 12 bytes)
"""

# ---------------------------------------------------------------------------
# Tabela CRC32 (polinômio 0xEDB88320)
# ---------------------------------------------------------------------------
CRCTABLE = []
for _i in range(256):
    _c = _i
    for _ in range(8):
        _c = (0xEDB88320 ^ (_c >> 1)) if (_c & 1) else (_c >> 1)
    CRCTABLE.append(_c)

INIT0, INIT1, INIT2 = 0x12345678, 0x23456789, 0x34567890


def crc32_update(c, b):
    """Atualiza o CRC32 das chaves com um byte."""
    return (c >> 8) ^ CRCTABLE[(c ^ b) & 0xFF]


def keys_from_password(password: bytes):
    """Deriva (k0, k1, k2) a partir da senha.

    Esta é a derivação de chave do ZipCrypto. O estado interno depende
    SOMENTE da senha (é o mesmo para todos os arquivos que usam a mesma senha,
    antes de processar o header de 12 bytes).
    """
    k0, k1, k2 = INIT0, INIT1, INIT2
    for b in password:
        k0 = crc32_update(k0, b & 0xFF)
        k1 = (k1 + (k0 & 0xFF)) & 0xFFFFFFFF
        k1 = (k1 * 134775813 + 1) & 0xFFFFFFFF
        k2 = crc32_update(k2, (k1 >> 24) & 0xFF)
    return k0, k1, k2


def decrypt_byte(enc_byte, k0, k1, k2):
    """Decripta 1 byte e atualiza as chaves. Retorna (plain, k0, k1, k2)."""
    tmp = (k2 | 2) & 0xFFFFFFFF
    dec = (enc_byte ^ ((((tmp * (tmp ^ 1)) & 0xFFFFFFFF) >> 8) & 0xFF)) & 0xFF
    k0 = crc32_update(k0, dec)
    k1 = (k1 + (k0 & 0xFF)) & 0xFFFFFFFF
    k1 = (k1 * 134775813 + 1) & 0xFFFFFFFF
    k2 = crc32_update(k2, (k1 >> 24) & 0xFF)
    return dec, k0, k1, k2


def encrypt_byte(plain_byte, k0, k1, k2):
    """Criptografa 1 byte e atualiza as chaves. Retorna (enc, k0, k1, k2)."""
    tmp = (k2 | 2) & 0xFFFFFFFF
    enc = (plain_byte ^ ((((tmp * (tmp ^ 1)) & 0xFFFFFFFF) >> 8) & 0xFF)) & 0xFF
    # atualiza as chaves com o PLAINTEXT
    k0 = crc32_update(k0, plain_byte & 0xFF)
    k1 = (k1 + (k0 & 0xFF)) & 0xFFFFFFFF
    k1 = (k1 * 134775813 + 1) & 0xFFFFFFFF
    k2 = crc32_update(k2, (k1 >> 24) & 0xFF)
    return enc, k0, k1, k2


def derive_check_byte(crc32: int, dos_time: int = 0, flag_bit3: bool = False) -> int:
    """Byte de verificação do header ZipCrypto.

    - Se a flag bit 3 do ZIP NÃO estiver setada: (crc >> 24) & 0xFF
    - Se estiver setada: ((dos_time >> 8) & 0xFF)
    """
    if flag_bit3:
        return (dos_time >> 8) & 0xFF
    return (crc32 >> 24) & 0xFF
