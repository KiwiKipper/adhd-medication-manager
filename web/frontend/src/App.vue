<script setup>
import PublicNav from './components/PublicNav.vue'
import UserNav from './components/UserNav.vue';
import { auth } from './stores/auth.js'
</script>
 
<template>
  <PublicNav v-if="!auth.user" />
  <UserNav v-else />
  <RouterView />
</template>
