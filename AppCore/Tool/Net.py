"""模块说明。"""

# ruff: noqa: N999

import asyncio
import ipaddress
import os


def is_private_ip(ip: str) -> bool:
    """判断 IP 地址是否为私有 IP（局域网）

    :param ip: IP 地址（字符串）
    :return: 如果是私有 IP 返回 True，否则返回 False
    """
    try:
        ip_obj = ipaddress.ip_address(ip)
    except ValueError:
        return False
    else:
        return ip_obj.is_private


def is_device_online(ip: str) -> bool:
    """判断设备是否在线（通过 ping 测试）

    :param ip: IP 地址（字符串）
    :return: 如果设备在线返回 True，否则返回 False
    """
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        return False
    command = ["ping", "-n", "1", "-w", "1000", ip] if os.name == "nt" else ["ping", "-c", "1", "-W", "1", ip]

    async def _ping_once() -> int:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        return await process.wait()

    try:
        return asyncio.run(_ping_once()) == 0
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_ping_once()) == 0
        finally:
            loop.close()
