<script setup>
import { useRoute } from 'vue-router';
import PublicNav from './components/PublicNav.vue'
import UserNav from './components/UserNav.vue';
import { auth } from './stores/auth.js'

const route = useRoute()
</script>

<template>
  <UserNav v-if="auth.user && route.name !== 'login'" />
  <PublicNav v-else />
  <main class="app-main" :class="{ 'with-sidebar': auth.user && route.name !== 'login' }">
    <RouterView />
  </main>
</template>

<style scoped>
.app-main {
  min-height: 100vh;
  box-sizing: border-box;
}

.app-main.with-sidebar {
  margin-left: var(--sidebar-width, 240px);
  padding: var(--page-padding, 32px);
}
</style>
