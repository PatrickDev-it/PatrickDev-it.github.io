# Patrick Dev — static engineering portfolio

The source for [patrickdev-it.github.io](https://patrickdev-it.github.io/), an evidence-led engineering portfolio optimized for fast delivery, accessible reading, search discovery, and low maintenance.

## Design constraints

- Hand-authored semantic HTML and CSS; no framework, package manager, build step, client-side application, or executable JavaScript.
- No first-party analytics, advertising, cookies, browser storage, fingerprinting, forms, embeds, remote fonts, or runtime CDN dependencies.
- One small local stylesheet, local SVG assets, immutable Git history, and native GitHub Pages hosting.
- Unique titles, descriptions, canonical and language-alternate URLs, per-project social previews, entity-linked JSON-LD, sitemap, robots policy, automated IndexNow notification, and an experimental `llms.txt` discovery surface.
- Claims are status-qualified and link to primary repository evidence when it exists.

GitHub Pages may process technical request information as part of its own hosting and security operation. The site's exact data-use statement is published at `/privacy/`; this repository does not claim legal compliance certification.

## Structure

```text
site/
├── index.html
├── about/
├── privacy/
├── projects/
├── assets/
├── .well-known/security.txt
├── robots.txt
├── sitemap.xml
└── llms.txt
```

## Validate locally

```bash
python scripts/validate_site.py
python scripts/submit_indexnow.py --dry-run
python -m http.server 8000 --directory site
```

The validator fails on incomplete page or social metadata, missing or malformed 1200×630 first-party previews, invalid structured data, broken internal links, executable scripts, forms, embeds, common tracking signatures, or remote runtime resources.

## Deploy

Pushes to `main` run validation, publish the exact `site/` directory with GitHub's official Pages workflow, and then notify IndexNow participants using the canonical sitemap. Search-engine notification runs after deployment and does not introduce browser-side code or data collection. There is no generated production output to drift from source.

## Maintenance

Update the affected HTML page, structured-data `dateModified`, social preview, and `sitemap.xml` when a project status changes. Review `.well-known/security.txt` before its expiry date. Search Console and Bing Webmaster Tools verification remain optional account-level operations; the site itself has no analytics dependency. No dependency-update cycle is required for the website itself; only the GitHub Actions versions require periodic review.

## License

Code and original site content are available under the [MIT License](LICENSE).
