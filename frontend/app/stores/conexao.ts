import { defineStore } from 'pinia'

type EstadoApi = 'verificando' | 'ok' | 'indisponivel'

/** Estado de conectividade com a API. Base para o indicador offline (F7). */
export const useConexaoStore = defineStore('conexao', () => {
  const api = ref<EstadoApi>('verificando')

  async function verificar() {
    const { apiBase } = useRuntimeConfig().public
    try {
      await $fetch('/saude', { baseURL: apiBase, timeout: 4000 })
      api.value = 'ok'
    }
    catch {
      api.value = 'indisponivel'
    }
  }

  return { api, verificar }
})
