# bibliography

Two audiences, one repo:

1. **GitHub Pages + CSL** — instruction site (`index.html`) and HLCEES citation styles.
2. **eXist package** — Zotero group [358366](https://www.zotero.org/groups/358366/ethiostudies) caches under `/db/apps/EthioStudies`.

## What ships in the xar

| File | Consumer |
| --- | --- |
| `EthioStudies.xml` | `expand.xqm` — `//t:biblStruct` by `note[@type="tag"] = $ptr` (`bm:…`) |
| `citations.xml` | `string:Zotero()` — `@tag = $ptr` then `div.csl-entry` (styled HTML) |
| `expath-pkg.xml` / `repo.xml` | eXist package metadata (`target=EthioStudies`) |

Refresh: `python3 bin/refresh-ethiostudies.py` (TEI pages + JSON `include=bib` for tags and CSL HTML). `SKIP_TEI=1` rewrites only `citations.xml`.

Live fallbacks remain for cache misses. Other `format=bib` call sites that use `-with-url-doi` are not this cache.

## CSL (not installed into eXist)

Main style: [hiob-ludolf-centre-for-ethiopian-studies](hiob-ludolf-centre-for-ethiopian-studies.csl). Variants: URLs/DOIs, full names, fullcit, combinations.
