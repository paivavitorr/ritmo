import { defineStore } from 'pinia'
import type { components } from '~/types/api'
import { dbLocal, segundosLiquidosEntre } from '~/utils/dbLocal'
import { novoId } from '~/utils/id'
import { dataIsoNoFuso } from '~/utils/tempo'

export type BlocoRead = components['schemas']['BlocoRead']
export type TipoBloco = components['schemas']['BlocoCreate']['tipo']
export type BlocoCreate = Omit<
  components['schemas']['BlocoCreate'],
  'tipo' | 'pausas'
> & {
  tipo?: TipoBloco
  pausas?: components['schemas']['PausaPlanejadaInput'][]
}
export type BlocoUpdate = components['schemas']['BlocoUpdate']
export type ModeloBlocoRead = components['schemas']['ModeloBlocoRead']
export type ModeloBlocoCreate = Omit<
  components['schemas']['ModeloBlocoCreate'],
  'pausas' | 'lembretes' | 'ativo'
> & {
  pausas?: components['schemas']['PausaModeloSchema'][]
  lembretes?: number[]
  ativo?: boolean
}
export type ModeloBlocoUpdate = components['schemas']['ModeloBlocoUpdate']

function fusoDoUsuario(): string {
  return useAuthStore().usuario?.fuso ?? Intl.DateTimeFormat().resolvedOptions().timeZone
}

function ordenarModelos(lista: ModeloBlocoRead[]): ModeloBlocoRead[] {
  return [...lista].sort((a, b) => a.dia_semana - b.dia_semana || a.hora_inicio.localeCompare(b.hora_inicio))
}

function ordenarBlocos(lista: BlocoRead[]): BlocoRead[] {
  return [...lista].sort((a, b) => a.inicio.localeCompare(b.inicio))
}

