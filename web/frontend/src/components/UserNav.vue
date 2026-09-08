<script setup>
import { computed } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { auth, clearUser } from '@/stores/auth.js'
import { logout } from '@/api.js'

const router = useRouter()

const navItems = [
  { label: 'Today', to: '/today' },
  { label: 'Day curve', to: '/curve' },
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
      <div class="disclaimer">
        <span class="disclaimer-icon">i</span>
        <span class="disclaimer-text">Not medical advice. Generic published curves, not a measurement of you.</span>
      </div>
      <div class="sidebar-user">
        <span class="nav-user">{{ userName }}</span>
        <button class="nav-btn" @click="handleLogout">Log out</button>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  position: fixed;
  inset-block: 0;
  left: 0;
  width: var(--sidebar-width, 236px);
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  padding: 28px 20px;
  gap: 28px;
  background: var(--bg);
  border-right: 1px solid var(--border);
  overflow-y: auto;
}

.sidebar-title {
  font: 700 20px 'Inter', sans-serif;
  color: var(--fg);
  padding: 0 8px;
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-link {
  display: block;
  padding: 10px 14px;
  border-radius: 9px;
  color: var(--fg-muted);
  text-decoration: none;
  font: 500 14px 'Inter', sans-serif;
  transition: background 0.15s, color 0.15s;
}

.nav-link:hover {
  color: var(--fg);
}

.nav-link.router-link-active {
  background: var(--accent-soft);
  color: var(--accent);
  font-weight: 600;
}

.sidebar-footer {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.disclaimer {
  display: flex;
  gap: 9px;
  align-items: flex-start;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px 13px;
}

.disclaimer-icon {
  flex: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 1.5px solid var(--fg-muted);
  color: var(--fg-muted);
  font: 600 10px/16px 'Inter', sans-serif;
  text-align: center;
}

.disclaimer-text {
  font: 400 11.5px/1.5 'Inter', sans-serif;
  color: var(--fg-muted);
}

.sidebar-user {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 0 8px;
}

.nav-user {
  font: 400 13px 'Inter', sans-serif;
  color: var(--fg-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.nav-btn {
  align-self: flex-start;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--fg);
  padding: 6px 12px;
  border-radius: 8px;
  cursor: pointer;
  font: 500 13px 'Inter', sans-serif;
}

.nav-btn:hover {
  background: var(--surface);
}
</style>
