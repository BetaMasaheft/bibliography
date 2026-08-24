#!/usr/bin/env node
import { execFileSync } from 'node:child_process'
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

export function escapeAttr (value) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
}

export function escapeText (value) {
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
  if (doi) {
    const href = escapeAttr(`https://doi.org/${doi}`)
    const already =
      out.includes(`href="${href}"`) ||
      out.includes(`href="https://doi.org/${doi}"`) ||
      out.includes(`doi.org/${doi}`)
    if (out.includes(doi) && !already) {
      out = out.replaceAll(doi, `<a href="${href}">${escapeText(doi)}</a>`)
    }
  }
  const url = item.URL || item.url
  if (url) {
    const href = escapeAttr(url)
    const text = escapeText(url)
    const already =
      out.includes(`href="${href}"`) || out.includes(`href="${url}"`)
    const present = out.includes(url) || out.includes(text)
    if (present && !already) {
      if (out.includes(url)) {
        out = out.replaceAll(url, `<a href="${href}">${text}</a>`)
      } else {
        out = out.replaceAll(text, `<a href="${href}">${text}</a>`)
      }
    }
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

function assertWellFormed (xml, path) {
  try {
    execFileSync('xmllint', ['--noout', '-'], {
      input: xml,
      stdio: ['pipe', 'pipe', 'pipe']
    })
  } catch (err) {
    const detail = err.stderr ? String(err.stderr) : String(err)
    throw new Error(`well-formedness failed for ${path}: ${detail}`)
  }
}

function writeCitations (path, byTag) {
  const parts = [
    '<?xml version="1.0" encoding="UTF-8"?>\n',
    `<citations xmlns="${NS}">\n`
  ]
  for (const tag of Object.keys(byTag).sort()) {
    parts.push(
      `  <citation tag="${escapeAttr(tag)}">${byTag[tag]}</citation>\n`
    )
  }
  parts.push('</citations>\n')
  const xml = parts.join('')
  assertWellFormed(xml, path)
  writeFileSync(path, xml)
}

export async function renderAll (itemsByTag, { root, outDir }) {
  register(root)
  const bib = {}
  const bibUrlDoi = {}
  const citUrlDoi = {}
  const citMain = {}
  let skipped = 0

  for (const [tag, item] of Object.entries(itemsByTag)) {
    if (!validBmTag(tag)) continue
    const mainBib = extractEntry(formatItem(item, 'hlcees', 'bibliography'))
    const urlBib = extractEntry(formatItem(item, 'hlcees-url-doi', 'bibliography'))
    if (!mainBib || !urlBib) {
      skipped += 1
      process.stderr.write(`skip ${tag}: missing csl-entry\n`)
      continue
    }
    bib[tag] = linkwrap(mainBib, item)
    bibUrlDoi[tag] = linkwrap(urlBib, item)
    citMain[tag] = formatItem(item, 'hlcees', 'citation').trim()
    citUrlDoi[tag] = formatItem(item, 'hlcees-url-doi', 'citation').trim()
  }

  const paths = {
    bib: join(outDir, 'citations.xml'),
    bibUrlDoi: join(outDir, 'citations-url-doi.xml'),
    citUrlDoi: join(outDir, 'citations-short.xml'),
    citMain: join(outDir, 'citations-short-main.xml')
  }
  writeCitations(paths.bib, bib)
  writeCitations(paths.bibUrlDoi, bibUrlDoi)
  writeCitations(paths.citUrlDoi, citUrlDoi)
  writeCitations(paths.citMain, citMain)

  const written = Object.keys(bib).length
  process.stderr.write(`rendered ${written} tags, skipped ${skipped}\n`)
  return { paths, skipped, written }
}

async function main () {
  const root = join(dirname(fileURLToPath(import.meta.url)), '..')
  const jsonPath = resolve(process.argv[2] || join(root, 'build/ethiostudies.csl.json'))
  const outDir = resolve(process.argv[3] || root)
  const items = JSON.parse(readFileSync(jsonPath, 'utf8'))
  const { paths } = await renderAll(items, { root, outDir })
  for (const [kind, path] of Object.entries(paths)) {
    process.stderr.write(`wrote ${kind}: ${path}\n`)
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  main().catch((err) => {
    process.stderr.write(`${String(err)}\n`)
    process.exit(1)
  })
}
