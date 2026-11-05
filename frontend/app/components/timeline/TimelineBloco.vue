<script setup lang="ts">
import type { ModoArrasto } from '~/composables/useArrasto'
import type { BlocoRead } from '~/stores/blocos'
import type { CategoriaRead } from '~/stores/categorias'
import {
  ESTILOS_CATEGORIA,
  formatarDuracaoMinutos,
} from '~/utils/coresCategoria'
import { calcularMinutosLiquidos, type PosicaoBlocoLayout } from '~/utils/horasLiquidas'
import { minutosDesdeMeiaNoiteNoFuso, minutosParaHoraInput } from '~/utils/tempo'

interface Props {
  bloco: BlocoRead
  categoria?: CategoriaRead
  dataIso: string
  fuso: string
  pxPorMinuto: number
  layout: PosicaoBlocoLayout
  inicioMinExibido: number
  fimMinExibido: number
  emArrasto?: boolean
  percentualExecutado?: number
}

const props = withDefaults(defineProps<Props>(), {
  categoria: undefined,
  emArrasto: false,
  percentualExecutado: 0,
})

const emit = defineEmits<{
  selecionar: [bloco: BlocoRead]
  iniciarPointer: [evento: PointerEvent, modo: ModoArrasto]
  moverTeclado: [deltaIniMin: number, deltaFimMin: number]
}>()

const corToken = computed(() => props.categoria?.cor ?? 'ardosia')
const estiloCor = computed(() => ESTILOS_CATEGORIA[corToken.value])

const pausasEmMinutos = computed(() =>
  props.bloco.pausas_planejadas
    .map((p) => {
      const ini = minutosDesdeMeiaNoiteNoFuso(p.inicio, props.dataIso, props.fuso)
      const fim = minutosDesdeMeiaNoiteNoFuso(p.fim, props.dataIso, props.fuso)
      return { inicioMin: ini, fimMin: fim }
    })
    .filter(p => p.fimMin > p.inicioMin),
)

const minutosLiquidos = computed(() =>
  calcularMinutosLiquidos(
    props.inicioMinExibido,
    props.fimMinExibido,
    pausasEmMinutos.value,
  ),
)

const estiloPosicao = computed(() => {
  const iniClamped = Math.max(0, Math.min(1425, props.inicioMinExibido))
  const fimClamped = Math.max(iniClamped + 15, Math.min(1440, props.fimMinExibido))
  const topPx = iniClamped * props.pxPorMinuto
  const duracaoMin = fimClamped - iniClamped
  const heightPx = duracaoMin * props.pxPorMinuto
  const larguraPct = 100 / props.layout.totalColunas
  const leftPct = props.layout.coluna * larguraPct

  return {
    top: `${topPx}px`,
    height: `${heightPx}px`,
    left: `calc(${leftPct}% + 2px)`,
    width: `calc(${larguraPct}% - 6px)`,
  }
})

const ariaLabel = computed(() => {
  const nomeCat = props.categoria?.nome ?? 'Rotina'
  const iniStr = minutosParaHoraInput(props.inicioMinExibido)
  const fimStr = minutosParaHoraInput(props.fimMinExibido)
  const liqStr = formatarDuracaoMinutos(minutosLiquidos.value)
  return `${props.bloco.titulo}, ${nomeCat}, ${iniStr} às ${fimStr}, ${liqStr} líquidas`
})

function aoTeclar(e: KeyboardEvent) {
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault()
    emit('selecionar', props.bloco)
    return
  }
  if (e.key === 'ArrowUp') {
    e.preventDefault()
    if (e.shiftKey) {
      emit('moverTeclado', 0, -15)
    }
    else {
      emit('moverTeclado', -15, -15)
    }
  }
  else if (e.key === 'ArrowDown') {
    e.preventDefault()
    if (e.shiftKey) {
      emit('moverTeclado', 0, 15)
    }
    else {
      emit('moverTeclado', 15, 15)
    }
  }
}
</script>

