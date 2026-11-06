import { defineStore } from 'pinia'
import {
  dbLocal,
  gravarMeta,
  lerMeta,
  type BlocoLocal,
  type CategoriaLocal,
  type ConflitoLocal,
  type EntidadeSync,
  type ExecucaoLocal,
  type AcaoSync,
  type ModeloBlocoLocal,
  type MutacaoOutbox,
  type StatusConflito,
} from '~/utils/dbLocal'
import { novoId } from '~/utils/id'

// Tipos do contrato /sync (campos novos ainda não presentes no api.d.ts gerado).
interface ItemMutacaoSync {
  id: string
  entidade: EntidadeSync
  acao: AcaoSync
  entidade_id: string
  payload: Record<string, unknown>
  criado_em: string
  versao_base: number | null
}

interface ResultadoMutacaoSync {
  mutacao_id: string
  status: 'aplicado' | 'ignorado' | 'conflito' | 'erro'
  mensagem?: string | null
  versao_servidor?: number | null
  entidade_servidor?: Record<string, unknown> | null
}

interface SyncBatchResposta {
  processadas: number
  resultados: ResultadoMutacaoSync[]
}

type CursorSync = string | number

interface MudancasResposta {
  blocos: BlocoLocal[]
  categorias: CategoriaLocal[]
  execucoes: ExecucaoLocal[]
  modelos_bloco: ModeloBlocoLocal[]
  excluidos: { entidade: string, id: string }[]
  cursor: CursorSync | null
  tem_mais: boolean
}

const TAMANHO_LOTE = 200
const MAX_TENTATIVAS = 5
const ESPERA_BASE_MS = 2000
const ESPERA_MAXIMA_MS = 5 * 60 * 1000
const MAX_PAGINAS_PULL = 50
const CHAVE_CURSOR = 'cursor'

const ENTIDADE_POR_NOME: Record<string, EntidadeSync> = {
  bloco: 'bloco',
  blocos: 'bloco',
  categoria: 'categoria',
  categorias: 'categoria',
  execucao: 'execucao',
  execucoes: 'execucao',
  modelo_bloco: 'modelo_bloco',
  modelos_bloco: 'modelo_bloco',
}

function tabelaDe(entidade: EntidadeSync) {
  switch (entidade) {
    case 'bloco': return dbLocal.blocos
    case 'categoria': return dbLocal.categorias
    case 'execucao': return dbLocal.execucoes
    case 'modelo_bloco': return dbLocal.modelos_bloco
  }
}

type EntidadeComVersao = { id: string, versao: number }

