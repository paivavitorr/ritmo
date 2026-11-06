<script setup lang="ts">
import { sincronizarPendenciasPush } from '~/composables/usePushNotification'

const auth = useAuthStore()
const { requisitar } = useApi()

// Mensagens do service worker (clique em notificação, assinatura push renovada).
onMounted(() => {
  if (!('serviceWorker' in navigator)) return

  navigator.serviceWorker.addEventListener('message', (evento: MessageEvent) => {
    const dados = evento.data as { tipo?: string, url?: string } | undefined
    if (dados?.tipo === 'push-navegar' && dados.url) {
      const destino = new URL(dados.url, window.location.origin)
      if (destino.origin === window.location.origin) {
        void navigateTo(destino.pathname + destino.search + destino.hash)
      }
    }
    else if (dados?.tipo === 'push-reassinado' && auth.autenticado) {
      void sincronizarPendenciasPush(requisitar)
    }
  })
})

// Conclui no backend uma re-assinatura feita pelo SW enquanto não havia sessão.
watch(() => auth.autenticado, (autenticado) => {
  if (autenticado) void sincronizarPendenciasPush(requisitar)
}, { immediate: true })
</script>

<template>
  <NuxtPwaManifest />
  <NuxtLayout>
    <NuxtPage />
  </NuxtLayout>
  <PwaAvisoAtualizacao />
</template>
