#!/usr/bin/env python3
"""Trasforma il mirror wget in un sito statico pronto per GitHub Pages.

- rimuove file spazzatura (.DS_Store, __MACOSX)
- trasforma la paginazione ?page=N in pagine reali /path/page-N/
- rende i link root-relative e "puliti" (senza index.html)
- aggiunge canonical, 404, CNAME, robots.txt, sitemap.xml
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

SRC = Path("mirror/www.parcoecclesialetna.it")
OUT = Path("site")
DOMAIN = "www.parcoecclesialetna.it"

PAGE_FILE_RE = re.compile(r"^(?P<dir>.*)/index\.html\?page=(?P<n>\d+)\.html$")

JS = {"js"}
HTML_EXT = {".html", ".htm"}


def clean_junk(root: Path) -> None:
    for p in root.rglob("*"):
        if p.name in {".DS_Store", "Thumbs.db"}:
            p.unlink()
    mac = root / "__MACOSX"
    if mac.exists():
        shutil.rmtree(mac)


def flatten_pagination(root: Path) -> list[tuple[Path, Path]]:
    """Rinomina X/index.html?page=N.html in X/page-N/index.html.

    Ritorna la lista di (sorgente, destinazione) applicata.
    """
    moved: list[tuple[Path, Path]] = []
    for p in list(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        m = PAGE_FILE_RE.match(rel)
        if not m:
            continue
        directory, n = m.group("dir"), int(m.group("n"))
        if n == 1:
            # la prima pagina è identica a index.html
            p.unlink()
            continue
        dest_dir = root / directory / f"page-{n}"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / "index.html"
        if dest.exists():
            p.unlink()
            continue
        p.rename(dest)
        moved.append((p, dest))
    return moved


def strip_query_filenames(root: Path) -> None:
    """I file salvati con ?query nel nome perdono la query."""
    for p in list(root.rglob("*")):
        if not p.is_file() or "?" not in p.name:
            continue
        clean_name = p.name.split("?", 1)[0]
        dest = p.with_name(clean_name)
        if dest.exists():
            p.unlink()
            continue
        p.rename(dest)


def url_for(file: Path, root: Path) -> str:
    rel = file.relative_to(root).as_posix()
    if rel == "index.html":
        return "/"
    if rel.endswith("/index.html"):
        return "/" + rel[: -len("index.html")]
    return "/" + rel


def pagination_base(file: Path, root: Path) -> str:
    """Directory della lista a cui appartengono i link ?page=N."""
    url = url_for(file, root)
    m = re.fullmatch(r"(.*/)page-\d+/", url)
    if m:
        return m.group(1)
    return url


ABS_RE = re.compile(
    r'(=\s*")(?:https?:)?//' + re.escape(DOMAIN) + r'(/[^"]*|)"'
)
ROOT_ATTR_RE = re.compile(r'(href|src|action|poster)="(/[^"]*)"')
CSS_ABS_RE = re.compile(
    r"url\((?:https?:)?//" + re.escape(DOMAIN) + r"([^)\"']*)\)"
)
CSS_ROOT_RE = re.compile(r"url\((/[^)\"']*)\)")
QUERY_PAGE_RE = re.compile(r'(href|action)="\?page=(\d+)"')
OGURL_RE = re.compile(r'<meta[^>]+property=["\']og:url["\'][^>]*>')
CANONICAL_RE = re.compile(r'<link[^>]+rel=["\']canonical["\'][^>]*>')
ATTR_REL_RE = re.compile(
    r'\b(href|src|action|poster|srcset|data-[a-zA-Z0-9_-]+)="([^"]*)"', re.I
)
META_IMAGE_RE = re.compile(
    r'(<meta[^>]+(?:property|name)="(?:og:image|twitter:image)"[^>]*?content=")([^"]*)"'
)


def depth_of(file: Path, root: Path) -> int:
    """Profondità della directory che contiene il file, rispetto alla radice."""
    return len(file.parent.relative_to(root).parts)


def to_relative(value: str, depth: int) -> str:
    prefix = "../" * depth if depth else "./"
    return prefix + value.lstrip("/")


def relativize_html(text: str, depth: int) -> str:
    """Trasforma i path root-relative in path relativi al documento."""
    def attr_repl(m: re.Match[str]) -> str:
        attr, value = m.group(1), m.group(2)
        if not value.startswith("/") or value.startswith("//"):
            return m.group(0)
        return f'{attr}="{to_relative(value, depth)}"'

    text = ATTR_REL_RE.sub(attr_repl, text)

    def css_repl(m: re.Match[str]) -> str:
        return f"url({to_relative(m.group(1), depth)})"

    return CSS_ROOT_RE.sub(css_repl, text)


def absolutize_social_images(text: str) -> str:
    """og:image e twitter:image devono restare URL assoluti."""
    def repl(m: re.Match[str]) -> str:
        prefix, value = m.group(1), m.group(2)
        if value.startswith("/") and not value.startswith("//"):
            value = f"https://{DOMAIN}{value}"
        return f'{prefix}{value}"'

    return META_IMAGE_RE.sub(repl, text)


def clean_path(path: str) -> str:
    path, sep, fragment = path.partition("#")
    if path.endswith("/index.html"):
        path = path[: -len("index.html")]
    elif path == "/index.html":
        path = "/"
    return path + sep + fragment


def fix_html(file: Path, root: Path) -> bool:
    text = file.read_text(encoding="utf-8", errors="replace")
    original = text
    url = url_for(file, root)
    page_base = pagination_base(file, root)

    # ?page=N -> pagina statica
    def page_repl(m: re.Match[str]) -> str:
        attr, n = m.group(1), int(m.group(2))
        target = page_base if n == 1 else f"{page_base}page-{n}/"
        return f'{attr}="{target}"'

    text = QUERY_PAGE_RE.sub(page_repl, text)

    # URL assoluti del dominio -> root-relative (qualsiasi attributo, es. og:image)
    def abs_repl(m: re.Match[str]) -> str:
        prefix = m.group(1)
        path = m.group(2) or "/"
        return f'{prefix}{clean_path(path)}"'

    text = ABS_RE.sub(abs_repl, text)

    # /path/index.html -> /path/
    def root_repl(m: re.Match[str]) -> str:
        attr, path = m.group(1), m.group(2)
        return f'{attr}="{clean_path(path)}"'

    text = ROOT_ATTR_RE.sub(root_repl, text)
    text = CSS_ABS_RE.sub(lambda m: f"url({clean_path(m.group(1) or '/')})", text)
    text = CSS_ROOT_RE.sub(lambda m: f"url({clean_path(m.group(1))})", text)

    # immagini senza file associato: il template genera src="/media/"
    text = text.replace('src="/media/"', 'src="/static/css/images/blank.gif"')

    # og:image e twitter:image devono restare assoluti
    text = absolutize_social_images(text)

    # root-relative -> relativi al documento (funziona sia su / sia su /repo/)
    text = relativize_html(text, depth_of(file, root))

    canonical = f"https://{DOMAIN}{url}"
    if not CANONICAL_RE.search(text):
        text = text.replace(
            "</head>", f'    <link rel="canonical" href="{canonical}">\n</head>', 1
        )

    # og:url: sostituisci l'URL globale con quello della pagina
    text = OGURL_RE.sub(
        f'<meta property="og:url" content="{canonical}">', text, count=1
    )

    if text != original:
        file.write_text(text, encoding="utf-8")
        return True
    return False


def build_extra_files(root: Path) -> None:
    (root / ".nojekyll").write_text("", encoding="utf-8")

    # necessario solo se si pubblica con GitHub Pages
    (root / "CNAME").write_text(f"{DOMAIN}\n", encoding="utf-8")

    root_index = """<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <title>Parco Culturale Ecclesiale Terre dell'Etna e dell'Alcantara</title>
  <link rel="canonical" href="https://www.parcoecclesialetna.it/it/">
  <meta http-equiv="refresh" content="0; url=it/">
  <meta name="robots" content="noindex">
  <script>location.replace("it/");</script>
