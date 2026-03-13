import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  base: process.env.VITE_BASE || '/',
  json: {
    stringify: false,
  },
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
