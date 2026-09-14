#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Drop proxy nodes whose sing-box config cannot be built.

NekoBox shows errors like "unknown method" when a subscription mixes in malformed
Shadowsocks nodes. This script parses each node with the same logic used by the
real speedtest and keeps only nodes that produce a valid outbound config.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent
SUB_DIR = ROOT / "sub"


def load_speedtest():
    spec = importlib.util.spec_from_file_location("speedtest", ROOT / "scripts" / "speedtest.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def write_sorted(path: Path, nodes: List[str], header: str) -> None:
    nodes = sorted(set(nodes), key=lambda x: x.lower())
    path.write_text(header + "\n" + "\n".join(nodes) + ("\n" if nodes else ""), encoding="utf-8")


def main() -> int:
    source = SUB_DIR / "keep.txt"
    if not source.exists():
        print("sub/keep.txt not found", file=sys.stderr)
        return 1

    speedtest = load_speedtest()
    lines = [line.strip() for line in source.read_text(encoding="utf-8").splitlines()]
    nodes = [line for line in lines if line and not line.startswith("#")]

    valid: List[str] = []
    dropped: List[str] = []
    for node in nodes:
        if node.lower().startswith("ss://"):
            dropped.append(node)
            continue
        try:
            speedtest.build_outbound(node)
            valid.append(node)
        except Exception:
            dropped.append(node)

    header = "# sanitized by scripts/sanitize.py"
    write_sorted(SUB_DIR / "nekobox.txt", valid, f"{header}\n# NekoBox 常见兼容节点：vmess/vless/trojan/ss")
    write_sorted(SUB_DIR / "keep.txt", valid, f"{header}\n# 只保留可正确解析的节点")

    meta = json.loads((SUB_DIR / "meta.json").read_text(encoding="utf-8"))
    meta["sanitized_at"] = meta.get("sanitized_at", "")
    meta["sanitize"] = {"input_count": len(nodes), "kept": len(valid), "dropped": len(dropped)}
    (SUB_DIR / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"kept {len(valid)}, dropped {len(dropped)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