</head>
<body>
  <p><a href="it/">Vai al sito</a></p>
</body>
</html>
"""
    (root / "index.html").write_text(root_index, encoding="utf-8")

    robots = f"""User-agent: *
Allow: /

Sitemap: https://{DOMAIN}/sitemap.xml
"""
    (root / "robots.txt").write_text(robots, encoding="utf-8")

    urls = sorted(
        url_for(p, root)
        for p in root.rglob("*.html")
        if p.name == "index.html"
    )
    entries = "\n".join(
        f"  <url><loc>https://{DOMAIN}{u}</loc></url>" for u in urls
    )
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries}\n</urlset>\n"
    )
    (root / "sitemap.xml").write_text(sitemap, encoding="utf-8")

    notfound = f"""<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pagina non trovata - Parco Culturale Ecclesiale Terre dell'Etna e dell'Alcantara</title>
  <meta name="robots" content="noindex">
  <style>
    body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 0;
           display: grid; place-items: center; min-height: 100vh; background: #f5f3ef; color: #2c3e50; }}
    main {{ text-align: center; padding: 2rem; max-width: 32rem; }}
    h1 {{ font-size: 3rem; margin: 0 0 .5rem; }}
    a {{ color: #1a73a8; }}
  </style>
</head>
<body>
  <main>
    <h1>404</h1>
    <p>La pagina che cerchi non esiste o è stata spostata.</p>
    <p><a href="https://www.parcoecclesialetna.it/">Torna alla home</a></p>
  </main>
</body>
</html>
"""
    (root / "404.html").write_text(notfound, encoding="utf-8")

    # sezioni presenti solo in italiano: pagina-ponte invece di un link morto
    for rel, target, title in [
        ("en/events", "../../it/eventi/", "Events"),
        ("en/il-territorio", "../../it/il-territorio/", "The territory"),
    ]:
        dest_dir = root / rel
        dest_dir.mkdir(parents=True, exist_ok=True)
        bridge = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} - Parco Culturale Ecclesiale Terre dell'Etna e dell'Alcantara</title>
  <meta name="robots" content="noindex">
  <style>
    body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 0;
           display: grid; place-items: center; min-height: 100vh; background: #f5f3ef; color: #2c3e50; }}
    main {{ text-align: center; padding: 2rem; max-width: 34rem; }}
    a {{ color: #1a73a8; }}
  </style>
</head>
<body>
  <main>
    <h1>{title}</h1>
    <p>This section is currently available in Italian only.</p>
    <p><a href="{target}">Continua in italiano</a></p>
    <p><a href="../../en/">Back to the English home</a></p>
  </main>
</body>
</html>
"""
        (dest_dir / "index.html").write_text(bridge, encoding="utf-8")


def fix_css(file: Path, root: Path) -> bool:
    text = file.read_text(encoding="utf-8", errors="replace")
    original = text
    depth = depth_of(file, root)

    text = CSS_ABS_RE.sub(lambda m: f"url({clean_path(m.group(1) or '/')})", text)
    text = CSS_ROOT_RE.sub(
        lambda m: f"url({to_relative(clean_path(m.group(1)), depth)})", text
    )

    if text != original:
        file.write_text(text, encoding="utf-8")
        return True
    return False


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SRC, OUT)
    clean_junk(OUT)
    moved = flatten_pagination(OUT)
    strip_query_filenames(OUT)

    fixed = 0
    for file in OUT.rglob("*.html"):
        if fix_html(file, OUT):
            fixed += 1

    css_fixed = 0
    for file in OUT.rglob("*.css"):
        if fix_css(file, OUT):
            css_fixed += 1

    build_extra_files(OUT)
    total = sum(1 for p in OUT.rglob("*") if p.is_file())
    print(f"Pagine paginazione: {len(moved)}")
    print(f"HTML modificati:    {fixed}")
    print(f"CSS modificati:     {css_fixed}")
    print(f"File totali:        {total}")


if __name__ == "__main__":
    main()
