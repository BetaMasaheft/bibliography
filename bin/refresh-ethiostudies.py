#!/usr/bin/env python3
"""Fetch top-level items from Zotero group 358366 into local caches.

EthioStudies.xml (format=tei)
    expand.xqm resolves bm: pointers via
      biblStruct[note[@type="tags"]/note[@type="tag"] = $ptr]
    Zotero's current format=tei translator omits those tag notes, so tags
    are fetched as format=json and injected after merge.

citations.xml (format=json include=bib)
    string:Zotero() needs pre-styled CSL HTML keyed by bm: tag
    (style=hiob-ludolf-centre-for-ethiopian-studies&linkwrap=1).

format=tei 500s on some windows; bisects and skips lone bad items.

xml:id is rewritten to item_<zotero-key> after merge (citekeys collide
across paginated requests).

Usage: python3 bin/refresh-ethiostudies.py
Env: MAX_PAGES=N (test), SKIP_TEI=1 (citations.xml only).
"""
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

BASE = "https://api.zotero.org/groups/358366/items/top"
PAGE_LIMIT = 50
JSON_LIMIT = 100
BIB_STYLE = "hiob-ludolf-centre-for-ethiopian-studies"
MAX_PAGES = int(os.environ.get("MAX_PAGES", "0")) or None
SKIP_TEI = os.environ.get("SKIP_TEI", "") in ("1", "true", "yes")
OUT_PATH = os.environ.get("OUT_PATH", "EthioStudies.xml")
CITATIONS_PATH = os.environ.get("CITATIONS_PATH", "citations.xml")
LISTBIBL_RE = re.compile(r"<listBibl[^>]*>(.*)</listBibl>", re.S)
XML_ID_RE = re.compile(
    r'xml:id="[^"]*"(\s+corresp="http://zotero\.org/groups/358366/items/([A-Za-z0-9]+)")'
)
BIBLSTRUCT_RE = re.compile(
    r'(<biblStruct\b[^>]*corresp="http://zotero\.org/groups/358366/items/'
    r'([A-Za-z0-9]+)"[^>]*>)(.*?)(</biblStruct>)',
    re.S,
)
CSL_ENTRY_RE = re.compile(r'<div class="csl-entry"[^>]*>(.*?)</div>', re.S)
UA = {"User-Agent": "BetaMasaheft-bibliography-refresh"}
JSON_BIB_QS = (
    "&include=bib,data"
    f"&style={urllib.parse.quote(BIB_STYLE)}"
    "&linkwrap=1"
)


def fetch(start, limit, fmt="tei", extra="", retries=3):
    url = f"{BASE}?format={fmt}&limit={limit}&start={start}{extra}"
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
        print(
            f"  tei window start={start} limit={limit}: +{n} biblStruct",
            file=sys.stderr,
        )
        time.sleep(0.3)
        return [m.group(1)] if m else []
    except urllib.error.HTTPError as e:
        if limit == 1:
            print(f"  SKIPPING item at start={start}: {e}", file=sys.stderr)
            return []
        half = limit // 2
        print(
            f"  tei window start={start} limit={limit} failed ({e}), bisecting",
            file=sys.stderr,
        )
        return (
            fetch_window(start, half, total_results_box)
            + fetch_window(start + half, limit - half, total_results_box)
        )


def extract_csl_entry(bib_html):
    m = CSL_ENTRY_RE.search(bib_html or "")
    if not m:
        return None
    # No default xmlns: string:Zotero() / string:tei2string match element(a|i).
    frag = f'<div class="csl-entry">{m.group(1)}</div>'
    try:
        ET.fromstring(frag)
    except ET.ParseError:
        return None
    return frag


def fetch_json_index():
    """Return (tags_by_key, bib_by_bm_tag) from format=json include=bib."""
    tags_by_key = {}
    bib_by_tag = {}
    start = 0
    pages = 0
    total = None
    skipped_bib = 0
    while True:
        pages += 1
        items, header_total = fetch(
            start, JSON_LIMIT, fmt="json", extra=JSON_BIB_QS
        )
        if total is None and header_total is not None:
            total = int(header_total)
        for item in items:
            data = item.get("data") or {}
            key = data.get("key") or item.get("key")
            if not key:
                continue
            tags = [t["tag"] for t in data.get("tags") or [] if t.get("tag")]
            tags_by_key[key] = tags
            entry = extract_csl_entry(item.get("bib") or "")
            if entry is None:
                skipped_bib += 1
                continue
            for tag in tags:
                if (
                    tag.startswith("bm:")
                    and tag != "bm:"
                    and " " not in tag
                    and tag not in bib_by_tag
                ):
                    bib_by_tag[tag] = entry
        print(
            f"  json+bib window start={start} limit={JSON_LIMIT}: "
            f"+{len(items)} items ({len(tags_by_key)} keys, "
            f"{len(bib_by_tag)} bm: citations)",
            file=sys.stderr,
        )
        start += JSON_LIMIT
        time.sleep(0.3)
        if MAX_PAGES and pages >= MAX_PAGES:
            break
        if total is not None and start >= total:
            break
        if not items:
            break
    print(f"  skipped malformed bib blobs: {skipped_bib}", file=sys.stderr)
    return tags_by_key, bib_by_tag


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

    return BIBLSTRUCT_RE.sub(repl, body), injected


def write_citations(bib_by_tag):
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>\n',
        '<citations xmlns="https://betamasaheft.eu/bibliography">\n',
    ]
    for tag in sorted(bib_by_tag):
        parts.append(
            f'  <citation tag="{html.escape(tag, quote=True)}">'
            f"{bib_by_tag[tag]}</citation>\n"
        )
    parts.append("</citations>\n")
    body = "".join(parts)
    ET.fromstring(body)
    with open(CITATIONS_PATH, "w", encoding="utf-8") as f:
        f.write(body)
    print(
        f"wrote {len(bib_by_tag)} bm: citations to {CITATIONS_PATH}",
        file=sys.stderr,
    )


def write_tei(tags_by_key):
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
    body, injected = inject_tags(body, tags_by_key)
    merged = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<listBibl xmlns="http://www.tei-c.org/ns/1.0">' + body + "</listBibl>\n"
    )
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(merged)
    print(
        f"done tei: {pages} pages, total-results={total_results_box[0]}, "
        f"{merged.count('<biblStruct')} biblStruct, "
        f"{injected} with tag notes, written to {OUT_PATH}",
        file=sys.stderr,
    )


def main():
    print("fetching JSON tags + styled bib...", file=sys.stderr)
    tags_by_key, bib_by_tag = fetch_json_index()
    write_citations(bib_by_tag)
    if SKIP_TEI:
        print("SKIP_TEI set, not rewriting EthioStudies.xml", file=sys.stderr)
        return
    write_tei(tags_by_key)


if __name__ == "__main__":
    main()
