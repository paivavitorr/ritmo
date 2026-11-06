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
  ocupado?: boolean
  percentualExecutado?: number
  statusExecucao?: 'em_andamento' | 'concluida' | 'parcial' | 'pulada' | null
}

const props = withDefaults(defineProps<Props>(), {
  categoria: undefined,
  emArrasto: false,
  ocupado: false,
  percentualExecutado: 0,
  statusExecucao: null,
})

const emit = defineEmits<{
  selecionar: [bloco: BlocoRead]
  iniciarPointer: [evento: PointerEvent, modo: ModoArrasto]
  moverTeclado: [deltaIniMin: number, deltaFimMin: number]
  alternarConfirmacao: [bloco: BlocoRead]
  iniciarCronometro: [bloco: BlocoRead]
}>()

const MIN_VISUAL_MIN = 15

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

// Só a exibição é limitada ao dia; os minutos reais (que podem cruzar a meia-noite) ficam intactos.
const estiloPosicao = computed(() => {
  const iniVisivel = Math.max(0, props.inicioMinExibido)
  const fimVisivel = Math.min(1440, props.fimMinExibido)
  const duracaoVisivel = Math.max(MIN_VISUAL_MIN, fimVisivel - iniVisivel)
  const topPx = Math.min(iniVisivel, 1440 - MIN_VISUAL_MIN) * props.pxPorMinuto
  const heightPx = duracaoVisivel * props.pxPorMinuto
  const larguraPct = 100 / props.layout.totalColunas
  const leftPct = props.layout.coluna * larguraPct

  return {
    top: `${topPx}px`,
    height: `${heightPx}px`,
    left: `calc(${leftPct}% + 2px)`,
    width: `calc(${larguraPct}% - 6px)`,
  }
})

const duracaoExibida = computed(() => props.fimMinExibido - props.inicioMinExibido)

// Alça com ~24px de área de toque, mas nunca mais de metade do bloco.
const alturaAlcaPx = computed(() =>
  Math.max(8, Math.min(24, (Math.max(MIN_VISUAL_MIN, duracaoExibida.value) * props.pxPorMinuto) / 2)),
)

const ariaLabel = computed(() => {
  const nomeCat = props.categoria?.nome ?? 'Rotina'
  const iniStr = minutosParaHoraInput(props.inicioMinExibido)
  const fimStr = minutosParaHoraInput(props.fimMinExibido)
  const liqStr = formatarDuracaoMinutos(minutosLiquidos.value)
  return `${props.bloco.titulo}, ${nomeCat}, ${iniStr} às ${fimStr}, ${liqStr} líquidas`
})

function aoTeclar(e: KeyboardEvent) {
  const passo = e.key === 'ArrowUp' ? -15 : e.key === 'ArrowDown' ? 15 : 0
  if (passo === 0) return
  e.preventDefault()
  if (!e.shiftKey) {
    emit('moverTeclado', passo, passo)
  }
  else if (e.altKey) {
    emit('moverTeclado', passo, 0)
  }
  else {
    emit('moverTeclado', 0, passo)
  }
}
</script>

