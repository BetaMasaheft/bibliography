# bibliography

Two audiences, one repo:

1. **GitHub Pages + CSL** — instruction site (`index.html`) and HLCEES citation styles (the original contents of this repo).
2. **eXist package** — `EthioStudies.xml`, a TEI cache of [Zotero group 358366](https://www.zotero.org/groups/358366/ethiostudies). Ships as `/db/apps/EthioStudies`.

## What `expand.xqm` actually reads

`BetMasWeb/modules/expand.xqm` does **not** use CSL, `xml:id`, or the Pages site. It does:

```xquery
collection("/db/apps/EthioStudies")
  //t:biblStruct[t:note[@type = "tags"]/t:note[@type = "tag"] = $ptr]
```

where `$ptr` is a `bm:…` value from catalogue `ptr/@target`. On a cache miss it falls back to a live `format=tei` Zotero call.

So the xar must contain TEI `biblStruct` entries with those tag notes. `ant` therefore packages **only**:

- `expath-pkg.xml`
- `repo.xml`
- `EthioStudies.xml`

Refresh: `python3 bin/refresh-ethiostudies.py` (TEI pages + JSON tags, because Zotero's current `format=tei` translator omits tags).

`string:Zotero()` and friends still hit Zotero `format=bib` live (bibliography#17). They do not read this cache.

## CSL

The main style is [hiob-ludolf-centre-for-ethiopian-studies](hiob-ludolf-centre-for-ethiopian-studies.csl). Variants: URLs/DOIs, full names, fullcit, and combinations. These stay in git for Zotero users; they are not installed into eXist.
