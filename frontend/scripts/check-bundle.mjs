#!/usr/bin/env node
/**
 * Phase 32: assert the production bundle's *load graph*, not just its chunk sizes.
 *
 * Why this exists
 * ---------------
 * `vite build` prints two diagnostics. One is real and was fixed: a circular chunk
 * (`vendor-charts -> vendor -> vendor-charts`) caused by a catch-all `vendor` bucket in the manual
 * chunk logic. The other is "some chunks are larger than 500 kB", and it cannot be fixed by
 * configuration: three.js is ~800 kB minified even when a module imports only
 * `{ WebGLRenderer, Scene }` (measured, see docs/PHASE32_FRONTEND_BUNDLE.md). Phase 33 removed
 * three.js and rebuilt the growth chamber in plain SVG, so that warning is gone at the source
 * rather than hidden.
 *
 * Raising `build.chunkSizeWarningLimit` would hide it and change nothing; leaving an oversized
 * chunk as an unfixed warning is how a 900 kB chunk ends up on the critical path later. So this
 * script asserts the properties that actually matter:
 *
 *   1. no circular chunk in the built graph;
 *   2. NO chunk anywhere in the bundle is above the size budget - not merely absent from the
 *      initial path (Phase 33 tightened this from a note into a failure);
 *   3. the initial request (index.html + everything it statically imports) stays inside a small
 *      budget, so a regression in code-splitting fails here rather than in a user's browser.
 *
 * Usage: npm run build && node scripts/check-bundle.mjs
 */
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)))
const DIST = join(ROOT, 'dist')
const ASSETS = join(DIST, 'assets')

const BIG_CHUNK_BUDGET = 500 * 1024 // the size Vite itself warns about
// index.html + its static import graph, minified. Phase 32 measured 240 kB and the budget was
// padded to 260 kB while three.js was still shipped lazily; Phase 33 removed the last oversized
// library, so the budget now states the 240 kB target Phase 32 left behind.
// 240 * 1024 = 245760 bytes.
const INITIAL_BUDGET = 240 * 1024

const failures = []
const files = readdirSync(ASSETS).filter((name) => name.endsWith('.js'))
const size = (name) => statSync(join(ASSETS, name)).size

/** Every module specifier a chunk imports statically. Dynamic imports are collected separately. */
function importsOf(file) {
  const source = readFileSync(join(ASSETS, file), 'utf8')
  const staticTargets = []
  const dynamicTargets = []
  const staticRe = /(?:^|[;\s])import\s*(?:[^'"]*?from\s*)?["']([^"']+)["']/g
  const dynamicRe = /import\(\s*["']([^"']+)["']\s*\)/g
  let match
  while ((match = staticRe.exec(source))) {
    if (match[1].startsWith('.')) staticTargets.push(match[1].replace('./', ''))
  }
  while ((match = dynamicRe.exec(source))) {
    if (match[1].startsWith('.')) dynamicTargets.push(match[1].replace('./', ''))
  }
  return { staticTargets, dynamicTargets }
}

// ------------------------------------------------------------------ 1. entry and its static graph
const html = readFileSync(join(DIST, 'index.html'), 'utf8')
const entry = [...html.matchAll(/src="\/assets\/([^"]+\.js)"/g)].map((m) => m[1])
if (entry.length === 0) failures.push('index.html references no entry script')

const initial = new Set()
const queue = [...entry]
while (queue.length) {
  const current = queue.shift()
  if (initial.has(current)) continue
  initial.add(current)
  for (const target of importsOf(current).staticTargets) queue.push(target)
}
const initialBytes = [...initial].reduce((total, file) => total + size(file), 0)

// ------------------------------------------------------------------ 2. oversized chunks
const big = files.filter((file) => size(file) > BIG_CHUNK_BUDGET).sort((a, b) => size(b) - size(a))
for (const file of big) {
  failures.push(
    `${file} (${(size(file) / 1024).toFixed(0)} kB) is above the ${BIG_CHUNK_BUDGET / 1024} kB ` +
    'budget' +
    (initial.has(file)
      ? ' and is statically imported by the entry, so every route downloads it'
      : '; being lazy is not an excuse, the bundle is supposed to contain no oversized chunk'),
  )
}

// ------------------------------------------------------------------ 3. cycles
//
// Static edges only. A page chunk that statically imports the entry chunk it was dynamically
// imported *from* is normal with Vite's code splitting (the shared runtime lives in the entry) and
// is not a cycle in the module graph; Vite itself reports cycles on the static graph.
const edges = new Map(files.map((file) => [file, importsOf(file).staticTargets
  .filter((target) => files.includes(target))]))
const state = new Map()
const cycles = []
function visit(node, stack) {
  if (state.get(node) === 'done') return
  if (state.get(node) === 'open') {
    cycles.push([...stack.slice(stack.indexOf(node)), node].join(' -> '))
    return
  }
  state.set(node, 'open')
  for (const next of edges.get(node) || []) visit(next, [...stack, node])
  state.set(node, 'done')
}
for (const file of files) visit(file, [])

for (const cycle of cycles) failures.push(`circular chunk: ${cycle}`)

// ------------------------------------------------------------------ 4. report
const table = files
  .map((file) => ({ file, bytes: size(file), lazy: !initial.has(file) }))
  .sort((a, b) => b.bytes - a.bytes)
  .slice(0, 8)

console.log('production bundle:')
for (const row of table) {
  console.log(`  ${row.file.padEnd(34)} ${(row.bytes / 1024).toFixed(0).padStart(6)} kB  ` +
    `${row.lazy ? 'lazy' : 'INITIAL'}`)
}
console.log(`  initial request (index.html static graph): ${(initialBytes / 1024).toFixed(0)} kB ` +
  `across ${initial.size} module(s)`)

if (initialBytes > INITIAL_BUDGET) {
  failures.push(
    `the initial request is ${(initialBytes / 1024).toFixed(0)} kB, over the ` +
    `${INITIAL_BUDGET / 1024} kB budget: something was imported statically that should be lazy`,
  )
}

if (failures.length) {
  console.error('\nbundle check FAILED:')
  for (const failure of failures) console.error(`  - ${failure}`)
  process.exit(1)
}
console.log('bundle check passed: no cycles, no oversized chunk anywhere, initial request within budget')
