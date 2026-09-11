import { createRouter, createWebHistory } from 'vue-router'
import Login from '@/views/Login.vue'
import Today from '@/views/user/Today.vue'
import Curve from '@/views/user/Curve.vue'
import Medications from '@/views/user/Medications.vue'
import Notes from '@/views/user/Notes.vue'
import History from '@/views/user/History.vue'
import { auth, loadUser } from '@/stores/auth.js'

const router = createRouter({
    history: createWebHistory(),
    routes: [
        /* ---- public ---- */
        { path: '/', redirect: '/login' },
        { path: '/login', name: 'login', component: Login },

        /* ---- user ---- */
        { path: '/today', name: 'today', component: Today, meta: { requiresAuth: true } },
        { path: '/curve', name: 'curve', component: Curve, meta: { requiresAuth: true } },
        { path: '/medications', name: 'medications', component: Medications, meta: { requiresAuth: true } },
        { path: '/notes', name: 'notes', component: Notes, meta: { requiresAuth: true } },
        { path: '/history', name: 'history', component: History, meta: { requiresAuth: true } },
    ]
})
 
router.beforeEach(async (to) => {
    // Bounce an already-authenticated user straight past the login page.
    if (to.name === 'login') {
        const user = auth.user ?? await loadUser()
        return user ? '/today' : true
    }

    if (!to.meta.requiresAuth) return true

    // main.js resolves the session before mount, so this is normally cached.
    const user = auth.user ?? await loadUser()
    if (!user) return '/login'

    return true
})
 
export default router