<template>
  <div
    class="group absolute z-10 select-none overflow-hidden rounded-[var(--radius-bloco)] transition-[top,height,box-shadow] duration-120 ease-[var(--ease-suave)]"
    :class="[
      estiloCor.blocoContorno,
      props.emArrasto ? 'z-30 shadow-[var(--shadow-elevado)] ring-2 ring-foco' : '',
    ]"
    :style="estiloPosicao"
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
        top: `${Math.max(0, p.inicioMin - Math.max(0, props.inicioMinExibido)) * props.pxPorMinuto}px`,
        height: `${Math.max(8, (p.fimMin - p.inicioMin) * props.pxPorMinuto)}px`,
      }"
      aria-hidden="true"
    >
      <span v-if="(p.fimMin - p.inicioMin) >= 15">pausa</span>
    </div>

    <!--
      Botão principal ocupa o bloco inteiro (seleção, arrasto e setas do teclado).
      Os botões de ação são irmãos dele, nunca filhos (sem interativo aninhado).
    -->
    <button
      type="button"
      :aria-label="ariaLabel"
      aria-keyshortcuts="ArrowUp ArrowDown Shift+ArrowUp Shift+ArrowDown"
      title="Setas movem 15 min; Shift redimensiona o fim; Alt+Shift o início"
      class="absolute inset-0 z-10 flex flex-col justify-between px-3 py-1.5 text-left [touch-action:pan-y] focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-foco"
      @pointerdown="emit('iniciarPointer', $event, 'mover')"
      @click.stop="emit('selecionar', props.bloco)"
      @keydown="aoTeclar"
    >
      <span class="block min-w-0 pr-28">
        <span class="block truncate text-xs font-semibold leading-tight">
          {{ props.bloco.titulo }}
        </span>
        <span
          v-if="duracaoExibida >= 40"
          class="block truncate text-[11px] opacity-80"
        >
          {{ props.categoria?.nome ?? 'Rotina' }}
          <span v-if="props.bloco.tipo === 'compromisso'"> · Compromisso</span>
        </span>
      </span>

      <span
        v-if="duracaoExibida >= 55"
        class="flex items-center justify-between text-[11px] opacity-85"
      >
        <span class="tabular">{{ formatarDuracaoMinutos(minutosLiquidos) }} líquidas</span>
        <span
          v-if="props.bloco.pausas_planejadas.length"
          class="tabular"
        >
          {{ props.bloco.pausas_planejadas.length }} pausa(s)
        </span>
      </span>
    </button>

    <!-- Horário e ações (acima do botão principal, mas fora dele) -->
    <div class="pointer-events-none absolute right-2 top-1 z-20 flex items-start gap-1.5">
      <span class="tabular pointer-events-none pt-0.5 text-[11px] font-medium">
        {{ minutosParaHoraInput(props.inicioMinExibido) }}–{{ minutosParaHoraInput(props.fimMinExibido) }}
      </span>

      <!-- Botão 1-toque: Fiz como planejado / Desmarcar -->
      <button
        type="button"
        :aria-label="
          props.statusExecucao === 'concluida'
            ? `Desmarcar conclusão de ${props.bloco.titulo}`
            : `Confirmar ${props.bloco.titulo} como planejado`
        "
        :aria-pressed="props.statusExecucao === 'concluida'"
        :disabled="props.ocupado"
        :title="
          props.statusExecucao === 'concluida'
            ? 'Concluído (toque para desmarcar)'
            : 'Fiz como planejado (1 toque)'
        "
        class="pointer-events-auto flex size-6 items-center justify-center rounded-full border transition-colors focus-visible:outline-2 focus-visible:outline-foco disabled:opacity-50"
        :class="
          props.statusExecucao === 'concluida'
            ? 'border-current bg-tinta text-papel'
            : 'border-current/40 bg-papel/80 text-current hover:bg-papel'
        "
        @pointerdown.stop
        @click.stop="emit('alternarConfirmacao', props.bloco)"
      >
        <span
          class="text-[11px] font-bold leading-none"
          aria-hidden="true"
        >✓</span>
      </button>

      <!-- Iniciar cronômetro: sempre no toque; em mouse aparece no hover/foco -->
      <button
        v-if="props.statusExecucao !== 'em_andamento' && duracaoExibida >= 30"
        type="button"
        :aria-label="`Iniciar cronômetro para ${props.bloco.titulo}`"
        title="Iniciar cronômetro neste bloco"
        class="pointer-events-auto flex size-6 items-center justify-center rounded-full border border-current/40 bg-papel/80 text-[10px] text-current transition-opacity hover:bg-papel focus-visible:outline-2 focus-visible:outline-foco [@media(hover:hover)]:opacity-0 [@media(hover:hover)]:focus-visible:opacity-100 [@media(hover:hover)]:group-focus-within:opacity-100 [@media(hover:hover)]:group-hover:opacity-100"
        @pointerdown.stop
        @click.stop="emit('iniciarCronometro', props.bloco)"
      >
        <span aria-hidden="true">▶</span>
      </button>
    </div>

    <!-- Alças de resize: sempre visíveis no toque; em mouse, no hover/foco -->
    <div
      class="absolute inset-x-0 top-0 z-20 flex cursor-ns-resize items-start justify-center [touch-action:none] [@media(hover:hover)]:opacity-0 [@media(hover:hover)]:group-focus-within:opacity-100 [@media(hover:hover)]:group-hover:opacity-100"
      :style="{ height: `${alturaAlcaPx}px` }"
      aria-hidden="true"
      @pointerdown.stop="emit('iniciarPointer', $event, 'redimensionar-topo')"
      @click.stop
    >
      <span class="mt-0.5 h-1 w-8 rounded-full bg-current/50" />
    </div>
    <div
      class="absolute inset-x-0 bottom-0 z-20 flex cursor-ns-resize items-end justify-center [touch-action:none] [@media(hover:hover)]:opacity-0 [@media(hover:hover)]:group-focus-within:opacity-100 [@media(hover:hover)]:group-hover:opacity-100"
      :style="{ height: `${alturaAlcaPx}px` }"
      aria-hidden="true"
      @pointerdown.stop="emit('iniciarPointer', $event, 'redimensionar-base')"
      @click.stop
    >
      <span class="mb-0.5 h-1 w-8 rounded-full bg-current/50" />
    </div>
  </div>
</template>
