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

const email = ref('')
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
    await login(email.value, password.value)
    await loadUser()
    router.push('/today')
  } catch (err) {
    if (err.code === TIMEOUT_ERROR) {
      error.value = 'The server took too long to respond.'
    } else if (err.response?.status === 401) {
      error.value = 'Incorrect username/email or password.'
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
  <div class="login-page">
    <div class="login-left">
      <div class="login-wordmark">Dose</div>
      <p class="login-tagline">A personal medication log. Quiet, plain, yours.</p>
    </div>

    <div class="login-right">
      <div class="login-form-wrap">
        <form class="login-form" @submit.prevent="handleSubmit">
          <div class="field">
            <label for="email">Username or email</label>
            <input
              id="email"
              v-model="email"
              type="text"
              placeholder="you@example.com"
              autocomplete="username"
              required
            />
          </div>

          <div class="field">
            <label for="password">Password</label>
            <input
              id="password"
              v-model="password"
              type="password"
              placeholder="••••••••"
              autocomplete="current-password"
              required
            />
          </div>

          <p v-if="error" class="error-msg" role="alert">{{ error }}</p>

          <button type="submit" class="submit-btn" :disabled="loading">
            {{ loading ? 'Signing in…' : 'Sign in' }}
          </button>
        </form>

        <p class="alt-action">
          Don't have an account?
          <router-link to="/register">Create one</router-link>
        </p>

        <div class="disclaimer">
          <span class="disclaimer-icon">i</span>
          <p>
            Dose is a personal log, not medical advice. It shows a generic published
            release curve for your medication — never a prediction about your body,
            and never a suggestion to take another dose.
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  min-height: 100vh;
}

.login-left {
  flex: 1;
  background: var(--accent-soft);
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 80px;
}

.login-wordmark {
  font: 700 44px/1.15 'Inter', sans-serif;
  color: var(--fg);
}

.login-tagline {
  font: 400 18px/1.5 'Inter', sans-serif;
  color: var(--fg-muted);
  margin: 10px 0 0;
  max-width: 380px;
}

.login-right {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 60px;
}

.login-form-wrap {
  width: 100%;
  max-width: 380px;
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field label {
  font: 500 12px/1 'Inter', sans-serif;
  color: var(--fg-muted);
}

.field input {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px 14px;
  font-size: 15px;
  color: var(--fg);
  outline: none;
}

.field input:focus {
  border-color: var(--accent);
}

.error-msg {
  margin: 0;
  padding: 10px 14px;
  border-radius: 9px;
  background: var(--flag-soft);
  color: var(--flag);
  font: 500 13px/1.4 'Inter', sans-serif;
}

.submit-btn {
  background: var(--accent);
  color: var(--accent-contrast);
  border: none;
  border-radius: 10px;
  padding: 14px;
  font: 600 15px 'Inter', sans-serif;
  cursor: pointer;
}

.submit-btn:disabled {
  opacity: 0.7;
  cursor: default;
}

.alt-action {
  margin: -8px 0 0;
  text-align: center;
  font: 400 13px 'Inter', sans-serif;
  color: var(--fg-muted);
}

.alt-action a {
  color: var(--accent);
  font-weight: 600;
  text-decoration: none;
}

.disclaimer {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 14px 16px;
  display: flex;
  gap: 11px;
  align-items: flex-start;
}

.disclaimer-icon {
  flex: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 1.5px solid var(--fg-muted);
  color: var(--fg-muted);
  font: 600 11px/18px 'Inter', sans-serif;
  text-align: center;
}

.disclaimer p {
  margin: 0;
  font: 400 13px/1.55 'Inter', sans-serif;
  color: var(--fg);
}

</style>
