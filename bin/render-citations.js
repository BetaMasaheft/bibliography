#!/usr/bin/env node
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import process from 'node:process'
import { fileURLToPath, pathToFileURL } from 'node:url'

import { Cite, plugins } from '@citation-js/core'
import '@citation-js/plugin-csl'

const NS = 'https://betamasaheft.eu/bibliography'
const ENTRY_RE = /<div[^>]*class="csl-entry"[^>]*>([\s\S]*?)<\/div>/

const STYLE_FILES = {
  hlcees: 'hiob-ludolf-centre-for-ethiopian-studies.csl',
  'hlcees-url-doi': 'hiob-ludolf-centre-for-ethiopian-studies-with-url-doi.csl'
}

export function validBmTag (tag) {
  return typeof tag === 'string' &&
    tag.startsWith('bm:') &&
    tag.length > 3 &&
    !tag.includes(' ')
}

function escapeAttr (value) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
}

function escapeText (value) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

export function extractEntry (html) {
  const match = ENTRY_RE.exec(html || '')
  if (!match) return null
  return `<div class="csl-entry">${match[1]}</div>`
}

export function linkwrap (html, item) {
  let out = html
  const doi = item.DOI || item.doi
  if (doi && out.includes(doi) && !out.includes(`doi.org/${doi}`)) {
    out = out.replaceAll(doi, `<a href="https://doi.org/${doi}">${doi}</a>`)
  }
  const url = item.URL || item.url
  if (url && out.includes(url) && !out.includes(`href="${url}"`)) {
    out = out.replaceAll(url, `<a href="${url}">${url}</a>`)
  }
  return out
}

function register (root) {
  const config = plugins.config.get('@csl')
  for (const [name, file] of Object.entries(STYLE_FILES)) {
    if (!config.templates.has(name)) {
      config.templates.add(name, readFileSync(join(root, file), 'utf8'))
    }
  }
  if (!config.locales.has('en-GB')) {
    config.locales.add(
      'en-GB',
      readFileSync(join(root, 'locales/locales-en-GB.xml'), 'utf8')
    )
  }
}

function formatItem (item, template, kind) {
  const cite = new Cite(item)
  return cite.format(kind, {
    format: 'html',
    template,
    lang: 'en-GB'
  })
}

function writeCitations (path, byTag, asHtml) {
  const parts = [
    '<?xml version="1.0" encoding="UTF-8"?>\n',
    `<citations xmlns="${NS}">\n`
  ]
  for (const tag of Object.keys(byTag).sort()) {
    const body = asHtml ? byTag[tag] : escapeText(byTag[tag])
    parts.push(`  <citation tag="${escapeAttr(tag)}">${body}</citation>\n`)
  }
  parts.push('</citations>\n')
  writeFileSync(path, parts.join(''))
}

export async function renderAll (itemsByTag, { root, outDir }) {
  register(root)
  const bib = {}
  const bibUrlDoi = {}
  const citUrlDoi = {}
  const citMain = {}

  for (const [tag, item] of Object.entries(itemsByTag)) {
    if (!validBmTag(tag)) continue
    const mainBib = extractEntry(formatItem(item, 'hlcees', 'bibliography'))
    const urlBib = extractEntry(formatItem(item, 'hlcees-url-doi', 'bibliography'))
    if (!mainBib || !urlBib) continue
    bib[tag] = linkwrap(mainBib, item)
    bibUrlDoi[tag] = linkwrap(urlBib, item)
    citMain[tag] = formatItem(item, 'hlcees', 'citation').trim()
    citUrlDoi[tag] = formatItem(item, 'hlcees-url-doi', 'citation').trim()
  }

  const files = {
    bib: join(outDir, 'citations.xml'),
    bibUrlDoi: join(outDir, 'citations-url-doi.xml'),
    citUrlDoi: join(outDir, 'citations-short.xml'),
    citMain: join(outDir, 'citations-short-main.xml')
  }
  writeCitations(files.bib, bib, true)
  writeCitations(files.bibUrlDoi, bibUrlDoi, true)
  writeCitations(files.citUrlDoi, citUrlDoi, true)
  writeCitations(files.citMain, citMain, true)
  return files
}

async function main () {
  const root = join(dirname(fileURLToPath(import.meta.url)), '..')
  const jsonPath = resolve(process.argv[2] || join(root, 'build/ethiostudies.csl.json'))
  const outDir = resolve(process.argv[3] || root)
  const items = JSON.parse(readFileSync(jsonPath, 'utf8'))
  const files = await renderAll(items, { root, outDir })
  for (const [kind, path] of Object.entries(files)) {
    process.stderr.write(`wrote ${kind}: ${path}\n`)
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  main().catch((err) => {
    process.stderr.write(String(err) + '\n')
    process.exit(1)
  })
}
