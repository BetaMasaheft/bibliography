#!/usr/bin/env python3
"""Fetch top-level items from Zotero group 358366 as TEI, merge into
EthioStudies.xml.

Same format=tei/biblStruct shape expand.xqm's live fallback already calls
per-tag (BetMasWeb modules/expand.xqm) - this is a bulk equivalent, run
ahead of time and committed as a local cache.

format=tei 500s on some (start, limit) windows regardless of limit size -
some items choke the translator. Bisects a failing window down to
individual items and skips (logs) any single item that still 500s.

Zotero's own xml:id (author-year citekey) is disambiguated per request,
not globally, so paginated fetches produce duplicate ids across pages.
Replaced with item_<zotero-key> (from each entry's own corresp URL) after
merging - always unique, always a valid NCName.

Usage: python3 bin/refresh-ethiostudies.py
Env: MAX_PAGES=N to stop after N page windows (manual testing).
"""
import os
import re
import sys
import time
import urllib.error
import urllib.request

BASE = "https://api.zotero.org/groups/358366/items/top"
PAGE_LIMIT = 50
MAX_PAGES = int(os.environ.get("MAX_PAGES", "0")) or None
OUT_PATH = os.environ.get("OUT_PATH", "EthioStudies.xml")
LISTBIBL_RE = re.compile(r"<listBibl[^>]*>(.*)</listBibl>", re.S)
XML_ID_RE = re.compile(
    r'xml:id="[^"]*"(\s+corresp="http://zotero\.org/groups/358366/items/([A-Za-z0-9]+)")'
)


def fetch(start, limit, retries=3):
    url = f"{BASE}?format=tei&limit={limit}&start={start}"
    req = urllib.request.Request(url, headers={"User-Agent": "BetaMasaheft-bibliography-refresh"})
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read().decode("utf-8")
                total = resp.headers.get("Total-Results")
                backoff = resp.headers.get("Backoff")
                if backoff:
                    time.sleep(float(backoff))
                return body, total
        except urllib.error.HTTPError as e:
            if e.code == 500 and attempt < retries:
                time.sleep(1.5 * attempt)
                continue
            raise


def fetch_window(start, limit, total_results_box):
    """Fetch [start, start+limit); bisect on repeated 500, skip a lone bad item."""
    try:
        body, total = fetch(start, limit)
        if total_results_box[0] is None:
            total_results_box[0] = total
        m = LISTBIBL_RE.search(body)
        n = body.count("<biblStruct")
        print(f"  window start={start} limit={limit}: +{n} biblStruct", file=sys.stderr)
        time.sleep(0.3)
        return [m.group(1)] if m else []
    except urllib.error.HTTPError as e:
        if limit == 1:
            print(f"  SKIPPING item at start={start}: {e}", file=sys.stderr)
            return []
        half = limit // 2
        print(f"  window start={start} limit={limit} failed ({e}), bisecting", file=sys.stderr)
        return (
            fetch_window(start, half, total_results_box)
            + fetch_window(start + half, limit - half, total_results_box)
        )


def main():
    total_results_box = [None]
    start = 0
    pages = 0
    chunks = []
    while True:
        pages += 1
        chunks.extend(fetch_window(start, PAGE_LIMIT, total_results_box))
        total = total_results_box[0]
        start += PAGE_LIMIT
        if MAX_PAGES and pages >= MAX_PAGES:
            break
        if total is not None and start >= int(total):
            break

    body = "".join(chunks)
    body = XML_ID_RE.sub(r'xml:id="item_\2"\1', body)
    merged = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<listBibl xmlns="http://www.tei-c.org/ns/1.0">' + body + "</listBibl>\n"
    )
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(merged)
    print(f"done: {pages} pages, total-results header={total_results_box[0]}, "
          f"{merged.count('<biblStruct')} biblStruct written to {OUT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
