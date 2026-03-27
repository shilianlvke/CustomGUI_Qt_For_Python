"""模块说明。"""

# ruff: noqa: N999

from AppCore.SYS.logger import Logger

try:
    import serial.tools.list_ports as serial_list_ports
except ImportError:
    serial_list_ports = None

try:
    import hid
except ImportError:
    hid = None

try:
    import wmi
except ImportError:
    wmi = None


def get_com_port() -> list[str]:
    """获取windwos所有USB(COM)设备列表

    :return:USB(COM)设备列表
    """
    if serial_list_ports is None:
        Logger.warning("pyserial 未安装，无法获取 COM 设备列表")
        return []
    ports = list(serial_list_ports.comports())
    return [f"{dev.device} - {dev.description}" for dev in ports]


def get_hid_port() -> list[str]:
    """获取windwos所有USB(HID)设备列表

    :return:USB(HID)设备列表
    """
    if hid is None:
        Logger.warning("hidapi 未安装，无法获取 HID 设备列表")
        return []
    devices = hid.enumerate(vendor_id=0, product_id=0)
    return [f"{dev['vendor_id']} - {dev['product_id']} - {dev['manufacturer_string']}" for dev in devices]


def get_net_adapter() -> list[str]:
    """获取windwos所有网卡设备列表

    :return:网卡设备列表
    """
    if wmi is None:
        Logger.warning("wmi 未安装，无法获取网卡设备列表")
        return []
    c = wmi.WMI()
    return [f"{dev.IPAddress[0]} - {dev.Description}" for dev in c.Win32_NetworkAdapterConfiguration(IPEnabled=True)]


if __name__ == "__main__":
    ad_list = get_net_adapter()
    for i in ad_list:
        Logger.info(str(i))
