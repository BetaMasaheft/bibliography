#!/usr/bin/env python3
"""Fetch top-level items from Zotero group 358366 into local caches.

EthioStudies.xml (format=tei)
    expand.xqm resolves bm: pointers via
      biblStruct[note[@type="tags"]/note[@type="tag"] = $ptr]
    Zotero's current format=tei translator omits those tag notes, so tags
    are fetched as format=json and injected after merge.

citations.xml + citations-url-doi.xml + citations-short*.xml
    citeproc-js (bin/render-citations.js) renders this repo's CSL against
    CSL-JSON. Zotero is the item source, not the CSL processor.

format=tei 500s on some windows; bisects and skips lone bad items.

xml:id is rewritten to item_<zotero-key> after merge (citekeys collide
across paginated requests).

Usage: python3 bin/refresh-ethiostudies.py
Env: MAX_PAGES=N (test), SKIP_TEI=1 (citations only), SKIP_RENDER=1,
     CSLJSON_PATH=build/ethiostudies.csl.json.
"""
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

BASE = "https://api.zotero.org/groups/358366/items/top"
PAGE_LIMIT = 50
JSON_LIMIT = 100
MAX_PAGES = int(os.environ.get("MAX_PAGES", "0")) or None
SKIP_TEI = os.environ.get("SKIP_TEI", "") in ("1", "true", "yes")
SKIP_RENDER = os.environ.get("SKIP_RENDER", "") in ("1", "true", "yes")
OUT_PATH = os.environ.get("OUT_PATH", "EthioStudies.xml")
CSLJSON_PATH = os.environ.get("CSLJSON_PATH", "build/ethiostudies.csl.json")
HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
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


def valid_bm_tag(tag):
    return (
        isinstance(tag, str)
        and tag.startswith("bm:")
        and tag != "bm:"
        and " " not in tag
    )


def csl_item_key(item):
    ident = str((item or {}).get("id") or "")
    return ident.rsplit("/", 1)[-1]


def parse_csljson(body):
    if isinstance(body, list):
        return body
    if isinstance(body, dict) and isinstance(body.get("items"), list):
        return body["items"]
    raise ValueError("unexpected CSL-JSON shape")


def join_by_tag(tags_by_key, csl_items):
    by_key = {}
    for item in csl_items:
        key = csl_item_key(item)
        if key:
            by_key[key] = item
    out = {}
    for key, tags in tags_by_key.items():
        item = by_key.get(key)
        if item is None:
            continue
        for tag in tags:
            if not valid_bm_tag(tag):
                continue
            if tag in out:
                print(
                    f"  warning: duplicate bm: tag {tag} (keeping first)",
                    file=sys.stderr,
                )
                continue
            out[tag] = item
    return out


def retry_wait_seconds(headers, attempt):
    """Seconds to wait before retrying a 429/5xx response."""
    retry_after = headers.get("Retry-After") or headers.get("Backoff")
    if retry_after:
        try:
            return float(retry_after)
        except ValueError:
            pass
    return 1.5 * attempt


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
                text = raw.decode("utf-8")
                if fmt in ("json", "csljson"):
                    return json.loads(text), total
                return text, total
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 503) and attempt < retries:
                wait = retry_wait_seconds(e.headers, attempt)
                print(
                    f"  HTTP {e.code} start={start} fmt={fmt}, "
                    f"retry in {wait}s (attempt {attempt}/{retries})",
                    file=sys.stderr,
                )
                time.sleep(wait)
                continue
            raise


def paginate(fmt, extra=""):
    start = 0
    pages = 0
    total = None
    while True:
        pages += 1
        body, header_total = fetch(start, JSON_LIMIT, fmt=fmt, extra=extra)
        if total is None and header_total is not None:
            total = int(header_total)
        yield body, total
        start += JSON_LIMIT
        time.sleep(0.3)
        if MAX_PAGES and pages >= MAX_PAGES:
            break
        if total is not None and start >= total:
            break
        if fmt == "csljson":
            if len(parse_csljson(body)) == 0:
                break
        elif not body:
            break


def fetch_tags_by_key():
    tags_by_key = {}
    for items, total in paginate("json"):
        for item in items:
            data = item.get("data") or {}
            key = data.get("key") or item.get("key")
            if not key:
                continue
            tags_by_key[key] = [
                t["tag"] for t in data.get("tags") or [] if t.get("tag")
            ]
        print(
            f"  json window: {len(tags_by_key)} keys (total-results={total})",
            file=sys.stderr,
        )
    return tags_by_key


def fetch_csl_items():
    items = []
    for body, total in paginate("csljson"):
        chunk = parse_csljson(body)
        items.extend(chunk)
        print(
            f"  csljson window: {len(items)} items (total-results={total})",
            file=sys.stderr,
        )
    return items


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


def render_citations(items_by_tag):
    os.makedirs(os.path.dirname(os.path.abspath(CSLJSON_PATH)) or ".", exist_ok=True)
    with open(CSLJSON_PATH, "w", encoding="utf-8") as f:
        json.dump(items_by_tag, f, ensure_ascii=False)
    print(
        f"wrote {len(items_by_tag)} bm: items to {CSLJSON_PATH}",
        file=sys.stderr,
    )
    if SKIP_RENDER:
        print("SKIP_RENDER set, not running citeproc", file=sys.stderr)
        return
    script = os.path.join(HERE, "render-citations.js")
    subprocess.run(
        ["node", script, os.path.abspath(CSLJSON_PATH), REPO_ROOT],
        check=True,
    )
    citation_files = [
        "citations.xml",
        "citations-url-doi.xml",
        "citations-short.xml",
        "citations-short-main.xml",
    ]
    for name in citation_files:
        path = os.path.join(REPO_ROOT, name)
        subprocess.run(["xmllint", "--noout", path], check=True)


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
    print("fetching JSON tags + CSL-JSON...", file=sys.stderr)
    tags_by_key = fetch_tags_by_key()
    csl_items = fetch_csl_items()
    items_by_tag = join_by_tag(tags_by_key, csl_items)
    print(
        f"joined {len(items_by_tag)} bm: tags from {len(csl_items)} CSL items",
        file=sys.stderr,
    )
    render_citations(items_by_tag)
    if SKIP_TEI:
        print("SKIP_TEI set, not rewriting EthioStudies.xml", file=sys.stderr)
        return
    write_tei(tags_by_key)


if __name__ == "__main__":
    main()
