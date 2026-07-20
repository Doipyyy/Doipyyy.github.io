#!/usr/bin/env python3
"""
Enrich a hand-maintained list of your own TikTok video URLs with public
metadata (title, author, thumbnail, embed HTML) via TikTok's official,
key-free oEmbed endpoint: https://developers.tiktok.com/doc/embed-videos/

This does NOT scrape TikTok or bypass any protections. You provide the URLs
of your own uploads in videos.json; this script only asks the public oEmbed
service to describe each one so your site can render nice cards.

Usage:
    python fetch_videos.py                 # reads videos.json, writes videos.enriched.json
    python fetch_videos.py --in urls.json --out out.json

videos.json schema (input):
    { "videos": [ "https://www.tiktok.com/@you/video/123", ... ] }
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

OEMBED_ENDPOINT = "https://www.tiktok.com/oembed?url="
REQUEST_TIMEOUT = 15  # seconds
RETRIES = 3
RETRY_BACKOFF = 2.0  # seconds, multiplied by attempt number


def fetch_oembed(video_url: str) -> dict:
    """Return the oEmbed payload for a single video, or raise on failure."""
    req = Request(
        OEMBED_ENDPOINT + quote(video_url, safe=""),
        headers={"User-Agent": "Doipyyy.github.io video lister (+oembed)"},
    )
    last_err: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        try:
            with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                if resp.status != 200:
                    raise URLError(f"HTTP {resp.status}")
                return json.loads(resp.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as err:
            last_err = err
            if attempt < RETRIES:
                wait = RETRY_BACKOFF * attempt
                print(f"  attempt {attempt} failed ({err}); retrying in {wait:.0f}s",
                      file=sys.stderr)
                time.sleep(wait)
    raise RuntimeError(f"gave up after {RETRIES} attempts: {last_err}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="infile", default="videos.json")
    parser.add_argument("--out", dest="outfile", default="videos.enriched.json")
    args = parser.parse_args()

    src = Path(args.infile)
    if not src.exists():
        print(f"error: {src} not found. Create it with your video URLs.", file=sys.stderr)
        return 1

    try:
        urls = json.loads(src.read_text()).get("videos", [])
    except (json.JSONDecodeError, OSError) as err:
        print(f"error: could not read {src}: {err}", file=sys.stderr)
        return 1

    if not urls:
        print(f"error: no URLs in {src} under the \"videos\" key.", file=sys.stderr)
        return 1

    enriched: list[dict] = []
    failures = 0
    for url in urls:
        print(f"fetching {url}")
        try:
            data = fetch_oembed(url)
            enriched.append({
                "url": url,
                "title": data.get("title", ""),
                "author": data.get("author_name", ""),
                "thumbnail": data.get("thumbnail_url", ""),
                "embed_html": data.get("html", ""),
            })
        except RuntimeError as err:
            failures += 1
            print(f"  skipped: {err}", file=sys.stderr)

    out = Path(args.outfile)
    out.write_text(json.dumps({"videos": enriched}, indent=2, ensure_ascii=False))
    print(f"\nwrote {len(enriched)} video(s) to {out} ({failures} failed).")
    return 0 if enriched else 1


if __name__ == "__main__":
    raise SystemExit(main())
