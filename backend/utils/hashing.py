def crc32_to_hex(value: int) -> str:
    return (value & 0xFFFFFFFF).to_bytes(4, byteorder="big").hex()
