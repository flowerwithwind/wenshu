/**
 * 认证相关 API
 * JWT 通过 httpOnly Cookie 自动传递，前端无需手动管理 Token
 */
import api from './index'

/** 注册 */
export const register = (username, password, displayName = '') =>
  api.post('/auth/register', { username, password, display_name: displayName })

/** 登录 */
export const login = (username, password) =>
  api.post('/auth/login', { username, password })

/** 登出 */
export const logout = () => api.post('/auth/logout')

/** 获取当前用户（未登录返回 401） */
export const getMe = () => api.get('/auth/me')
