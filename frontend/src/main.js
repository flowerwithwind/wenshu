import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import AppLayout from './layouts/AppLayout.vue'
import Home from './views/Home.vue'
import Dashboard from './views/Dashboard.vue'
import DatasourceManage from './views/DatasourceManage.vue'
import KnowledgePage from './views/KnowledgePage.vue'
import SettingsPage from './views/SettingsPage.vue'
import Login from './views/Login.vue'
import { useAuthStore } from './stores/auth'
import './style.css'

const routes = [
  {
    path: '/login',
    component: Login,
    meta: { guest: true }, // 仅未登录可访问
  },
  {
    path: '/',
    component: AppLayout,
    meta: { requiresAuth: true },
    children: [
      { path: '', redirect: '/chat' },
      { path: 'chat', component: Home },
      { path: 'dashboard', component: Dashboard },
      { path: 'datasources', component: DatasourceManage },
      { path: 'knowledge', component: KnowledgePage },
      { path: 'settings', component: SettingsPage },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫：未登录跳转到 /login，已登录访问 /login 跳转到 /chat
router.beforeEach(async (to) => {
  const authStore = useAuthStore()

  // 首次访问时恢复登录态
  if (!authStore.loading && !authStore.isLoggedIn && !authStore.user) {
    await authStore.init()
  }

  // 需要认证但未登录 → 跳转登录页
  if (to.meta.requiresAuth && !authStore.isLoggedIn) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  // 已登录用户访问 /login → 跳转主页
  if (to.meta.guest && authStore.isLoggedIn) {
    return { path: '/chat' }
  }
})

const pinia = createPinia()
const app = createApp(App)
app.use(pinia)
app.use(router)
app.mount('#app')
