#!/usr/bin/env python3
"""Fail closed when the portfolio violates its static, metadata, or privacy contract."""

from __future__ import annotations

import json
import re
import struct
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
ORIGIN = "https://patrickdev-it.github.io"
PUBLIC_ROLE = "AI Agent, Platform & Full-stack Engineer"
GOOGLE_SITE_VERIFICATION = "SDRpU9uekSorB0AMVWqNsg15J1lCjftGlEs79zDA-KM"
TRACKING_SIGNATURES = (
    "google-analytics.com",
    "googletagmanager.com",
    "gtag(",
    "plausible.io/js",
    "umami.is/script",
    "matomo.js",
    "hotjar.com",
    "cdn.segment.com",
    "mixpanel.init",
    "document.cookie",
    "localstorage.",
    "sessionstorage.",
)
INDEXNOW_KEY_PATTERN = re.compile(r"[a-f0-9]{32}\.txt")
FEATURED_PROJECTS = (
    ("/projects/prompt-enhancer/", "https://github.com/PatrickDev-it/cowork-prompt-enhancer"),
    ("/projects/sysops-agent/", "https://github.com/PatrickDev-it/sysops-agent"),
    ("/projects/autoblog-cms/", "https://github.com/PatrickDev-it/AutoBlog-CMS"),
    ("/projects/privacy-proxy/", "https://github.com/PatrickDev-it/VPN"),
)


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_count = 0
        self.in_title = False
        self.title_text: list[str] = []
        self.meta: list[dict[str, str]] = []
        self.links: list[dict[str, str]] = []
        self.scripts: list[dict[str, str]] = []
        self.script_payloads: list[str] = []
        self.current_script: list[str] | None = None
        self.forbidden_tags: list[str] = []
        self.html_lang = ""
        self.featured_depth = 0
        self.featured_links: list[str] = []
        self.headings: list[int] = []
        self.ids: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value or "" for key, value in attrs}
        if values.get("id"):
            self.ids.append(values["id"])
        if re.fullmatch(r"h[1-6]", tag):
            self.headings.append(int(tag[1]))
        if tag == "div":
            if self.featured_depth:
                self.featured_depth += 1
            elif "project-grid" in values.get("class", "").split():
                self.featured_depth = 1
        elif tag == "a" and self.featured_depth:
            self.featured_links.append(values.get("href", ""))
        if tag == "html":
            self.html_lang = values.get("lang", "")
        elif tag == "title":
            self.title_count += 1
            self.in_title = True
        elif tag == "meta":
            self.meta.append(values)
        elif tag in {"a", "link", "img", "script"}:
            self.links.append({"tag": tag, **values})
        if tag == "script":
            self.scripts.append(values)
            self.current_script = []
        if tag in {"form", "iframe", "embed", "object"}:
            self.forbidden_tags.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag == "div" and self.featured_depth:
            self.featured_depth -= 1
        if tag == "title":
            self.in_title = False
        elif tag == "script" and self.current_script is not None:
            self.script_payloads.append("".join(self.current_script))
            self.current_script = None

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_text.append(data)
        if self.current_script is not None:
            self.current_script.append(data)


def meta_value(parser: PageParser, key: str, value: str, content: str = "content") -> str:
    for item in parser.meta:
        if item.get(key) == value:
            return item.get(content, "")
    return ""


def local_target(url: str) -> Path | None:
    parsed = urlparse(url)
    if parsed.scheme or parsed.netloc or url.startswith(("#", "mailto:", "tel:")):
        return None
    path = parsed.path
    if not path:
        return None
    candidate = SITE / path.lstrip("/")
    if path.endswith("/"):
        candidate /= "index.html"
    return candidate


def published_asset(url: str) -> Path | None:
    """Resolve first-party absolute URLs to the static artifact they advertise."""
    parsed = urlparse(url)
    if f"{parsed.scheme}://{parsed.netloc}" != ORIGIN or not parsed.path:
        return None
    return SITE / parsed.path.lstrip("/")


def png_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        header = path.read_bytes()[:24]
        if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
            return None
        return struct.unpack(">II", header[16:24])
    except OSError:
        return None


