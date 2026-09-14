#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Probe aggregated proxy nodes and write latency-based quality files.

This does lightweight TCP handshake checks against each node host:port. It
cannot measure real bandwidth without a proxy core, so the "speed grade" is an
approximation driven by latency.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import csv
import json
import socket
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
SUB_DIR = ROOT / "sub"
QUALITY_DIR = SUB_DIR / "quality"


def log(message: str) -> None:
    print(message, flush=True)


def parse_host_port(node: str) -> Optional[Tuple[str, int]]:
    node = node.strip()
    if not node:
        return None
    if "#" in node:
        node = node.split("#", 1)[0]

    try:
        if node.startswith("vmess://"):
            payload = node[len("vmess://"):]
            decoded = base64.b64decode(payload + "=" * (-len(payload) % 4)).decode("utf-8", "ignore")
            obj = json.loads(decoded)
            host = obj.get("add", "") or obj.get("host", "")
            port = int(obj.get("port", 0))
            return (host, port) if host and port else None

        if node.startswith("ssr://"):
            payload = node[len("ssr://"):]
            decoded = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)).decode("utf-8", "ignore")
            parts = decoded.split(":")
            if len(parts) >= 2:
                host, port = parts[0], int(parts[1])
                return (host, port) if host else None

        if node.startswith(("vless://", "trojan://", "hysteria2://", "hy2://", "tuic://", "ss://", "ssr://")):
            parsed = urllib.parse.urlparse(node)
            host = parsed.hostname
            if not host and parsed.netloc and "@" in parsed.netloc:
                host = parsed.netloc.rsplit("@", 1)[-1].split(":")[0]
            if not host:
                return None
            port = parsed.port or (443 if node.startswith(("vless://", "trojan://", "hysteria2://", "hy2://", "tuic://")) else 80)
            return (host.strip("[]"), port)
    except Exception:  # noqa: BLE001
        return None
    return None


async def check_host(host: str, port: int, timeout: float) -> Optional[float]:
    try:
        start = time.monotonic()
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )
        latency_ms = (time.monotonic() - start) * 1000
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:  # noqa: BLE001
            pass
        return latency_ms
    except Exception:  # noqa: BLE001
        return None


async def run_checks(keys: List[Tuple[str, int]], timeout: float, concurrency: int) -> Dict[Tuple[str, int], Optional[float]]:
    sem = asyncio.Semaphore(concurrency)
    results: Dict[Tuple[str, int], Optional[float]] = {}

    async def worker(key: Tuple[str, int]) -> Tuple[Tuple[str, int], Optional[float]]:
        async with sem:
            latency = await check_host(key[0], key[1], timeout)
            return key, latency

    tasks = [asyncio.create_task(worker(key)) for key in keys]
    for task in asyncio.as_completed(tasks):
        key, latency = await task
        results[key] = latency
    return results


def grade(latency_ms: float) -> str:
    if latency_ms <= 400:
        return "fast"
    if latency_ms <= 900:
        return "medium"
    return "slow"


def estimated_mbps(latency_ms: float) -> int:
    if latency_ms <= 400:
        return 100
    if latency_ms <= 900:
        return 30
    return 10


