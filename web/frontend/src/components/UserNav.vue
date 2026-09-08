<script setup>
import { computed } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { auth, clearUser } from '@/stores/auth.js'
import { logout } from '@/api.js'

const router = useRouter()

const navItems = [
  { label: 'Today', to: '/today' },
  { label: 'Curve', to: '/curve' },
  { label: 'Medications', to: '/medications' },
  { label: 'Notes', to: '/notes' },
  { label: 'History', to: '/history' },
]

const userName = computed(() => {
  const u = auth.user
  if (!u) return ''
  return `${u.first_name ?? ''} ${u.last_name ?? ''}`.trim() || u.email
})

async function handleLogout() {
  try { await logout() } catch (e) {}
  clearUser()
  router.push('/login')
}
</script>

<template>
  <aside class="sidebar">
    <div class="sidebar-title">Dose</div>

    <nav class="sidebar-nav">
      <RouterLink
        v-for="item in navItems"
        :key="item.to"
        :to="item.to"
        class="nav-link"
      >
        {{ item.label }}
      </RouterLink>
    </nav>

    <div class="sidebar-footer">
      <span class="nav-user">{{ userName }}</span>
      <button class="nav-btn" @click="handleLogout">Log out</button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  position: fixed;
  inset-block: 0;
  left: 0;
  width: var(--sidebar-width, 240px);
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  padding: 24px 16px;
  background: var(--surface, #ffffff);
  border-right: 1px solid var(--border, #e5e7eb);
  overflow-y: auto;
}

.sidebar-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-h, #08060d);
  padding: 0 8px;
  margin-bottom: 28px;
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
}

.nav-link {
  display: block;
  padding: 10px 12px;
  border-radius: var(--radius, 8px);
  color: var(--text-muted, #6b7280);
  text-decoration: none;
  font-size: 15px;
  transition: background 0.15s, color 0.15s;
}

.nav-link:hover {
  background: var(--code-bg, #f4f3ec);
  color: var(--text-h, #08060d);
}

.nav-link.router-link-active {
  background: var(--accent-bg, rgba(122, 31, 61, 0.1));
  color: var(--maroon, #7a1f3d);
  font-weight: 600;
}

.sidebar-footer {
  border-top: 1px solid var(--border, #e5e7eb);
  padding-top: 16px;
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.nav-user {
  padding: 0 8px;
  font-size: 13px;
  color: var(--text-muted, #6b7280);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.nav-btn {
  border: 1px solid var(--border, #e5e7eb);
  background: transparent;
  color: var(--text-h, #08060d);
  padding: 8px 12px;
  border-radius: var(--radius, 8px);
  cursor: pointer;
  font-size: 14px;
}

.nav-btn:hover {
  background: var(--code-bg, #f4f3ec);
}
</style>
