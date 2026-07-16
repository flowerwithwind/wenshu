<template>
  <div class="login-page">
    <div class="login-bg" aria-hidden="true">
      <div class="orb orb-a"></div>
      <div class="orb orb-b"></div>
      <div class="grid-overlay"></div>
    </div>

    <div class="login-shell">
      <section class="login-hero">
        <div class="hero-badge">AI Data Copilot</div>
        <h1 class="hero-title">
          用自然语言
          <span class="hero-highlight">问透数据</span>
        </h1>
        <p class="hero-desc">
          SmartQA 将 NL2SQL、多数据源与知识增强融为一体，提供清晰、可观测的智能问数体验。
        </p>
        <ul class="hero-points">
          <li><span class="dot"></span>一句话生成安全 SQL</li>
          <li><span class="dot"></span>多源连接与看板洞察</li>
          <li><span class="dot"></span>知识库增强业务语义</li>
        </ul>
      </section>

      <!-- 方案 B：纯白抬升卡 · Dify 极简 -->
      <section class="login-panel scale-in">
        <div class="login-card login-card--solid">
          <div class="login-brand">
            <div class="brand-mark">S</div>
            <div class="brand-copy">
              <h2 class="brand-title">SmartQA</h2>
              <p class="brand-sub">智能问数平台</p>
            </div>
          </div>

          <div class="login-tabs login-tabs--underline" role="tablist">
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
            <div class="tab-line" :class="{ register: isRegister }"></div>
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
              class="submit-btn submit-btn--solid"
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
/* 方案 B：深色 mesh 底 + 纯白抬升卡（Dify 干净风） */
.login-page {
  position: relative;
  min-height: 100vh;
  min-height: 100dvh;
  overflow: auto;
  display: flex;
  align-items: stretch;
  justify-content: center;
  padding: var(--space-lg);
  background: #0b1220;
  color: var(--text-inverse);
}

.login-bg {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
  background:
    radial-gradient(ellipse 70% 55% at 15% 25%, rgba(79, 70, 229, 0.35), transparent 55%),
    radial-gradient(ellipse 55% 45% at 85% 15%, rgba(99, 102, 241, 0.22), transparent 50%),
    linear-gradient(165deg, #0b1220 0%, #111827 50%, #1e293b 100%);
}

.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(48px);
  opacity: 0.45;
  animation: floatOrb 14s ease-in-out infinite;
}
.orb-a {
  width: min(42vw, 380px);
  height: min(42vw, 380px);
  left: -6%;
  top: 18%;
  background: rgba(79, 70, 229, 0.5);
}
.orb-b {
  width: min(36vw, 320px);
  height: min(36vw, 320px);
  right: -4%;
  bottom: 12%;
  background: rgba(51, 65, 85, 0.8);
  animation-delay: -5s;
}

.grid-overlay {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
  background-size: 56px 56px;
  mask-image: radial-gradient(ellipse 75% 70% at 50% 45%, #000 15%, transparent 72%);
  opacity: 0.55;
}

.login-shell {
  position: relative;
  z-index: 1;
  width: min(1040px, 100%);
  margin: auto;
  display: grid;
  grid-template-columns: 1.05fr 0.9fr;
  gap: clamp(28px, 5vw, 64px);
  align-items: center;
  padding: clamp(12px, 2vw, 28px) 0;
}

.login-hero {
  padding: 8px 4px;
  animation: fadeIn 0.45s var(--ease-out);
}

.hero-badge {
  display: inline-flex;
  padding: 5px 11px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #c7d2fe;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.1);
  margin-bottom: 18px;
}

.hero-title {
  font-size: clamp(28px, 4vw, 38px);
  font-weight: 800;
  line-height: 1.22;
  letter-spacing: -0.03em;
  margin-bottom: 14px;
}

.hero-highlight {
  color: #a5b4fc;
}

.hero-desc {
  font-size: 15px;
  line-height: 1.7;
  color: #94a3b8;
  max-width: 40ch;
  margin-bottom: 22px;
}

.hero-points {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 11px;
  color: #cbd5e1;
  font-size: 14px;
  font-weight: 500;
}

.hero-points .dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  margin-right: 10px;
  background: #818cf8;
  vertical-align: middle;
}

.login-panel {
  width: 100%;
  max-width: 420px;
  margin-left: auto;
}

