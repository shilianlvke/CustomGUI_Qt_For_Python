#!/usr/bin/env python3
"""将版本同步发布到 Gitee Release（幂等，可重复执行）。

用于 .github/workflows/gitee-release.yml：
  1. 查询 Gitee 仓库中指定 tag 的 Release，不存在则创建（tag 不存在时 Gitee
     会基于默认分支自动创建）。
  2. 上传 assets-dir 目录下的所有文件为 Release 附件，已存在的同名附件跳过。

仅依赖 Python 标准库（urllib / json），GitHub Actions ubuntu-latest 自带 python3。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

GITEE_API = os.environ.get("GITEE_API_BASE", "https://gitee.com/api/v5")


def _request(method: str, url: str, *, params: dict | None = None, json_body: dict | None = None, multipart: tuple[bytes, str] | None = None) -> dict:
    """发送请求并返回 JSON；非 2xx 时抛出带响应体的 RuntimeError。"""
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    data = None
    headers = {}
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif multipart is not None:
        body, boundary = multipart
        data = body
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gitee API {method} {url} 失败: HTTP {exc.code} {detail}") from exc


def _encode_multipart(fields: dict[str, str], file_path: Path) -> tuple[bytes, str]:
    """构造 multipart/form-data：普通字段 + 单个 file 字段。"""
    boundary = "----CustomGUI" + os.urandom(16).hex()
    lines = []
    for key, value in fields.items():
        lines.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n".encode("utf-8"))
    filename = file_path.name
    lines.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
        "Content-Type: application/octet-stream\r\n\r\n".encode("utf-8")
    )
    lines.append(file_path.read_bytes())
    lines.append(b"\r\n" + f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(lines), boundary


def find_or_create_release(owner: str, repo: str, token: str, tag: str, body: str, prerelease: bool) -> int:
    """返回 release id：存在则复用，不存在则创建。"""
    tag_quoted = urllib.parse.quote(tag, safe="")
    check_url = f"{GITEE_API}/repos/{owner}/{repo}/releases/tags/{tag_quoted}"
    try:
        existing = _request("GET", check_url, params={"access_token": token})
        release_id = existing.get("id")
        if release_id:
            print(f"[Gitee] 已存在 Release（tag={tag}），复用 id={release_id}")
            return int(release_id)
    except RuntimeError as exc:
        if "HTTP 404" not in str(exc):
            raise
        print(f"[Gitee] tag={tag} 尚无 Release，准备创建")

    create_url = f"{GITEE_API}/repos/{owner}/{repo}/releases"
    created = _request(
        "POST",
        create_url,
        json_body={
            "access_token": token,
            "tag_name": tag,
            "name": tag,
            "body": body,
            "prerelease": prerelease,
        },
    )
    release_id = created.get("id")
    if not release_id:
        raise RuntimeError(f"创建 Gitee Release 失败，响应: {created}")
    print(f"[Gitee] 已创建 Release（tag={tag}），id={release_id}")
    return int(release_id)


def upload_assets(owner: str, repo: str, token: str, release_id: int, assets_dir: Path) -> None:
    """上传目录下所有文件；同名附件已存在则跳过。"""
    files = sorted(assets_dir.iterdir()) if assets_dir.is_dir() else []
    if not files:
        print("[Gitee] assets 目录为空或无文件，跳过附件上传")
        return

    list_url = f"{GITEE_API}/repos/{owner}/{repo}/releases/{release_id}/attach_files"
    existing_names = {
        item.get("name")
        for item in _request("GET", list_url, params={"access_token": token})
        if item.get("name")
    }
    upload_url = f"{GITEE_API}/repos/{owner}/{repo}/releases/{release_id}/attach_files"
    for file_path in files:
        if not file_path.is_file():
            continue
        if file_path.name in existing_names:
            print(f"[Gitee] 跳过已存在附件: {file_path.name}")
            continue
        multipart = _encode_multipart({"access_token": token}, file_path)
        uploaded = _request("POST", upload_url, multipart=multipart)
        print(f"[Gitee] 已上传附件: {file_path.name} (id={uploaded.get('id')})")


def parse_prerelease(value: str | None) -> bool:
    return value is not None and value.strip().lower() in ("true", "1", "yes", "on")


def main() -> int:
    parser = argparse.ArgumentParser(description="同步发布版本到 Gitee Release")
    parser.add_argument("--owner", required=True, help="Gitee 仓库所属空间地址（个人/组织 path）")
    parser.add_argument("--repo", required=True, help="Gitee 仓库路径")
    parser.add_argument("--token", required=True, help="Gitee 私人令牌（Personal Access Token）")
    parser.add_argument("--tag", required=True, help="要发布的 tag（如 v1.2.3）")
    parser.add_argument("--body-file", help="Release 描述（markdown 文件路径），缺省为空")
    parser.add_argument("--assets-dir", default="assets", help="待上传附件目录，缺省 assets")
    parser.add_argument("--prerelease", default="false", help="是否为预览版本（true/false），缺省 false")
    args = parser.parse_args()

    if not args.token:
        print("[Gitee] 错误: 缺少 Gitee 私人令牌（GITEE_TOKEN）", file=sys.stderr)
        return 2

    body = ""
    if args.body_file and Path(args.body_file).is_file():
        body = Path(args.body_file).read_text(encoding="utf-8")

    try:
        release_id = find_or_create_release(
            args.owner, args.repo, args.token, args.tag, body, parse_prerelease(args.prerelease)
        )
        upload_assets(args.owner, args.repo, args.token, release_id, Path(args.assets_dir))
    except RuntimeError as exc:
        print(f"[Gitee] 失败: {exc}", file=sys.stderr)
        return 1

    print(f"[Gitee] 发布完成: https://gitee.com/{args.owner}/{args.repo}/releases/tag/{urllib.parse.quote(args.tag, safe='')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
