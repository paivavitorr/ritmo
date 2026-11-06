import { defineStore } from 'pinia'
import type { components } from '~/types/api'
import { dbLocal, gravarMeta, lerMeta, segundosLiquidosEntre } from '~/utils/dbLocal'
import { novoId } from '~/utils/id'
import { dataIsoNoFuso, somarDiasIso } from '~/utils/tempo'

export type ExecucaoRead = components['schemas']['ExecucaoRead']
export type ExecucaoCreate = Omit<
  components['schemas']['ExecucaoCreate'],
  'status' | 'origem' | 'pausas'
> & {
  status?: components['schemas']['ExecucaoCreate']['status']
  origem?: components['schemas']['ExecucaoCreate']['origem']
  pausas?: components['schemas']['PausaExecucaoInput'][]
}
export type ExecucaoUpdate = components['schemas']['ExecucaoUpdate']
export type ExecucaoIniciarRequest = components['schemas']['ExecucaoIniciarRequest']
export type ExecucaoConfirmarBlocoRequest = components['schemas']['ExecucaoConfirmarBlocoRequest']

type StatusFinal = 'concluida' | 'parcial' | 'pulada'

const CHAVE_EXECUCOES_OFFLINE = 'execucoes_offline'

/**
 * Calcula quantos segundos líquidos se passaram em uma execução aberta até `agoraMs`.
 */
export function calcularSegundosLiquidosAoVivo(
  execucao: ExecucaoRead,
  agoraMs = Date.now(),
): number {
  if (execucao.fim != null && execucao.status !== 'em_andamento') {
    return execucao.segundos_liquidos
  }
  const inicioMs = new Date(execucao.inicio).getTime()
  const fimEfetivoMs = execucao.fim ? new Date(execucao.fim).getTime() : Math.max(inicioMs, agoraMs)
  return segundosLiquidosEntre(
    execucao.inicio,
    new Date(fimEfetivoMs).toISOString(),
    execucao.pausas,
  )
}

function fusoDoUsuario(): string {
  return useAuthStore().usuario?.fuso ?? Intl.DateTimeFormat().resolvedOptions().timeZone
}

function abertaEmAndamento(e: ExecucaoRead): boolean {
  return e.status === 'em_andamento' && e.fim == null
}

/** Pausas no formato de envio (todas fechadas em `fimIso`). */
function pausasParaEnvio(pausas: ExecucaoRead['pausas'], fimIso: string) {
  return pausas.map(p => ({ id: p.id, inicio: p.inicio, fim: p.fim ?? fimIso }))
}

