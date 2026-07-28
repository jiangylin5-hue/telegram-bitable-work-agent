import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig, loadEnv } from 'vite'

const localApiRoots = [
  '/api',
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

export function createBuildOutputOptions() {
  return {
    manualChunks(moduleId: string) {
      const normalizedId = moduleId.replaceAll('\\', '/')
      if (normalizedId.includes('/node_modules/react/') || normalizedId.includes('/node_modules/react-dom/')) return 'vendor-react'
      if (normalizedId.includes('/node_modules/@tanstack/react-query/')) return 'vendor-query'
      if (normalizedId.includes('/node_modules/lucide-react/')) return 'vendor-icons'
      return null
    },
  }
}

export default defineConfig(({ mode }) => {
  const environment = loadEnv(mode, '.', '')

  return {
    plugins: [react(), tailwindcss()],
    server: {
      proxy: createLocalApiProxy(environment.STAGE07_LOCAL_ACCEPTANCE_USER_ID),
    },
    build: {
      rolldownOptions: {
        output: createBuildOutputOptions(),
      },
    },
  }
})
