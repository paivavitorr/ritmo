import type { PausaEditavel } from '~/components/bloco/PausasEditor.vue'
import type { BlocoRead } from '~/stores/blocos'
import type { CategoriaRead } from '~/stores/categorias'
import type { PausaIso } from '~/utils/pausas'
import { calcularMinutosLiquidos } from '~/utils/horasLiquidas'
import {
  intervaloParaPausaIso,
  intervaloParaPausaModelo,
  pausaHoraParaIntervalo,
  pausasIsoParaHora,
  validarPausa,
} from '~/utils/pausas'
import {
  criarTimestampUtcDeMinutosLocais,
  diaSemanaDeDataIso,
  horaInputParaMinutos,
  minutosDesdeMeiaNoiteNoFuso,
  minutosParaHoraInput,
} from '~/utils/tempo'

export interface EntradaFormularioBloco {
  aberto: boolean
  dataIso: string
  fuso: string
  categorias: CategoriaRead[]
  blocoEditando: BlocoRead | null
  minutoInicialSugerido: number
}

export interface PayloadBloco {
  categoria_id: string
  tipo: 'rotina' | 'compromisso'
  titulo: string
  notas: string | null
  data_local: string
  inicio: string
  fim: string
  pausas: PausaIso[]
}

export type ResultadoPayloadBloco = { erro: string, payload?: undefined } | { erro?: undefined, payload: PayloadBloco }

/** Estado, preenchimento e montagem de payloads do formulário de bloco. */
export function useFormularioBloco(props: Readonly<EntradaFormularioBloco>) {
  const titulo = ref('')
  const categoriaId = ref('')
  const tipo = ref<'rotina' | 'compromisso'>('rotina')
  const horaInicio = ref('08:00')
  const horaFim = ref('09:00')
  const notas = ref('')
  const pausas = ref<PausaEditavel[]>([])
  const lembretes = ref<number[]>([10])
  const repetirNaSemana = ref(false)

  const intervaloMinutos = computed(() => {
    const ini = horaInputParaMinutos(horaInicio.value)
    let fim = horaInputParaMinutos(horaFim.value)
    if (fim <= ini) fim += 1440
    return { ini, fim }
  })

  const minutosLiquidosPreview = computed(() => {
    const { ini, fim } = intervaloMinutos.value
    const intervalos = pausas.value
      .map(p => pausaHoraParaIntervalo(p, ini))
      .filter(p => p.fimMin > p.inicioMin)
    return calcularMinutosLiquidos(ini, fim, intervalos)
  })

  function preencher() {
    repetirNaSemana.value = false
    lembretes.value = [10]

    const b = props.blocoEditando
    if (b) {
      titulo.value = b.titulo
      categoriaId.value = b.categoria_id
      tipo.value = b.tipo
      horaInicio.value = minutosParaHoraInput(
        minutosDesdeMeiaNoiteNoFuso(b.inicio, props.dataIso, props.fuso),
      )
      horaFim.value = minutosParaHoraInput(
        minutosDesdeMeiaNoiteNoFuso(b.fim, props.dataIso, props.fuso),
      )
      notas.value = b.notas ?? ''
      pausas.value = pausasIsoParaHora(b.pausas_planejadas, props.dataIso, props.fuso)
      return
    }

    titulo.value = ''
    categoriaId.value = props.categorias[0]?.id ?? ''
    tipo.value = 'rotina'
    const ini = props.minutoInicialSugerido
    horaInicio.value = minutosParaHoraInput(ini)
    horaFim.value = minutosParaHoraInput(Math.min(1440, ini + 60))
    notas.value = ''
    pausas.value = []
  }

  watch(
    () => [props.aberto, props.blocoEditando, props.minutoInicialSugerido],
    ([aberto]) => {
      if (aberto) preencher()
    },
    { immediate: true },
  )

  /** Valida o formulário e devolve o payload de bloco (`erro` preenchido se inválido). */
  function montarPayload(): ResultadoPayloadBloco {
    if (!categoriaId.value) {
      return { erro: 'Selecione uma categoria para o bloco.' }
    }
    const { ini, fim } = intervaloMinutos.value
    if (fim <= ini) {
      return { erro: 'O horário de término deve ser posterior ao início.' }
    }

    const pausasPayload = []
    for (const p of pausas.value) {
      const intervalo = pausaHoraParaIntervalo(p, ini)
      const problema = validarPausa(intervalo, ini, fim)
      if (problema === 'invertida') {
        return { erro: 'O término de cada pausa deve ser posterior ao início da pausa.' }
      }
      if (problema === 'fora') {
        return { erro: 'Todas as pausas devem ficar contidas dentro do horário do bloco.' }
      }
      pausasPayload.push(intervaloParaPausaIso(intervalo, props.dataIso, props.fuso))
    }

    return {
      payload: {
        categoria_id: categoriaId.value,
        tipo: tipo.value,
        titulo: titulo.value.trim(),
        notas: notas.value.trim() || null,
        data_local: props.dataIso,
        inicio: criarTimestampUtcDeMinutosLocais(props.dataIso, ini, props.fuso),
        fim: criarTimestampUtcDeMinutosLocais(props.dataIso, fim, props.fuso),
        pausas: pausasPayload,
      },
    }
  }

  /** Payload do modelo semanal ("repetir toda semana neste dia e horário"). */
  function montarPayloadModelo() {
    const { ini } = intervaloMinutos.value
    return {
      categoria_id: categoriaId.value,
      titulo: titulo.value.trim(),
      dia_semana: diaSemanaDeDataIso(props.dataIso),
      hora_inicio: `${horaInicio.value}:00`,
      hora_fim: `${horaFim.value}:00`,
      pausas: pausas.value.map(p => intervaloParaPausaModelo(pausaHoraParaIntervalo(p, ini), ini)),
      lembretes: lembretes.value,
      ativo: true,
    }
  }

  return {
    titulo,
    categoriaId,
    tipo,
    horaInicio,
    horaFim,
    notas,
    pausas,
    lembretes,
    repetirNaSemana,
    intervaloMinutos,
    minutosLiquidosPreview,
    montarPayload,
    montarPayloadModelo,
  }
}
