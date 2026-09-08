<script setup>
import PublicNav from './components/PublicNav.vue'
import UserNav from './components/UserNav.vue';
import { auth } from './stores/auth.js'
</script>

<template>
  <PublicNav v-if="!auth.user" />
  <UserNav v-else />
  <main class="app-main" :class="{ 'with-sidebar': auth.user }">
    <RouterView />
  </main>
</template>

<style scoped>
.app-main {
  min-height: 100vh;
  box-sizing: border-box;
}

.app-main.with-sidebar {
  margin-left: var(--sidebar-width, 236px);
}
</style>