/* —— 方案 B 核心：不透明白卡、大留白、轻阴影 —— */
.login-card--solid {
  width: 100%;
  padding: clamp(32px, 4.5vw, 40px) clamp(28px, 4vw, 36px) 32px;
  border-radius: 16px;
  background: #ffffff;
  border: 1px solid rgba(226, 232, 240, 0.9);
  box-shadow:
    0 1px 2px rgba(15, 23, 42, 0.04),
    0 16px 48px rgba(15, 23, 42, 0.14),
    0 0 0 1px rgba(255, 255, 255, 0.06);
  color: var(--text);
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
}

.login-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 28px;
}

.brand-mark {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: linear-gradient(145deg, #4f46e5, #6366f1);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 900;
  font-size: 18px;
  color: #fff;
  flex-shrink: 0;
  box-shadow: 0 6px 16px rgba(79, 70, 229, 0.28);
}

.brand-title {
  font-size: 18px;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: #0f172a;
  margin: 0;
}

.brand-sub {
  font-size: 12px;
  color: #94a3b8;
  margin: 3px 0 0;
  font-weight: 500;
}

/* 细线 Tab（非胶囊底） */
.login-tabs--underline {
  position: relative;
  display: grid;
  grid-template-columns: 1fr 1fr;
  background: transparent;
  border-bottom: 1px solid #e2e8f0;
  border-radius: 0;
  padding: 0;
  margin-bottom: 28px;
}

.tab-btn {
  position: relative;
  z-index: 1;
  border: none;
  background: transparent;
  padding: 12px 8px 14px;
  border-radius: 0;
  font-size: 14px;
  font-weight: 600;
  color: #94a3b8;
  cursor: pointer;
  letter-spacing: 0.01em;
}

.tab-btn:hover {
  color: #64748b;
}

.tab-btn.active {
  color: #0f172a;
  font-weight: 700;
}

.tab-line {
  position: absolute;
  bottom: -1px;
  left: 0;
  width: 50%;
  height: 2px;
  background: #4f46e5;
  border-radius: 2px 2px 0 0;
  transition: transform 0.3s var(--ease-out);
}

.tab-line.register {
  transform: translateX(100%);
}

.login-error {
  background: #fef2f2;
  color: #dc2626;
  border: 1px solid #fecaca;
  border-radius: 10px;
  padding: 10px 14px;
  font-size: 13px;
  margin-bottom: 18px;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-field label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 8px;
}

.form-field .optional {
  font-weight: 400;
  color: #94a3b8;
}

.form-field input {
  width: 100%;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 12px 14px;
  font-size: 14px;
  color: #0f172a;
  background: #fff;
  outline: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.form-field input::placeholder {
  color: #94a3b8;
}

.form-field input:hover {
  border-color: #cbd5e1;
}

.form-field input:focus {
  border-color: #6366f1;
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.12);
  background: #fff;
}

/* 沉稳实心主按钮（非花哨渐变条） */
.submit-btn--solid {
  width: 100%;
  margin-top: 8px;
  padding: 12px 16px;
  font-size: 15px;
  font-weight: 700;
  color: #fff;
  border: none;
  border-radius: 10px;
  background: #4f46e5;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06);
  transition: background 0.15s ease, transform 0.12s ease, box-shadow 0.15s ease;
}

.submit-btn--solid:hover:not(:disabled) {
  background: #4338ca;
  box-shadow: 0 8px 20px rgba(67, 56, 202, 0.28);
  transform: translateY(-1px);
}

.submit-btn--solid:active:not(:disabled) {
  transform: translateY(0);
  background: #3730a3;
}

.submit-btn--solid:disabled {
  opacity: 0.65;
  cursor: not-allowed;
  transform: none;
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
  margin-top: 22px;
  text-align: center;
  font-size: 13px;
  color: #94a3b8;
}

.linkish {
  border: none;
  background: none;
  color: #4f46e5;
  font-weight: 700;
  cursor: pointer;
  padding: 0 2px;
}

.linkish:hover {
  color: #4338ca;
  text-decoration: underline;
}

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
    max-width: 440px;
  }
  .login-hero {
    text-align: center;
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
  .login-card--solid {
    padding: 28px 20px 24px;
  }
}
</style>