def write_lines(path: Path, nodes: List[str], header: str) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    unique = sorted(set(nodes), key=lambda s: s.lower())
    path.write_text(header + "\n" + "\n".join(unique) + ("\n" if unique else ""), encoding="utf-8")
    return len(unique)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-nodes", type=int, default=20000, help="Only probe the first N nodes.")
    parser.add_argument("--timeout", type=float, default=2.5, help="TCP connect timeout in seconds.")
    parser.add_argument("--concurrency", type=int, default=120, help="Concurrent connection checks.")
    args = parser.parse_args()

    all_file = SUB_DIR / "all.txt"
    if not all_file.exists():
        log("sub/all.txt not found, run scripts/aggregate.py first")
        return 1

    nodes = [line.strip() for line in all_file.read_text(encoding="utf-8").splitlines()]
    nodes = [node for node in nodes if node and not node.startswith("#")]
    if args.max_nodes:
        nodes = nodes[: args.max_nodes]

    key_to_nodes: Dict[Tuple[str, int], List[str]] = {}
    unparsed: List[str] = []
    for node in nodes:
        key = parse_host_port(node)
        if key:
            key_to_nodes.setdefault(key, []).append(node)
        else:
            unparsed.append(node)

    keys = list(key_to_nodes.keys())
    log(f"Probing {len(keys)} unique host:port entries for {len(nodes)} nodes")
    start = time.monotonic()
    results = asyncio.run(run_checks(keys, args.timeout, args.concurrency))
    elapsed = time.monotonic() - start
    log(f"Probe finished in {elapsed:.1f}s")

    fast_nodes: List[str] = []
    medium_nodes: List[str] = []
    slow_nodes: List[str] = []
    speed_100_nodes: List[str] = []
    speed_30_nodes: List[str] = []
    speed_10_nodes: List[str] = []
    unreachable_nodes: List[str] = []
    rows: List[Dict[str, object]] = []

    for key, node_list in key_to_nodes.items():
        latency = results.get(key)
        if latency is None:
            unreachable_nodes.extend(node_list)
            rows.append({"node": "; ".join(node_list), "host": key[0], "port": key[1], "latency_ms": None, "grade": "unreachable"})
            continue
        g = grade(latency)
        rows.append({"node": "; ".join(node_list), "host": key[0], "port": key[1], "latency_ms": round(latency, 1), "grade": g, "estimated_mbps": estimated_mbps(latency)})
        if g == "fast":
            fast_nodes.extend(node_list)
            speed_100_nodes.extend(node_list)
        elif g == "medium":
            medium_nodes.extend(node_list)
            speed_30_nodes.extend(node_list)
        else:
            slow_nodes.extend(node_list)
            speed_10_nodes.extend(node_list)

    header = "# latency-based quality, generated by scripts/probe.py"
    counts = {
        "fast": write_lines(QUALITY_DIR / "fast.txt", fast_nodes, f"{header}\n# latency <= 400ms, estimated ~100 Mbps"),
        "medium": write_lines(QUALITY_DIR / "medium.txt", medium_nodes, f"{header}\n# 401-900ms, estimated ~30 Mbps"),
        "slow": write_lines(QUALITY_DIR / "slow.txt", slow_nodes, f"{header}\n# > 900ms, estimated ~10 Mbps"),
        "unreachable": write_lines(QUALITY_DIR / "unreachable.txt", unreachable_nodes + unparsed, f"{header}\n# unreachable or unparsable"),
    }
    counts["fast_only"] = write_lines(
        SUB_DIR / "fast-only.txt",
        fast_nodes,
        f"{header}\n# 筛选后的推荐订阅：延迟 <= 400ms，估测速率约 100 Mbps",
    )
    counts["speed-100"] = write_lines(
        SUB_DIR / "speed-100.txt",
        speed_100_nodes,
        f"{header}\n# 约 100 Mbps 分组（延迟 <= 400ms）",
    )
    counts["speed-30"] = write_lines(
        SUB_DIR / "speed-30.txt",
        speed_30_nodes,
        f"{header}\n# 约 30 Mbps 分组（延迟 401-900ms）",
    )
    counts["speed-10"] = write_lines(
        SUB_DIR / "speed-10.txt",
        speed_10_nodes,
        f"{header}\n# 约 10 Mbps 分组（延迟 > 900ms）",
    )

    with (QUALITY_DIR / "probe.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["node", "host", "port", "latency_ms", "grade", "estimated_mbps"])
        writer.writeheader()
        writer.writerows(rows)

    if SUB_DIR.joinpath("meta.json").exists():
        meta = json.loads(SUB_DIR.joinpath("meta.json").read_text(encoding="utf-8"))
    else:
        meta = {}
    meta["last_probe_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    meta["probe"] = {
        "node_count": len(nodes),
        "unique_hosts": len(keys),
        "counts": counts,
        "probe_seconds": round(elapsed, 1),
    }
    SUB_DIR.joinpath("meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"Quality files written to {QUALITY_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
