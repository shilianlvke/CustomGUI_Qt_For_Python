#!/usr/bin/env python3
"""把 SllkGuiLauncher.bat 的脚本主体重新打包进 SllkGuiLauncher.exe。

exe 是 .NET 外壳：启动时读取内嵌资源 launcher.ps1.gz，用 DeflateStream 解压后
写到 %LOCALAPPDATA%\\SllkGuiLauncher\\launcher.ps1，再交给 powershell -File 执行。
本脚本不重新编译外壳，只替换该资源的数据区，因此要求新负载压缩后不超过原槽位。

用法：
    python build_exe.py            # zopfli（若已安装），失败则回退 zlib -9
    pip install zopfli             # 想要最好的压缩率时装它
"""

from __future__ import annotations

import hashlib
import pathlib
import sys
import zlib

HERE = pathlib.Path(__file__).resolve().parent
BAT = HERE / "SllkGuiLauncher.bat"
EXE = HERE / "SllkGuiLauncher.exe"

MARKER = b"#__SLLK_BODY__"
RES_START = 0x44C      # launcher.ps1.gz 资源在文件中的起始偏移
RES_END = 0x6F8B       # 资源槽位结束（其后紧跟 #~ 元数据，以 BSJB 开头）


def read_payload() -> bytes:
    raw = BAT.read_bytes()
    idx = raw.rindex(MARKER) + len(MARKER)
    body = raw[idx:]
    if not body.lstrip().startswith(b"$ErrorActionPreference"):
        sys.exit("bat 结构异常：标记之后没有找到脚本主体")
    # 与原 exe 保持一致：UTF-8 BOM + CRLF
    return b"\xef\xbb\xbf" + body


def deflate(data: bytes) -> tuple[bytes, str]:
    try:
        import zopfli.zopfli as core  # type: ignore

        wrapped = core.compress(data, gzip_mode=0, numiterations=120, blocksplitting=1)
        return wrapped[2:-4], "zopfli"
    except ImportError:
        c = zlib.compressobj(9, zlib.DEFLATED, -15)
        return c.compress(data) + c.flush(), "zlib-9"


def main() -> int:
    exe = bytearray(EXE.read_bytes())
    if exe[RES_END + 1:RES_END + 5] != b"BSJB":
        sys.exit("exe 布局与预期不符（元数据签名不在预期位置），请用 csc 重新编译外壳")

    payload = read_payload()
    stream, how = deflate(payload)
    capacity = RES_END - RES_START

    print(f"脚本主体 : {len(payload):,} 字节")
    print(f"压缩结果 : {len(stream):,} 字节（{how}） / 槽位 {capacity:,} 字节")
    if len(stream) > capacity:
        sys.exit(f"压缩后仍超出 {len(stream) - capacity:,} 字节，需要重新编译外壳扩展资源区")

    # 自检：确保压缩流能被原样还原
    if zlib.decompressobj(-15).decompress(stream) != payload:
        sys.exit("压缩流自检失败")

    exe[RES_START:RES_START + len(stream)] = stream
    exe[RES_START + len(stream):RES_END] = b"\x00" * (capacity - len(stream))
    EXE.write_bytes(exe)

    digest = hashlib.sha256(payload).hexdigest()
    print(f"已写入   : {EXE.name}（{len(exe):,} 字节，余量 {capacity - len(stream):,} 字节）")
    print(f"主体 sha256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
