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
  { label: 'History', to: '/dose' },
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
  <nav class="app-nav">
    <div class="nav-left">
      <span class="nav-brand">Taurite Tū</span>
    </div>

    <div class="nav-links">
      <RouterLink
        v-for="item in navItems"
        :key="item.to"
        :to="item.to"
        class="nav-link"
      >
        {{ item.label }}
      </RouterLink>
    </div>

    <div class="nav-right">
      <span class="nav-user">{{ userName }}</span>
      <button class="nav-btn" @click="handleLogout">Log out</button>
    </div>
  </nav>
</template>
