#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run a real bandwidth test through proxy nodes.

This script requires a proxy core binary that supports the node protocol:

  - sing-box (recommended): vmess, vless, trojan, shadowsocks, hysteria2, tuic
  - xray: vless, vmess, trojan, shadowsocks

It starts the core locally with a SOCKS inbound, then downloads a real file via
that SOCKS proxy and reports Mbps.

Example:
  python3 scripts/speedtest.py --input sub/keep.txt --core /path/to/sing-box --limit 5
"""

from __future__ import annotations

import argparse
import base64
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent


def log(message: str) -> None:
    print(message, flush=True)


def detect_core() -> Optional[str]:
    for name in ("sing-box", "xray", "mihomo"):
        path = shutil.which(name)
        if path:
            return path
    return None


def parse_vmess(node: str) -> Dict[str, object]:
    payload = node[len("vmess://"):]
    payload = payload.split("#", 1)[0]
    decoded = base64.b64decode(payload + "=" * (-len(payload) % 4)).decode("utf-8", "ignore")
    return json.loads(decoded)


def parse_ss(node: str) -> Dict[str, str]:
    body = node[len("ss://"):].split("#", 1)[0]
    if "@" in body:
        userinfo, hostport = body.rsplit("@", 1)
        if ":" in userinfo:
            method, password = userinfo.split(":", 1)
        else:
            method, password = "aes-128-gcm", userinfo
        host, port = hostport.rsplit(":", 1)
        return {"method": method, "password": password, "server": host, "server_port": int(port)}
    raw = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)).decode("utf-8", "ignore")
    userinfo, hostport = raw.rsplit("@", 1)
    method, password = userinfo.split(":", 1)
    host, port = hostport.rsplit(":", 1)
    return {"method": method, "password": password, "server": host, "server_port": int(port)}


def transport_from_query(query: Dict[str, str], host: str, default_path: str = "/") -> Optional[Dict[str, object]]:
    transport_type = query.get("type", "")
    if transport_type == "ws":
        return {
            "type": "ws",
            "path": query.get("path", default_path) or "/",
            "headers": {"Host": query.get("host", host)},
        }
    return None


def build_outbound(node: str) -> Dict[str, object]:
    node = node.strip()
    if node.startswith("vmess://"):
        obj = parse_vmess(node)
        outbound = {
            "type": "vmess",
            "tag": "out",
            "server": obj.get("add") or obj.get("host"),
            "server_port": int(obj.get("port", 443)),
            "uuid": obj.get("id"),
            "security": obj.get("security", "auto"),
            "alter_id": int(obj.get("aid", 0)),
        }
        if obj.get("tls") or obj.get("sni"):
            outbound["tls"] = {
                "enabled": True,
                "server_name": obj.get("sni") or obj.get("host"),
                "insecure": True,
            }
        if obj.get("net") == "ws":
            outbound["transport"] = transport_from_query(
                {"type": "ws", "path": obj.get("path", "/"), "host": obj.get("host")},
                str(obj.get("host") or outbound["server"]),
            )
        return outbound

    if node.startswith("ss://"):
        obj = parse_ss(node)
        return {
            "type": "shadowsocks",
            "tag": "out",
            "server": obj["server"],
            "server_port": obj["server_port"],
            "method": obj["method"],
            "password": obj["password"],
        }

    if node.startswith(("vless://", "trojan://", "hysteria2://", "hy2://", "tuic://")):
        parsed = urllib.parse.urlparse(node)
        query = dict(urllib.parse.parse_qsl(parsed.query))
        host = parsed.hostname or ""
        port = parsed.port or 443
        username = parsed.username or ""
        password = parsed.password or username
        sni = query.get("sni") or query.get("host") or host

        if node.startswith("vless://"):
            outbound = {
                "type": "vless",
                "tag": "out",
                "server": host,
                "server_port": port,
                "uuid": username,
            }
        elif node.startswith("trojan://"):
            outbound = {
                "type": "trojan",
                "tag": "out",
                "server": host,
                "server_port": port,
                "password": password or username,
            }
        elif node.startswith(("hysteria2://", "hy2://")):
            outbound = {
                "type": "hysteria2",
                "tag": "out",
                "server": host,
                "server_port": port,
                "password": password,
            }
        else:
            outbound = {
                "type": "tuic",
                "tag": "out",
                "server": host,
                "server_port": port,
                "uuid": username,
                "password": password,
            }

        if query.get("security") == "tls" or node.startswith(("vless://", "trojan://")):
            outbound["tls"] = {
                "enabled": True,
                "server_name": sni,
                "insecure": True,
            }
        transport = transport_from_query(query, host)
        if transport:
            outbound["transport"] = transport
        return outbound

    raise ValueError(f"Unsupported node protocol: {node[:12]}...")


def build_sing_box_config(node: str, port: int) -> Dict[str, object]:
    return {
        "log": {"level": "warn"},
        "inbounds": [
            {
                "type": "socks",
                "tag": "socks-in",
                "listen": "127.0.0.1",
                "listen_port": port,
            }
        ],
        "outbounds": [build_outbound(node)],
    }


def wait_for_port(port: int, timeout: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(0.3)
    return False


def run_node_speed(node: str, core: str, port: int, url: str, max_time: int) -> Optional[float]:
    config = build_sing_box_config(node, port)
    with tempfile.TemporaryDirectory() as tmp:
        cfg_path = Path(tmp) / "config.json"
        cfg_path.write_text(json.dumps(config), encoding="utf-8")

        proc = subprocess.Popen(
            [core, "run", "-c", str(cfg_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            if not wait_for_port(port):
                return None
            cmd = [
                "curl",
                "-s",
                "-o",
                "/dev/null",
                "-w",
                "%{speed_download}",
                "--proxy",
                f"socks5h://127.0.0.1:{port}",
                "--max-time",
                str(max_time),
                "-L",
                url,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=max_time + 20)
            if result.returncode != 0 or not result.stdout.strip():
                return None
            bytes_per_sec = float(result.stdout.strip())
            return bytes_per_sec * 8 / 1_000_000
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, default=str(ROOT / "sub" / "keep.txt"))
    parser.add_argument("--core", type=str, help="Path to sing-box/xray binary")
    parser.add_argument("--url", default="https://proof.ovh.net/files/20Mb.dat")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--port", type=int, default=10801)
    parser.add_argument("--max-time", type=int, default=20)
    args = parser.parse_args()

    core = args.core or detect_core()
    if not core:
        log("No sing-box/xray core found. Install sing-box or pass --core /path/to/sing-box.")
        return 1

    input_path = Path(args.input)
    if not input_path.exists():
        log(f"input not found: {args.input}")
        return 1

    lines = [line.strip() for line in input_path.read_text(encoding="utf-8").splitlines()]
    nodes = [line for line in lines if line and not line.startswith("#")]
    if args.limit:
        nodes = nodes[: args.limit]

    results = []
    port = args.port
    for node in nodes:
        log(f"testing {node[:80]}")
        mbps = run_node_speed(node, core, port, args.url, args.max_time)
        results.append({"node": node, "mbps": round(mbps, 2) if mbps is not None else None})
        port += 1

    if results:
        out_path = ROOT / "sub" / "speedtest.json"
        out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        log(f"written {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
