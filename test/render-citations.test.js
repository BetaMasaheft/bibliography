import { readFileSync } from 'node:fs'
import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { execFileSync } from 'node:child_process'
import { test } from 'node:test'
import assert from 'node:assert/strict'

import { renderAll, validBmTag } from '../bin/render-citations.js'

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

test('renders main bib, url-doi bib, and both short-cite files from local CSL', async () => {
  const outDir = mkdtempSync(join(tmpdir(), 'citations-'))
  const files = await renderAll(fixture, { root, outDir })

  const main = readFileSync(files.bib, 'utf8')
  const urlDoi = readFileSync(files.bibUrlDoi, 'utf8')
  const shortUrlDoi = readFileSync(files.citUrlDoi, 'utf8')
  const shortMain = readFileSync(files.citMain, 'utf8')

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
