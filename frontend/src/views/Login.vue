<template>
  <div class="login-page">
    <!-- Animated mesh / tech background -->
    <div class="login-bg" aria-hidden="true">
      <div class="orb orb-a"></div>
      <div class="orb orb-b"></div>
      <div class="orb orb-c"></div>
      <div class="grid-overlay"></div>
    </div>

    <div class="login-shell">
      <!-- Brand storytelling (desktop) -->
      <section class="login-hero">
        <div class="hero-badge">AI Data Copilot</div>
        <h1 class="hero-title">
          用自然语言
          <span class="hero-highlight">问透数据</span>
        </h1>
        <p class="hero-desc">
          SmartQA 将 NL2SQL、多数据源与知识增强融为一体，提供类 Coze / Dify 的流畅体验与可观测的智能问数流程。
        </p>
        <ul class="hero-points">
          <li><span class="dot"></span>一句话生成安全 SQL</li>
          <li><span class="dot"></span>多源连接与看板洞察</li>
          <li><span class="dot"></span>知识库增强业务语义</li>
        </ul>
      </section>

      <!-- Glass form card -->
      <section class="login-panel scale-in">
        <div class="login-card">
          <div class="login-brand">
            <div class="brand-mark">S</div>
            <div class="brand-copy">
              <h2 class="brand-title">SmartQA</h2>
              <p class="brand-sub">智能问数平台</p>
            </div>
          </div>

          <div class="login-tabs" role="tablist">
            <button
              type="button"
              class="tab-btn"
              role="tab"
              :aria-selected="!isRegister"
              :class="{ active: !isRegister }"
              @click="switchMode(false)"
            >
              登录
            </button>
            <button
              type="button"
              class="tab-btn"
              role="tab"
              :aria-selected="isRegister"
              :class="{ active: isRegister }"
              @click="switchMode(true)"
            >
              注册
            </button>
            <div class="tab-ink" :class="{ register: isRegister }"></div>
          </div>

          <transition name="fade-slide">
            <div v-if="authStore.error" key="err" class="login-error">
              {{ authStore.error }}
            </div>
          </transition>

          <form class="login-form" @submit.prevent="handleSubmit">
            <div class="form-field">
              <label for="login-username">用户名</label>
              <input
                id="login-username"
                v-model="username"
                type="text"
                placeholder="请输入用户名"
                autocomplete="username"
                required
              />
            </div>
            <div class="form-field">
              <label for="login-password">密码</label>
              <input
                id="login-password"
                v-model="password"
                type="password"
                :placeholder="isRegister ? '至少 6 位' : '请输入密码'"
                autocomplete="current-password"
                required
              />
            </div>
            <transition name="fade-slide">
              <div v-if="isRegister" key="dn" class="form-field">
                <label for="login-display">
                  昵称 <span class="optional">(可选)</span>
                </label>
                <input
                  id="login-display"
                  v-model="displayName"
                  type="text"
                  placeholder="显示名称"
                  autocomplete="nickname"
                />
              </div>
            </transition>
            <button
              class="submit-btn btn-primary-grad btn-ripple"
              type="submit"
              :disabled="submitting"
            >
              <span v-if="submitting" class="spinner" aria-hidden="true"></span>
              {{ submitting ? '请稍候…' : isRegister ? '创建账号' : '进入工作台' }}
            </button>
          </form>

          <p class="login-footnote">
            {{ isRegister ? '已有账号？' : '还没有账号？' }}
            <button type="button" class="linkish" @click="switchMode(!isRegister)">
              {{ isRegister ? '去登录' : '立即注册' }}
            </button>
          </p>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const isRegister = ref(false)
const username = ref('')
const password = ref('')
const displayName = ref('')
const submitting = ref(false)

function switchMode(toRegister) {
  isRegister.value = toRegister
  authStore.error = ''
}

