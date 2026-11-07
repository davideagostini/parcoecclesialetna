# Parco Culturale Ecclesiale Terre dell'Etna e dell'Alcantara — sito statico

Sito statico di `www.parcoecclesialetna.it`: solo HTML, CSS, JS e immagini,
nessun backend.

## Struttura

```
site/                # quello che viene pubblicato (output directory)
  index.html         # home
  it/                # sito italiano
  en/                # sito inglese
  static/            # css, js, immagini, video
  media/             # immagini e PDF
  404.html
  robots.txt
  sitemap.xml
  CNAME
```

## Anteprima in locale

```sh
python3 -m http.server 8765 -d site
# poi apri http://127.0.0.1:8765/
```

## Deploy

Guida completa con passaggi DNS e checklist di verifica:
[`docs/deploy-github-pages.md`](docs/deploy-github-pages.md).

Il workflow GitHub Actions è pronto in `.github/workflows/pages.yml`, il file
`CNAME` viene generato automaticamente in `site/CNAME`.

I link interni sono relativi al documento, quindi il sito funziona sia su
`https://davideagostini.github.io/parcoecclesialetna/` sia sul dominio
personalizzato servito dalla radice.

## Note

- I contenuti sono congelati: il sito non viene più aggiornato.
- La paginazione con query string (`?page=2`) è stata convertita in pagine
  statiche (`/it/eventi/page-2/`).
- Le sezioni inglesi senza traduzione (`/en/events/`, `/en/il-territorio/`)
  puntano a una pagina-ponte verso la versione italiana.
