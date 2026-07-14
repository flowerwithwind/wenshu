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
import './style.css'

const routes = [
  {
    path: '/',
    component: AppLayout,
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

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
