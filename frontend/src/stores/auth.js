/**
 * 认证状态管理
 * - 应用启动时尝试恢复登录态（GET /api/auth/me）
 * - 登录/注册成功后写入 user
 * - 登出清除状态
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as apiLogin, register as apiRegister, logout as apiLogout, getMe } from '../api/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)       // { id, username, display_name, created_at }
  const loading = ref(false)   // 启动恢复中
  const error = ref('')        // 登录/注册错误

  const isLoggedIn = computed(() => !!user.value)
  const displayName = computed(() => user.value?.display_name || user.value?.username || '')

  /** 启动时调用：尝试从 Cookie 恢复登录态 */
  async function init() {
    loading.value = true
    try {
      const { data } = await getMe()
      user.value = data
    } catch {
      user.value = null
    } finally {
      loading.value = false
    }
  }

  /** 登录 */
  async function login(username, password) {
    error.value = ''
    try {
      const { data } = await apiLogin(username, password)
      user.value = data
      return true
    } catch (e) {
      error.value = e.response?.data?.detail || '登录失败'
      return false
    }
  }

  /** 注册 */
  async function register(username, password, displayName) {
    error.value = ''
    try {
      const { data } = await apiRegister(username, password, displayName)
      user.value = data
      return true
    } catch (e) {
      error.value = e.response?.data?.detail || '注册失败'
      return false
    }
  }

  /** 登出 */
  async function logout() {
    try {
      await apiLogout()
    } finally {
      user.value = null
    }
  }

  return { user, loading, error, isLoggedIn, displayName, init, login, register, logout }
})
