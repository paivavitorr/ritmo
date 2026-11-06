<script setup lang="ts">
import { calcularNovosLimites, useArrasto, type ModoArrasto } from '~/composables/useArrasto'
import type { BlocoRead } from '~/stores/blocos'
import type { CategoriaRead } from '~/stores/categorias'
import { calcularSegundosLiquidosAoVivo, type ExecucaoRead } from '~/stores/execucoes'
import { calcularLayoutSobreposicao } from '~/utils/horasLiquidas'
import {
  arredondarParaStep,
  criarTimestampUtcDeMinutosLocais,
  minutosDesdeMeiaNoiteNoFuso,
} from '~/utils/tempo'

interface Props {
  dataIso: string
  fuso: string
  blocos: BlocoRead[]
  categoriasPorId: Map<string, CategoriaRead>
  execucoesPorBlocoId?: Map<string, ExecucaoRead[]>
  blocosOcupados?: Set<string>
}

const props = withDefaults(defineProps<Props>(), {
  execucoesPorBlocoId: () => new Map(),
  blocosOcupados: () => new Set(),
})

const emit = defineEmits<{
  criarEmMinuto: [inicioMin: number]
  selecionarBloco: [bloco: BlocoRead]
  moverOuRedimensionar: [bloco: BlocoRead, novoInicioIso: string, novoFimIso: string]
  alternarConfirmacao: [bloco: BlocoRead]
  iniciarCronometro: [bloco: BlocoRead]
}>()

const larguraJanela = ref(1024)
const agoraMs = ref(Date.now())
let timerRelogio: ReturnType<typeof setInterval> | null = null
const containerScroll = ref<HTMLElement | null>(null)
const areaBlocos = ref<HTMLElement | null>(null)

function execucaoPrincipal(blocoId: string): ExecucaoRead | undefined {
  const lista = props.execucoesPorBlocoId.get(blocoId)
  if (!lista || !lista.length) return undefined
  const aberta = lista.find(e => e.status === 'em_andamento' && e.fim == null)
  if (aberta) return aberta
  return lista[lista.length - 1]
}

function percentualExecutadoDoBloco(bloco: BlocoRead): number {
  const lista = props.execucoesPorBlocoId.get(bloco.id)
  if (!lista || !lista.length || bloco.segundos_liquidos_planejados <= 0) return 0
  let totalSegundos = 0
  for (const e of lista) {
    if (e.status === 'pulada') continue
    if (e.status === 'em_andamento' && e.fim == null) {
      totalSegundos += calcularSegundosLiquidosAoVivo(e, agoraMs.value)
    }
    else {
      totalSegundos += e.segundos_liquidos
    }
  }
  return Math.min(100, Math.round((totalSegundos / bloco.segundos_liquidos_planejados) * 100))
}

const pxPorMinuto = computed(() => (larguraJanela.value >= 1024 ? 1.4 : 1.1))

function atualizarLargura() {
  larguraJanela.value = window.innerWidth
}

const blocosComMinutos = computed(() =>
  props.blocos.map((b) => {
    // Sem clamp: blocos que cruzam a meia-noite mantêm os limites reais (<0 ou >1440).
    const inicioMin = minutosDesdeMeiaNoiteNoFuso(b.inicio, props.dataIso, props.fuso)
    const fimMin = minutosDesdeMeiaNoiteNoFuso(b.fim, props.dataIso, props.fuso)
    return {
      bloco: b,
      inicioMin,
      fimMin,
    }
  }),
)

const { ativo: arrastoAtivo, iniciarPointer } = useArrasto({
  pxPorMinuto,
  stepMinutos: 15,
  duracaoMinimaMin: 15,
  aoConcluir: async (blocoId, novoInicioMin, novoFimMin) => {
    const item = blocosComMinutos.value.find(x => x.bloco.id === blocoId)
    if (!item) return
    const novoIniIso = criarTimestampUtcDeMinutosLocais(
      props.dataIso,
      novoInicioMin,
      props.fuso,
    )
    const novoFimIso = criarTimestampUtcDeMinutosLocais(
      props.dataIso,
      novoFimMin,
      props.fuso,
    )
    emit('moverOuRedimensionar', item.bloco, novoIniIso, novoFimIso)
  },
})

const mapaLayout = computed(() =>
  calcularLayoutSobreposicao(
    blocosComMinutos.value.map(item => ({
      id: item.bloco.id,
      inicioMin:
        arrastoAtivo.value?.blocoId === item.bloco.id
          ? arrastoAtivo.value.inicioMinAtual
          : item.inicioMin,
      fimMin:
        arrastoAtivo.value?.blocoId === item.bloco.id
          ? arrastoAtivo.value.fimMinAtual
          : item.fimMin,
    })),
  ),
)

function inicioMinParaRender(item: (typeof blocosComMinutos.value)[number]): number {
  if (arrastoAtivo.value?.blocoId === item.bloco.id) {
    return arrastoAtivo.value.inicioMinAtual
  }
  return item.inicioMin
}

