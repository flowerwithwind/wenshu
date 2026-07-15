/**
 * Structural verification for SmartQA frontend design system.
 * Asserts shipped Login.vue + style.css + AppLayout contain required UX tokens.
 * Run: node scripts/check-ui-tokens.mjs
 */
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const src = path.join(__dirname, '..', 'src')

function read(rel) {
  return fs.readFileSync(path.join(src, rel), 'utf8')
}

function assertIncludes(file, content, needles) {
  const missing = needles.filter((n) => !content.includes(n))
  if (missing.length) {
    throw new Error(`${file} missing: ${missing.join(', ')}`)
  }
}

const style = read('style.css')
assertIncludes('style.css', style, [
  '--brand-gradient',
  '--bg-glass',
  '--mesh-1',
  '--transition',
  '--primary',
  'prefers-reduced-motion',
])

const login = read('views/Login.vue')
assertIncludes('Login.vue', login, [
  'login-page',
  'login-bg',
  'login-card',
  'login-tabs',
  'authStore.login',
  'authStore.register',
  'isRegister',
  'displayName',
  'btn-primary-grad',
  'tab-ink',
  'login-hero',
])

// Ensure handlers still call store (not inlined fake APIs)
if (!/authStore\.login\(username\.value,\s*password\.value\)/.test(login)) {
  throw new Error('Login.vue must call authStore.login with username/password refs')
}
if (!/authStore\.register\(username\.value,\s*password\.value,\s*displayName\.value\)/.test(login)) {
  throw new Error('Login.vue must call authStore.register with three field refs')
}

const layout = read('layouts/AppLayout.vue')
assertIncludes('AppLayout.vue', layout, [
  'var(--bg-sidebar)',
  'var(--brand-gradient)',
  'var(--primary-muted)',
  'nav-rail',
  'router-link',
])

const home = read('views/Home.vue')
assertIncludes('Home.vue', home, ['var(--brand-gradient)', 'var(--border-focus)'])

console.log('check-ui-tokens: OK')
console.log(JSON.stringify({
  ok: true,
  files: ['style.css', 'Login.vue', 'AppLayout.vue', 'Home.vue'],
  checks: 'tokens+auth-handlers+shell',
}, null, 2))
