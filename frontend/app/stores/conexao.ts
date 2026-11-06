import { defineStore } from 'pinia'

/** `verificando`: ainda sem resposta da primeira checagem; `indisponivel`: API inacessível. */
type EstadoApi = 'verificando' | 'ok' | 'indisponivel'

const INTERVALO_VERIFICACAO_MS = 15000

/** Estado de conectividade com a API; dispara a sincronização ao voltar a ficar online. */
export const useConexaoStore = defineStore('conexao', () => {
  const api = ref<EstadoApi>('verificando')
  const verificandoAgora = ref(false)

  const online = computed(() => api.value === 'ok')
  const offline = computed(() => api.value === 'indisponivel')

  function marcarIndisponivel() {
    api.value = 'indisponivel'
  }

  async function verificar() {
    if (verificandoAgora.value) return
    const { apiBase } = useRuntimeConfig().public
    const estadoAnterior = api.value
    verificandoAgora.value = true
    try {
      await $fetch('/saude', { baseURL: apiBase, timeout: 4000 })
      api.value = 'ok'
      if (estadoAnterior !== 'ok') {
        // verificando -> ok ou indisponivel -> ok: sincroniza em segundo plano
        void useSyncStore().disparar()
      }
    }
    catch {
      api.value = 'indisponivel'
    }
    finally {
      verificandoAgora.value = false
    }
  }

  let monitorando = false
  let temporizador: ReturnType<typeof setInterval> | null = null

  function pararTemporizador() {
    if (temporizador) clearInterval(temporizador)
    temporizador = null
  }

  function iniciarTemporizador() {
    pararTemporizador()
    temporizador = setInterval(() => void verificar(), INTERVALO_VERIFICACAO_MS)
  }

  function aoMudarVisibilidade() {
    if (document.hidden) {
      pararTemporizador()
      return
    }
    iniciarTemporizador()
    void verificar().then(() => {
      if (api.value === 'ok') void useSyncStore().disparar()
    })
  }

  function iniciarMonitoramento() {
    if (!import.meta.client || monitorando) return
    monitorando = true
    window.addEventListener('online', () => void verificar())
    window.addEventListener('offline', marcarIndisponivel)
    document.addEventListener('visibilitychange', aoMudarVisibilidade)
    if (!document.hidden) iniciarTemporizador()
  }

  return { api, online, offline, verificandoAgora, verificar, marcarIndisponivel, iniciarMonitoramento }
})
