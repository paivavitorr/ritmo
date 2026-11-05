<script setup lang="ts">
interface Props {
  valor: number // [0.0, 1.0] ou superior
  rotulo?: string
  tamanho?: 'sm' | 'md'
}

const props = withDefaults(defineProps<Props>(), {
  rotulo: 'Aderência',
  tamanho: 'md',
})

const pct = computed(() => Math.round(props.valor * 100))

const estiloCor = computed(() => {
  if (pct.value >= 85) {
    return 'border-salvia-200 bg-salvia-50 text-salvia-700'
  }
  if (pct.value >= 60) {
    return 'border-manteiga-200 bg-manteiga-50 text-manteiga-700'
  }
  return 'border-rosa-cha-200 bg-rosa-cha-50 text-rosa-cha-700'
})
</script>

<template>
  <div
    class="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5"
    :class="[
      estiloCor,
      props.tamanho === 'sm' ? 'text-[11px]' : 'text-xs font-medium',
    ]"
  >
    <span class="opacity-75">{{ props.rotulo }}</span>
    <span class="tabular font-semibold">{{ pct }}%</span>
  </div>
</template>
