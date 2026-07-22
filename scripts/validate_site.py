from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
REQUIRED_FILES = {
    "index.html",
    "404.html",
    "about/index.html",
    "privacy/index.html",
    "projects/prompt-enhancer/index.html",
    "projects/autoblog-cms/index.html",
    "projects/image-classifier/index.html",
    "projects/loyalty-platform/index.html",
    "assets/styles.css",
    "assets/favicon.svg",
    "assets/social-card.png",
    "robots.txt",
    "sitemap.xml",
    "site.webmanifest",
    "llms.txt",
    ".nojekyll",
}
FORBIDDEN_PATTERNS = {
    "analytics": re.compile(r"google-analytics|googletagmanager|gtag\s*\(|plausible|umami|hotjar|segment\.com", re.I),
    "tracking APIs": re.compile(r"document\.cookie|localStorage|sessionStorage|indexedDB", re.I),
    "remote runtime asset": re.compile(r"<(?:script|img|iframe)[^>]+(?:src)=['\"]https?://", re.I),
    "remote stylesheet": re.compile(r"<link[^>]+rel=['\"]stylesheet['\"][^>]+href=['\"]https?://", re.I),
}


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_count = 0
        self.in_title = False
        self.title_text: list[str] = []
        self.meta_names: set[str] = set()
        self.meta_properties: set[str] = set()
        self.canonicals: list[str] = []
        self.hrefs: list[str] = []
        self.script_types: list[str] = []
        self.json_ld_text: list[str] = []
        self.current_json_ld = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value or "" for key, value in attrs}
        if tag == "title":
            self.title_count += 1
            self.in_title = True
        elif tag == "meta":
            if values.get("name"):
                self.meta_names.add(values["name"].lower())
            if values.get("property"):
                self.meta_properties.add(values["property"].lower())
        elif tag == "link":
            if values.get("rel") == "canonical":
                self.canonicals.append(values.get("href", ""))
            if values.get("href"):
                self.hrefs.append(values["href"])
        elif tag == "a" and values.get("href"):
            self.hrefs.append(values["href"])
        elif tag == "script":
            script_type = values.get("type", "")
            self.script_types.append(script_type)
            self.current_json_ld = script_type == "application/ld+json"

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        elif tag == "script":
            self.current_json_ld = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_text.append(data)
        if self.current_json_ld:
            self.json_ld_text.append(data)


def resolve_internal(page: Path, href: str) -> Path | None:
    parsed = urlparse(href)
    if parsed.scheme or parsed.netloc or href.startswith(("#", "mailto:", "tel:")):
        return None
    clean = unquote(parsed.path)
    if not clean:
        return None
    target = SITE / clean.lstrip("/") if clean.startswith("/") else page.parent / clean
    if clean.endswith("/"):
        target /= "index.html"
    elif target.is_dir():
        target /= "index.html"
    return target.resolve()


def validate_page(page: Path) -> list[str]:
    errors: list[str] = []
    source = page.read_text(encoding="utf-8")
    parser = PageParser()
    parser.feed(source)
    relative = page.relative_to(SITE)

    if parser.title_count != 1 or not "".join(parser.title_text).strip():
        errors.append(f"{relative}: expected one non-empty title")
    for required in {"description", "robots"}:
        if required not in parser.meta_names:
            errors.append(f"{relative}: missing meta name={required}")
    for required in {"og:type", "og:title", "og:description", "og:url", "og:image"}:
        if required not in parser.meta_properties:
            errors.append(f"{relative}: missing meta property={required}")
    if len(parser.canonicals) != 1 or not parser.canonicals[0].startswith("https://patrickdev-it.github.io/"):
        errors.append(f"{relative}: expected one canonical portfolio URL")
    if any(script_type != "application/ld+json" for script_type in parser.script_types):
        errors.append(f"{relative}: executable JavaScript is not allowed")
    if parser.json_ld_text:
        try:
            json.loads("".join(parser.json_ld_text))
        except json.JSONDecodeError as exc:
            errors.append(f"{relative}: invalid JSON-LD: {exc}")

    for label, pattern in FORBIDDEN_PATTERNS.items():
        if pattern.search(source):
            errors.append(f"{relative}: forbidden {label}")

    for href in parser.hrefs:
        target = resolve_internal(page, href)
        if target is not None and not target.exists():
            errors.append(f"{relative}: broken internal target {href}")
    return errors


def main() -> int:
    errors: list[str] = []
    for required in sorted(REQUIRED_FILES):
        if not (SITE / required).exists():
            errors.append(f"missing required file: {required}")
    for page in sorted(SITE.rglob("*.html")):
        errors.extend(validate_page(page))

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Validated {len(list(SITE.rglob('*.html')))} HTML pages: metadata, links, JSON-LD, and privacy constraints pass.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
