import type { NitroFetchOptions, NitroFetchRequest } from 'nitropack'

interface OpcoesApi extends Omit<NitroFetchOptions<NitroFetchRequest>, 'body'> {
  body?: Record<string, unknown> | BodyInit | null
  _jaTentouRefresh?: boolean
}

/** A sessão expirou ou foi revogada; o usuário já foi enviado para /login. As telas podem ignorar este erro. */
export class ErroSessaoEncerrada extends Error {
  constructor() {
    super('Sessão expirada. Faça login novamente.')
    this.name = 'ErroSessaoEncerrada'
  }
}

/** Não foi possível renovar a sessão por falta de rede (a sessão local continua válida). */
export class ErroSessaoOffline extends Error {
  constructor() {
    super('Sem conexão com o servidor.')
    this.name = 'ErroSessaoOffline'
  }
}

export function ehErroSessaoEncerrada(erro: unknown): erro is ErroSessaoEncerrada {
  return erro instanceof ErroSessaoEncerrada
}

/** Erro de rede = falha do `$fetch` (FetchError) sem resposta HTTP, ou erro de sessão offline. */
export function ehErroDeRede(erro: unknown): boolean {
  if (erro instanceof ErroSessaoOffline) return true
  if (!erro || typeof erro !== 'object') return false
  const { name, response } = erro as { name?: string, response?: unknown }
  if (name === 'FetchError' || name === 'TypeError') return !response
  return false
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
  if (ehErroDeRede(erro)) return 'Sem conexão com o servidor.'
  if (erro instanceof Error) return erro.message
  return padrao
}

/**
 * Cliente HTTP autenticado com renovação automática de access token em caso de 401.
 * Falha de rede no refresh não derruba a sessão; só 401/403 do refresh encerra.
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
        const resultado = await auth.renovarSessao()
        if (resultado === 'ok') {
          return await requisitar<T>(caminho, { ...opcoes, _jaTentouRefresh: true })
        }
        if (resultado === 'rede') throw new ErroSessaoOffline()
        await navigateTo('/login')
        throw new ErroSessaoEncerrada()
      }
      throw erro
    }
  }

  return { requisitar }
}