export const useSyncStore = defineStore('sync', () => {
  const sincronizando = ref(false)
  const puxando = ref(false)
  const pendenciasCount = ref(0)
  const conflitos = ref<ConflitoLocal[]>([])
  const ultimoSyncSucesso = ref<Date | null>(null)
  const ultimoErro = ref<string | null>(null)

  /** Compatível com a API anterior. */
  const erroSync = computed(() => ultimoErro.value)

  const idsEmVoo = new Set<string>()
  let promessaCiclo: Promise<void> | null = null
  let pedirNovoCiclo = false
  let promessaPull: Promise<boolean> | null = null
  let temporizadorRetentativa: ReturnType<typeof setTimeout> | null = null
  let gatilhosAtivos = false

  async function atualizarContadorPendencias() {
    pendenciasCount.value = await dbLocal.outbox.count()
    iniciarGatilhos()
  }

  async function carregarConflitos() {
    conflitos.value = await dbLocal.conflitos.orderBy('criadoEm').toArray()
  }

  function podeUsarRede(): boolean {
    if (!import.meta.client) return false
    if (!navigator.onLine) return false
    return useConexaoStore().api !== 'indisponivel'
  }

  /** Garante access token válido; em sessão offline tenta renová-lo agora que há rede. */
  async function garantirSessaoParaRede(): Promise<boolean> {
    const auth = useAuthStore()
    if (!auth.autenticado) return false
    if (auth.accessToken) return true
    return (await auth.renovarSessao()) === 'ok'
  }

  async function recarregarStores() {
    await Promise.all([
      useCategoriasStore().recarregarLocal(),
      useBlocosStore().recarregarLocal(),
      useExecucoesStore().recarregarLocal(),
    ])
  }

  // ---------- Outbox: enfileirar ----------

  async function enfileirarMutacao(
    entidade: EntidadeSync,
    acao: AcaoSync,
    entidadeId: string,
    payload: Record<string, unknown>,
    versaoBase: number | null = null,
  ): Promise<void> {
    const existentes = (await dbLocal.outbox.where('entidadeId').equals(entidadeId).toArray())
      .filter(m => !idsEmVoo.has(m.id))
      .sort((a, b) => a.criadoEm.localeCompare(b.criadoEm))
    const ultima = existentes[existentes.length - 1]
    const pendenteCriar = existentes.find(m => m.acao === 'criar')

    if (acao === 'excluir' && pendenteCriar) {
      // A entidade nunca chegou ao servidor: descarta tudo em vez de criar e excluir.
      await dbLocal.outbox.bulkDelete(existentes.map(m => m.id))
    }
    else if (acao === 'atualizar' && ultima && (ultima.acao === 'criar' || ultima.acao === 'atualizar')) {
      await dbLocal.outbox.update(ultima.id, { payload: { ...ultima.payload, ...payload } })
    }
    else {
      const mutacao: MutacaoOutbox = {
        id: novoId(),
        entidade,
        acao,
        entidadeId,
        payload,
        criadoEm: new Date().toISOString(),
        versaoBase,
        tentativas: 0,
      }
      await dbLocal.outbox.add(mutacao)
    }

    await atualizarContadorPendencias()
    void disparar()
  }

  // ---------- Conflitos ----------

  async function registrarConflito(
    mutacao: MutacaoOutbox,
    status: StatusConflito,
    mensagem: string,
  ) {
    await dbLocal.conflitos.add({
      id: novoId(),
      mutacaoId: mutacao.id,
      entidade: mutacao.entidade,
      acao: mutacao.acao,
      entidadeId: mutacao.entidadeId,
      status,
      mensagem,
      payload: mutacao.payload,
      versaoBase: mutacao.versaoBase ?? null,
      criadoEm: new Date().toISOString(),
    })
  }

  async function descartarConflito(id: string) {
    await dbLocal.conflitos.delete(id)
    await carregarConflitos()
  }

  async function descartarTodosConflitos() {
    await dbLocal.conflitos.clear()
    await carregarConflitos()
  }

  /** Reenfileira a mutação rejeitada, usando a versão local atual como base. */
  async function tentarNovamente(id: string) {
    const conflito = await dbLocal.conflitos.get(id)
    if (!conflito) return
    const local = await tabelaDe(conflito.entidade).get(conflito.entidadeId) as EntidadeComVersao | undefined
    await dbLocal.conflitos.delete(id)
    await carregarConflitos()
    await enfileirarMutacao(
      conflito.entidade,
      conflito.acao,
      conflito.entidadeId,
      conflito.payload,
      local?.versao ?? null,
    )
  }

  // ---------- Outbox: enviar ----------

  async function aplicarEntidadeServidor(entidade: EntidadeSync, dados: Record<string, unknown>) {
    const id = dados.id
    if (typeof id !== 'string') return
    await (tabelaDe(entidade) as unknown as { put: (v: unknown) => Promise<unknown> }).put(dados)
  }

  async function tratarResultado(mutacao: MutacaoOutbox, res: ResultadoMutacaoSync): Promise<boolean> {
    const restantes = await dbLocal.outbox
      .where('entidadeId').equals(mutacao.entidadeId)
      .filter(m => m.id !== mutacao.id)
      .toArray()

    if (res.status === 'erro') {
      const tentativas = mutacao.tentativas + 1
      const mensagem = res.mensagem ?? 'Erro no servidor'
      if (tentativas >= MAX_TENTATIVAS) {
        await registrarConflito(mutacao, 'falhou', mensagem)
        await dbLocal.outbox.delete(mutacao.id)
        return true
      }
      const espera = Math.min(ESPERA_BASE_MS * 2 ** (tentativas - 1), ESPERA_MAXIMA_MS)
      await dbLocal.outbox.update(mutacao.id, {
        tentativas,
        ultimoErro: mensagem,
        proximaTentativaEm: Date.now() + espera,
      })
      return false
    }

    await dbLocal.outbox.delete(mutacao.id)

    if (res.status === 'aplicado') {
      if (res.versao_servidor != null) {
        for (const r of restantes) {
          await dbLocal.outbox.update(r.id, { versaoBase: res.versao_servidor })
        }
      }
      // O estado do servidor só sobrescreve o local se não houver edição posterior pendente.
      if (res.entidade_servidor && restantes.length === 0) {
        await aplicarEntidadeServidor(mutacao.entidade, res.entidade_servidor)
      }
      else if (res.versao_servidor != null && restantes.length === 0 && mutacao.acao !== 'excluir') {
        await tabelaDe(mutacao.entidade).update(mutacao.entidadeId, { versao: res.versao_servidor } as never)
      }
      return true
    }

    // ignorado ou conflito: servidor vence
    if (res.entidade_servidor) {
      await aplicarEntidadeServidor(mutacao.entidade, res.entidade_servidor)
      await registrarConflito(
        mutacao,
        res.status === 'conflito' ? 'conflito' : 'ignorado',
        res.mensagem ?? 'O servidor manteve uma versão diferente desta alteração.',
      )
    }
    else if (res.status === 'conflito') {
      await registrarConflito(mutacao, 'conflito', res.mensagem ?? 'Conflito com o servidor.')
    }
    return true
  }

  /** Envia a outbox em lotes ordenados. Retorna `false` se parou por falha de rede/sessão. */
  async function enviarOutbox(): Promise<boolean> {
    const { requisitar } = useApi()

    for (;;) {
      const agora = Date.now()
      const todas = await dbLocal.outbox.orderBy('criadoEm').limit(TAMANHO_LOTE).toArray()
      // Preserva a ordem: para na primeira mutação ainda em backoff.
      const lote: MutacaoOutbox[] = []
      for (const m of todas) {
        if ((m.proximaTentativaEm ?? 0) > agora) break
        lote.push(m)
      }
      if (!lote.length) return true

      lote.forEach(m => idsEmVoo.add(m.id))
      try {
        const corpo = {
          mutacoes: lote.map<ItemMutacaoSync>(m => ({
            id: m.id,
            entidade: m.entidade,
            acao: m.acao,
            entidade_id: m.entidadeId,
            payload: m.payload,
            criado_em: m.criadoEm,
            versao_base: m.versaoBase ?? null,
          })),
        }
        const resposta = await requisitar<SyncBatchResposta>('/sync/batch', {
          method: 'POST',
          body: corpo,
        })

        let progresso = 0
        for (const res of resposta.resultados) {
          const mutacao = lote.find(m => m.id === res.mutacao_id)
          if (!mutacao) continue
          if (await tratarResultado(mutacao, res)) progresso++
        }
        ultimoSyncSucesso.value = new Date()
        ultimoErro.value = null
        if (progresso === 0) return true
      }
      catch (erro) {
        if (ehErroSessaoEncerrada(erro)) return false
        if (ehErroDeRede(erro)) {
          useConexaoStore().marcarIndisponivel()
          return false
        }
        ultimoErro.value = extrairMensagemErro(erro, 'Falha ao sincronizar dados com o servidor.')
        return false
      }
      finally {
        lote.forEach(m => idsEmVoo.delete(m.id))
      }
    }
  }

  // ---------- Pull ----------

  async function mesclarLista<T extends EntidadeComVersao>(
    entidade: EntidadeSync,
    lista: T[],
    pendentes: Set<string>,
  ) {
    if (!lista.length) return
    const tabela = tabelaDe(entidade) as unknown as {
      bulkGet: (ids: string[]) => Promise<(EntidadeComVersao | undefined)[]>
      bulkPut: (v: unknown[]) => Promise<unknown>
    }
    const locais = await tabela.bulkGet(lista.map(e => e.id))
    const aplicar = lista.filter((e, i) => {
      if (pendentes.has(e.id)) return false
      const local = locais[i]
      return !local || e.versao >= local.versao
    })
    if (aplicar.length) await tabela.bulkPut(aplicar)
  }

  async function executarPull(): Promise<boolean> {
    const { requisitar } = useApi()
    let alterou = false
    let cursor = await lerMeta<CursorSync>(CHAVE_CURSOR)
    puxando.value = true
    try {
      for (let pagina = 0; pagina < MAX_PAGINAS_PULL; pagina++) {
        const consulta = cursor != null ? `?desde=${encodeURIComponent(String(cursor))}` : ''
        const resposta = await requisitar<MudancasResposta>(`/sync/mudancas${consulta}`)

        // Entidades com edição local ainda não enviada (outbox ou cronômetro offline) não são sobrescritas.
        const pendentes = new Set((await dbLocal.outbox.toArray()).map(m => m.entidadeId))
        for (const id of (await lerMeta<string[]>('execucoes_offline')) ?? []) pendentes.add(id)
        await mesclarLista('categoria', resposta.categorias ?? [], pendentes)
        await mesclarLista('bloco', resposta.blocos ?? [], pendentes)
        await mesclarLista('execucao', resposta.execucoes ?? [], pendentes)
        await mesclarLista('modelo_bloco', resposta.modelos_bloco ?? [], pendentes)
        for (const excluido of resposta.excluidos ?? []) {
          const entidade = ENTIDADE_POR_NOME[excluido.entidade]
          if (entidade && !pendentes.has(excluido.id)) await tabelaDe(entidade).delete(excluido.id)
        }

        alterou ||= Boolean(
          resposta.blocos?.length || resposta.categorias?.length || resposta.execucoes?.length
          || resposta.modelos_bloco?.length || resposta.excluidos?.length,
        )
        if (resposta.cursor != null) {
          cursor = resposta.cursor
          await gravarMeta(CHAVE_CURSOR, cursor)
        }
        if (!resposta.tem_mais) break
      }
      ultimoErro.value = null
    }
    catch (erro) {
      if (ehErroDeRede(erro)) useConexaoStore().marcarIndisponivel()
      else if (!ehErroSessaoEncerrada(erro)) {
        ultimoErro.value = extrairMensagemErro(erro, 'Falha ao buscar mudanças do servidor.')
      }
    }
    finally {
      puxando.value = false
    }
    return alterou
  }

  /** Busca mudanças do servidor (single-flight) e mescla no Dexie. Nunca lança. Retorna se algo mudou. */
  async function puxarMudancas(): Promise<boolean> {
    if (promessaPull) return promessaPull
    if (!podeUsarRede() || !(await garantirSessaoParaRede())) return false
    promessaPull = executarPull().finally(() => {
      promessaPull = null
    })
    return promessaPull
  }

  // ---------- Ciclo de sincronização ----------

  function agendarRetentativa() {
    if (temporizadorRetentativa) clearTimeout(temporizadorRetentativa)
    temporizadorRetentativa = null
    void dbLocal.outbox.toArray().then((todas) => {
      const futuras = todas.map(m => m.proximaTentativaEm ?? 0).filter(t => t > Date.now())
      if (!futuras.length) return
      const espera = Math.min(...futuras) - Date.now()
      temporizadorRetentativa = setTimeout(() => void disparar(), Math.max(espera, 500))
    })
  }

  async function cicloSync() {
    if (!podeUsarRede() || !(await garantirSessaoParaRede())) {
      await atualizarContadorPendencias()
      return
    }
    sincronizando.value = true
    try {
      const enviou = await enviarOutbox()
      if (enviou) await puxarMudancas()
    }
    finally {
      sincronizando.value = false
      await atualizarContadorPendencias()
      await carregarConflitos()
      await recarregarStores()
      agendarRetentativa()
    }
  }

  /** Dispara a sincronização (push + pull). Se chamado durante um ciclo, roda de novo ao terminar. */
  function disparar(): Promise<void> {
    if (promessaCiclo) {
      pedirNovoCiclo = true
      return promessaCiclo
    }
    promessaCiclo = (async () => {
      try {
        do {
          pedirNovoCiclo = false
          await cicloSync()
        } while (pedirNovoCiclo)
      }
      finally {
        promessaCiclo = null
      }
    })()
    return promessaCiclo
  }

  /** Compatível com a API anterior: retorna quantas pendências restaram resolvidas neste ciclo. */
  async function sincronizarOutbox(): Promise<number> {
    const antes = await dbLocal.outbox.count()
    await disparar()
    return Math.max(0, antes - pendenciasCount.value)
  }

  function iniciarGatilhos() {
    if (gatilhosAtivos || !import.meta.client) return
    gatilhosAtivos = true
    void carregarConflitos()
    window.addEventListener('online', () => void disparar())
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden) void disparar()
    })
    // App iniciando com sessão: sincroniza assim que a hidratação terminar.
    const auth = useAuthStore()
    watch(
      () => auth.autenticado,
      (ok) => {
        if (ok) void disparar()
      },
      { immediate: true },
    )
  }

  function limpar() {
    conflitos.value = []
    pendenciasCount.value = 0
    ultimoErro.value = null
    ultimoSyncSucesso.value = null
    idsEmVoo.clear()
    if (temporizadorRetentativa) clearTimeout(temporizadorRetentativa)
    temporizadorRetentativa = null
  }

  return {
    sincronizando,
    puxando,
    pendenciasCount,
    conflitos,
    ultimoSyncSucesso,
    ultimoErro,
    erroSync,
    enfileirarMutacao,
    sincronizarOutbox,
    disparar,
    puxarMudancas,
    atualizarContadorPendencias,
    carregarConflitos,
    descartarConflito,
    descartarTodosConflitos,
    tentarNovamente,
    iniciarGatilhos,
    limpar,
  }
})
