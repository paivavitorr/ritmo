import { defineStore } from 'pinia'
import type { components } from '~/types/api'
import { gravarMeta, lerMeta, limparBancoLocal } from '~/utils/dbLocal'

export type UsuarioRead = components['schemas']['UsuarioRead']
export type LoginRequest = components['schemas']['LoginRequest']
export type UsuarioCreate = Omit<
  components['schemas']['UsuarioCreate'],
  'fuso' | 'inicio_semana' | 'antecedencia_padrao_min'
> & {
  fuso?: string
  inicio_semana?: number
  antecedencia_padrao_min?: number
}
export type UsuarioUpdate = components['schemas']['UsuarioUpdate']
export type TokenResponse = components['schemas']['TokenResponse']

export type ResultadoRenovacao = 'ok' | 'rede' | 'negado'

const CHAVE_USUARIO = 'usuario'
const CHAVE_USUARIO_ID = 'usuario_id'
const TIMEOUT_SERVICE_WORKER_MS = 3000

function aguardar<T>(promessa: Promise<T>, ms: number): Promise<T | null> {
  return Promise.race([
    promessa,
    new Promise<null>(resolve => setTimeout(() => resolve(null), ms)),
  ])
}

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string | null>(null)
  const usuario = ref<UsuarioRead | null>(null)
  const hidratado = ref(false)
  /** Usuário vindo do cache local, sem access token válido (refresh falhou por rede). */
  const sessaoOffline = ref(false)

  let promessaRefresh: Promise<ResultadoRenovacao> | null = null

  const autenticado = computed(() =>
    Boolean(usuario.value && (accessToken.value || sessaoOffline.value)),
  )

  function limparEstadoDasStores() {
    useCategoriasStore().limpar()
    useBlocosStore().limpar()
    useExecucoesStore().limpar()
  }

  async function aplicarSessao(resposta: TokenResponse): Promise<void> {
    const idLocal = await lerMeta<string>(CHAVE_USUARIO_ID)
    const idMemoria = usuario.value?.id
    const trocouUsuario = (idLocal && idLocal !== resposta.usuario.id)
      || (idMemoria && idMemoria !== resposta.usuario.id)
    if (trocouUsuario) {
      limparEstadoDasStores()
      await limparBancoLocal()
    }
    accessToken.value = resposta.access_token
    usuario.value = resposta.usuario
    sessaoOffline.value = false
    await gravarMeta(CHAVE_USUARIO_ID, resposta.usuario.id)
    await gravarMeta(CHAVE_USUARIO, resposta.usuario)
  }

  /** Encerra a sessão em memória. Os dados locais só são apagados no logout explícito. */
  function limparSessao() {
    accessToken.value = null
    usuario.value = null
    sessaoOffline.value = false
    limparEstadoDasStores()
  }

  async function restaurarUsuarioDoCache(): Promise<boolean> {
    const cache = await lerMeta<UsuarioRead>(CHAVE_USUARIO)
    if (!cache) return false
    usuario.value = cache
    accessToken.value = null
    sessaoOffline.value = true
    return true
  }

  /** Renovação single-flight: chamadas concorrentes compartilham a mesma promise. */
  function renovarSessao(): Promise<ResultadoRenovacao> {
    if (promessaRefresh) return promessaRefresh

    const { apiBase } = useRuntimeConfig().public
    promessaRefresh = (async (): Promise<ResultadoRenovacao> => {
      try {
        const resposta = await $fetch<TokenResponse>('/auth/refresh', {
          baseURL: apiBase,
          method: 'POST',
          credentials: 'include',
        })
        await aplicarSessao(resposta)
        return 'ok'
      }
      catch (erro) {
        const status = (erro as { response?: { status?: number } })?.response?.status
        if (status === 401 || status === 403) {
          limparSessao()
          return 'negado'
        }
        // Rede fora, timeout ou 5xx: não derruba a sessão, segue com o usuário em cache.
        if (!usuario.value) await restaurarUsuarioDoCache()
        else sessaoOffline.value = !accessToken.value
        return 'rede'
      }
      finally {
        hidratado.value = true
        promessaRefresh = null
      }
    })()

    return promessaRefresh
  }

  async function tentarRefresh(): Promise<boolean> {
    return (await renovarSessao()) === 'ok'
  }

  async function garantirHidratacao(): Promise<void> {
    if (hidratado.value) return
    await renovarSessao()
  }

  async function login(credenciais: LoginRequest): Promise<void> {
    const { apiBase } = useRuntimeConfig().public
    const resposta = await $fetch<TokenResponse>('/auth/login', {
      baseURL: apiBase,
      method: 'POST',
      body: credenciais,
      credentials: 'include',
    })
    await aplicarSessao(resposta)
    hidratado.value = true
  }

  async function registrar(dados: UsuarioCreate): Promise<void> {
    const { apiBase } = useRuntimeConfig().public
    const resposta = await $fetch<TokenResponse>('/auth/registrar', {
      baseURL: apiBase,
      method: 'POST',
      body: dados,
      credentials: 'include',
    })
    await aplicarSessao(resposta)
    hidratado.value = true
  }

  /** Cancela a assinatura Web Push deste dispositivo (servidor e navegador). Nunca lança. */
  async function cancelarPush(): Promise<void> {
    if (!import.meta.client || !('serviceWorker' in navigator)) return
    try {
      const registro = await aguardar(navigator.serviceWorker.ready, TIMEOUT_SERVICE_WORKER_MS)
      const assinatura = await registro?.pushManager.getSubscription()
      if (!assinatura) return
      try {
        await useApi().requisitar('/push/desassinar', {
          method: 'POST',
          body: { endpoint: assinatura.endpoint },
        })
      }
      catch {
        // Offline ou sessão inválida: ainda assim cancela a assinatura no navegador.
      }
      await assinatura.unsubscribe()
    }
    catch {
      // Push indisponível neste navegador.
    }
  }

  async function sair(): Promise<void> {
    const { apiBase } = useRuntimeConfig().public
    try {
      await cancelarPush()
      await $fetch('/auth/sair', {
        baseURL: apiBase,
        method: 'POST',
        credentials: 'include',
      })
    }
    catch {
      // Servidor inacessível: o logout local prossegue.
    }
    finally {
      limparSessao()
      await limparBancoLocal()
      useSyncStore().limpar()
      await navigateTo('/login')
    }
  }

  return {
    accessToken,
    usuario,
    hidratado,
    sessaoOffline,
    autenticado,
    aplicarSessao,
    limparSessao,
    renovarSessao,
    tentarRefresh,
    garantirHidratacao,
    login,
    registrar,
    sair,
  }
})
