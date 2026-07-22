import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig, loadEnv } from 'vite'

const localApiRoots = [
  '/mini-app',
  '/workspaces',
  '/bases',
  '/tables',
  '/views',
  '/records',
  '/templates',
  '/import-jobs',
]

export function createLocalApiProxy(acceptanceActor?: string) {
  const actor = acceptanceActor?.trim()
  return Object.fromEntries(localApiRoots.map((root) => [root, {
    target: 'http://127.0.0.1:8000',
    changeOrigin: true,
    ...(actor ? { headers: { 'X-Stage06-User-Id': actor } } : {}),
  }]))
}

export default defineConfig(({ mode }) => {
  const environment = loadEnv(mode, '.', '')

  return {
    plugins: [react(), tailwindcss()],
    server: {
      proxy: createLocalApiProxy(environment.STAGE07_LOCAL_ACCEPTANCE_USER_ID),
    },
  }
})
