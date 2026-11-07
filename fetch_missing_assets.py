#!/usr/bin/env python3
"""Scarica le risorse interne referenziate ma non ancora presenti nel mirror.

wget non segue gli attributi data-* (gallerie), i srcset e le URL costruite in
JS. Questo script li estrae da HTML/CSS/JS e scarica quello che manca.
"""

from __future__ import annotations

import re
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import unquote, urljoin

ROOT = Path("mirror/www.parcoecclesialetna.it")
BASE = "https://www.parcoecclesialetna.it"
UA = "Mozilla/5.0 (Macintosh; archive)"

ATTR_RE = re.compile(
    r'(href|src|poster|data-[a-zA-Z0-9_-]+)\s*=\s*"([^"]+)"', re.I
)
SRCSET_RE = re.compile(r'srcset\s*=\s*"([^"]+)"', re.I)
CSS_URL_RE = re.compile(r"url\(\s*([\"']?)([^)\"']+)\1\s*\)", re.I)
JS_STR_RE = re.compile(
    r'["\'](/(?:static|media)/[^"\']+\.(?:jpg|jpeg|png|gif|svg|webp|mp4|webm|pdf|ico|woff2?|ttf|eot|css|js))["\']',
    re.I,
)
TEASER_RE = re.compile(r'data-teaser-source\s*=\s*"([^"]+)"', re.I)

ASSET_EXT = {
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
    ".mp4", ".webm", ".pdf", ".css", ".js",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
}
PAGE_EXT = {".html", ".htm"}


def is_internal(u: str) -> bool:
    return u.startswith("/") and not u.startswith("//")


def local_path(url_path: str) -> Path | None:
    path = unquote(url_path.split("?", 1)[0].split("#", 1)[0])
    if not path.startswith("/"):
        return None
    rel = path.lstrip("/")
    if not rel:
        rel = "index.html"
    if path.endswith("/"):
        rel += "index.html"
    last = rel.rsplit("/", 1)[-1]
    if "." not in last:
        rel += "/index.html"
    return ROOT / rel


def collect_urls() -> tuple[set[str], set[str]]:
    assets: set[str] = set()
    pages: set[str] = set()

    files = list(ROOT.rglob("*.html")) + list(ROOT.rglob("*.css")) + list(ROOT.rglob("*.js"))

    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")

        for attr, value in ATTR_RE.findall(text):
            for candidate in value.split(","):
                candidate = candidate.strip()
                if not candidate or not is_internal(candidate):
                    continue
                low = candidate.lower().split("?", 1)[0]
                ext = "." + low.rsplit(".", 1)[-1] if "." in low.rsplit("/", 1)[-1] else ""
                if ext in ASSET_EXT or ext in PAGE_EXT:
                    (assets if ext in ASSET_EXT else pages).add(candidate)
                elif ext == "" and attr.lower() in {"href"}:
                    pages.add(candidate)

        for value in SRCSET_RE.findall(text):
            for part in value.split(","):
                candidate = part.strip().split(" ")[0]
                if is_internal(candidate):
                    assets.add(candidate)

        for _q, value in CSS_URL_RE.findall(text):
            if is_internal(value):
                assets.add(value)

        for value in JS_STR_RE.findall(text):
            if is_internal(value):
                assets.add(value)

        for value in TEASER_RE.findall(text):
            if is_internal(value) and not value.lower().endswith(".mp4"):
                assets.add(value + ".mp4")

    return assets, pages


def fetch(url_path: str) -> tuple[bool, str]:
    url = BASE + url_path
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    cafile = "/etc/ssl/cert.pem"
    context = (
        ssl.create_default_context(cafile=cafile)
        if Path(cafile).exists()
        else ssl.create_default_context()
    )
    try:
        with urllib.request.urlopen(req, timeout=60, context=context) as resp:
            data = resp.read()
            ctype = resp.headers.get("Content-Type", "")
            if "text/html" in ctype and not url_path.endswith("/"):
                # directory senza slash: salva come index
                pass
            dest = local_path(url_path)
            if dest is None:
                return False, "path non valido"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            return True, f"{len(data)} bytes"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def main() -> None:
    assets, pages = collect_urls()

    targets: list[tuple[str, str]] = []
    for url_path in sorted(assets):
        dest = local_path(url_path)
        if dest and not dest.exists():
            targets.append(("asset", url_path))
    for url_path in sorted(pages):
        if url_path == "/":
            continue
        dest = local_path(url_path)
        if dest and not dest.exists():
            targets.append(("page", url_path))

    print(f"Risorse mancanti: {len(targets)}")
    ok = 0
    failed: list[tuple[str, str]] = []
    for kind, url_path in targets:
        success, info = fetch(url_path)
        if success:
            ok += 1
        else:
            failed.append((url_path, info))

    print(f"Scaricate: {ok}")
    print(f"Fallite:   {len(failed)}")
    for url_path, info in failed:
        print(f"  {info:20} {url_path}")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
