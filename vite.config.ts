import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueJsx(),
    //vueDevTools(),
  ],
  server: {
    proxy: {
      '/static': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/Login': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/Register': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/next-image': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    }
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  base: './'
})
