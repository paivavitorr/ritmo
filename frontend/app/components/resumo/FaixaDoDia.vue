<script setup lang="ts">
import type { components } from '~/types/api'
import { ESTILOS_CATEGORIA, formatarDuracaoSegundos } from '~/utils/coresCategoria'
import { formatarDataCabecalho, minutosDesdeMeiaNoiteNoFuso } from '~/utils/tempo'

type FaixaDia = components['schemas']['FaixaDia']
type FaixaIntervalo = components['schemas']['FaixaIntervalo']

interface Props {
  faixa: FaixaDia
  fuso: string
}

const props = defineProps<Props>()

function estiloSegmento(item: FaixaIntervalo) {
  const iniMin = minutosDesdeMeiaNoiteNoFuso(item.inicio_iso, props.faixa.data, props.fuso)
  const fimMin = minutosDesdeMeiaNoiteNoFuso(item.fim_iso, props.faixa.data, props.fuso)
  const leftPct = (Math.max(0, Math.min(1440, iniMin)) / 1440) * 100
  const rightMin = Math.max(iniMin, Math.min(1440, fimMin))
  const widthPct = Math.max(0.6, ((rightMin - iniMin) / 1440) * 100)

  const token = (item.categoria_cor as keyof typeof ESTILOS_CATEGORIA) || 'ardosia'
  const cor = ESTILOS_CATEGORIA[token] ?? ESTILOS_CATEGORIA.ardosia

  return {
    style: {
      left: `${leftPct}%`,
      width: `${widthPct}%`,
    },
    classe: item.tipo === 'planejado' ? `${cor.blocoContorno} border` : cor.blocoPreenchimento,
  }
}
</script>

<template>
  <div class="rounded-[var(--radius-bloco)] border border-linha bg-papel p-4 shadow-sm">
    <div class="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-linha">
      <div>
        <h3 class="text-sm font-semibold capitalize text-tinta">
          {{ formatarDataCabecalho(props.faixa.data) }}
        </h3>
        <p class="tabular text-xs text-grafite-suave">
          Planejado: {{ formatarDuracaoSegundos(props.faixa.segundos_planejados) }} ·
          Executado: {{ formatarDuracaoSegundos(props.faixa.segundos_executados) }}
        </p>
      </div>

      <div class="flex items-center gap-2">
        <AderenciaIndicador
          :valor="props.faixa.aderencia_volume"
          rotulo="Volume"
          tamanho="sm"
        />
        <AderenciaIndicador
          :valor="props.faixa.aderencia_temporal"
          rotulo="Temporal"
          tamanho="sm"
        />
      </div>
    </div>

    <!-- Comparação visual estilo fita 24h (Planejado vs Executado) -->
    <div class="mt-4 space-y-2.5">
      <!-- Fita Planejada -->
      <div>
        <div class="flex items-center justify-between text-[11px] text-grafite-suave mb-1">
          <span>Planejado (contorno)</span>
          <span class="tabular">00:00 – 24:00</span>
        </div>
        <div class="relative h-4 w-full rounded bg-nevoa/80 overflow-hidden">
          <div
            v-for="(p, idx) in props.faixa.planejados"
            :key="idx"
            class="absolute top-0 bottom-0 rounded-sm"
            :class="estiloSegmento(p).classe"
            :style="estiloSegmento(p).style"
            :title="`${p.titulo} (${p.categoria_nome})`"
          />
        </div>
      </div>

      <!-- Fita Executada -->
      <div>
        <div class="flex items-center justify-between text-[11px] text-grafite-suave mb-1">
          <span>Executado (preenchimento)</span>
        </div>
        <div class="relative h-4 w-full rounded bg-nevoa/80 overflow-hidden">
          <div
            v-for="(e, idx) in props.faixa.executados"
            :key="idx"
            class="absolute top-0 bottom-0 rounded-sm"
            :class="estiloSegmento(e).classe"
            :style="estiloSegmento(e).style"
            :title="`${e.categoria_nome}`"
          />
        </div>
      </div>
    </div>
  </div>
</template>
