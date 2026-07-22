#!/usr/bin/env python3
"""Notify IndexNow about the canonical URLs in the deployed sitemap."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
ORIGIN = "https://patrickdev-it.github.io"
ENDPOINT = "https://api.indexnow.org/indexnow"
KEY_PATTERN = re.compile(r"[a-f0-9]{32}\.txt")


def load_submission() -> dict[str, object]:
    key_files = [path for path in SITE.glob("*.txt") if KEY_PATTERN.fullmatch(path.name)]
    if len(key_files) != 1:
        raise ValueError("Expected exactly one 32-character IndexNow key file at the site root")

    key_file = key_files[0]
    key = key_file.read_text(encoding="utf-8").strip()
    if key != key_file.stem:
        raise ValueError("IndexNow key file contents must match its filename")

    sitemap = ElementTree.parse(SITE / "sitemap.xml")
    urls = [
        node.text
        for node in sitemap.findall(
            "{http://www.sitemaps.org/schemas/sitemap/0.9}url/"
            "{http://www.sitemaps.org/schemas/sitemap/0.9}loc"
        )
        if node.text
    ]
    if not urls or any(not url.startswith(f"{ORIGIN}/") for url in urls):
        raise ValueError("Sitemap contains no URLs or a URL outside the canonical host")

    return {
        "host": "patrickdev-it.github.io",
        "key": key,
        "keyLocation": f"{ORIGIN}/{key_file.name}",
        "urlList": urls,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate the key and sitemap without contacting IndexNow",
    )
    args = parser.parse_args()
    try:
        payload = load_submission()
        if args.dry_run:
            print(
                f"IndexNow payload validated: {len(payload['urlList'])} canonical URLs, "
                f"key at {payload['keyLocation']}."
            )
            return 0
        request = Request(
            ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "PatrickDev-it-portfolio-indexer/1.0",
            },
            method="POST",
        )
        with urlopen(request, timeout=20) as response:
            if response.status not in {200, 202}:
                raise RuntimeError(f"Unexpected IndexNow response: HTTP {response.status}")
        print(f"IndexNow accepted {len(payload['urlList'])} canonical URLs (HTTP {response.status}).")
        return 0
    except (ValueError, RuntimeError, HTTPError, URLError, OSError, ElementTree.ParseError) as exc:
        print(f"IndexNow notification failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
