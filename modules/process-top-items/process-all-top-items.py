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
Env: SKIP_TEI=1 (citations only), SKIP_RENDER=1,
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

with open("./data/all-top-items.json") as top_items_json_file:
    top_items_json = json.load(top_items_json_file)

with open("./data/all-top-items.csljson") as top_items_csljson_file:
    top_items_csljson = json.load(top_items_csljson_file)

with open("./data/all-top-items.xml") as top_items_xml_file:
    top_items_xml = top_items_xml_file.read()

top_items_json_count = len(top_items_json)


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

def get_tags_by_key():
    tags_by_key = {}

    for item in top_items_json:
        data = item.get("data") or {}
        key = data.get("key") or item.get("key")
        if not key:
            continue
        tags_by_key[key] = [
            t["tag"] for t in data.get("tags") or [] if t.get("tag")
        ]
    print(
        f"  json window: {len(tags_by_key)} keys (total-results={top_items_json_count})",
        file=sys.stderr,
    )
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
    body = top_items_xml
    body = XML_ID_RE.sub(r'xml:id="item_\2"\1', body)
    body, injected = inject_tags(body, tags_by_key)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(body)
    print(
        #f"done tei: {pages} pages, total-results={total_results_box[0]}, "
        f"{body.count('<biblStruct')} biblStruct, "
        f"{injected} with tag notes, written to {OUT_PATH}",
        file=sys.stderr,
    )


def main():
    print("get JSON tags + CSL-JSON...", file=sys.stderr)

    tags_by_key = get_tags_by_key()

    items_by_tag = join_by_tag(tags_by_key, top_items_csljson)

    print(
        f"joined {len(items_by_tag)} bm: tags from {len(top_items_csljson)} CSL items",
        file=sys.stderr,
    )

    render_citations(items_by_tag)

    if SKIP_TEI:
        print("SKIP_TEI set, not rewriting EthioStudies.xml", file=sys.stderr)
        return

    write_tei(tags_by_key)


if __name__ == "__main__":
    main()
