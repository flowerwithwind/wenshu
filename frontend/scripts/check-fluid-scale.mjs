/**
 * Gating checks for SmartQA fluid root type scale.
 * Exercises shipped scale helper + verifies CSS wires the same clamp.
 */
import fs from 'fs'
import path from 'path'
import { fileURLToPath, pathToFileURL } from 'url'
import { rootFontSizePx, rootFontSizeCssClamp, FLUID_ROOT_SCALE } from '../src/scale/fluidRoot.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.join(__dirname, '..')
const failures = []

function assert(cond, msg) {
  if (!cond) failures.push(msg)
}

const narrow = rootFontSizePx(375)
const mid = rootFontSizePx(768)
const wide = rootFontSizePx(1440)

assert(narrow === FLUID_ROOT_SCALE.minFont, `narrow expected ${FLUID_ROOT_SCALE.minFont}, got ${narrow}`)
assert(wide === FLUID_ROOT_SCALE.maxFont, `wide expected ${FLUID_ROOT_SCALE.maxFont}, got ${wide}`)
assert(wide > narrow, `wide (${wide}) must be > narrow (${narrow})`)
assert(mid > narrow && mid < wide, `mid (${mid}) must be between narrow and wide`)
assert(rootFontSizePx(200) === FLUID_ROOT_SCALE.minFont, 'below minWidth clamps to minFont')
assert(rootFontSizePx(2000) === FLUID_ROOT_SCALE.maxFont, 'above maxWidth clamps to maxFont')

const clamp = rootFontSizeCssClamp()
assert(clamp.includes('clamp('), 'css clamp string missing clamp(')
assert(clamp.includes('vw'), 'css clamp must use vw for fluid scale')

const style = fs.readFileSync(path.join(root, 'src/style.css'), 'utf8')
assert(/html\s*\{[^}]*font-size\s*:\s*clamp\(/s.test(style), 'style.css html font-size must use clamp()')
assert(style.includes('vw'), 'style.css fluid root must use vw')
assert(/--space-md\s*:\s*[\d.]+rem/.test(style), 'spacing tokens should be rem-based')
assert(/body\s*\{[^}]*font-size\s*:\s*1rem/s.test(style) || /body\s*\{[^}]*font-size\s*:\s*var\(--font-size-base\)/s.test(style),
  'body font-size should be rem-based')

const layout = fs.readFileSync(path.join(root, 'src/layouts/AppLayout.vue'), 'utf8')
assert(/font-size:\s*[\d.]+rem/.test(layout), 'AppLayout shell should use rem type sizes')

if (failures.length) {
  console.error('check-fluid-scale FAILED:')
  failures.forEach((f) => console.error(' -', f))
  process.exit(1)
}

const report = {
  ok: true,
  app: 'smartqa',
  narrowPx: narrow,
  midPx: mid,
  widePx: wide,
  clamp,
  files: ['src/scale/fluidRoot.js', 'src/style.css', 'src/layouts/AppLayout.vue'],
}
console.log('check-fluid-scale: OK')
console.log(JSON.stringify(report, null, 2))
