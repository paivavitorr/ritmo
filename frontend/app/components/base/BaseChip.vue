<script setup lang="ts">
import { ESTILOS_CATEGORIA, type CorCategoria } from '~/utils/coresCategoria'

interface Props {
  cor: CorCategoria
  selecionado?: boolean
  interativo?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  selecionado: false,
  interativo: false,
})

const estilo = computed(() => ESTILOS_CATEGORIA[props.cor])
</script>

<template>
  <component
    :is="props.interativo ? 'button' : 'span'"
    :type="props.interativo ? 'button' : undefined"
    :aria-pressed="props.interativo ? props.selecionado : undefined"
    class="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-medium transition-colors duration-150"
    :class="[props.selecionado ? estilo.chipAtivo : estilo.chip, props.interativo ? 'min-h-11' : '']"
  >
    <span
      class="h-2 w-2 rounded-full"
      :class="estilo.ponto"
      aria-hidden="true"
    />
    <slot />
  </component>
</template>