export const useExecucoesStore = defineStore('execucoes', () => {
  const itens = ref<ExecucaoRead[]>([])
  const ativa = ref<ExecucaoRead | null>(null)
  const carregando = ref(false)
  const ultimoRangeCarregado = ref<{ de: string, ate: string } | null>(null)

  function _ordenar(lista: ExecucaoRead[]): ExecucaoRead[] {
    return [...lista].sort((a, b) => a.inicio.localeCompare(b.inicio))
  }

  function _inserirOuAtualizarNaMemoria(execucao: ExecucaoRead) {
    const semAntiga = itens.value.filter(e => e.id !== execucao.id)
    itens.value = _ordenar([...semAntiga, execucao])

    if (abertaEmAndamento(execucao)) {
      ativa.value = execucao
    }
    else if (ativa.value?.id === execucao.id) {
      ativa.value = null
    }
  }

  function _removerDaMemoria(execucaoId: string) {
    itens.value = itens.value.filter(e => e.id !== execucaoId)
    if (ativa.value?.id === execucaoId) {
      ativa.value = null
    }
  }

  async function _salvar(execucao: ExecucaoRead): Promise<ExecucaoRead> {
    await dbLocal.execucoes.put(execucao)
    _inserirOuAtualizarNaMemoria(execucao)
    return execucao
  }

  async function _buscar(execucaoId: string): Promise<ExecucaoRead> {
    const encontrada = itens.value.find(e => e.id === execucaoId) ?? await dbLocal.execucoes.get(execucaoId)
    if (!encontrada) throw new Error('Execução não encontrada.')
    return encontrada
  }

  // Cronômetros alterados offline só são enviados ao concluir; esta lista os identifica.
  async function _ehOffline(id: string): Promise<boolean> {
    return ((await lerMeta<string[]>(CHAVE_EXECUCOES_OFFLINE)) ?? []).includes(id)
  }

  async function _marcarOffline(id: string, marcar: boolean) {
    const atual = (await lerMeta<string[]>(CHAVE_EXECUCOES_OFFLINE)) ?? []
    const novo = marcar ? [...new Set([...atual, id])] : atual.filter(x => x !== id)
    await gravarMeta(CHAVE_EXECUCOES_OFFLINE, novo)
  }

  async function _apenasLocal(execucao: ExecucaoRead): Promise<boolean> {
    return execucao.versao === 0 || await _ehOffline(execucao.id)
  }

  /** Executa pela API; se a rede falhar, cai no caminho local equivalente. */
  async function _comFallback(
    execucao: ExecucaoRead,
    online: () => Promise<ExecucaoRead>,
    local: () => Promise<ExecucaoRead>,
  ): Promise<ExecucaoRead> {
    const conexao = useConexaoStore()
    const usarRede = navigator.onLine && conexao.api !== 'indisponivel' && !(await _apenasLocal(execucao))
    if (usarRede) {
      try {
        return await _salvar(await online())
      }
      catch (erro) {
        if (!ehErroDeRede(erro)) throw erro
        conexao.marcarIndisponivel()
      }
    }
    return await local()
  }

  /** Enfileira o estado final de uma execução que mudou localmente (criar se o servidor não a conhece). */
  async function _enfileirarEstadoFinal(execucao: ExecucaoRead, fimIso: string, versaoBase: number) {
    const sync = useSyncStore()
    const pausas = pausasParaEnvio(execucao.pausas, fimIso)
    if (execucao.versao === 0) {
      await sync.enfileirarMutacao('execucao', 'criar', execucao.id, {
        id: execucao.id,
        categoria_id: execucao.categoria_id,
        bloco_id: execucao.bloco_id,
        inicio: execucao.inicio,
        fim: fimIso,
        status: execucao.status,
        origem: execucao.origem,
        pausas,
      })
    }
    else {
      await sync.enfileirarMutacao('execucao', 'atualizar', execucao.id, {
        fim: fimIso,
        status: execucao.status,
        pausas,
      }, versaoBase)
    }
    await _marcarOffline(execucao.id, false)
  }

  const porBlocoId = computed(() => {
    const mapa = new Map<string, ExecucaoRead[]>()
    for (const e of itens.value) {
      if (!e.bloco_id) continue
      const lista = mapa.get(e.bloco_id) ?? []
      lista.push(e)
      mapa.set(e.bloco_id, lista)
    }
    if (ativa.value?.bloco_id) {
      const lista = mapa.get(ativa.value.bloco_id) ?? []
      if (!lista.some(x => x.id === ativa.value?.id)) {
        lista.push(ativa.value)
        mapa.set(ativa.value.bloco_id, lista)
      }
    }
    return mapa
  })

  function execucaoPrincipalDoBloco(blocoId: string): ExecucaoRead | undefined {
    const lista = porBlocoId.value.get(blocoId)
    if (!lista || !lista.length) return undefined
    // Prioriza em_andamento, depois a mais recente
    const aberta = lista.find(abertaEmAndamento)
    if (aberta) return aberta
    return lista[lista.length - 1]
  }

  async function _lerAtivaLocal(): Promise<ExecucaoRead | null> {
    const abertas = await dbLocal.execucoes
      .where('status').equals('em_andamento')
      .filter(e => e.fim == null)
      .toArray()
    return _ordenar(abertas).pop() ?? null
  }

  async function _lerPeriodoLocal(deIso: string, ateIso: string): Promise<ExecucaoRead[]> {
    const fuso = fusoDoUsuario()
    // Margem de um dia em UTC; o filtro exato é pelo dia no fuso do usuário.
    const inicioBusca = `${somarDiasIso(deIso, -1)}T00:00:00.000Z`
    const fimBusca = `${somarDiasIso(ateIso, 2)}T00:00:00.000Z`
    const lista = await dbLocal.execucoes
      .where('inicio').between(inicioBusca, fimBusca, true, true)
      .filter((e) => {
        const dia = dataIsoNoFuso(new Date(e.inicio), fuso)
        return dia >= deIso && dia <= ateIso
      })
      .toArray()
    const execAtiva = await _lerAtivaLocal()
    ativa.value = execAtiva
    if (execAtiva && !lista.some(e => e.id === execAtiva.id)) lista.push(execAtiva)
    itens.value = _ordenar(lista)
    return itens.value
  }

  async function recarregarLocal() {
    const range = ultimoRangeCarregado.value
    if (range) await _lerPeriodoLocal(range.de, range.ate)
    else ativa.value = await _lerAtivaLocal()
  }

  async function carregarAtiva(): Promise<ExecucaoRead | null> {
    ativa.value = await _lerAtivaLocal()
    if (await useSyncStore().puxarMudancas()) {
      ativa.value = await _lerAtivaLocal()
    }
    if (ativa.value) _inserirOuAtualizarNaMemoria(ativa.value)
    return ativa.value
  }

  async function carregarPeriodo(deIso: string, ateIso: string): Promise<ExecucaoRead[]> {
    carregando.value = true
    try {
      ultimoRangeCarregado.value = { de: deIso, ate: ateIso }
      await _lerPeriodoLocal(deIso, ateIso)
      carregando.value = false
      if (await useSyncStore().puxarMudancas()) {
        await _lerPeriodoLocal(deIso, ateIso)
      }
      return itens.value
    }
    finally {
      carregando.value = false
    }
  }

  // ---------- Cronômetro ----------

  /** Encerra localmente uma execução aberta (usado ao iniciar outra sem rede). */
  async function _encerrarLocal(execucao: ExecucaoRead, instanteIso: string, status: StatusFinal = 'concluida') {
    const fim = instanteIso < execucao.inicio ? execucao.inicio : instanteIso
    const pausas = execucao.pausas.map(p => ({ ...p, fim: p.fim ?? fim }))
    const encerrada: ExecucaoRead = {
      ...execucao,
      pausas,
      fim,
      status,
      segundos_liquidos: segundosLiquidosEntre(execucao.inicio, fim, pausas),
      atualizado_em: new Date().toISOString(),
    }
    await _salvar(encerrada)
    await _enfileirarEstadoFinal(encerrada, fim, execucao.versao)
    return encerrada
  }

  async function iniciarCronometro(dados: ExecucaoIniciarRequest): Promise<ExecucaoRead> {
    const conexao = useConexaoStore()
    const id = dados.id ?? novoId()
    const instante = dados.instante ?? new Date().toISOString()
    const anterior = ativa.value

    // Cronômetro anterior que o servidor desconhece não pode ser encerrado por ele.
    if (anterior && await _apenasLocal(anterior)) {
      await _encerrarLocal(anterior, instante)
    }

    if (navigator.onLine && conexao.api !== 'indisponivel') {
      try {
        const iniciada = await useApi().requisitar<ExecucaoRead>('/execucoes/iniciar', {
          method: 'POST',
          body: { ...dados, id } as unknown as Record<string, unknown>,
        })
        // O servidor encerra a execução aberta anterior: recarrega seus dados atualizados.
        if (anterior && anterior.id !== iniciada.id && !(await _apenasLocal(anterior))) {
          try {
            const encerrada = await useApi().requisitar<ExecucaoRead>(`/execucoes/${anterior.id}`)
            await _salvar(encerrada)
          }
          catch {
            // Segue com o que há localmente; o pull corrige depois.
          }
        }
        return await _salvar(iniciada)
      }
      catch (erro) {
        if (!ehErroDeRede(erro)) throw erro
        conexao.marcarIndisponivel()
      }
    }

    // Offline: cria localmente; só vai para a outbox quando for concluída.
    if (anterior && !(await _apenasLocal(anterior)) && ativa.value?.id === anterior.id) {
      await _encerrarLocal(anterior, instante)
    }
    const bloco = dados.bloco_id ? await dbLocal.blocos.get(dados.bloco_id) : undefined
    const categoriaId = dados.categoria_id ?? bloco?.categoria_id
    if (!categoriaId) throw new Error('Informe a categoria ou o bloco para iniciar a execução.')
    const agora = new Date().toISOString()
    const nova: ExecucaoRead = {
      id,
      usuario_id: useAuthStore().usuario?.id ?? '',
      categoria_id: categoriaId,
      bloco_id: dados.bloco_id ?? null,
      inicio: instante,
      fim: null,
      status: 'em_andamento',
      origem: 'cronometro',
      segundos_liquidos: 0,
      pausas: [],
      versao: 0,
      criado_em: agora,
      atualizado_em: agora,
    }
    await _marcarOffline(id, true)
    return await _salvar(nova)
  }

  async function pausarCronometro(execucaoId: string): Promise<ExecucaoRead> {
    const exec = await _buscar(execucaoId)
    return await _comFallback(
      exec,
      () => useApi().requisitar<ExecucaoRead>(`/execucoes/${execucaoId}/pausar`, { method: 'POST', body: {} }),
      async () => {
        const agora = new Date().toISOString()
        if (exec.pausas.some(p => p.fim == null)) return exec
        await _marcarOffline(execucaoId, true)
        return await _salvar({
          ...exec,
          pausas: [...exec.pausas, { id: novoId(), execucao_id: exec.id, inicio: agora, fim: null }],
          atualizado_em: agora,
        })
      },
    )
  }

  async function retomarCronometro(execucaoId: string): Promise<ExecucaoRead> {
    const exec = await _buscar(execucaoId)
    return await _comFallback(
      exec,
      () => useApi().requisitar<ExecucaoRead>(`/execucoes/${execucaoId}/retomar`, { method: 'POST', body: {} }),
      async () => {
        const agora = new Date().toISOString()
        await _marcarOffline(execucaoId, true)
        return await _salvar({
          ...exec,
          pausas: exec.pausas.map(p => (p.fim == null ? { ...p, fim: agora } : p)),
          atualizado_em: agora,
        })
      },
    )
  }

  async function concluirCronometro(
    execucaoId: string,
    statusFinal: 'concluida' | 'parcial' = 'concluida',
  ): Promise<ExecucaoRead> {
    const exec = await _buscar(execucaoId)
    return await _comFallback(
      exec,
      () => useApi().requisitar<ExecucaoRead>(`/execucoes/${execucaoId}/concluir`, {
        method: 'POST',
        body: { status: statusFinal },
      }),
      async () => await _encerrarLocal(exec, new Date().toISOString(), statusFinal),
    )
  }

  // ---------- Confirmação e CRUD manual ----------

  async function confirmarBloco(
    blocoId: string,
    statusConfirmacao: 'concluida' | 'parcial' | 'pulada' = 'concluida',
  ): Promise<ExecucaoRead> {
    const bloco = await dbLocal.blocos.get(blocoId)
    if (!bloco) throw new Error('Bloco não encontrado.')
    const existente = execucaoPrincipalDoBloco(blocoId)
    const sync = useSyncStore()

    let resultado: ExecucaoRead
    if (existente && abertaEmAndamento(existente)) {
      resultado = await _encerrarLocal(existente, new Date().toISOString(), statusConfirmacao)
    }
    else if (existente) {
      resultado = await _salvar({
        ...existente,
        status: statusConfirmacao,
        segundos_liquidos: statusConfirmacao === 'pulada'
          ? 0
          : segundosLiquidosEntre(existente.inicio, existente.fim ?? bloco.fim, existente.pausas),
        atualizado_em: new Date().toISOString(),
      })
      await sync.enfileirarMutacao(
        'execucao',
        'atualizar',
        existente.id,
        { status: statusConfirmacao },
        existente.versao,
      )
    }
    else {
      const id = novoId()
      const agora = new Date().toISOString()
      const pausas = bloco.pausas_planejadas.map(p => ({
        id: novoId(),
        execucao_id: id,
        inicio: p.inicio,
        fim: p.fim as string | null,
      }))
      resultado = await _salvar({
        id,
        usuario_id: useAuthStore().usuario?.id ?? '',
        categoria_id: bloco.categoria_id,
        bloco_id: bloco.id,
        inicio: bloco.inicio,
        fim: bloco.fim,
        status: statusConfirmacao,
        origem: 'confirmacao',
        segundos_liquidos: statusConfirmacao === 'pulada'
          ? 0
          : segundosLiquidosEntre(bloco.inicio, bloco.fim, pausas),
        pausas,
        versao: 0,
        criado_em: agora,
        atualizado_em: agora,
      })
      await sync.enfileirarMutacao('execucao', 'criar', id, {
        id,
        categoria_id: bloco.categoria_id,
        bloco_id: bloco.id,
        inicio: bloco.inicio,
        fim: bloco.fim,
        status: statusConfirmacao,
        origem: 'confirmacao',
        pausas: pausas.map(p => ({ id: p.id, inicio: p.inicio, fim: p.fim ?? bloco.fim })),
      })
    }
    if (ativa.value?.bloco_id === blocoId && resultado.id !== ativa.value.id) {
      ativa.value = null
    }
    return resultado
  }

  async function criarManual(dados: ExecucaoCreate): Promise<ExecucaoRead> {
    const id = dados.id ?? novoId()
    const agora = new Date().toISOString()
    const status = dados.status ?? 'concluida'
    const origem = dados.origem ?? 'manual'
    const pausas = (dados.pausas ?? []).map(p => ({
      id: p.id ?? novoId(),
      execucao_id: id,
      inicio: p.inicio,
      fim: p.fim as string | null,
    }))
    const criada = await _salvar({
      id,
      usuario_id: useAuthStore().usuario?.id ?? '',
      categoria_id: dados.categoria_id,
      bloco_id: dados.bloco_id ?? null,
      inicio: dados.inicio,
      fim: dados.fim,
      status,
      origem,
      segundos_liquidos: status === 'pulada' ? 0 : segundosLiquidosEntre(dados.inicio, dados.fim, pausas),
      pausas,
      versao: 0,
      criado_em: agora,
      atualizado_em: agora,
    })
    await useSyncStore().enfileirarMutacao('execucao', 'criar', id, {
      id,
      categoria_id: dados.categoria_id,
      bloco_id: dados.bloco_id ?? null,
      inicio: dados.inicio,
      fim: dados.fim,
      status,
      origem,
      pausas: pausas.map(p => ({ id: p.id, inicio: p.inicio, fim: p.fim ?? dados.fim })),
    })
    return criada
  }

  async function atualizarManual(
    execucaoId: string,
    dados: ExecucaoUpdate,
  ): Promise<ExecucaoRead> {
    const base = await _buscar(execucaoId)
    const pausas = dados.pausas
      ? dados.pausas.map(p => ({
          id: p.id ?? novoId(),
          execucao_id: execucaoId,
          inicio: p.inicio,
          fim: p.fim as string | null,
        }))
      : base.pausas
    const inicio = dados.inicio ?? base.inicio
    const fim = dados.fim === undefined ? base.fim : dados.fim
    const status = dados.status ?? base.status
    const atualizada = await _salvar({
      ...base,
      categoria_id: dados.categoria_id ?? base.categoria_id,
      bloco_id: dados.bloco_id === undefined ? base.bloco_id : dados.bloco_id,
      inicio,
      fim,
      status,
      pausas,
      segundos_liquidos: fim == null
        ? base.segundos_liquidos
        : status === 'pulada' ? 0 : segundosLiquidosEntre(inicio, fim, pausas),
      atualizado_em: new Date().toISOString(),
    })
    const payload: Record<string, unknown> = { ...dados }
    if (dados.pausas) payload.pausas = pausas.map(p => ({ id: p.id, inicio: p.inicio, fim: p.fim }))
    await useSyncStore().enfileirarMutacao('execucao', 'atualizar', execucaoId, payload, base.versao)
    return atualizada
  }

  async function excluirExecucao(execucaoId: string): Promise<void> {
    const base = itens.value.find(e => e.id === execucaoId) ?? await dbLocal.execucoes.get(execucaoId)
    await dbLocal.execucoes.delete(execucaoId)
    _removerDaMemoria(execucaoId)
    await _marcarOffline(execucaoId, false)
    await useSyncStore().enfileirarMutacao('execucao', 'excluir', execucaoId, {}, base?.versao ?? null)
  }

  function limpar() {
    itens.value = []
    ativa.value = null
    ultimoRangeCarregado.value = null
  }

  return {
    itens,
    ativa,
    carregando,
    porBlocoId,
    execucaoPrincipalDoBloco,
    carregarAtiva,
    carregarPeriodo,
    recarregarLocal,
    iniciarCronometro,
    pausarCronometro,
    retomarCronometro,
    concluirCronometro,
    confirmarBloco,
    criarManual,
    atualizarManual,
    excluirExecucao,
    limpar,
  }
})
