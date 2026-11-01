import ipaddress
import os


def is_private_ip(ip: str) -> bool:
    """
    判断 IP 地址是否为私有 IP（局域网）
    :param ip: IP 地址（字符串）
    :return: 如果是私有 IP 返回 True，否则返回 False
    """
    try:
        ip_obj = ipaddress.ip_address(ip)
        return ip_obj.is_private
    except ValueError:
        return False


def is_device_online(ip: str) -> bool:
    """
    判断设备是否在线（通过 ping 测试）
    :param ip: IP 地址（字符串）
    :return: 如果设备在线返回 True，否则返回 False
    """
    if os.name == "nt":  # Windows
        command = f"ping -n 1 -w 1000 {ip}"
    else:  # Linux/Mac
        command = f"ping -c 1 -W 1 {ip}"
    response = os.system(command)
    return response == 0
