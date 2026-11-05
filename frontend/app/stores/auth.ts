import { defineStore } from 'pinia'
import type { components } from '~/types/api'

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

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string | null>(null)
  const usuario = ref<UsuarioRead | null>(null)
  const hidratado = ref(false)

  let promessaRefresh: Promise<boolean> | null = null

  const autenticado = computed(() => Boolean(accessToken.value && usuario.value))

  function aplicarSessao(resposta: TokenResponse) {
    if (usuario.value && usuario.value.id !== resposta.usuario.id) {
      useCategoriasStore().limpar()
      useBlocosStore().limpar()
      useExecucoesStore().limpar()
    }
    accessToken.value = resposta.access_token
    usuario.value = resposta.usuario
  }

  function limparSessao() {
    accessToken.value = null
    usuario.value = null
    useCategoriasStore().limpar()
    useBlocosStore().limpar()
    useExecucoesStore().limpar()
  }

  async function tentarRefresh(): Promise<boolean> {
    if (promessaRefresh) return promessaRefresh

    const { apiBase } = useRuntimeConfig().public
    promessaRefresh = (async () => {
      try {
        const resposta = await $fetch<TokenResponse>('/auth/refresh', {
          baseURL: apiBase,
          method: 'POST',
          credentials: 'include',
        })
        aplicarSessao(resposta)
        return true
      }
      catch {
        limparSessao()
        return false
      }
      finally {
        hidratado.value = true
        promessaRefresh = null
      }
    })()

    return promessaRefresh
  }

  async function garantirHidratacao(): Promise<void> {
    if (hidratado.value) return
    await tentarRefresh()
  }

  async function login(credenciais: LoginRequest): Promise<void> {
    const { apiBase } = useRuntimeConfig().public
    const resposta = await $fetch<TokenResponse>('/auth/login', {
      baseURL: apiBase,
      method: 'POST',
      body: credenciais,
      credentials: 'include',
    })
    aplicarSessao(resposta)
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
    aplicarSessao(resposta)
    hidratado.value = true
  }

  async function sair(): Promise<void> {
    const { apiBase } = useRuntimeConfig().public
    try {
      await $fetch('/auth/sair', {
        baseURL: apiBase,
        method: 'POST',
        credentials: 'include',
      })
    }
    finally {
      limparSessao()
      await navigateTo('/login')
    }
  }

  return {
    accessToken,
    usuario,
    hidratado,
    autenticado,
    aplicarSessao,
    limparSessao,
    tentarRefresh,
    garantirHidratacao,
    login,
    registrar,
    sair,
  }
})
