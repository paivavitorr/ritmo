<script setup lang="ts">
interface Props {
  pxPorMinuto: number
}

const props = defineProps<Props>()

const horas = Array.from({ length: 25 }, (_, i) => i)

function formatarHora(h: number): string {
  if (h === 24) return '24:00'
  return `${String(h).padStart(2, '0')}:00`
}
</script>

<template>
  <div
    class="pointer-events-none relative select-none"
    :style="{ height: `${1440 * props.pxPorMinuto}px` }"
    aria-hidden="true"
  >
    <div
      v-for="h in horas"
      :key="h"
      class="absolute inset-x-0 flex items-center"
      :style="{ top: `${h * 60 * props.pxPorMinuto}px` }"
    >
      <span class="tabular w-14 shrink-0 -translate-y-2 pr-3 text-right text-xs text-grafite-suave">
        {{ formatarHora(h) }}
      </span>
      <div class="h-px flex-1 bg-linha" />
    </div>
  </div>
</template>
