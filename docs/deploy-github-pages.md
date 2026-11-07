# Deploy su GitHub Pages

Alternativa gratuita e senza servizi esterni. Ha però un vincolo importante:
con il piano **Free** GitHub Pages funziona **solo con repository pubblici**.
Con repo privato serve GitHub Pro (a pagamento).

## Riepilogo

| Voce | Valore |
|---|---|
| Costo | 0 € (repo pubblico) |
| Repo | **pubblico** |
| Banda | ~100 GB/mese (soft limit) |
| Spazio | 1 GB per sito |
| Build | 10/ora (soft limit) |
| Dominio | `www.parcoecclesialetna.it` primario + apex |
| File speciali | `CNAME`, `404.html`, `.nojekyll` |

> Il contenuto del sito è già pubblico sul web, quindi pubblicare il repo non
> espone nulla di sensibile.

## 1. Rendi pubblico il repository

GitHub → repo → **Settings** → **General** → **Danger Zone** → **Change visibility** → **Public**.

## 2. Aggiungi il file CNAME

Il dominio personalizzato deve essere dentro l'artefatto pubblicato:

```sh
echo "www.parcoecclesialetna.it" > site/CNAME
git add site/CNAME
git commit -m "Add CNAME for GitHub Pages"
git push
```

## 3. Configura il deploy con GitHub Actions (consigliato)

Copia `docs/github-pages-workflow.yml` in `.github/workflows/pages.yml`:

```sh
mkdir -p .github/workflows
cp docs/github-pages-workflow.yml .github/workflows/pages.yml
```

Il contenuto è:

```yaml
name: Deploy static site to Pages

on:
  push:
    branches: ["main"]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: true

jobs:
  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with:
          path: site
      - id: deployment
        uses: actions/deploy-pages@v4
```

Poi su GitHub: **Settings** → **Pages** → **Build and deployment** →
**Source: GitHub Actions**.

Al primo push su `main` il sito viene pubblicato su
`https://<utente>.github.io/<repo>/`.

> Il redirect `/` → `/it/` è fatto da `site/index.html` con un meta refresh.
> Anche `404.html` viene servito automaticamente.
>
> I link interni sono relativi al documento: il sito funziona sia sotto
> `https://<utente>.github.io/<repo>/` sia sul dominio personalizzato servito
> dalla radice.

### Alternativa senza Actions

Se preferisci evitare le Actions, puoi pubblicare direttamente il contenuto:

```sh
git subtree split --prefix site -b gh-pages
git push origin gh-pages
```

e impostare **Source: Deploy from a branch** → branch `gh-pages` → `/ (root)`.
Metodo più semplice ma il branch `gh-pages` contiene solo il sito, senza script.

## 4. Configura il DNS

Il DNS resta sul provider attuale: nessun cambio nameserver e nessun intervento
su DNSSEC.

### Record da creare

| Tipo | Nome | Valore |
|---|---|---|
| CNAME | `www` | `<utente>.github.io` |
| A | `@` | `185.199.108.153` |
| A | `@` | `185.199.109.153` |
| A | `@` | `185.199.110.153` |
| A | `@` | `185.199.111.153` |
| AAAA | `@` | `2606:50c0:8000::153` |
| AAAA | `@` | `2606:50c0:8001::153` |
| AAAA | `@` | `2606:50c0:8002::153` |
| AAAA | `@` | `2606:50c0:8003::153` |

Poi **cancella i record A/AAAA del vecchio hosting** e imposta il TTL a **300**.

## 5. Imposta il dominio su GitHub

**Settings** → **Pages** → **Custom domain** → inserisci
`www.parcoecclesialetna.it` → **Save**.

GitHub verifica il DNS (può volerci qualche minuto). Quando compare la voce,
attiva **Enforce HTTPS**.

Con il file `CNAME` impostato su `www`, le richieste all'apex
`parcoecclesialetna.it` vengono reindirizzate a `www`. I canonical delle pagine
puntano già a `https://www.parcoecclesialetna.it/...`.

## 6. Verifica prima di dismettere il vecchio hosting

```sh
dig +short CNAME www.parcoecclesialetna.it
dig +short A parcoecclesialetna.it

curl -I https://www.parcoecclesialetna.it/
curl -I https://parcoecclesialetna.it/          # deve rispondere 301 -> www
curl -I https://www.parcoecclesialetna.it/it/eventi/page-2/
curl -I https://www.parcoecclesialetna.it/media/opera/assunzione_assunta.jpg
```

Checklist finale:

- [ ] Home IT e EN caricano
- [ ] Paginazione `/it/eventi/page-2/` funziona
- [ ] Immagini e video presenti
- [ ] `https://parcoecclesialetna.it` → redirect a `www`
- [ ] Certificato HTTPS valido
- [ ] Il vecchio hosting non riceve più traffico

## Problemi comuni

| Sintomo | Causa | Rimedio |
|---|---|---|
| 404 su tutto | Pages non configurato o branch sbagliato | Settings → Pages → Source e branch |
| 404 sulle pagine interne | build pubblica la root invece di `site` | Correggere `path: site` nel workflow |
| Dominio "not properly formatted" | record A rimasti sul vecchio hosting | Cancellare i vecchi record |
| HTTPS non attivo | DNS non ancora verificato | Attendere la verifica e riprovare |
| Sito senza stile | `CNAME` o `site/` non inclusi nell'artefatto | Verificare il commit deployato |
