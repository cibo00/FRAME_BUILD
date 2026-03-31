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
      // 当你访问 /static 时，Vite 会自动转发到 8080 端口
      '/static': {
        target: 'http://localhost:8080',
        changeOrigin: true,
        // 如果后端接口没有 /static 前缀，可以用 rewrite 去掉它
        // rewrite: (path) => path.replace(/^\/static/, '')
      }
    }
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  base: './'
})