def validate_html(path: Path) -> list[str]:
    errors: list[str] = []
    raw = path.read_text(encoding="utf-8")
    parser = PageParser()
    parser.feed(raw)
    relative = path.relative_to(ROOT)
    is_error_page = path.name == "404.html"

    if parser.html_lang != "en":
        errors.append(f"{relative}: html lang must be 'en'")
    if parser.title_count != 1 or not "".join(parser.title_text).strip():
        errors.append(f"{relative}: requires exactly one non-empty title")
    if parser.forbidden_tags:
        errors.append(f"{relative}: forbidden elements: {', '.join(sorted(set(parser.forbidden_tags)))}")
    duplicate_ids = sorted(identifier for identifier, count in Counter(parser.ids).items() if count > 1)
    if duplicate_ids:
        errors.append(f"{relative}: duplicate element IDs: {', '.join(duplicate_ids)}")
    if parser.headings.count(1) != 1 or not parser.headings or parser.headings[0] != 1:
        errors.append(f"{relative}: requires one h1 as the first heading")
    for previous, current in zip(parser.headings, parser.headings[1:]):
        if current > previous + 1:
            errors.append(f"{relative}: heading level skips from h{previous} to h{current}")

    if not is_error_page:
        required = {
            "meta description": meta_value(parser, "name", "description"),
            "robots policy": meta_value(parser, "name", "robots"),
            "Open Graph site name": meta_value(parser, "property", "og:site_name"),
            "Open Graph title": meta_value(parser, "property", "og:title"),
            "Open Graph description": meta_value(parser, "property", "og:description"),
            "Open Graph URL": meta_value(parser, "property", "og:url"),
            "Open Graph image": meta_value(parser, "property", "og:image"),
            "Open Graph image width": meta_value(parser, "property", "og:image:width"),
            "Open Graph image height": meta_value(parser, "property", "og:image:height"),
            "Open Graph image alt text": meta_value(parser, "property", "og:image:alt"),
            "Twitter card": meta_value(parser, "name", "twitter:card"),
            "Twitter title": meta_value(parser, "name", "twitter:title"),
            "Twitter description": meta_value(parser, "name", "twitter:description"),
            "Twitter image": meta_value(parser, "name", "twitter:image"),
            "Twitter image alt text": meta_value(parser, "name", "twitter:image:alt"),
        }
        for label, value in required.items():
            if not value:
                errors.append(f"{relative}: missing {label}")
        canonical = next(
            (item.get("href", "") for item in parser.links if item.get("tag") == "link" and item.get("rel") == "canonical"),
            "",
        )
        if not canonical.startswith(f"{ORIGIN}/"):
            errors.append(f"{relative}: missing or invalid canonical URL")
        alternates = {
            item.get("hreflang", ""): item.get("href", "")
            for item in parser.links
            if item.get("tag") == "link" and item.get("rel") == "alternate"
        }
        for language in ("en", "x-default"):
            if alternates.get(language) != canonical:
                errors.append(f"{relative}: {language} alternate must match the canonical URL")

        og_image = required["Open Graph image"]
        twitter_image = required["Twitter image"]
        if og_image and twitter_image and og_image != twitter_image:
            errors.append(f"{relative}: Open Graph and Twitter images must reference the same asset")
        asset = published_asset(og_image)
        if asset is None or not asset.is_file():
            errors.append(f"{relative}: social preview must be an existing first-party asset")
        elif png_dimensions(asset) != (1200, 630):
            errors.append(f"{relative}: social preview must be a 1200x630 PNG")
        if path.parent.parent.name == "projects" and asset is not None and asset.name == "social-card.png":
            errors.append(f"{relative}: project pages require a project-specific social preview")

    for index, script in enumerate(parser.scripts):
        if script.get("type") != "application/ld+json" or script.get("src"):
            errors.append(f"{relative}: executable or remote script is forbidden")
            continue
        try:
            json.loads(parser.script_payloads[index])
        except (json.JSONDecodeError, IndexError) as exc:
            errors.append(f"{relative}: invalid JSON-LD: {exc}")

    lowered = raw.lower()
    for signature in TRACKING_SIGNATURES:
        if signature in lowered:
            errors.append(f"{relative}: tracking or browser-storage signature found: {signature}")

    for item in parser.links:
        tag = item.get("tag", "")
        url = item.get("href", "") if tag in {"a", "link"} else item.get("src", "")
        is_runtime_link = tag == "link" and item.get("rel") in {"stylesheet", "icon", "manifest", "preload", "modulepreload"}
        if (tag in {"img", "script"} or is_runtime_link) and url.startswith(("http://", "https://", "//")):
            errors.append(f"{relative}: remote runtime resource is forbidden: {url}")
        target = local_target(url)
        if target is not None and not target.exists():
            errors.append(f"{relative}: broken internal reference: {url}")
        if tag == "a" and url.startswith("#") and url[1:] not in parser.ids:
            errors.append(f"{relative}: broken same-page fragment: {url}")
    return errors


