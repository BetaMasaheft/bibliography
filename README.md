# bibliography

Two audiences, one repo:

1. **GitHub Pages + CSL** — instruction site (`index.html`) and HLCEES citation styles.
2. **eXist package** — Zotero group [358366](https://www.zotero.org/groups/358366/ethiostudies) caches under `/db/apps/EthioStudies`.

## What ships in the xar

| File | Consumer |
| --- | --- |
| `EthioStudies.xml` | `expand.xqm` — `//t:biblStruct` by `note[@type="tag"] = $ptr` (`bm:…`) |
| `citations.xml` | `string:Zotero()` / `fo:Zotero()` — main HLCEES `div.csl-entry` |
| `citations-url-doi.xml` | `gfb:zot()` / `viewItem:zot()` — HLCEES with-url-doi `div.csl-entry` |
| `citations-short.xml` | `gfb:shortCit()` — with-url-doi in-text cite |
| `citations-short-main.xml` | `fo:zoteroCit()` — main HLCEES in-text cite |
| `expath-pkg.xml` / `repo.xml` | eXist package metadata (`target=EthioStudies`) |

Callers must `doc("/db/apps/EthioStudies/citations.xml")` (or the sibling file). `collection()` would mix styles once several citation files share `@tag`.

## Refresh

Zotero is the **item** source (`format=json` tags + `format=csljson`). This repo's `.csl` files are the **processor** input.

```
python3 bin/refresh-ethiostudies.py
```

Requires Node 20+ (`npm ci`) and `xmllint`. `bin/render-citations.js` runs citeproc-js (citation-js) with `locales/locales-en-GB.xml` and wraps DOI/URL like Zotero `linkwrap=1`. `SKIP_TEI=1` skips the TEI dump; `SKIP_RENDER=1` writes `build/ethiostudies.csl.json` only. `MAX_PAGES=N` is for tests.

### Cache vs live Zotero

Cached HTML is citeproc-js + local CSL + `en-GB`, not Zotero's server-side CSL. Link wrapping aims to match `linkwrap=1`, but punctuation and small markup differences vs live fallback are expected. Prefer the cache for eXist; treat live Zotero as a miss fallback only.

### Deploy coupling

New citation XML files must land in the bibliography package **and** be jarred by BetMas `data.Dockerfile`. Merge/rebuild order: bibliography → BetMas data image → BetMasWeb cache callers.

## CSL (not installed into eXist)

Main style: [hiob-ludolf-centre-for-ethiopian-studies](hiob-ludolf-centre-for-ethiopian-studies.csl). Variants: URLs/DOIs, full names, fullcit, combinations.