async function handleSubmit() {
  submitting.value = true
  try {
    let ok
    if (isRegister.value) {
      ok = await authStore.register(username.value, password.value, displayName.value)
    } else {
      ok = await authStore.login(username.value, password.value)
    }
    if (ok) router.push('/chat')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.login-page {
  position: relative;
  min-height: 100vh;
  min-height: 100dvh;
  overflow: auto;
  display: flex;
  align-items: stretch;
  justify-content: center;
  padding: var(--space-lg);
  background: #070b16;
  color: var(--text-inverse);
}

.login-bg {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
  background:
    var(--mesh-1),
    var(--mesh-2),
    var(--mesh-3),
    linear-gradient(160deg, #070b16 0%, #0f172a 45%, #111827 100%);
}

.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(40px);
  opacity: 0.7;
  animation: floatOrb 12s ease-in-out infinite;
}
.orb-a {
  width: min(48vw, 420px);
  height: min(48vw, 420px);
  left: -8%;
  top: 10%;
  background: rgba(99, 102, 241, 0.55);
}
.orb-b {
  width: min(40vw, 360px);
  height: min(40vw, 360px);
  right: -6%;
  top: 20%;
  background: rgba(34, 211, 238, 0.35);
  animation-delay: -4s;
}
.orb-c {
  width: min(36vw, 300px);
  height: min(36vw, 300px);
  left: 35%;
  bottom: -10%;
  background: rgba(168, 85, 247, 0.28);
  animation-delay: -7s;
}

.grid-overlay {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.04) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: radial-gradient(ellipse 70% 70% at 50% 40%, #000 20%, transparent 75%);
  opacity: 0.5;
}

.login-shell {
  position: relative;
  z-index: 1;
  width: min(1080px, 100%);
  margin: auto;
  display: grid;
  grid-template-columns: 1.05fr 0.95fr;
  gap: clamp(24px, 4vw, 56px);
  align-items: center;
  padding: clamp(12px, 2vw, 24px) 0;
}

.login-hero {
  padding: 12px 8px 12px 4px;
  animation: fadeIn 0.5s var(--ease-out);
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #c7d2fe;
  background: rgba(99, 102, 241, 0.18);
  border: 1px solid rgba(129, 140, 248, 0.35);
  margin-bottom: 18px;
}

.hero-title {
  font-size: clamp(28px, 4vw, 40px);
  font-weight: 800;
  line-height: 1.2;
  letter-spacing: -0.03em;
  margin-bottom: 14px;
}

.hero-highlight {
  background: linear-gradient(90deg, #a5b4fc, #67e8f9);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.hero-desc {
  font-size: 15px;
  line-height: 1.7;
  color: #94a3b8;
  max-width: 42ch;
  margin-bottom: 22px;
}

.hero-points {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 10px;
  color: #cbd5e1;
  font-size: 14px;
  font-weight: 500;
}

.hero-points .dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 10px;
  background: var(--brand-gradient);
  box-shadow: 0 0 12px rgba(99, 102, 241, 0.7);
}

.login-panel {
  width: 100%;
  max-width: 440px;
  margin-left: auto;
}

.login-card {
  width: 100%;
  padding: clamp(28px, 4vw, 36px);
  border-radius: var(--radius-xl);
  background: var(--bg-glass);
  backdrop-filter: blur(22px) saturate(1.35);
  -webkit-backdrop-filter: blur(22px) saturate(1.35);
  border: 1px solid var(--bg-glass-border);
  box-shadow: var(--shadow-glow);
  color: var(--text);
}

.login-brand {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 26px;
}

.brand-mark {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  background: var(--brand-gradient);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 900;
  font-size: 20px;
  color: #fff;
  box-shadow: 0 10px 24px rgba(79, 70, 229, 0.35);
  flex-shrink: 0;
}

.brand-title {
  font-size: 20px;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--text);
  margin: 0;
}

.brand-sub {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 2px 0 0;
}

.login-tabs {
  position: relative;
  display: grid;
  grid-template-columns: 1fr 1fr;
  background: var(--bg);
  border-radius: var(--radius-sm);
  padding: 4px;
  margin-bottom: 20px;
}

.tab-btn {
  position: relative;
  z-index: 1;
  border: none;
  background: transparent;
  padding: 10px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 650;
  color: var(--text-secondary);
  cursor: pointer;
}

.tab-btn.active {
  color: var(--primary-deep);
}

.tab-ink {
  position: absolute;
  top: 4px;
  bottom: 4px;
  left: 4px;
  width: calc(50% - 4px);
  border-radius: 8px;
  background: var(--bg-card);
  box-shadow: var(--shadow-xs);
  transition: transform var(--transition-slow) var(--ease-out);
}

.tab-ink.register {
  transform: translateX(100%);
}

.login-error {
  background: var(--danger-light);
  color: #dc2626;
  border: 1px solid #fecaca;
  border-radius: var(--radius-sm);
  padding: 10px 14px;
  font-size: 13px;
  margin-bottom: 16px;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-field label {
  display: block;
  font-size: 13px;
  font-weight: 650;
  color: #374151;
  margin-bottom: 6px;
}

.form-field .optional {
  font-weight: 400;
  color: var(--text-tertiary);
}

.form-field input {
  width: 100%;
  border: 1.5px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 12px 14px;
  font-size: 14px;
  color: var(--text);
  background: var(--bg-input);
  outline: none;
}

.form-field input:hover {
  border-color: #c7d2fe;
}

.form-field input:focus {
  border-color: var(--border-focus);
  box-shadow: 0 0 0 3px rgba(129, 140, 248, 0.18);
  background: #fff;
}

.submit-btn {
  width: 100%;
  padding: 13px;
  font-size: 15px;
  margin-top: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

.login-footnote {
  margin-top: 18px;
  text-align: center;
  font-size: 13px;
  color: var(--text-secondary);
}

.linkish {
  border: none;
  background: none;
  color: var(--primary);
  font-weight: 700;
  cursor: pointer;
  padding: 0 2px;
}

.linkish:hover {
  color: var(--primary-hover);
  text-decoration: underline;
}

/* transitions for register field / error */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.28s var(--ease-out);
}
.fade-slide-enter-from,
.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-6px);
  max-height: 0;
}
.fade-slide-enter-to,
.fade-slide-leave-from {
  max-height: 120px;
}

@media (max-width: 900px) {
  .login-shell {
    grid-template-columns: 1fr;
    max-width: 480px;
  }
  .login-hero {
    text-align: center;
    padding: 8px 4px 0;
  }
  .hero-desc {
    margin-left: auto;
    margin-right: auto;
  }
  .hero-points {
    align-items: center;
  }
  .login-panel {
    margin: 0 auto;
    max-width: 100%;
  }
}

@media (max-width: 480px) {
  .login-page {
    padding: 16px 12px;
  }
  .login-card {
    padding: 24px 18px;
  }
  .hero-title {
    font-size: 26px;
  }
}
</style>
