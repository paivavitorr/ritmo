<script setup lang="ts">
import { useArrasto, type ModoArrasto } from '~/composables/useArrasto'
import type { BlocoRead } from '~/stores/blocos'
import type { CategoriaRead } from '~/stores/categorias'
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
}

const props = defineProps<Props>()

const emit = defineEmits<{
  criarEmMinuto: [inicioMin: number]
  selecionarBloco: [bloco: BlocoRead]
  moverOuRedimensionar: [bloco: BlocoRead, novoInicioIso: string, novoFimIso: string]
}>()

const larguraJanela = ref(1024)
const containerScroll = ref<HTMLElement | null>(null)
const areaBlocos = ref<HTMLElement | null>(null)

const pxPorMinuto = computed(() => (larguraJanela.value >= 1024 ? 1.4 : 1.1))

function atualizarLargura() {
  larguraJanela.value = window.innerWidth
}

const blocosComMinutos = computed(() =>
  props.blocos.map((b) => {
    const iniBruto = minutosDesdeMeiaNoiteNoFuso(b.inicio, props.dataIso, props.fuso)
    const fimBruto = minutosDesdeMeiaNoiteNoFuso(b.fim, props.dataIso, props.fuso)
    const inicioMin = Math.max(0, Math.min(1425, iniBruto))
    const fimMin = Math.max(inicioMin + 15, fimBruto)
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
  const duracao = item.fimMin - item.inicioMin
  let novoIni = item.inicioMin + deltaIni
  let novoFim = item.fimMin + deltaFim

  if (deltaIni === deltaFim) {
    novoIni = Math.max(0, Math.min(1440 - duracao, novoIni))
    novoFim = novoIni + duracao
  }
  else {
    novoFim = Math.max(novoIni + 15, Math.min(1440, novoFim))
  }

  const novoIniIso = criarTimestampUtcDeMinutosLocais(props.dataIso, novoIni, props.fuso)
  const novoFimIso = criarTimestampUtcDeMinutosLocais(props.dataIso, novoFim, props.fuso)
  emit('moverOuRedimensionar', item.bloco, novoIniIso, novoFimIso)
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
          @selecionar="emit('selecionarBloco', $event)"
          @iniciar-pointer="(ev, modo) => aoIniciarPointerNoBloco(ev, item, modo)"
          @mover-teclado="(dIni, dFim) => aoMoverPorTeclado(item, dIni, dFim)"
        />
      </div>
    </div>
  </div>
</template>
