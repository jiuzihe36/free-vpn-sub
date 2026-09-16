#!/usr/bin/env python3
"""One-shot deploy edgetunnel2 to Cloudflare Pages via the Cloudflare API.

Usage:
    export CLOUDFLARE_API_TOKEN=...
    export CLOUDFLARE_ACCOUNT_ID=...
    export EDGETUNNEL_ADMIN=your_admin_password
    export EDGETUNNEL_KEY=mykey
    python3 scripts/deploy_edgetunnel2.py

Optional env vars:
    EDGETUNNEL_PROJECT       default: edgetunnel
    EDGETUNNEL_UUID          force a UUIDv4 node UUID
    EDGETUNNEL_PROXYIP       custom reverse-proxy host:port
    EDGETUNNEL_URL           fake homepage or "1101"
    EDGETUNNEL_OFF_LOG       "1" to disable KV logging
"""

import hashlib
import base64
import json
import mimetypes
import os
import random
import re
import string
import sys
import tempfile
import time
import uuid as uuid_lib
import zipfile
from pathlib import Path
from urllib import error as urlerror
from urllib import request as urlrequest

try:
    import blake3
except ImportError:
    print(
        "缺少 blake3 支持，先运行: python3 -m pip install --user blake3",
        file=sys.stderr,
    )
    sys.exit(1)


API_BASE = "https://api.cloudflare.com/client/v4"
ROOT = Path(__file__).resolve().parent.parent
ZIP_PATH = ROOT / "deploy" / "edgetunnel2-main.zip"
COMPAT_DATE = "2025-11-04"
IGNORE_PATTERNS = [
    "_worker.js",
    "_redirects",
    "_headers",
    "_routes.json",
    "functions",
    ".DS_Store",
    "node_modules",
    ".git",
    ".wrangler",
]


class CloudflareError(RuntimeError):
    def __init__(self, message, code=None, response=None):
        super().__init__(message)
        self.code = code
        self.response = response


def cf_request(method, path, token, payload=None, headers=None, raw_body=None):
    url = API_BASE + path if path.startswith("/") else path
    req_headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    if headers:
        req_headers.update(headers)

    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    elif raw_body is not None:
        data = raw_body

    req = urlrequest.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urlrequest.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except urlerror.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            payload_json = json.loads(body)
            # Cloudflare API uses {"success": false, "errors": [...]}
            if not payload_json.get("success", False):
                err = payload_json.get("errors", [{}])[0]
                raise CloudflareError(
                    err.get("message", body),
                    code=err.get("code"),
                    response=payload_json,
                )
        except CloudflareError:
            raise
        except Exception:
            pass
        raise CloudflareError(
            f"HTTP {exc.code}: {body[:500]}",
            code=exc.code,
            response=None,
        )
    except urlerror.URLError as exc:
        raise CloudflareError(f"网络错误: {exc}") from exc


def get_result(method, path, token, payload=None):
    _status, body = cf_request(method, path, token, payload)
    if not body.get("success"):
        err = body.get("errors", [{}])[0]
        raise CloudflareError(
            err.get("message", json.dumps(body)[:500]),
            code=err.get("code"),
            response=body,
        )
    return body.get("result")


def random_boundary():
    return "----CodexEdgetunnel" + "".join(
        random.choice(string.ascii_letters + string.digits) for _ in range(24)
    )


def encode_multipart(fields, files):
    boundary = random_boundary()
    body = bytearray()
    for name, value in fields:
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(value.encode("utf-8"))
        body.extend(b"\r\n")
    for name, filename, content_type, content in files:
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(
            (
                f'Content-Disposition: form-data; name="{name}"; '
                f'filename="{filename}"\r\n'
            ).encode()
        )
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode())
        body.extend(content)
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def build_worker_bundle(worker_js):
    metadata = {
        "main_module": "_worker.js",
        "compatibility_date": COMPAT_DATE,
    }
    fields = [("metadata", json.dumps(metadata, separators=(",", ":")))]
    files = [
        (
            "_worker.js",
            "_worker.js",
            "application/javascript+module",
            worker_js.encode("utf-8"),
        )
    ]
    body, _content_type = encode_multipart(fields, files)
    return body


def ignored(name):
    normalized = name.replace("\\", "/")
    parts = normalized.split("/")
    for part in parts:
        if part in IGNORE_PATTERNS:
            return True
    if any(part.startswith(".github") for part in parts):
        return True
    if any(part == ".git" or part == "node_modules" or part == ".wrangler" for part in parts):
        return True
    if normalized.startswith(".") and normalized != ".gitignore":
        return True
    return False


