"""模块说明。"""

import struct


# 异或校验码计算
def bbc(data: bytes) -> int:
    """计算 BBC 异或校验值。

    参数:
    - data: 输入字节序列。

    返回:
    - int: 异或校验结果。
    """
    res = 0x00
    for byte in data:
        res ^= byte
    return res


# CRC-16-MODBUS
def crc_16_modbus(data: bytes) -> list[int]:
    """计算 CRC-16/MODBUS 校验并返回字节列表。

    参数:
    - data: 输入字节序列。

    返回:
    - list: 校验结果字节列表。
    """
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = crc >> 1 ^ 40961 if crc & 1 else crc >> 1
    byte_representation = struct.pack(">H", crc)
    hex_representation = byte_representation.hex()
    re = bytes.fromhex(hex_representation)
    return list(re)


# Backward compatibility aliases.
BBC = bbc
CRC_16_MODBUS = crc_16_modbus
