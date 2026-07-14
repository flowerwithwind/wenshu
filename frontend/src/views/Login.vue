<template>
  <div class="login-page">
    <div class="login-card">
      <!-- Logo 区 -->
      <div class="login-brand">
        <div class="brand-mark">S</div>
        <h1 class="brand-title">SmartQA</h1>
        <p class="brand-sub">智能问数平台</p>
      </div>

      <!-- 登录/注册切换 -->
      <div class="login-tabs">
        <button
          class="tab-btn"
          :class="{ active: !isRegister }"
          @click="switchMode(false)"
        >登录</button>
        <button
          class="tab-btn"
          :class="{ active: isRegister }"
          @click="switchMode(true)"
        >注册</button>
      </div>

      <!-- 错误提示 -->
      <div v-if="authStore.error" class="login-error">
        {{ authStore.error }}
      </div>

      <!-- 表单 -->
      <form class="login-form" @submit.prevent="handleSubmit">
        <div class="form-field">
          <label>用户名</label>
          <input
            v-model="username"
            type="text"
            placeholder="请输入用户名"
            autocomplete="username"
            required
          />
        </div>
        <div class="form-field">
          <label>密码</label>
          <input
            v-model="password"
            type="password"
            :placeholder="isRegister ? '至少 6 位' : '请输入密码'"
            autocomplete="current-password"
            required
          />
        </div>
        <div v-if="isRegister" class="form-field">
          <label>昵称 <span class="optional">(可选)</span></label>
          <input
            v-model="displayName"
            type="text"
            placeholder="显示名称"
            autocomplete="nickname"
          />
        </div>
        <button
          class="submit-btn"
          type="submit"
          :disabled="submitting"
        >
          <span v-if="submitting" class="spinner"></span>
          {{ submitting ? '请稍候…' : (isRegister ? '注册' : '登录') }}
        </button>
      </form>
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
  min-height: 100vh;
  min-height: 100dvh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #eef2ff 0%, #e0e7ff 50%, #c7d2fe 100%);
  padding: 24px;
}

.login-card {
  width: 100%;
  max-width: 400px;
  background: #fff;
  border-radius: 20px;
  box-shadow: 0 20px 60px rgba(79, 70, 229, 0.12), 0 2px 8px rgba(0,0,0,0.04);
  padding: 40px 36px 36px;
}

/* 品牌区 */
.login-brand {
  text-align: center;
  margin-bottom: 28px;
}

.brand-mark {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  background: linear-gradient(135deg, #4f46e5, #818cf8);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 900;
  font-size: 22px;
  color: #fff;
  margin-bottom: 12px;
}

.brand-title {
  font-size: 22px;
  font-weight: 800;
  color: #0f172a;
  letter-spacing: -0.02em;
  margin: 0;
}

.brand-sub {
  font-size: 13px;
  color: #64748b;
  margin: 4px 0 0;
}

/* Tab 切换 */
.login-tabs {
  display: flex;
  background: #f1f5f9;
  border-radius: 10px;
  padding: 3px;
  margin-bottom: 20px;
}

.tab-btn {
  flex: 1;
  border: none;
  background: transparent;
  padding: 9px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #64748b;
  cursor: pointer;
  transition: all 0.15s;
}

.tab-btn.active {
  background: #fff;
  color: #4f46e5;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

/* 错误提示 */
.login-error {
  background: #fef2f2;
  color: #dc2626;
  border: 1px solid #fecaca;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 13px;
  margin-bottom: 16px;
}

/* 表单 */
.login-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-field label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 6px;
}

.form-field .optional {
  font-weight: 400;
  color: #9ca3af;
}

.form-field input {
  width: 100%;
  border: 1.5px solid #e2e8f0;
  border-radius: 10px;
  padding: 11px 14px;
  font-size: 14px;
  color: #0f172a;
  outline: none;
  transition: border-color 0.15s;
  box-sizing: border-box;
}

.form-field input:focus {
  border-color: #818cf8;
  box-shadow: 0 0 0 3px rgba(129, 140, 248, 0.15);
}

/* 提交按钮 */
.submit-btn {
  width: 100%;
  border: none;
  border-radius: 10px;
  padding: 12px;
  font-size: 15px;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(135deg, #4f46e5, #6366f1);
  cursor: pointer;
  transition: opacity 0.15s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 4px;
}

.submit-btn:hover:not(:disabled) {
  opacity: 0.9;
}

.submit-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