def hash_file(content, filename):
    import blake3 as blake3_module

    ext = Path(filename).suffix[1:]
    base64_content = base64.b64encode(bytes(content)).decode("ascii")
    digest = blake3_module.blake3((base64_content + ext).encode("utf-8")).hexdigest()
    return digest[:32]


def assets_from_zip(zip_path):
    items = []
    with zipfile.ZipFile(zip_path) as zf:
        prefix = None
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            parts = name.split("/")
            if prefix is None and parts:
                prefix = parts[0]
            rel = "/".join(parts[1:]) if prefix and parts[0] == prefix else name
            if not rel or ignored(rel):
                continue
            content = zf.read(name)
            ctype = mimetypes.guess_type(rel)[0] or "application/octet-stream"
            file_hash = hash_file(content, rel)
            items.append((rel, content, ctype, file_hash))
    return items


def project_exists(account_id, project, token):
    try:
        get_result(
            "GET",
            f"/accounts/{account_id}/pages/projects/{project}",
            token,
        )
        return True
    except CloudflareError as exc:
        if exc.code == 8000007:
            return False
        raise


def create_project(account_id, project, token):
    return get_result(
        "POST",
        f"/accounts/{account_id}/pages/projects",
        token,
        {
            "name": project,
            "production_branch": "main",
        },
    )


def get_or_create_kv(account_id, title, token):
    result = get_result(
        "POST",
        f"/accounts/{account_id}/storage/kv/namespaces",
        token,
        {"title": title},
    )
    return result["id"]


def update_project_config(account_id, project, token, env_vars, kv_id):
    deployment_config = {"env_vars": env_vars}
    if kv_id:
        deployment_config["kv_namespaces"] = {
            "KV": {"namespace_id": kv_id}
        }
    return get_result(
        "PATCH",
        f"/accounts/{account_id}/pages/projects/{project}",
        token,
        {"deployment_configs": {"production": deployment_config}},
    )


def get_upload_token(account_id, project, token):
    result = get_result(
        "GET",
        f"/accounts/{account_id}/pages/projects/{project}/upload-token",
        token,
    )
    return result["jwt"]


def check_missing(jwt, asset_hashes):
    _status, body = cf_request(
        "POST",
        "/pages/assets/check-missing",
        None,
        {"hashes": asset_hashes},
        headers={"Authorization": f"Bearer {jwt}", "Content-Type": "application/json"},
    )
    if not body.get("success"):
        err = body.get("errors", [{}])[0]
        raise CloudflareError(err.get("message", str(body)))
    return body.get("result", [])


def upload_assets(jwt, missing):
    payload = [
        {
            "key": name,
            "value": base64.b64encode(content).decode("ascii"),
            "metadata": {"contentType": ctype},
            "base64": True,
        }
        for name, content, ctype in missing
    ]
    if not payload:
        return
    _status, body = cf_request(
        "POST",
        "/pages/assets/upload",
        None,
        payload,
        headers={"Authorization": f"Bearer {jwt}", "Content-Type": "application/json"},
    )
    if not body.get("success"):
        err = body.get("errors", [{}])[0]
        raise CloudflareError(err.get("message", str(body)))


def upsert_hashes(jwt, asset_hashes):
    _status, body = cf_request(
        "POST",
        "/pages/assets/upsert-hashes",
        None,
        {"hashes": asset_hashes},
        headers={"Authorization": f"Bearer {jwt}", "Content-Type": "application/json"},
    )
    if not body.get("success"):
        err = body.get("errors", [{}])[0]
        raise CloudflareError(err.get("message", str(body)))


def create_deployment(account_id, project, token, manifest, worker_bundle, branch="main"):
    fields = [("manifest", json.dumps(manifest)), ("branch", branch)]
    files = [
        (
            "_worker.bundle",
            "_worker.bundle",
            "application/octet-stream",
            worker_bundle,
        )
    ]
    body, content_type = encode_multipart(fields, files)
    headers = {"Content-Type": content_type}
    _status, resp = cf_request(
        "POST",
        f"/accounts/{account_id}/pages/projects/{project}/deployments",
        token,
        headers=headers,
        raw_body=body,
    )
    if not resp.get("success"):
        err = resp.get("errors", [{}])[0]
        raise CloudflareError(err.get("message", str(resp)[:500]))
    return resp.get("result", {})


def wait_for_deployment(account_id, project, deployment_id, token):
    for _ in range(20):
        result = get_result(
            "GET",
            f"/accounts/{account_id}/pages/projects/{project}/deployments/{deployment_id}",
            token,
        )
        status = ((result.get("latest_stage") or {}).get("status") or "").lower()
        if status == "success":
            return result
        if status in ("failure", "failed"):
            raise CloudflareError(f"部署失败: {json.dumps(result, ensure_ascii=False)[:500]}")
        time.sleep(3)
    return None


