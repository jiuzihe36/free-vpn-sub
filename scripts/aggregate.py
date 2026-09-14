#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aggregate public free proxy/VPN subscription links into categorized files.

The result is a set of plain-text files that can be consumed by Clash, V2RayN,
Shadowrocket, Quantumult X and similar tools.
"""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request
import ssl
from urllib.parse import unquote
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SUB_DIR = ROOT / "sub"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "*/*",
}

PROTOCOLS = ("vmess://", "vless://", "trojan://", "ss://", "ssr://", "hysteria2://", "hy2://", "tuic://")

COUNTRY_PATTERNS: List[tuple] = [
    ("US", ("美国", "us", "United States", "san jose", "sanjose", "los angeles", "losangeles",
            "la ", "seattle", "portland", "new york", "ny ", "chicago", "miami", "dallas", "denver",
            "atlanta", "dca", "sjc", "lax", "fremont", "silicon valley", "texas", "ohio", "florida",
            "virginia", "washington", "salt lake", "phoenix", "houston", "philadelphia")),
    ("HK", ("香港", "hongkong", "hong kong", "hkg", "hk ")),
    ("JP", ("日本", "jp", "tokyo", "大阪", "osaka", "sakura", "ntt", "softbank", "kddi", "iij", "ix", "bbtec")),
    ("SG", ("新加坡", "singapore", "狮城", "sgp", "sg ")),
    ("KR", ("韩国", "korea", "seoul", "kr ")),
    ("TW", ("台湾", "taiwan", "taipei", "tw ")),
    ("DE", ("德国", "germany", "frankfurt", "de ")),
    ("GB", ("英国", "uk ", "united kingdom", "london", "gb ")),
    ("FR", ("法国", "france", "paris", "fr ")),
    ("CA", ("加拿大", "canada", "toronto", "montreal", "vancouver")),
    ("AU", ("澳大利亚", "australia", "sydney")),
    ("IN", ("印度", "india", "mumbai", "delhi")),
    ("RU", ("俄罗斯", "russia", "moscow", "ru ")),
]

COUNTRY_KEYWORDS = []
for _code, _keywords in COUNTRY_PATTERNS:
    COUNTRY_KEYWORDS.extend(_keywords)


def log(msg: str) -> None:
    print(msg, flush=True)


def fetch_text(url: str, timeout: int = 15) -> Optional[str]:
    """Fetch a text resource over HTTPS."""
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                raw = resp.read()
                try:
                    return raw.decode("utf-8")
                except UnicodeDecodeError:
                    return raw.decode("utf-8", "ignore")
        except Exception as exc:  # noqa: BLE001
            if attempt == 0:
                time.sleep(3)
            else:
                log(f"  ! failed {url}: {exc}")
                return None
    return None


def try_base64_decode(text: str) -> Optional[str]:
    """Return decoded text if the payload looks like a base64 subscription."""
    compact = "".join(text.split())
    if not compact:
        return None
    for variant in (
        lambda b: base64.b64decode(b, validate=True),
        lambda b: base64.urlsafe_b64decode(b),
        lambda b: base64.b64decode(b + "=" * (-len(b) % 4), validate=True),
    ):
        try:
            decoded = variant(compact).decode("utf-8", "ignore")
        except Exception:
            continue
        if decoded and any(p in decoded for p in PROTOCOLS):
            return decoded
    return None


def parse_subscription(text: str) -> List[str]:
    decoded = try_base64_decode(text) or text
    lines = [ln.strip() for ln in decoded.splitlines() if ln.strip()]
    nodes = [ln for ln in lines if ln.lower().startswith(PROTOCOLS)]
    if not nodes:
        # Some lists are still base64 rows split in many segments.
        compact = "".join(lines)
        if compact:
            decoded2 = try_base64_decode(compact)
            if decoded2:
                nodes = [ln.strip() for ln in decoded2.splitlines() if ln.strip()]
    return nodes


def protocol_of(node: str) -> str:
    lower = node.lower()
    if lower.startswith("vmess://"):
        return "vmess"
    if lower.startswith("vless://"):
        return "vless"
    if lower.startswith("trojan://"):
        return "trojan"
    if lower.startswith("ssr://"):
        return "ssr"
    if lower.startswith("ss://"):
        return "ss"
    if lower.startswith("hysteria2://") or lower.startswith("hy2://"):
        return "hysteria2"
    if lower.startswith("tuic://"):
        return "tuic"
    return "mixed"


def node_name(node: str) -> str:
    """Extract the display name from a node URI when possible."""
    if "#" in node:
        fragment = node.split("#", 1)[-1]
        try:
            return unquote(fragment)
        except Exception:
            return fragment
    if node.startswith("ssr://"):
        payload = node[len("ssr://"):]
        try:
            decoded = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)).decode("utf-8", "ignore")
            if "remarks=" in decoded:
                remark_b64 = decoded.split("remarks=", 1)[1].split("&", 1)[0]
                remark = base64.urlsafe_b64decode(remark_b64 + "=" * (-len(remark_b64) % 4)).decode("utf-8", "ignore")
                return remark
            return decoded
        except Exception:
            return ""
    if node.startswith("vmess://"):
        payload = node[len("vmess://"):]
        try:
            decoded = base64.b64decode(payload + "=" * (-len(payload) % 4)).decode("utf-8", "ignore")
            obj = json.loads(decoded)
            return obj.get("ps", "")
        except Exception:
            return ""
    if node.startswith("ss://"):
        try:
            parsed = urllib.parse.urlparse(node)
            if parsed.netloc and "@" in parsed.netloc:
                # ss://method:password@host:port#name
                return unquote(parsed.fragment)
            raw = parsed.path.lstrip("/")
            decoded = base64.b64decode(raw + "=" * (-len(raw) % 4), validate=True).decode("utf-8", "ignore")
            return decoded
        except Exception:
            return ""
    if "#" in node:
        return unquote(node.split("#", 1)[-1])
    return ""


def has_any(name: str, keywords: Iterable[str]) -> bool:
    lower = name.lower()
    return any(k in lower for k in keywords)


def country_for_node(name: str) -> List[str]:
    lower = name.lower()
    matched = []
    for code, keywords in COUNTRY_PATTERNS:
        for kw in keywords:
            if kw in lower or kw in name:
                matched.append(code)
                break
    return matched


def tags_for_node(name: str, protocol: str) -> List[str]:
    lower = name.lower()
    tags = []
    if has_any(lower, ("gpt", "chatgpt", "openai", "oai ")):
        tags.append("chatgpt")
    if has_any(lower, ("netflix", "nf ", "奈飞", "netfilx")):
        tags.append("netflix")
    if has_any(lower, ("disney", "disney+", "迪士尼")):
        tags.append("disney")
    if has_any(lower, ("youtube", "ytb", "油管")):
        tags.append("youtube")
    if has_any(lower, ("tiktok", "tok", "抖音")):
        tags.append("tiktok")
    if has_any(lower, ("spotify", "ytm ", "music", "apple")):
        tags.append("music")
    if any(t in tags for t in ("netflix", "disney", "youtube", "tiktok", "spotify")):
        tags.append("streaming")
    return tags


def write_sorted(path: Path, nodes: Iterable[str], header: str) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    unique = sorted(set(nodes), key=lambda s: s.lower())
    path.write_text(header + "\n" + "\n".join(unique) + ("\n" if unique else ""), encoding="utf-8")
    return len(unique)


def main() -> int:
    sources_file = DATA_DIR / "sources.json"
    sources = json.loads(sources_file.read_text(encoding="utf-8"))

    # Remove files generated by previous runs so stale feature/country lists do
    # not survive after a source stops providing those categories.
    for generated_dir in ("by-protocol", "by-country", "features"):
        path = SUB_DIR / generated_dir
        if path.exists():
            shutil.rmtree(path)

    all_nodes: List[str] = []
    node_extra_tags: Dict[str, set] = {}
    broken: List[str] = []
    log(f"Aggregating {len(sources)} sources")

    for src in sources:
        if isinstance(src, dict):
            url = src["url"]
            extra_tags = set(src.get("tags", []))
        else:
            url = src
            extra_tags = set()
        log(f"  fetching {url}")
        text = fetch_text(url)
        if not text:
            broken.append(url)
            continue
        nodes = parse_subscription(text)
        log(f"    -> {len(nodes)} nodes")
        all_nodes.extend(nodes)
        for node in nodes:
            node_extra_tags.setdefault(node, set()).update(extra_tags)

    unique = list(dict.fromkeys(all_nodes))
    log(f"Total unique nodes: {len(unique)}")

    by_protocol: Dict[str, List[str]] = {}
    by_country: Dict[str, List[str]] = {}
    by_tag: Dict[str, List[str]] = {}

    for node in unique:
        protocol = protocol_of(node)
        by_protocol.setdefault(protocol, []).append(node)
        name = node_name(node)
        for code in country_for_node(name):
            by_country.setdefault(code, []).append(node)
        tags = set(tags_for_node(name, protocol))
        tags.update(node_extra_tags.get(node, set()))
        for tag in tags:
            by_tag.setdefault(tag, []).append(node)

    header = "# Generated by scripts/aggregate.py - do not edit manually"
    counts = {"all": write_sorted(SUB_DIR / "all.txt", unique, header)}
    write_sorted(SUB_DIR / "all.raw.txt", unique, f"{header}\n# 未过滤的原始节点存档")

    for key in ("vmess", "vless", "trojan", "ss", "ssr", "hysteria2", "tuic", "mixed"):
        if key in by_protocol:
            counts[key] = write_sorted(
                SUB_DIR / "by-protocol" / f"{key}.txt",
                by_protocol[key],
                f"{header}\n# Protocol: {key}",
            )

    for key in sorted(by_country):
        counts[key] = write_sorted(
            SUB_DIR / "by-country" / f"{key}.txt",
            by_country[key],
            f"{header}\n# Country: {key}",
        )

    for key in sorted(by_tag):
        counts[key] = write_sorted(
            SUB_DIR / "features" / f"{key}.txt",
            by_tag[key],
            f"{header}\n# Feature: {key}",
        )

    # Keep stable files for common tags even when the current sources do not
    # declare those tags, so README links never 404.
    for key in ("chatgpt", "netflix", "disney", "youtube", "tiktok", "streaming"):
        if key not in by_tag:
            counts[key] = write_sorted(
                SUB_DIR / "features" / f"{key}.txt",
                [],
                f"{header}\n# Feature: {key}\n# 当前来源暂无标注该标签的节点，可在 data/sources.json 中补充带标签的订阅源。",
            )

    meta = {
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_count": len(sources),
        "broken_sources": broken,
        "node_count": len(unique),
        "counts": counts,
    }
    (SUB_DIR / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"Done. Wrote {meta['node_count']} nodes to {SUB_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
