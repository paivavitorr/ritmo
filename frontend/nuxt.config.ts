import tailwindcss from '@tailwindcss/vite'

export default defineNuxtConfig({

  modules: ['@pinia/nuxt', '@nuxt/fonts', '@nuxt/eslint'],

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
})
