<template>
  <div class="app-shell">
    <aside class="nav-rail" :class="{ collapsed: collapsed }">
      <div class="nav-brand">
        <div class="brand-mark">S</div>
        <div v-if="!collapsed" class="brand-text">
          <div class="brand-title">SmartQA</div>
          <div class="brand-sub">智能问数平台</div>
        </div>
      </div>

      <nav class="nav-menu">
        <router-link
          v-for="item in menus"
          :key="item.to"
          :to="item.to"
          class="nav-item"
          :class="{ active: isActive(item) }"
          :title="item.label"
        >
          <span class="nav-icon" v-html="item.icon"></span>
          <span v-if="!collapsed" class="nav-label">{{ item.label }}</span>
        </router-link>
      </nav>

      <!-- 用户信息 + 登出 -->
      <div class="nav-user">
        <div v-if="!collapsed" class="user-info">
          <div class="user-avatar">{{ userInitial }}</div>
          <div class="user-detail">
            <div class="user-name">{{ authStore.displayName }}</div>
            <button class="btn-logout" @click="handleLogout">登出</button>
          </div>
        </div>
        <button v-else class="btn-logout-icon" title="登出" @click="handleLogout">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
            <polyline points="16 17 21 12 16 7"/>
            <line x1="21" y1="12" x2="9" y2="12"/>
          </svg>
        </button>
      </div>

      <button class="nav-toggle" type="button" @click="collapsed = !collapsed">
        {{ collapsed ? '»' : '« 收起' }}
      </button>
    </aside>

    <div class="nav-main">
      <router-view />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const collapsed = ref(false)

/** 用户首字母头像 */
const userInitial = computed(() => {
  const name = authStore.displayName
  return name ? name.charAt(0).toUpperCase() : '?'
})

async function handleLogout() {
  await authStore.logout()
  router.push('/login')
}

const menus = [
  {
    to: '/chat',
    label: '智能问数',
    match: ['/chat', '/'],
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
  },
  {
    to: '/dashboard',
    label: '数据看板',
    match: ['/dashboard'],
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>',
  },
  {
    to: '/datasources',
    label: '数据源',
    match: ['/datasources'],
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>',
  },
  {
    to: '/knowledge',
    label: '知识库',
    match: ['/knowledge'],
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>',
  },
  {
    to: '/settings',
    label: '系统设置',
    match: ['/settings'],
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
  },
]

function isActive(item) {
  const p = route.path
  return item.match.some((m) => (m === '/' ? p === '/' || p === '/chat' : p.startsWith(m)))
}
</script>

<style scoped>
.app-shell {
  display: flex;
  height: 100vh;
  height: 100dvh;
  max-height: 100vh;
  max-height: 100dvh;
  overflow: hidden;
  background: var(--bg);
}

.nav-rail {
  width: 220px;
  height: 100%;
  background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
  color: #e2e8f0;
  display: flex;
  flex-direction: column;
  padding: 16px 12px;
  flex-shrink: 0;
  transition: width 0.2s ease;
  z-index: 40;
  overflow: hidden;
}

.nav-rail.collapsed {
  width: 72px;
}

.nav-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px 18px;
}

.brand-mark {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, #4f46e5, #818cf8);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  color: #fff;
  flex-shrink: 0;
}

.brand-title {
  font-weight: 800;
  font-size: 15px;
  letter-spacing: -0.02em;
}

.brand-sub {
  font-size: 11px;
  color: #94a3b8;
}

.nav-menu {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 11px 12px;
  border-radius: 12px;
  color: #94a3b8;
  text-decoration: none;
  font-size: 13px;
  font-weight: 600;
  transition: all 0.15s;
}

.nav-item:hover {
  background: rgba(255,255,255,0.06);
  color: #e2e8f0;
}

.nav-item.active {
  background: rgba(79, 70, 229, 0.25);
  color: #fff;
  box-shadow: inset 0 0 0 1px rgba(129, 140, 248, 0.35);
}

.nav-icon {
  display: inline-flex;
  width: 20px;
  justify-content: center;
  flex-shrink: 0;
}

.nav-user {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(255,255,255,0.06);
}

.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 6px;
}

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: rgba(129, 140, 248, 0.25);
  color: #c7d2fe;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 13px;
  flex-shrink: 0;
}

.user-detail {
  flex: 1;
  min-width: 0;
}

.user-name {
  font-size: 13px;
  font-weight: 600;
  color: #e2e8f0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.btn-logout {
  border: none;
  background: none;
  color: #94a3b8;
  font-size: 12px;
  padding: 0;
  cursor: pointer;
  margin-top: 2px;
}

.btn-logout:hover {
  color: #f87171;
}

.btn-logout-icon {
  width: 100%;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.04);
  color: #94a3b8;
  border-radius: 10px;
  padding: 10px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-logout-icon:hover {
  color: #f87171;
}

.nav-toggle {
  margin-top: 12px;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.04);
  color: #94a3b8;
  border-radius: 10px;
  padding: 8px;
  cursor: pointer;
  font-size: 12px;
}

.nav-toggle:hover {
  color: #fff;
}

.nav-main {
  flex: 1;
  min-width: 0;
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 子页面（Home / Dashboard 等）填满主区 */
.nav-main > :deep(*) {
  flex: 1;
  min-height: 0;
  min-width: 0;
}

@media (max-width: 1024px) {
  .nav-rail {
    width: 72px;
  }
  .nav-rail .brand-text,
  .nav-rail .nav-label,
  .nav-rail .nav-toggle {
    display: none;
  }
  .nav-rail .nav-user .user-info {
    display: none;
  }
}

@media (max-width: 768px) {
  .nav-rail {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    transform: translateX(0);
  }
  .nav-rail.collapsed {
    width: 0;
    padding: 0;
    overflow: hidden;
  }
  .nav-main {
    width: 100%;
  }
}
</style>