def main() -> int:
    errors: list[str] = []
    html_files = sorted(SITE.rglob("*.html"))
    if not html_files:
        errors.append("No HTML pages found")
    for path in html_files:
        errors.extend(validate_html(path))

    featured_paths = [path for path, _repository in FEATURED_PROJECTS]
    home_parser = PageParser()
    home_parser.feed((SITE / "index.html").read_text(encoding="utf-8"))
    if GOOGLE_SITE_VERIFICATION != meta_value(home_parser, "name", "google-site-verification"):
        errors.append("site/index.html: missing or incorrect Google Search Console verification")
    if PUBLIC_ROLE not in "".join(home_parser.title_text):
        errors.append(f"site/index.html: title must expose the public role '{PUBLIC_ROLE}'")
    if home_parser.featured_links != featured_paths:
        errors.append(
            "site/index.html: featured project links must match the pinned repository order "
            f"(expected={featured_paths}, actual={home_parser.featured_links})"
        )

    home_documents: list[object] = []
    for payload in home_parser.script_payloads:
        try:
            home_documents.append(json.loads(payload))
        except json.JSONDecodeError:
            continue
    item_lists = [
        node
        for document in home_documents
        if isinstance(document, dict)
        for node in document.get("@graph", [])
        if isinstance(node, dict) and node.get("@type") == "ItemList"
    ]
    structured_paths = [
        urlparse(item.get("url", "")).path
        for item_list in item_lists
        for item in item_list.get("itemListElement", [])
        if isinstance(item, dict)
    ]
    if len(item_lists) != 1 or structured_paths != featured_paths:
        errors.append(
            "site/index.html: JSON-LD ItemList must match the pinned repository order "
            f"(expected={featured_paths}, actual={structured_paths})"
        )

    people = [
        node
        for document in home_documents
        if isinstance(document, dict)
        for node in document.get("@graph", [])
        if isinstance(node, dict) and node.get("@type") == "Person"
    ]
    if len(people) != 1 or people[0].get("jobTitle") != PUBLIC_ROLE:
        errors.append(f"site/index.html: Person jobTitle must equal '{PUBLIC_ROLE}'")

    llms = (SITE / "llms.txt").read_text(encoding="utf-8") if (SITE / "llms.txt").exists() else ""
    project_section = llms.partition("## Project cases")[2].partition("## Primary sources")[0]
    llms_paths = [urlparse(url).path for url in re.findall(r"\]\((https://[^)]+)\)", project_section)]
    if llms_paths != featured_paths:
        errors.append(
            "site/llms.txt: project cases must match the pinned repository order "
            f"(expected={featured_paths}, actual={llms_paths})"
        )

    for project_path, repository in FEATURED_PROJECTS:
        page = SITE / project_path.lstrip("/") / "index.html"
        if not page.is_file() or repository not in page.read_text(encoding="utf-8"):
            errors.append(f"site{project_path}: missing canonical repository link {repository}")

    try:
        sitemap = ElementTree.parse(SITE / "sitemap.xml")
        locations = {node.text for node in sitemap.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url/{http://www.sitemaps.org/schemas/sitemap/0.9}loc")}
        indexable_html = []
        for path in html_files:
            parser = PageParser()
            parser.feed(path.read_text(encoding="utf-8"))
            if path.name != "404.html" and "noindex" not in meta_value(parser, "name", "robots").lower():
                indexable_html.append(path)
        expected = {
            ORIGIN + ("/" if path == SITE / "index.html" else "/" + path.parent.relative_to(SITE).as_posix() + "/")
            for path in indexable_html
        }
        if locations != expected:
            errors.append(f"site/sitemap.xml: URL set differs from indexable HTML pages (missing={sorted(expected - locations)}, extra={sorted(locations - expected)})")
    except (ElementTree.ParseError, OSError) as exc:
        errors.append(f"site/sitemap.xml: invalid or missing: {exc}")

    robots = (SITE / "robots.txt").read_text(encoding="utf-8") if (SITE / "robots.txt").exists() else ""
    if f"Sitemap: {ORIGIN}/sitemap.xml" not in robots or "Allow: /" not in robots:
        errors.append("site/robots.txt: missing allow or canonical sitemap directive")

    indexnow_keys = [path for path in SITE.glob("*.txt") if INDEXNOW_KEY_PATTERN.fullmatch(path.name)]
    if len(indexnow_keys) != 1:
        errors.append("site: requires exactly one 32-character IndexNow verification file")
    elif indexnow_keys[0].read_text(encoding="utf-8").strip() != indexnow_keys[0].stem:
        errors.append("site: IndexNow verification file content must match its filename")

    if errors:
        print("Static-site validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Static-site validation passed: {len(html_files)} HTML pages, no executable scripts or remote runtime resources.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
