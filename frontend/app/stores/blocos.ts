import { defineStore } from 'pinia'
import type { components } from '~/types/api'

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

export const useBlocosStore = defineStore('blocos', () => {
  const porData = ref<Record<string, BlocoRead[]>>({})
  const modelos = ref<ModeloBlocoRead[]>([])
  const carregando = ref(false)
  const carregandoModelos = ref(false)
  const filaMovimentoPorBloco = new Map<string, Promise<BlocoRead>>()
  const ultimoConfirmadoPorBloco = new Map<string, BlocoRead>()

  function _buscarBlocoNaMemoria(blocoId: string): BlocoRead | undefined {
    for (const lista of Object.values(porData.value)) {
      const encontrado = lista.find(b => b.id === blocoId)
      if (encontrado) return encontrado
    }
    return undefined
  }

  function ordenarBlocos(lista: BlocoRead[]): BlocoRead[] {
    return [...lista].sort((a, b) => a.inicio.localeCompare(b.inicio))
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

  async function carregarPeriodo(deIso: string, ateIso: string): Promise<BlocoRead[]> {
    const { requisitar } = useApi()
    carregando.value = true
    try {
      const lista = await requisitar<BlocoRead[]>(
        `/blocos?de=${encodeURIComponent(deIso)}&ate=${encodeURIComponent(ateIso)}`,
      )
      const agrupado: Record<string, BlocoRead[]> = { ...porData.value }

      // Inicializa os dias consultados vazios para limpar blocos excluídos no servidor
      let cursor = deIso
      while (cursor <= ateIso) {
        agrupado[cursor] = []
        const [a = 2026, m = 1, d = 1] = cursor.split('-').map(Number)
        const dt = new Date(Date.UTC(a, m - 1, d + 1, 12, 0, 0))
        cursor = `${dt.getUTCFullYear()}-${String(dt.getUTCMonth() + 1).padStart(2, '0')}-${String(dt.getUTCDate()).padStart(2, '0')}`
      }

      for (const b of lista) {
        const atual = agrupado[b.data_local] ?? []
        atual.push(b)
        agrupado[b.data_local] = ordenarBlocos(atual)
      }
      porData.value = agrupado
      return lista
    }
    finally {
      carregando.value = false
    }
  }

  async function criarBloco(dados: BlocoCreate): Promise<BlocoRead> {
    const { requisitar } = useApi()
    const criado = await requisitar<BlocoRead>('/blocos', {
      method: 'POST',
      body: dados as unknown as Record<string, unknown>,
    })
    _inserirOuAtualizarNaMemoria(criado)
    return criado
  }

  async function atualizarBloco(
    blocoId: string,
    dados: BlocoUpdate,
    versaoEsperada?: number,
  ): Promise<BlocoRead> {
    const { requisitar } = useApi()
    const headers: Record<string, string> = {}
    if (versaoEsperada != null) {
      headers['If-Match'] = String(versaoEsperada)
    }
    const atualizado = await requisitar<BlocoRead>(`/blocos/${blocoId}`, {
      method: 'PATCH',
      headers,
      body: dados as unknown as Record<string, unknown>,
    })
    _inserirOuAtualizarNaMemoria(atualizado)
    return atualizado
  }

  /**
   * Atualiza otimisticamente o horário de um bloco durante/após arrasto na régua
   * e faz rollback automático caso a API retorne erro (ex.: 409 Conflict).
   * Chamadas concorrentes para o mesmo bloco são serializadas para evitar If-Match obsoleto.
   */
  async function moverOuRedimensionarOtimista(
    blocoOriginal: BlocoRead,
    novoInicioIso: string,
    novoFimIso: string,
  ): Promise<BlocoRead> {
    if (!ultimoConfirmadoPorBloco.has(blocoOriginal.id)) {
      ultimoConfirmadoPorBloco.set(blocoOriginal.id, blocoOriginal)
    }

    const baseReferencia = _buscarBlocoNaMemoria(blocoOriginal.id) ?? blocoOriginal
    const duracaoAntigaMs = new Date(baseReferencia.fim).getTime() - new Date(baseReferencia.inicio).getTime()
    const duracaoNovaMs = new Date(novoFimIso).getTime() - new Date(novoInicioIso).getTime()
    const deltaInicioMs = new Date(novoInicioIso).getTime() - new Date(baseReferencia.inicio).getTime()

    const novasPausas = baseReferencia.pausas_planejadas
      .map((p) => {
        if (Math.abs(duracaoNovaMs - duracaoAntigaMs) < 1000) {
          return {
            id: p.id,
            inicio: new Date(new Date(p.inicio).getTime() + deltaInicioMs).toISOString(),
            fim: new Date(new Date(p.fim).getTime() + deltaInicioMs).toISOString(),
          }
        }
        return {
          id: p.id,
          inicio: p.inicio,
          fim: p.fim,
        }
      })
      .filter(
        p => new Date(p.inicio).getTime() >= new Date(novoInicioIso).getTime()
          && new Date(p.fim).getTime() <= new Date(novoFimIso).getTime(),
      )

    const otimista: BlocoRead = {
      ...baseReferencia,
      inicio: novoInicioIso,
      fim: novoFimIso,
      pausas_planejadas: novasPausas.map(p => ({
        id: p.id,
        bloco_id: baseReferencia.id,
        inicio: p.inicio,
        fim: p.fim,
      })),
    }
    _inserirOuAtualizarNaMemoria(otimista)

    const anterior = filaMovimentoPorBloco.get(blocoOriginal.id) ?? Promise.resolve(blocoOriginal)
    const tarefa = anterior
      .catch(() => ultimoConfirmadoPorBloco.get(blocoOriginal.id) ?? blocoOriginal)
      .then(async () => {
        const confirmado = ultimoConfirmadoPorBloco.get(blocoOriginal.id) ?? blocoOriginal
        try {
          const salvo = await atualizarBloco(
            blocoOriginal.id,
            {
              inicio: novoInicioIso,
              fim: novoFimIso,
              pausas: novasPausas,
            },
            confirmado.versao,
          )
          ultimoConfirmadoPorBloco.set(blocoOriginal.id, salvo)
          return salvo
        }
        catch (erro) {
          const restaurar = ultimoConfirmadoPorBloco.get(blocoOriginal.id) ?? blocoOriginal
          _inserirOuAtualizarNaMemoria(restaurar)
          throw erro
        }
      })

    filaMovimentoPorBloco.set(blocoOriginal.id, tarefa)
    try {
      return await tarefa
    }
    finally {
      if (filaMovimentoPorBloco.get(blocoOriginal.id) === tarefa) {
        filaMovimentoPorBloco.delete(blocoOriginal.id)
        ultimoConfirmadoPorBloco.delete(blocoOriginal.id)
      }
    }
  }

  async function excluirBloco(blocoId: string): Promise<void> {
    const { requisitar } = useApi()
    await requisitar(`/blocos/${blocoId}`, { method: 'DELETE' })
    _removerDaMemoria(blocoId)
  }

  async function carregarModelos(): Promise<ModeloBlocoRead[]> {
    const { requisitar } = useApi()
    carregandoModelos.value = true
    try {
      const lista = await requisitar<ModeloBlocoRead[]>('/modelos-bloco')
      modelos.value = lista
      return lista
    }
    finally {
      carregandoModelos.value = false
    }
  }

  async function criarModelo(dados: ModeloBlocoCreate): Promise<ModeloBlocoRead> {
    const { requisitar } = useApi()
    const criado = await requisitar<ModeloBlocoRead>('/modelos-bloco', {
      method: 'POST',
      body: dados as unknown as Record<string, unknown>,
    })
    modelos.value = [...modelos.value, criado].sort(
      (a, b) => a.dia_semana - b.dia_semana || a.hora_inicio.localeCompare(b.hora_inicio),
    )
    return criado
  }

  async function atualizarModelo(
    modeloId: string,
    dados: ModeloBlocoUpdate,
  ): Promise<ModeloBlocoRead> {
    const { requisitar } = useApi()
    const atualizado = await requisitar<ModeloBlocoRead>(`/modelos-bloco/${modeloId}`, {
      method: 'PATCH',
      body: dados as unknown as Record<string, unknown>,
    })
    modelos.value = modelos.value
      .map(m => (m.id === modeloId ? atualizado : m))
      .sort((a, b) => a.dia_semana - b.dia_semana || a.hora_inicio.localeCompare(b.hora_inicio))
    return atualizado
  }

  async function excluirModelo(modeloId: string): Promise<void> {
    const { requisitar } = useApi()
    await requisitar(`/modelos-bloco/${modeloId}`, { method: 'DELETE' })
    modelos.value = modelos.value.filter(m => m.id !== modeloId)
  }

  async function aplicarModeloNaSemana(inicioSemanaIso: string): Promise<BlocoRead[]> {
    const { requisitar } = useApi()
    const materializados = await requisitar<BlocoRead[]>(
      `/semanas/${encodeURIComponent(inicioSemanaIso)}/aplicar-modelo`,
      { method: 'POST' },
    )
    for (const b of materializados) {
      _inserirOuAtualizarNaMemoria(b)
    }
    return materializados
  }

  function limpar() {
    porData.value = {}
    modelos.value = []
  }

  return {
    porData,
    modelos,
    carregando,
    carregandoModelos,
    blocosDoDia,
    carregarPeriodo,
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