export const useBlocosStore = defineStore('blocos', () => {
  const porData = ref<Record<string, BlocoRead[]>>({})
  const modelos = ref<ModeloBlocoRead[]>([])
  const carregando = ref(false)
  const carregandoModelos = ref(false)
  let ultimoPeriodo: { de: string, ate: string } | null = null

  function _buscarBlocoNaMemoria(blocoId: string): BlocoRead | undefined {
    for (const lista of Object.values(porData.value)) {
      const encontrado = lista.find(b => b.id === blocoId)
      if (encontrado) return encontrado
    }
    return undefined
  }

  function blocosDoDia(dataIso: string): BlocoRead[] {
    return porData.value[dataIso] ?? []
  }

  function _inserirOuAtualizarNaMemoria(bloco: BlocoRead) {
    // Remove o bloco de qualquer data anterior (caso tenha mudado de data_local)
    const novoMapa: Record<string, BlocoRead[]> = {}
    for (const [dataKey, lista] of Object.entries(porData.value)) {
      novoMapa[dataKey] = lista.filter(b => b.id !== bloco.id)
    }
    const listaAlvo = novoMapa[bloco.data_local] ?? []
    novoMapa[bloco.data_local] = ordenarBlocos([...listaAlvo, bloco])
    porData.value = novoMapa
  }

  function _removerDaMemoria(blocoId: string) {
    const novoMapa: Record<string, BlocoRead[]> = {}
    for (const [dataKey, lista] of Object.entries(porData.value)) {
      novoMapa[dataKey] = lista.filter(b => b.id !== blocoId)
    }
    porData.value = novoMapa
  }

  /** Substitui na memória apenas os dias do intervalo, com o que está no Dexie (sem zerar antes). */
  async function lerPeriodoLocal(deIso: string, ateIso: string): Promise<BlocoRead[]> {
    const lista = await dbLocal.blocos
      .where('data_local')
      .between(deIso, ateIso, true, true)
      .toArray()
    const mapa: Record<string, BlocoRead[]> = {}
    for (const [dia, blocos] of Object.entries(porData.value)) {
      if (dia < deIso || dia > ateIso) mapa[dia] = blocos
    }
    for (const b of lista) {
      mapa[b.data_local] = [...(mapa[b.data_local] ?? []), b]
    }
    for (const dia of Object.keys(mapa)) {
      mapa[dia] = ordenarBlocos(mapa[dia] ?? [])
    }
    porData.value = mapa
    return lista
  }

  async function recarregarLocal() {
    if (ultimoPeriodo) await lerPeriodoLocal(ultimoPeriodo.de, ultimoPeriodo.ate)
    modelos.value = ordenarModelos(await dbLocal.modelos_bloco.toArray())
  }

  async function carregarPeriodo(deIso: string, ateIso: string): Promise<BlocoRead[]> {
    carregando.value = true
    try {
      ultimoPeriodo = { de: deIso, ate: ateIso }
      let lista = await lerPeriodoLocal(deIso, ateIso)
      carregando.value = false
      if (await useSyncStore().puxarMudancas()) {
        lista = await lerPeriodoLocal(deIso, ateIso)
      }
      return lista
    }
    finally {
      carregando.value = false
    }
  }

  function _mapearPausas(
    blocoId: string,
    pausas: components['schemas']['PausaPlanejadaInput'][],
  ): BlocoRead['pausas_planejadas'] {
    return pausas.map(p => ({
      id: p.id ?? novoId(),
      bloco_id: blocoId,
      inicio: p.inicio,
      fim: p.fim,
    }))
  }

  async function criarBloco(dados: BlocoCreate): Promise<BlocoRead> {
    const id = dados.id ?? novoId()
    const agora = new Date().toISOString()
    const pausas = _mapearPausas(id, dados.pausas ?? [])
    const bloco: BlocoRead = {
      id,
      usuario_id: useAuthStore().usuario?.id ?? '',
      categoria_id: dados.categoria_id,
      modelo_bloco_id: null,
      tipo: dados.tipo ?? 'rotina',
      titulo: dados.titulo,
      notas: dados.notas ?? null,
      data_local: dados.data_local ?? dataIsoNoFuso(new Date(dados.inicio), fusoDoUsuario()),
      inicio: dados.inicio,
      fim: dados.fim,
      desvinculado: false,
      pausas_planejadas: pausas,
      segundos_liquidos_planejados: segundosLiquidosEntre(dados.inicio, dados.fim, pausas),
      versao: 0,
      criado_em: agora,
      atualizado_em: agora,
    }
    await dbLocal.blocos.put(bloco)
    _inserirOuAtualizarNaMemoria(bloco)
    await useSyncStore().enfileirarMutacao('bloco', 'criar', id, {
      id,
      categoria_id: bloco.categoria_id,
      tipo: bloco.tipo,
      titulo: bloco.titulo,
      notas: bloco.notas,
      data_local: bloco.data_local,
      inicio: bloco.inicio,
      fim: bloco.fim,
      pausas: pausas.map(p => ({ id: p.id, inicio: p.inicio, fim: p.fim })),
    })
    return bloco
  }

  async function atualizarBloco(
    blocoId: string,
    dados: BlocoUpdate,
    versaoEsperada?: number,
  ): Promise<BlocoRead> {
    const base = _buscarBlocoNaMemoria(blocoId) ?? await dbLocal.blocos.get(blocoId)
    if (!base) throw new Error('Bloco não encontrado.')

    const inicio = dados.inicio ?? base.inicio
    const fim = dados.fim ?? base.fim
    const payload: Record<string, unknown> = { ...dados }
    let dataLocal = dados.data_local ?? base.data_local
    if (dados.inicio && !dados.data_local) {
      dataLocal = dataIsoNoFuso(new Date(inicio), fusoDoUsuario())
      payload.data_local = dataLocal
    }
    const pausas = dados.pausas ? _mapearPausas(blocoId, dados.pausas) : base.pausas_planejadas
    if (dados.pausas) payload.pausas = pausas.map(p => ({ id: p.id, inicio: p.inicio, fim: p.fim }))

    const atualizado: BlocoRead = {
      ...base,
      categoria_id: dados.categoria_id ?? base.categoria_id,
      tipo: dados.tipo ?? base.tipo,
      titulo: dados.titulo ?? base.titulo,
      notas: dados.notas === undefined ? base.notas : dados.notas,
      data_local: dataLocal,
      inicio,
      fim,
      pausas_planejadas: pausas,
      segundos_liquidos_planejados: segundosLiquidosEntre(inicio, fim, pausas),
      atualizado_em: new Date().toISOString(),
    }
    await dbLocal.blocos.put(atualizado)
    _inserirOuAtualizarNaMemoria(atualizado)
    await useSyncStore().enfileirarMutacao(
      'bloco',
      'atualizar',
      blocoId,
      payload,
      versaoEsperada ?? base.versao,
    )
    return atualizado
  }

  /**
   * Atualiza o horário de um bloco durante/após arrasto na régua. A mudança é local e imediata;
   * o servidor recebe via outbox e, em caso de conflito, o estado dele volta para a tela.
   */
  async function moverOuRedimensionarOtimista(
    blocoOriginal: BlocoRead,
    novoInicioIso: string,
    novoFimIso: string,
  ): Promise<BlocoRead> {
    const baseReferencia = _buscarBlocoNaMemoria(blocoOriginal.id) ?? blocoOriginal
    const duracaoAntigaMs = new Date(baseReferencia.fim).getTime() - new Date(baseReferencia.inicio).getTime()
    const duracaoNovaMs = new Date(novoFimIso).getTime() - new Date(novoInicioIso).getTime()
    const deltaInicioMs = new Date(novoInicioIso).getTime() - new Date(baseReferencia.inicio).getTime()
    const apenasMoveu = Math.abs(duracaoNovaMs - duracaoAntigaMs) < 1000

    const novasPausas = baseReferencia.pausas_planejadas
      .map(p => apenasMoveu
        ? {
            id: p.id,
            inicio: new Date(new Date(p.inicio).getTime() + deltaInicioMs).toISOString(),
            fim: new Date(new Date(p.fim).getTime() + deltaInicioMs).toISOString(),
          }
        : { id: p.id, inicio: p.inicio, fim: p.fim })
      .filter(
        p => new Date(p.inicio).getTime() >= new Date(novoInicioIso).getTime()
          && new Date(p.fim).getTime() <= new Date(novoFimIso).getTime(),
      )

    return await atualizarBloco(
      blocoOriginal.id,
      { inicio: novoInicioIso, fim: novoFimIso, pausas: novasPausas },
      baseReferencia.versao,
    )
  }

  async function excluirBloco(blocoId: string): Promise<void> {
    const base = _buscarBlocoNaMemoria(blocoId) ?? await dbLocal.blocos.get(blocoId)
    await dbLocal.blocos.delete(blocoId)
    _removerDaMemoria(blocoId)
    await useSyncStore().enfileirarMutacao('bloco', 'excluir', blocoId, {}, base?.versao ?? null)
  }

  async function carregarModelos(): Promise<ModeloBlocoRead[]> {
    carregandoModelos.value = true
    try {
      modelos.value = ordenarModelos(await dbLocal.modelos_bloco.toArray())
      carregandoModelos.value = false
      if (await useSyncStore().puxarMudancas()) {
        modelos.value = ordenarModelos(await dbLocal.modelos_bloco.toArray())
      }
      return modelos.value
    }
    finally {
      carregandoModelos.value = false
    }
  }

  async function criarModelo(dados: ModeloBlocoCreate): Promise<ModeloBlocoRead> {
    const id = (dados as { id?: string | null }).id ?? novoId()
    const agora = new Date().toISOString()
    const criado: ModeloBlocoRead = {
      id,
      usuario_id: useAuthStore().usuario?.id ?? '',
      categoria_id: dados.categoria_id,
      titulo: dados.titulo,
      dia_semana: dados.dia_semana,
      hora_inicio: dados.hora_inicio,
      hora_fim: dados.hora_fim,
      pausas: dados.pausas ?? [],
      lembretes: dados.lembretes ?? [],
      ativo: dados.ativo ?? true,
      versao: 0,
      criado_em: agora,
      atualizado_em: agora,
    }
    await dbLocal.modelos_bloco.put(criado)
    modelos.value = ordenarModelos([...modelos.value, criado])
    await useSyncStore().enfileirarMutacao('modelo_bloco', 'criar', id, {
      id,
      categoria_id: criado.categoria_id,
      titulo: criado.titulo,
      dia_semana: criado.dia_semana,
      hora_inicio: criado.hora_inicio,
      hora_fim: criado.hora_fim,
      pausas: criado.pausas,
      lembretes: criado.lembretes,
      ativo: criado.ativo,
    })
    return criado
  }

  async function atualizarModelo(
    modeloId: string,
    dados: ModeloBlocoUpdate,
  ): Promise<ModeloBlocoRead> {
    const base = modelos.value.find(m => m.id === modeloId) ?? await dbLocal.modelos_bloco.get(modeloId)
    if (!base) throw new Error('Modelo não encontrado.')
    const atualizado: ModeloBlocoRead = {
      ...base,
      ...Object.fromEntries(Object.entries(dados).filter(([, v]) => v !== undefined && v !== null)),
      atualizado_em: new Date().toISOString(),
    }
    await dbLocal.modelos_bloco.put(atualizado)
    modelos.value = ordenarModelos(modelos.value.map(m => (m.id === modeloId ? atualizado : m)))
    await useSyncStore().enfileirarMutacao(
      'modelo_bloco',
      'atualizar',
      modeloId,
      dados as Record<string, unknown>,
      base.versao,
    )
    return atualizado
  }

  async function excluirModelo(modeloId: string): Promise<void> {
    const base = modelos.value.find(m => m.id === modeloId) ?? await dbLocal.modelos_bloco.get(modeloId)
    await dbLocal.modelos_bloco.delete(modeloId)
    modelos.value = modelos.value.filter(m => m.id !== modeloId)
    await useSyncStore().enfileirarMutacao('modelo_bloco', 'excluir', modeloId, {}, base?.versao ?? null)
  }

  /** Materialização é feita pelo servidor: exige conexão. */
  async function aplicarModeloNaSemana(inicioSemanaIso: string): Promise<BlocoRead[]> {
    const { requisitar } = useApi()
    const materializados = await requisitar<BlocoRead[]>(
      `/semanas/${encodeURIComponent(inicioSemanaIso)}/aplicar-modelo`,
      { method: 'POST' },
    )
    await dbLocal.blocos.bulkPut(materializados)
    for (const b of materializados) {
      _inserirOuAtualizarNaMemoria(b)
    }
    return materializados
  }

  function limpar() {
    porData.value = {}
    modelos.value = []
    ultimoPeriodo = null
  }

  return {
    porData,
    modelos,
    carregando,
    carregandoModelos,
    blocosDoDia,
    carregarPeriodo,
    recarregarLocal,
    criarBloco,
    atualizarBloco,
    moverOuRedimensionarOtimista,
    excluirBloco,
    carregarModelos,
    criarModelo,
    atualizarModelo,
    excluirModelo,
    aplicarModeloNaSemana,
    limpar,
  }
})
