import { readFileSync } from 'node:fs'
import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { execFileSync } from 'node:child_process'
import { test } from 'node:test'
import assert from 'node:assert/strict'

import { linkwrap, renderAll, validBmTag } from '../bin/render-citations.js'

function assertXml (xml) {
  execFileSync('xmllint', ['--noout', '-'], { input: xml })
}

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const fixture = JSON.parse(
  readFileSync(join(root, 'test/fixtures/gnisci-2020.csl.json'), 'utf8')
)

test('drops bm: tags that are empty or contain spaces', () => {
  assert.equal(validBmTag('bm:2020GnisciPsalter'), true)
  assert.equal(validBmTag('bm:'), false)
  assert.equal(validBmTag('bm: bad space'), false)
  assert.equal(validBmTag('not-bm'), false)
})

test('linkwrap escapes & in URL href and link text', () => {
  const url = 'https://example.com/view?a=1&b=2'
  const html = `<div class="csl-entry">See ${url} for details.</div>`
  const out = linkwrap(html, { URL: url })
  assert.match(out, /href="https:\/\/example\.com\/view\?a=1&amp;b=2"/)
  assert.match(out, />https:\/\/example\.com\/view\?a=1&amp;b=2</)
  assertXml(
    '<?xml version="1.0"?>' +
      '<citations xmlns="https://betamasaheft.eu/bibliography">' +
      `<citation tag="bm:Amp">${out}</citation></citations>`
  )
})

test('linkwrap does not double-wrap already linked escaped URLs', () => {
  const url = 'https://example.com/view?a=1&b=2'
  const html =
    '<div class="csl-entry">' +
    '<a href="https://example.com/view?a=1&amp;b=2">' +
    'https://example.com/view?a=1&amp;b=2</a></div>'
  const out = linkwrap(html, { URL: url })
  assert.equal((out.match(/<a /g) || []).length, 1)
})

test('renders main bib, url-doi bib, and both short-cite files from local CSL', async () => {
  const outDir = mkdtempSync(join(tmpdir(), 'citations-'))
  const { paths, skipped, written } = await renderAll(fixture, { root, outDir })

  assert.equal(skipped, 0)
  assert.equal(written, 1)

  const main = readFileSync(paths.bib, 'utf8')
  const urlDoi = readFileSync(paths.bibUrlDoi, 'utf8')
  const shortUrlDoi = readFileSync(paths.citUrlDoi, 'utf8')
  const shortMain = readFileSync(paths.citMain, 'utf8')

  for (const xml of [main, urlDoi, shortUrlDoi, shortMain]) {
    assertXml(xml)
    assert.match(xml, /tag="bm:2020GnisciPsalter"/)
    assert.doesNotMatch(xml, /tag="bm: bad space"/)
  }

  assert.match(main, /class="csl-entry"/)
  assert.match(main, /Gnisci/)
  assert.doesNotMatch(main, /DOI:/)

  assert.match(urlDoi, /DOI:/)
  assert.match(urlDoi, /10\.1080\/00043079\.2020\.1765629/)
  assert.match(urlDoi, /href="https:\/\/doi\.org\/10\.1080\/00043079\.2020\.1765629"/)

  assert.match(shortUrlDoi, /Gnisci/)
  assert.match(shortUrlDoi, /2020/)
  assert.match(shortMain, /Gnisci/)
})
