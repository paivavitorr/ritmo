import type { NitroFetchOptions, NitroFetchRequest } from 'nitropack'

interface OpcoesApi extends Omit<NitroFetchOptions<NitroFetchRequest>, 'body'> {
  body?: Record<string, unknown> | BodyInit | null
  _jaTentouRefresh?: boolean
}

export function extrairMensagemErro(erro: unknown, padrao = 'Não foi possível concluir a ação.'): string {
  if (erro && typeof erro === 'object' && 'data' in erro) {
    const data = (erro as { data?: unknown }).data
    if (data && typeof data === 'object' && 'detail' in data) {
      const detail = (data as { detail?: unknown }).detail
      if (typeof detail === 'string') return detail
      if (Array.isArray(detail) && detail.length > 0) {
        const primeiro = detail[0] as { msg?: string }
        if (primeiro?.msg) return primeiro.msg
      }
    }
  }
  if (erro instanceof Error) return erro.message
  return padrao
}

/**
 * Cliente HTTP autenticado com renovação automática de access token em caso de 401.
 */
export function useApi() {
  const { apiBase } = useRuntimeConfig().public
  const auth = useAuthStore()

  async function requisitar<T>(caminho: string, opcoes: OpcoesApi = {}): Promise<T> {
    const headers = new Headers(opcoes.headers as HeadersInit | undefined)
    if (auth.accessToken) {
      headers.set('Authorization', `Bearer ${auth.accessToken}`)
    }

    try {
      return await $fetch<T>(caminho, {
        ...opcoes,
        baseURL: apiBase,
        headers,
        credentials: 'include',
      })
    }
    catch (erro: unknown) {
      const status = (erro as { response?: { status?: number } })?.response?.status
      const ehRotaAuth = caminho.startsWith('/auth/login')
        || caminho.startsWith('/auth/registrar')
        || caminho.startsWith('/auth/refresh')

      if (status === 401 && !opcoes._jaTentouRefresh && !ehRotaAuth) {
        const renovou = await auth.tentarRefresh()
        if (renovou) {
          return await requisitar<T>(caminho, { ...opcoes, _jaTentouRefresh: true })
        }
        await navigateTo('/login')
      }
      throw erro
    }
  }

  return { requisitar }
}