def env_value(value, type_name="plain_text"):
    return {"type": type_name, "value": value}


def main():
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    project = os.environ.get("EDGETUNNEL_PROJECT", "edgetunnel").strip()
    admin = os.environ.get("EDGETUNNEL_ADMIN", "").strip()
    key = os.environ.get("EDGETUNNEL_KEY", "").strip()
    node_uuid = os.environ.get("EDGETUNNEL_UUID", "").strip()
    proxyip = os.environ.get("EDGETUNNEL_PROXYIP", "").strip()
    url_var = os.environ.get("EDGETUNNEL_URL", "").strip()
    off_log = os.environ.get("EDGETUNNEL_OFF_LOG", "").strip()

    missing = []
    if not token:
        missing.append("CLOUDFLARE_API_TOKEN")
    if not account_id:
        missing.append("CLOUDFLARE_ACCOUNT_ID")
    if missing:
        print("缺少环境变量: " + ", ".join(missing), file=sys.stderr)
        sys.exit(1)

    if not admin:
        admin = "".join(
            random.choice(string.ascii_letters + string.digits) for _ in range(10)
        )
        print(f"==> 自动生成 ADMIN 密码: {admin}")

    if node_uuid:
        if not re.fullmatch(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-4[0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}",
            node_uuid,
        ):
            print("EDGETUNNEL_UUID 必须是标准 UUIDv4", file=sys.stderr)
            sys.exit(1)
    else:
        node_uuid = str(uuid_lib.uuid4())

    if not key:
        key = node_uuid.split("-")[0]

    print(f"==> 使用 Pages 项目: {project}")
    print(f"==> 订阅密钥: {key}")

    print("==> 初始化 Pages 项目")
    if not project_exists(account_id, project, token):
        create_project(account_id, project, token)
        print("    已创建项目")
    else:
        print("    项目已存在")

    print("==> 创建/查找 KV 命名空间")
    kv_title = f"{project}_kv"
    kv_id = get_or_create_kv(account_id, kv_title, token)
    print(f"    KV ID: {kv_id}")

    print("==> 配置环境变量")
    env_vars = {
        "ADMIN": env_value(admin),
        "KEY": env_value(key),
        "UUID": env_value(node_uuid),
    }
    if proxyip:
        env_vars["PROXYIP"] = env_value(proxyip)
    if url_var:
        env_vars["URL"] = env_value(url_var)
    if off_log in ("1", "true"):
        env_vars["OFF_LOG"] = env_value("1")
    update_project_config(account_id, project, token, env_vars, kv_id)

    print("==> 准备静态资产")
    assets = assets_from_zip(ZIP_PATH)
    if not assets:
        print(f"没有找到部署包: {ZIP_PATH}", file=sys.stderr)
        sys.exit(1)

    jwt = get_upload_token(account_id, project, token)
    hashes = [h for _, _, _, h in assets]
    manifest = {f"/{name}": h for name, _, _, h in assets}
    missing_hashes = [h for h in hashes if h in check_missing(jwt, hashes)]
    missing_assets = [(name, content, ctype) for name, content, ctype, h in assets if h in missing_hashes]
    if missing_assets:
        print(f"==> 上传 {len(missing_assets)} 个静态文件")
        upload_assets(jwt, missing_assets)
        upsert_hashes(jwt, hashes)
    else:
        print("==> 静态文件已缓存，跳过上传")

    print("==> 生成 worker bundle 并部署")
    with zipfile.ZipFile(ZIP_PATH) as zf:
        worker_js = zf.read("edgetunnel-main/_worker.js").decode("utf-8")
    worker_bundle = build_worker_bundle(worker_js)
    deployment = create_deployment(account_id, project, token, manifest, worker_bundle)
    deployment_id = deployment.get("id")
    print(f"    Deployment ID: {deployment_id}")

    result = wait_for_deployment(account_id, project, deployment_id, token)
    if result:
        print(f"    部署状态: {result.get('latest_stage', {}).get('status')}")
    else:
        print("    部署还在进行中，稍后可在 Cloudflare 控制台查看。", file=sys.stderr)

    print()
    print("完成！下面是你的订阅地址：")
    print(f"订阅: https://{project}.pages.dev/{key}")
    print(f"后台: https://{project}.pages.dev/admin")
    print(f"ADMIN 密码: {admin}")


if __name__ == "__main__":
    main()
