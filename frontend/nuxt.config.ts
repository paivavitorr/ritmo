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
        { name: 'mobile-web-app-capable', content: 'yes' },
        { name: 'apple-mobile-web-app-capable', content: 'yes' },
        { name: 'apple-mobile-web-app-title', content: 'Ritmo' },
        { name: 'apple-mobile-web-app-status-bar-style', content: 'default' },
      ],
      link: [
        { rel: 'manifest', href: '/manifest.webmanifest' },
        { rel: 'icon', href: '/favicon.ico', sizes: '48x48' },
        { rel: 'icon', href: '/icon.svg', type: 'image/svg+xml', sizes: 'any' },
        { rel: 'apple-touch-icon', href: '/apple-touch-icon.png', sizes: '180x180' },
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
    // 'prompt': a nova versão só entra após o usuário tocar em "Atualizar" (AvisoAtualizacao).
    registerType: 'prompt',
    manifest: {
      name: 'Ritmo — Cronograma Inteligente',
      short_name: 'Ritmo',
      description: 'Cronograma inteligente de rotina pessoal, blocos de tempo e horas líquidas',
      theme_color: '#F5F6F3',
      background_color: '#F5F6F3',
      display: 'standalone',
      orientation: 'portrait',
      lang: 'pt-BR',
      icons: [
        { src: '/pwa-192x192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
        { src: '/pwa-512x512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
        { src: '/pwa-maskable-192x192.png', sizes: '192x192', type: 'image/png', purpose: 'maskable' },
        { src: '/pwa-maskable-512x512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
      ],
    },
    workbox: {
      navigateFallback: '/',
      globPatterns: ['**/*.{js,css,html,png,svg,ico,woff2}'],
      cleanupOutdatedCaches: true,
      importScripts: ['/sw-push.js'],
    },
    devOptions: { enabled: false },
  },
})
