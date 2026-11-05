import { defineStore } from 'pinia'
import type { components } from '~/types/api'

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
  if (fimEfetivoMs <= inicioMs) return 0

  let totalPausasMs = 0
  for (const p of execucao.pausas) {
    const pIni = Math.max(inicioMs, new Date(p.inicio).getTime())
    const pFim = Math.min(
      fimEfetivoMs,
      p.fim ? new Date(p.fim).getTime() : agoraMs,
    )
    if (pFim > pIni) {
      totalPausasMs += pFim - pIni
    }
  }

  return Math.max(0, Math.floor((fimEfetivoMs - inicioMs - totalPausasMs) / 1000))
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

    if (execucao.status === 'em_andamento' && execucao.fim == null) {
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
    const aberta = lista.find(e => e.status === 'em_andamento' && e.fim == null)
    if (aberta) return aberta
    return lista[lista.length - 1]
  }

  async function carregarAtiva(): Promise<ExecucaoRead | null> {
    const { requisitar } = useApi()
    const resposta = await requisitar<ExecucaoRead | null>('/execucoes/ativa')
    ativa.value = resposta
    if (resposta) {
      _inserirOuAtualizarNaMemoria(resposta)
    }
    return resposta
  }

  async function carregarPeriodo(deIso: string, ateIso: string): Promise<ExecucaoRead[]> {
    const { requisitar } = useApi()
    carregando.value = true
    try {
      const [lista, execAtiva] = await Promise.all([
        requisitar<ExecucaoRead[]>(
          `/execucoes?de=${encodeURIComponent(deIso)}&ate=${encodeURIComponent(ateIso)}`,
        ),
        requisitar<ExecucaoRead | null>('/execucoes/ativa'),
      ])
      ultimoRangeCarregado.value = { de: deIso, ate: ateIso }
      ativa.value = execAtiva
      const combinada = [...lista]
      if (execAtiva && !combinada.some(e => e.id === execAtiva.id)) {
        combinada.push(execAtiva)
      }
      itens.value = _ordenar(combinada)
      return itens.value
    }
    finally {
      carregando.value = false
    }
  }

  async function iniciarCronometro(dados: ExecucaoIniciarRequest): Promise<ExecucaoRead> {
    const { requisitar } = useApi()
    const idAnteriorAtiva = ativa.value?.id
    const iniciada = await requisitar<ExecucaoRead>('/execucoes/iniciar', {
      method: 'POST',
      body: dados as unknown as Record<string, unknown>,
    })

    // Se havia outra execução aberta que o servidor encerrou automaticamente,
    // recarrega seus dados atualizados para refletir os segundos líquidos na lista
    if (idAnteriorAtiva && idAnteriorAtiva !== iniciada.id) {
      try {
        const encerrada = await requisitar<ExecucaoRead>(`/execucoes/${idAnteriorAtiva}`)
        _inserirOuAtualizarNaMemoria(encerrada)
      }
      catch {
        // Ignora caso não encontrada
      }
    }

    _inserirOuAtualizarNaMemoria(iniciada)
    return iniciada
  }

  async function pausarCronometro(execucaoId: string): Promise<ExecucaoRead> {
    const { requisitar } = useApi()
    const pausada = await requisitar<ExecucaoRead>(`/execucoes/${execucaoId}/pausar`, {
      method: 'POST',
      body: {},
    })
    _inserirOuAtualizarNaMemoria(pausada)
    return pausada
  }

  async function retomarCronometro(execucaoId: string): Promise<ExecucaoRead> {
    const { requisitar } = useApi()
    const retomada = await requisitar<ExecucaoRead>(`/execucoes/${execucaoId}/retomar`, {
      method: 'POST',
      body: {},
    })
    _inserirOuAtualizarNaMemoria(retomada)
    return retomada
  }

  async function concluirCronometro(
    execucaoId: string,
    statusFinal: 'concluida' | 'parcial' = 'concluida',
  ): Promise<ExecucaoRead> {
    const { requisitar } = useApi()
    const concluida = await requisitar<ExecucaoRead>(`/execucoes/${execucaoId}/concluir`, {
      method: 'POST',
      body: { status: statusFinal },
    })
    _inserirOuAtualizarNaMemoria(concluida)
    return concluida
  }

  async function confirmarBloco(
    blocoId: string,
    statusConfirmacao: 'concluida' | 'parcial' | 'pulada' = 'concluida',
  ): Promise<ExecucaoRead> {
    const { requisitar } = useApi()
    const confirmada = await requisitar<ExecucaoRead>('/execucoes/confirmar-bloco', {
      method: 'POST',
      body: {
        bloco_id: blocoId,
        status: statusConfirmacao,
      },
    })
    if (ativa.value?.bloco_id === blocoId) {
      ativa.value = null
    }
    _inserirOuAtualizarNaMemoria(confirmada)
    return confirmada
  }

  async function criarManual(dados: ExecucaoCreate): Promise<ExecucaoRead> {
    const { requisitar } = useApi()
    const criada = await requisitar<ExecucaoRead>('/execucoes', {
      method: 'POST',
      body: dados as unknown as Record<string, unknown>,
    })
    _inserirOuAtualizarNaMemoria(criada)
    return criada
  }

  async function atualizarManual(
    execucaoId: string,
    dados: ExecucaoUpdate,
  ): Promise<ExecucaoRead> {
    const { requisitar } = useApi()
    const atualizada = await requisitar<ExecucaoRead>(`/execucoes/${execucaoId}`, {
      method: 'PATCH',
      body: dados as unknown as Record<string, unknown>,
    })
    _inserirOuAtualizarNaMemoria(atualizada)
    return atualizada
  }

  async function excluirExecucao(execucaoId: string): Promise<void> {
    const { requisitar } = useApi()
    await requisitar(`/execucoes/${execucaoId}`, { method: 'DELETE' })
    _removerDaMemoria(execucaoId)
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
