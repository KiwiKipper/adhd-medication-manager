import { createRouter, createWebHistory } from 'vue-router'
import LandingPage from '@/views/LandingPage.vue'
import Login from '@/views/Login.vue'
import AboutUs from '@/views/AboutUs.vue'
import ContactUs from '@/views/ContactUs.vue'
import { auth, loadUser } from '@/stores/auth.js'
 
const SA = ['super_admin']

const router = createRouter({
    history: createWebHistory(),
    routes: [
        /* ---- public ---- */
        { path: '/', name: 'home', component: LandingPage },
        { path: '/about', name: 'about-us', component: AboutUs },
        { path: '/contact', name: 'contact-us', component: ContactUs },
        { path: '/login', name: 'login', component: Login },
    ]
})
 
router.beforeEach(async (to) => {
    if (!to.meta.requiresAuth) return true
 
    // main.js resolves the session before mount, so this is normally cached.
    const user = auth.user ?? await loadUser()
    if (!user) return '/login'
 
    if (to.meta.roles && !to.meta.roles.includes(user.role)) return '/login'
    return true
})
 
export default router
