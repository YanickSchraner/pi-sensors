// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2024-11-01',
  devtools: { enabled: true },
  modules: ['@nuxt/ui'],
  runtimeConfig: {
    // Server-side only — overridden by NUXT_API_BASE_INTERNAL env var
    apiBaseInternal: '',
    public: {
      // Browser-accessible — overridden by NUXT_PUBLIC_API_BASE env var
      apiBase: '',
    },
  },
  components: [
    '~/components',
  ],
  future: {
    compatibilityVersion: 4,
  },
  app: {
    head: {
      link: [
        { rel: 'preconnect', href: 'https://fonts.googleapis.com' },
        { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' },
        {
          rel: 'stylesheet',
          href: 'https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Mono:wght@400;500&family=Outfit:wght@400;500;600;700&display=swap'
        }
      ]
    }
  }
})