<template>
  <div
    role="button"
    tabindex="0"
    :aria-label="ariaLabel"
    class="group absolute z-10 flex select-none flex-col justify-between overflow-hidden rounded-[var(--radius-bloco)] px-3 py-1.5 text-left transition-[top,height,box-shadow] duration-120 ease-[var(--ease-suave)]"
    :class="[
      estiloCor.blocoContorno,
      props.emArrasto ? 'z-30 shadow-[var(--shadow-elevado)] ring-2 ring-foco' : '',
    ]"
    :style="estiloPosicao"
    @pointerdown="emit('iniciarPointer', $event, 'mover')"
    @click.stop="emit('selecionar', props.bloco)"
    @keydown="aoTeclar"
  >
    <!-- Preenchimento do executado (Princípio 1: plano em contorno, real em preenchimento) -->
    <div
      v-if="props.percentualExecutado > 0"
      class="pointer-events-none absolute inset-x-0 top-0 opacity-65 transition-[height] duration-200"
      :class="estiloCor.blocoPreenchimento"
      :style="{ height: `${Math.min(100, Math.max(0, props.percentualExecutado))}%` }"
      aria-hidden="true"
    />

    <!-- Pausas planejadas demarcadas dentro do bloco -->
    <div
      v-for="(p, idx) in pausasEmMinutos"
      :key="idx"
      class="pointer-events-none absolute inset-x-1 flex items-center justify-center rounded border border-dashed border-current/35 bg-papel/55 text-[10px]"
      :style="{
        top: `${Math.max(0, p.inicioMin - props.inicioMinExibido) * props.pxPorMinuto}px`,
        height: `${Math.max(8, (p.fimMin - p.inicioMin) * props.pxPorMinuto)}px`,
      }"
      aria-hidden="true"
    >
      <span v-if="(p.fimMin - p.inicioMin) >= 15">pausa</span>
    </div>

    <!-- Alça superior de resize -->
    <div
      class="absolute inset-x-0 top-0 h-2.5 cursor-ns-resize opacity-0 group-hover:opacity-100"
      aria-hidden="true"
      @pointerdown.stop="emit('iniciarPointer', $event, 'redimensionar-topo')"
    />

    <!-- Conteúdo textual do bloco -->
    <div class="relative z-10 flex items-baseline justify-between gap-2">
      <div class="min-w-0">
        <p class="truncate text-xs font-semibold leading-tight">
          {{ props.bloco.titulo }}
        </p>
        <p
          v-if="(props.fimMinExibido - props.inicioMinExibido) >= 40"
          class="truncate text-[11px] opacity-80"
        >
          {{ props.categoria?.nome ?? 'Rotina' }}
          <span v-if="props.bloco.tipo === 'compromisso'"> · Compromisso</span>
        </p>
      </div>

      <span class="tabular shrink-0 text-[11px] font-medium">
        {{ minutosParaHoraInput(props.inicioMinExibido) }}–{{ minutosParaHoraInput(props.fimMinExibido) }}
      </span>
    </div>

    <div
      v-if="(props.fimMinExibido - props.inicioMinExibido) >= 55"
      class="relative z-10 flex items-center justify-between text-[11px] opacity-85"
    >
      <span class="tabular">{{ formatarDuracaoMinutos(minutosLiquidos) }} líquidas</span>
      <span
        v-if="props.bloco.pausas_planejadas.length"
        class="tabular"
      >
        {{ props.bloco.pausas_planejadas.length }} pausa(s)
      </span>
    </div>

    <!-- Alça inferior de resize -->
    <div
      class="absolute inset-x-0 bottom-0 h-2.5 cursor-ns-resize opacity-0 group-hover:opacity-100"
      aria-hidden="true"
      @pointerdown.stop="emit('iniciarPointer', $event, 'redimensionar-base')"
    />
  </div>
</template>
