<script setup lang="ts">
import type { components } from '~/types/api'
import { ESTILOS_CATEGORIA, formatarDuracaoSegundos } from '~/utils/coresCategoria'

type CategoriaResumo = components['schemas']['CategoriaResumo']

interface Props {
  categoria: CategoriaResumo
}

const props = defineProps<Props>()

const estiloCor = computed(() => {
  const token = (props.categoria.cor as keyof typeof ESTILOS_CATEGORIA) || 'ardosia'
  return ESTILOS_CATEGORIA[token] ?? ESTILOS_CATEGORIA.ardosia
})

const pctVolume = computed(() => Math.round(props.categoria.aderencia_volume * 100))
</script>

<template>
  <div class="flex flex-col gap-2 rounded-[var(--radius-bloco)] border border-linha bg-papel p-3.5 sm:flex-row sm:items-center sm:justify-between">
    <div class="flex items-center gap-3">
      <span
        class="h-3 w-3 shrink-0 rounded-full"
        :class="estiloCor.ponto"
      />
      <div>
        <p class="text-sm font-semibold text-tinta">
          {{ props.categoria.nome }}
        </p>
        <p class="tabular text-xs text-grafite-suave">
          <template v-if="props.categoria.eh_espontaneo">
            {{ formatarDuracaoSegundos(props.categoria.segundos_executados) }} executadas espontaneamente
          </template>
          <template v-else>
            {{ formatarDuracaoSegundos(props.categoria.segundos_executados) }} executadas de
            {{ formatarDuracaoSegundos(props.categoria.segundos_planejados) }} planejadas
          </template>
        </p>
      </div>
    </div>

    <div class="flex items-center gap-3">
      <!-- Barra de progresso visual de aderência -->
      <div
        v-if="!props.categoria.eh_espontaneo && props.categoria.segundos_planejados > 0"
        class="hidden w-28 overflow-hidden rounded-full bg-nevoa sm:block"
      >
        <div
          class="h-2 rounded-full transition-all duration-300"
          :class="estiloCor.blocoPreenchimento"
          :style="{ width: `${Math.min(100, pctVolume)}%` }"
        />
      </div>

      <AderenciaIndicador
        v-if="!props.categoria.eh_espontaneo"
        :valor="props.categoria.aderencia_volume"
        rotulo="Volume"
        tamanho="sm"
      />
      <AderenciaIndicador
        v-if="!props.categoria.eh_espontaneo"
        :valor="props.categoria.aderencia_temporal"
        rotulo="Temporal"
        tamanho="sm"
      />
      <span
        v-else
        class="rounded-full border border-ardosia-200 bg-nevoa px-2.5 py-0.5 text-xs text-grafite-suave"
      >
        Espontâneo
      </span>
    </div>
  </div>
</template>
