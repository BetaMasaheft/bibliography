#!/usr/bin/env python3
"""Fetch top-level items from Zotero group 358366 as TEI, merge into
EthioStudies.xml.

Same format=tei/biblStruct shape expand.xqm's live fallback already calls
per-tag (BetMasWeb modules/expand.xqm) - this is a bulk equivalent, run
ahead of time and committed as a local cache.

expand.xqm resolves bm: pointers via
  biblStruct[note[@type="tags"]/note[@type="tag"] = $ptr]
Zotero's current format=tei translator does not emit those tag notes, so
tags are fetched separately as format=json and injected into each
biblStruct after the TEI merge.

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
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

BASE = "https://api.zotero.org/groups/358366/items/top"
PAGE_LIMIT = 50
JSON_LIMIT = 100
MAX_PAGES = int(os.environ.get("MAX_PAGES", "0")) or None
OUT_PATH = os.environ.get("OUT_PATH", "EthioStudies.xml")
LISTBIBL_RE = re.compile(r"<listBibl[^>]*>(.*)</listBibl>", re.S)
XML_ID_RE = re.compile(
    r'xml:id="[^"]*"(\s+corresp="http://zotero\.org/groups/358366/items/([A-Za-z0-9]+)")'
)
BIBLSTRUCT_RE = re.compile(
    r'(<biblStruct\b[^>]*corresp="http://zotero\.org/groups/358366/items/'
    r'([A-Za-z0-9]+)"[^>]*>)(.*?)(</biblStruct>)',
    re.S,
)
UA = {"User-Agent": "BetaMasaheft-bibliography-refresh"}


def fetch(start, limit, fmt="tei", retries=3):
    url = f"{BASE}?format={fmt}&limit={limit}&start={start}"
    if not url.startswith("https://"):
        raise ValueError(f"refusing non-https URL: {url}")
    req = urllib.request.Request(url, headers=UA)
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read()
                total = resp.headers.get("Total-Results")
                backoff = resp.headers.get("Backoff")
                if backoff:
                    time.sleep(float(backoff))
                if fmt == "json":
                    return json.loads(raw.decode("utf-8")), total
                return raw.decode("utf-8"), total
        except urllib.error.HTTPError as e:
            if e.code == 500 and attempt < retries:
                time.sleep(1.5 * attempt)
                continue
            raise


def fetch_window(start, limit, total_results_box):
    """Fetch [start, start+limit); bisect on repeated 500, skip a lone bad item."""
    try:
        body, total = fetch(start, limit, fmt="tei")
        if total_results_box[0] is None:
            total_results_box[0] = total
        m = LISTBIBL_RE.search(body)
        n = body.count("<biblStruct")
        print(f"  tei window start={start} limit={limit}: +{n} biblStruct", file=sys.stderr)
        time.sleep(0.3)
        return [m.group(1)] if m else []
    except urllib.error.HTTPError as e:
        if limit == 1:
            print(f"  SKIPPING item at start={start}: {e}", file=sys.stderr)
            return []
        half = limit // 2
        print(f"  tei window start={start} limit={limit} failed ({e}), bisecting", file=sys.stderr)
        return (
            fetch_window(start, half, total_results_box)
            + fetch_window(start + half, limit - half, total_results_box)
        )


def fetch_tags_by_key():
    """Map Zotero item key -> list of tag strings via format=json."""
    tags_by_key = {}
    start = 0
    pages = 0
    total = None
    while True:
        pages += 1
        items, header_total = fetch(start, JSON_LIMIT, fmt="json")
        if total is None and header_total is not None:
            total = int(header_total)
        for item in items:
            data = item.get("data") or {}
            key = data.get("key") or item.get("key")
            if not key:
                continue
            tags_by_key[key] = [t["tag"] for t in data.get("tags") or [] if t.get("tag")]
        print(f"  json window start={start} limit={JSON_LIMIT}: "
              f"+{len(items)} items ({len(tags_by_key)} keys total)", file=sys.stderr)
        start += JSON_LIMIT
        time.sleep(0.3)
        if MAX_PAGES and pages >= MAX_PAGES:
            break
        if total is not None and start >= total:
            break
        if not items:
            break
    return tags_by_key


def inject_tags(body, tags_by_key):
    injected = 0

    def repl(m):
        nonlocal injected
        open_tag, key, inner, close = m.group(1), m.group(2), m.group(3), m.group(4)
        tags = tags_by_key.get(key) or []
        if not tags or 'type="tags"' in inner:
            return m.group(0)
        notes = "".join(
            f'<note type="tag">{html.escape(t, quote=True)}</note>' for t in tags
        )
        injected += 1
        return f'{open_tag}{inner}<note type="tags">{notes}</note>{close}'

    out = BIBLSTRUCT_RE.sub(repl, body)
    return out, injected


def main():
    print("fetching TEI biblStruct pages...", file=sys.stderr)
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

    print("fetching JSON tags...", file=sys.stderr)
    tags_by_key = fetch_tags_by_key()
    body, injected = inject_tags(body, tags_by_key)

    merged = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<listBibl xmlns="http://www.tei-c.org/ns/1.0">' + body + "</listBibl>\n"
    )
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(merged)
    tag_notes = merged.count('type="tag"')
    print(
        f"done: {pages} tei pages, total-results header={total_results_box[0]}, "
        f"{merged.count('<biblStruct')} biblStruct, "
        f"{injected} with injected tags notes, "
        f"{tag_notes} tag notes, written to {OUT_PATH}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
