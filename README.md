# bibliography

Two audiences, one repo:

1. **GitHub Pages + CSL** — instruction site (`index.html`) and HLCEES citation styles.
2. **eXist package** — Zotero group [358366](https://www.zotero.org/groups/358366/ethiostudies) caches under `/db/apps/EthioStudies`.

## What ships in the xar

| File | Consumer |
| --- | --- |
| `EthioStudies.xml` | BetMas `expand.xqm` — `//t:biblStruct` by `note[@type="tag"] = $ptr` (`bm:…`) |
| `citations.xml` | BetMasWeb `zc:full` / `zc:bib` (main HLCEES `div.csl-entry`) |
| `citations-url-doi.xml` | BetMasWeb `zc:full-url-doi` (HLCEES with-url-doi) |
| `citations-short.xml` | BetMasWeb `zc:short-url-doi` (with-url-doi in-text) |
| `citations-short-main.xml` | BetMasWeb `zc:short` (main HLCEES in-text) |
| `expath-pkg.xml` / `repo.xml` | eXist package metadata (`target=EthioStudies`) |

Callers must `doc("/db/apps/EthioStudies/citations.xml")` (or the sibling file). `collection()` would mix styles once several citation files share `@tag`.

Thin wrappers that still exist in BetMasWeb (`string:Zotero`, `fo:Zotero`, `gfb:zot`, `viewItem:zot`) delegate to these `zc:*` helpers.

## Refresh

Zotero is the **item** source (`format=json` tags + `format=csljson`). This repo's `.csl` files are the **processor** input.

```
python3 bin/refresh-ethiostudies.py
```

Requires Node 20+ (`npm ci`) and `xmllint`. `bin/render-citations.js` runs citeproc-js (citation-js) with `locales/locales-en-GB.xml` and wraps DOI/URL like Zotero `linkwrap=1`. `SKIP_TEI=1` skips the TEI dump; `SKIP_RENDER=1` writes `build/ethiostudies.csl.json` only. `MAX_PAGES=N` is for tests.

Cache render uses only:

- `hiob-ludolf-centre-for-ethiopian-studies.csl`
- `hiob-ludolf-centre-for-ethiopian-studies-with-url-doi.csl`

Other `.csl` files in the repo are for GitHub Pages / historical styles, not the EthioStudies xar.

### Cache vs live Zotero

Cached HTML is citeproc-js + local CSL + `en-GB`, not Zotero's server-side CSL. Link wrapping aims to match `linkwrap=1`, but punctuation and small markup differences vs live fallback are expected. Prefer the cache for eXist; treat live Zotero as a miss fallback only (BetMasWeb `zc:live-*`).

### Deploy coupling

New citation XML files must land in the bibliography package **and** be jarred by BetMas `data.Dockerfile`. Merge/rebuild order: bibliography → BetMas data image → BetMasWeb cache callers.

Push to `master` triggers `notify-betmas.yml` (`bibliography-updated` → BetMas). Re-export itself is still `workflow_dispatch` only (`re-export.yml`) until a CI-produced refresh diff has been reviewed and a schedule is added deliberately.

## CSL (not installed into eXist)

Main style: [hiob-ludolf-centre-for-ethiopian-studies](hiob-ludolf-centre-for-ethiopian-studies.csl). Variants: URLs/DOIs, full names, fullcit, combinations.
