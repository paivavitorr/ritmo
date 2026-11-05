import { defineStore } from 'pinia'

type EstadoApi = 'verificando' | 'ok' | 'indisponivel'

/** Estado de conectividade com a API com gatilho automático de sincronização offline (F7). */
export const useConexaoStore = defineStore('conexao', () => {
  const api = ref<EstadoApi>('verificando')

  async function verificar() {
    const { apiBase } = useRuntimeConfig().public
    const estadoAnterior = api.value
    try {
      await $fetch('/saude', { baseURL: apiBase, timeout: 4000 })
      api.value = 'ok'
      if (estadoAnterior === 'indisponivel') {
        // Conexão restabelecida: dispara sincronização silenciosa em segundo plano
        const syncStore = useSyncStore()
        void syncStore.sincronizarOutbox()
      }
    }
    catch {
      api.value = 'indisponivel'
    }
  }

  let monitorando = false

  function iniciarMonitoramento() {
    if (import.meta.client && !monitorando) {
      monitorando = true
      window.addEventListener('online', verificar)
      window.addEventListener('offline', () => {
        api.value = 'indisponivel'
      })
      setInterval(verificar, 15000)
    }
  }

  return { api, verificar, iniciarMonitoramento }
})
