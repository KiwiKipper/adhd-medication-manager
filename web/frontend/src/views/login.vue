<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  TIMEOUT_ERROR,
  MAX_ATTEMPTS,
  withRetry,
  login,
  fetchCsrfCookie
} from '@/api.js'
import { loadUser } from '@/stores/auth.js'
 
const router = useRouter()
 
const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)
 
onMounted(async () => {
  try {
    await withRetry(MAX_ATTEMPTS, fetchCsrfCookie)
  } catch (err) {
    console.error('Unable to get CSRF cookie:', err)
    error.value = 'Unable to connect to server. Try logging in later.'
  }
})
 
async function handleSubmit() {
  loading.value = true
  error.value = ''
 
  try {
    await login(username.value, password.value)
    await loadUser()
    router.push('/user/today')
  } catch (err) {
    if (err.code === TIMEOUT_ERROR) {
      error.value = 'The server took too long to respond.'
    } else if (err.response?.status === 401) {
      error.value = 'Incorrect username or password.'
    } else if (err.response?.status === 403) {
      error.value = 'Request was rejected. Please refresh and try again.'
    } else {
      error.value = 'Something went wrong. Please try again later.'
    }
  } finally {
    loading.value = false
  }
}
</script>
 
<template>
  <div class="public-page login-page">
    <div class="login-wrap">
 
      <div class="login-head">
        <h1>Taurite Tū</h1>
        <p>Sign in to your account</p>
      </div>
 
      <div class="login-card">
        <form @submit.prevent="handleSubmit">
 
          <div class="field">
            <label for="username">Username</label>
            <div class="input-wrap">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                   stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <circle cx="12" cy="8" r="4"></circle>
                <path d="M4 21a8 8 0 0 1 16 0"></path>
              </svg>
              <input
                id="username"
                v-model="username"
                type="text"
                placeholder="Enter your username"
                autocomplete="username"
                required
              />
            </div>
          </div>
 
          <div class="field">
            <label for="password">Password</label>
            <div class="input-wrap">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                   stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <rect x="3" y="11" width="18" height="11" rx="2"></rect>
                <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
              </svg>
              <input
                id="password"
                v-model="password"
                type="password"
                placeholder="Enter your password"
                autocomplete="current-password"
                required
              />
            </div>
          </div>
 
          <div class="forgot-row">
            <a href="#" @click.prevent>Forgot password?</a>
          </div>
 
          <p v-if="error" class="error-msg" role="alert">{{ error }}</p>
 
          <button type="submit" class="submit-btn" :disabled="loading">
            {{ loading ? 'Signing in…' : 'Sign in' }}
            <svg v-if="!loading" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M5 12h14"></path>
              <path d="m12 5 7 7-7 7"></path>
            </svg>
          </button>
 
        </form>
      </div>
 
    </div>
  </div>
</template>
 
<style scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 16px 64px;
}
 
.login-wrap {
  width: 100%;
  max-width: 440px;
}
 
.login-head { text-align: center; margin-bottom: 24px; }
.login-head h1 { font-size: 36px; margin-bottom: 6px; }
.login-head p { font-size: 15px; color: var(--text-muted); margin: 0; }
 
.login-card {
  background: var(--surface);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-panel);
  padding: 32px 28px;
}
 
form { display: flex; flex-direction: column; gap: 18px; }
 
.input-wrap { position: relative; display: flex; align-items: center; }
.input-wrap svg {
  position: absolute;
  left: 13px;
  width: 17px;
  height: 17px;
  color: var(--text-muted);
  pointer-events: none;
}
/* .field input in public.css sets `padding: 12px 14px`, which has the same
   specificity as `.input-wrap input` and so can win on source order and put
   the text back under the icon. The extra class settles it. */
.field .input-wrap input {
  width: 100%;
  height: 46px;
  padding: 12px 14px 12px 40px;
}
 
.forgot-row { text-align: right; margin-top: -6px; }
.forgot-row a { color: var(--text-muted); font-size: var(--text-base); }
 
.error-msg {
  margin: 0;
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  background: var(--danger-bg);
  color: var(--danger);
  font-size: var(--text-base);
}
 
.submit-btn {
  width: 100%;
  height: 46px;
 
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
 
  border: none;
  border-radius: var(--radius);
  background: var(--maroon);
  color: var(--text-on-ink);
 
  font-size: 15px;
  font-weight: 600;
}
.submit-btn:hover:not(:disabled) { background: var(--maroon-dark); }
.submit-btn svg { width: 17px; height: 17px; }
 
@media (max-width: 430px) {
  .login-head h1 { font-size: 30px; }
  .login-card { padding: 24px 20px; }
}
</style>