function fimMinParaRender(item: (typeof blocosComMinutos.value)[number]): number {
  if (arrastoAtivo.value?.blocoId === item.bloco.id) {
    return arrastoAtivo.value.fimMinAtual
  }
  return item.fimMin
}

function aoIniciarPointerNoBloco(
  ev: PointerEvent,
  item: (typeof blocosComMinutos.value)[number],
  modo: ModoArrasto,
) {
  iniciarPointer(ev, item.bloco.id, modo, item.inicioMin, item.fimMin)
}

function aoMoverPorTeclado(
  item: (typeof blocosComMinutos.value)[number],
  deltaIni: number,
  deltaFim: number,
) {
  const modo: ModoArrasto
    = deltaIni !== 0 && deltaIni === deltaFim
      ? 'mover'
      : deltaIni !== 0 ? 'redimensionar-topo' : 'redimensionar-base'
  const { inicioMin, fimMin } = calcularNovosLimites(
    modo,
    item.inicioMin,
    item.fimMin,
    deltaIni !== 0 ? deltaIni : deltaFim,
    { step: 15, duracaoMinimaMin: 15 },
  )
  if (inicioMin === item.inicioMin && fimMin === item.fimMin) return

  emit(
    'moverOuRedimensionar',
    item.bloco,
    criarTimestampUtcDeMinutosLocais(props.dataIso, inicioMin, props.fuso),
    criarTimestampUtcDeMinutosLocais(props.dataIso, fimMin, props.fuso),
  )
}

function aoClicarFundoRegua(evento: MouseEvent) {
  if (!areaBlocos.value) return
  const rect = areaBlocos.value.getBoundingClientRect()
  const y = evento.clientY - rect.top
  const minBruto = y / pxPorMinuto.value
  const inicioSnap = Math.max(0, Math.min(1380, arredondarParaStep(minBruto, 15)))
  emit('criarEmMinuto', inicioSnap)
}

onMounted(() => {
  atualizarLargura()
  window.addEventListener('resize', atualizarLargura)
  timerRelogio = setInterval(() => {
    agoraMs.value = Date.now()
  }, 5000)

  // Posiciona o scroll inicial próximo ao horário atual (ou 07:00)
  nextTick(() => {
    if (!containerScroll.value) return
    const minAgora = minutosDesdeMeiaNoiteNoFuso(
      new Date().toISOString(),
      props.dataIso,
      props.fuso,
    )
    const minAlvo = minAgora >= 0 && minAgora <= 1440 ? Math.max(0, minAgora - 90) : 420
    containerScroll.value.scrollTop = minAlvo * pxPorMinuto.value
  })
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', atualizarLargura)
  if (timerRelogio) clearInterval(timerRelogio)
})
</script>

<template>
  <div
    ref="containerScroll"
    class="relative max-h-[72dvh] overflow-y-auto rounded-[var(--radius-bloco)] border border-linha bg-papel px-2 py-4 sm:px-4"
  >
    <div
      class="relative"
      :style="{ height: `${1440 * pxPorMinuto}px` }"
    >
      <TimelineRegua :px-por-minuto="pxPorMinuto" />
      <LinhaAgora
        :data-iso="props.dataIso"
        :fuso="props.fuso"
        :px-por-minuto="pxPorMinuto"
      />

      <!-- Coluna interativa de blocos (à direita dos rótulos de hora) -->
      <div
        ref="areaBlocos"
        class="absolute inset-y-0 left-14 right-1 cursor-crosshair"
        @click="aoClicarFundoRegua"
      >
        <TimelineBloco
          v-for="item in blocosComMinutos"
          :key="item.bloco.id"
          :bloco="item.bloco"
          :categoria="props.categoriasPorId.get(item.bloco.categoria_id)"
          :data-iso="props.dataIso"
          :fuso="props.fuso"
          :px-por-minuto="pxPorMinuto"
          :layout="
            mapaLayout.get(item.bloco.id) ?? {
              id: item.bloco.id,
              inicioMin: item.inicioMin,
              fimMin: item.fimMin,
              coluna: 0,
              totalColunas: 1,
            }
          "
          :inicio-min-exibido="inicioMinParaRender(item)"
          :fim-min-exibido="fimMinParaRender(item)"
          :em-arrasto="arrastoAtivo?.blocoId === item.bloco.id"
          :percentual-executado="percentualExecutadoDoBloco(item.bloco)"
          :status-execucao="execucaoPrincipal(item.bloco.id)?.status ?? null"
          :ocupado="props.blocosOcupados.has(item.bloco.id)"
          @selecionar="emit('selecionarBloco', $event)"
          @iniciar-pointer="(ev, modo) => aoIniciarPointerNoBloco(ev, item, modo)"
          @mover-teclado="(dIni, dFim) => aoMoverPorTeclado(item, dIni, dFim)"
          @alternar-confirmacao="emit('alternarConfirmacao', $event)"
          @iniciar-cronometro="emit('iniciarCronometro', $event)"
        />
      </div>
    </div>
  </div>
</template>
