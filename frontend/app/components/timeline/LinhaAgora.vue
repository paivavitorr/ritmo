<script setup lang="ts">
import { minutosDesdeMeiaNoiteNoFuso, minutosParaHoraInput } from '~/utils/tempo'

interface Props {
  dataIso: string
  fuso: string
  pxPorMinuto: number
}

const props = defineProps<Props>()

const minutosAgora = ref<number | null>(null)
let intervaloId: ReturnType<typeof setInterval> | null = null

function atualizarAgora() {
  const agora = new Date()
  const min = minutosDesdeMeiaNoiteNoFuso(agora.toISOString(), props.dataIso, props.fuso)
  if (min >= 0 && min <= 1440) {
    minutosAgora.value = min
  }
  else {
    minutosAgora.value = null
  }
}

watch(() => [props.dataIso, props.fuso], atualizarAgora, { immediate: true })

onMounted(() => {
  intervaloId = setInterval(atualizarAgora, 30_000)
})

onBeforeUnmount(() => {
  if (intervaloId) clearInterval(intervaloId)
})
</script>

<template>
  <div
    v-if="minutosAgora !== null"
    class="pointer-events-none absolute inset-x-0 z-20 flex items-center"
    :style="{ top: `${minutosAgora * props.pxPorMinuto}px` }"
    aria-hidden="true"
  >
    <span class="tabular w-14 shrink-0 pr-2 text-right text-[11px] font-semibold text-foco">
      {{ minutosParaHoraInput(minutosAgora) }}
    </span>
    <span class="-ml-1 h-2.5 w-2.5 shrink-0 rounded-full bg-foco" />
    <div class="h-[1.5px] flex-1 bg-foco" />
  </div>
</template>
