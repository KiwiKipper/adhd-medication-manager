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
        { path: '/today', name: 'today', component: Today },
        { path: '/curve', name: 'curve', component: Curve },
        { path: '/medications', name: 'medications', component: Medications },
        { path: '/notes', name: 'notes', component: Notes },
        { path: '/history', name: 'history', component: History },
    ]
})
 
router.beforeEach(async (to) => {
    if (!to.meta.requiresAuth) return true
 
    // main.js resolves the session before mount, so this is normally cached.
    const user = auth.user ?? await loadUser()
    if (!user) return '/login'

    return true
})
 
export default router
