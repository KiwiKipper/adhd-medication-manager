import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig(() => {
  // Where `npm run dev` forwards API requests it can't serve itself, so
  // src/api.js's relative baseURL (see src/api.js) works unchanged against
  // a local `manage.py runserver` or against the backend VM. Override with
  // e.g. VITE_DEV_API=http://192.168.56.11:8000 to point a laptop frontend
  // at the provisioned backend instead.
  const devApi = process.env.VITE_DEV_API ?? 'http://127.0.0.1:8000'

  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      proxy: {
        '/api': devApi,
        '/auth': devApi,
        '/admin': devApi,
        '/static': devApi,
      },
    },
  }
})
