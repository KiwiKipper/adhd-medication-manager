import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import './assets/main.css'
import './assets/nav.css'
import { loadUser } from './stores/auth.js'
 
// Load the session before mount, or you get a flash of the public bar on every refresh
loadUser().finally(() => createApp(App).use(router).mount('#app'))
