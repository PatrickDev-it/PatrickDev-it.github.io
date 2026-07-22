# Patrick Dev Engineering Portfolio

A zero-dependency, static engineering portfolio optimized for fast delivery, crawlability, explicit
project semantics, and low maintenance.

## Runtime contract

- Static HTML and CSS only.
- No application JavaScript.
- No analytics, tracking pixels, cookies, browser storage, forms, advertising, external fonts, CDNs, or embeds.
- No build framework or package-manager dependency.
- GitHub Pages is the only hosting layer.
- All project-status statements distinguish target evidence from verified release evidence.

GitHub Pages may process technical hosting logs under GitHub's own privacy policy. This repository does not
create a first-party visitor profile or receive an analytics feed.

## Information architecture

```text
site/
├── index.html
├── about/index.html
├── privacy/index.html
├── projects/*/index.html
├── assets/{styles.css,favicon.svg,social-card.svg,social-card.png}
├── robots.txt
├── sitemap.xml
├── llms.txt
└── site.webmanifest
```

Each indexable page contains a unique title, description, canonical URL, Open Graph metadata and structured
data. `llms.txt` is provided as a lightweight machine-readable index; canonical HTML remains authoritative.

## Local review

```bash
python scripts/validate_site.py
python -m http.server 8000 --directory site
```

Open `http://localhost:8000`.

## Deployment

Pushes to `main` run the standard-library validator, package `site/`, and deploy the exact static artifact
through GitHub Pages. Pull requests validate without deploying.

## Maintenance

When project status changes:

1. update the project page and home-page card;
2. update the relevant structured data and `dateModified`;
3. update `sitemap.xml` `lastmod`;
4. update `llms.txt` if the canonical project description changes;
5. run `python scripts/validate_site.py`;
6. deploy only after the linked repository evidence passes.

## Known platform constraint

GitHub Pages controls hosting-level HTTP headers and server logs. The site avoids runtime code and third-party
requests to minimize the remaining browser-side privacy and security surface.
