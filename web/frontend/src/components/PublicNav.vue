<script setup>
import { RouterLink } from 'vue-router'
 
const links = [
  { label: 'Home',       to: '/' },
  { label: 'About Us',   to: '/about' },
  { label: 'Contact Us', to: '/contact' },
]
</script>
 
<template>
  <nav class="app-nav">
    <div class="nav-left">
      <img :src="logoSrc" class="nav-logo" alt="" />
      <RouterLink to="/" class="nav-brand">Taurite Tū</RouterLink>
    </div>
 
    <div class="nav-links">
      <RouterLink
        v-for="link in links"
        :key="link.to"
        :to="link.to"
        class="nav-link"
      >
        {{ link.label }}
      </RouterLink>
    </div>
 
    <div class="nav-right">
      <RouterLink to="/login" class="nav-btn nav-btn--accent">Login</RouterLink>
    </div>
  </nav>
</template>
