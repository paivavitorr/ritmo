import { fileURLToPath } from 'node:url'
import { defineVitestProject } from '@nuxt/test-utils/config'
import { defineConfig } from 'vitest/config'

// Utils puras rodam em ambiente node (rápido); componentes rodam no ambiente Nuxt + happy-dom.
export default defineConfig({
  test: {
    projects: [
      {
        resolve: { alias: { '~': fileURLToPath(new URL('./app', import.meta.url)) } },
        test: {
          name: 'unit',
          environment: 'node',
          include: ['tests/unit/**/*.test.ts'],
        },
      },
      await defineVitestProject({
        test: {
          name: 'nuxt',
          environment: 'nuxt',
          include: ['tests/nuxt/**/*.test.ts'],
          environmentOptions: {
            nuxt: { domEnvironment: 'happy-dom' },
          },
        },
      }),
    ],
  },
})
