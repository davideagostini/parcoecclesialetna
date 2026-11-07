#!/usr/bin/env python3
"""Verifica che ogni link/asset interno del sito statico esista."""

from __future__ import annotations

import posixpath
import re
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

ROOT = Path("site")
ATTR_RE = re.compile(
    r'(href|src|poster|data-[a-zA-Z0-9_-]+)\s*=\s*"([^"]+)"', re.I
)
CSS_RE = re.compile(r"url\(\s*([\"']?)([^)\"']+)\1\s*\)", re.I)
SKIP = ("http://", "https://", "//", "mailto:", "tel:", "javascript:", "data:", "#")


def base_url(file: Path) -> str:
    rel = file.relative_to(ROOT).as_posix()
    directory = posixpath.dirname(rel)
    return "/" + (directory + "/" if directory else "")


def target_exists(path: str) -> bool:
    path = unquote(path.split("?", 1)[0].split("#", 1)[0])
    if path in {"", "/"}:
        return True
    candidate = ROOT / path.lstrip("/")
    if candidate.is_file():
        return True
    if (candidate / "index.html").is_file():
        return True
    return False


def main() -> None:
    broken: Counter[str] = Counter()
    sources: dict[str, set[str]] = {}
    checked = 0

    for page in list(ROOT.rglob("*.html")) + list(ROOT.rglob("*.css")):
        text = page.read_text(encoding="utf-8", errors="replace")
        base = base_url(page)
        urls = []
        for attr, value in ATTR_RE.findall(text):
            if attr.lower().startswith("data-") and "/" not in value:
                continue
            urls.append(value)
        urls += [m[1] for m in CSS_RE.findall(text)]
        for url in urls:
            url = url.strip()
            if not url or url.startswith(SKIP):
                continue
            if url.startswith("/"):
                resolved = url
            else:
                resolved = posixpath.normpath(posixpath.join(base, url))
            checked += 1
            if not target_exists(resolved):
                broken[resolved] += 1
                sources.setdefault(resolved, set()).add(str(page))

    print(f"URL interni controllati: {checked}")
    print(f"Rotti: {len(broken)}")
    for url, count in broken.most_common(30):
        src = sorted(sources[url])[:2]
        print(f"  {count:5}x {url}  <- {src}")


if __name__ == "__main__":
    main()
