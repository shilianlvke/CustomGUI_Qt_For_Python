# -*- coding=utf-8 -*-
import struct


# 异或校验码计算
def BBC(data: bytes) -> int:
    res = 0x00
    for byte in data:
        res ^= byte
    return res


# CRC-16-MODBUS
def CRC_16_MODBUS(data: bytes) -> list:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc = crc >> 1
    byte_representation = struct.pack(">H", crc)
    hex_representation = byte_representation.hex()
    re = bytes.fromhex(hex_representation)
    return list(re)
