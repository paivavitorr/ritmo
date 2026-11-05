import tailwindcss from '@tailwindcss/vite'

export default defineNuxtConfig({

  modules: ['@pinia/nuxt', '@nuxt/fonts', '@nuxt/eslint', '@vite-pwa/nuxt'],

  // App autenticado e offline-first: SPA (sem SSR). Ver blueprint, seção 1.
  ssr: false,
  devtools: { enabled: true },

  app: {
    head: {
      htmlAttrs: { lang: 'pt-BR' },
      title: 'Ritmo',
      meta: [
        { name: 'description', content: 'Ritmo — sua rotina em blocos' },
        { name: 'theme-color', content: '#F5F6F3' },
      ],
    },
  },

  css: ['~/assets/css/main.css'],

  runtimeConfig: {
    public: {
      apiBase: 'http://localhost:8000',
    },
  },
  compatibilityDate: '2026-11-01',

  vite: {
    plugins: [tailwindcss()],
  },

  typescript: {
    strict: true,
  },

  eslint: {
    config: { stylistic: true },
  },

  fonts: {
    families: [{ name: 'Figtree', weights: [400, 500, 650], provider: 'google' }],
  },

  pwa: {
    registerType: 'autoUpdate',
    manifest: {
      name: 'Ritmo — Cronograma Inteligente',
      short_name: 'Ritmo',
      description: 'Cronograma inteligente de rotina pessoal, blocos de tempo e horas líquidas',
      theme_color: '#F5F6F3',
      background_color: '#FFFFFF',
      display: 'standalone',
      orientation: 'portrait',
      lang: 'pt-BR',
      icons: [
        {
          src: '/pwa-192x192.png',
          sizes: '192x192',
          type: 'image/png',
        },
        {
          src: '/pwa-512x512.png',
          sizes: '512x512',
          type: 'image/png',
        },
      ],
    },
    workbox: {
      navigateFallback: '/',
      globPatterns: ['**/*.{js,css,html,png,svg,ico,woff2}'],
      importScripts: ['/sw-push.js'],
    },
  },
})
