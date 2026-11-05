<script setup lang="ts">
interface Props {
  modelValue: number[]
}

const props = defineProps<Props>()
const emit = defineEmits<{
  'update:modelValue': [lembretes: number[]]
}>()

const opcoes = [
  { min: 5, rotulo: '5 min antes' },
  { min: 10, rotulo: '10 min antes' },
  { min: 15, rotulo: '15 min antes' },
  { min: 30, rotulo: '30 min antes' },
] as const

function alternar(min: number) {
  const existe = props.modelValue.includes(min)
  const novo = existe
    ? props.modelValue.filter(x => x !== min)
    : [...props.modelValue, min].sort((a, b) => a - b)
  emit('update:modelValue', novo)
}
</script>

<template>
  <div class="space-y-2">
    <span class="block text-sm font-medium text-tinta">
      Lembretes antes do início
    </span>
    <div class="flex flex-wrap gap-2">
      <button
        v-for="op in opcoes"
        :key="op.min"
        type="button"
        :aria-pressed="props.modelValue.includes(op.min)"
        class="tabular rounded-full border px-3 py-1 text-xs font-medium transition-colors duration-150"
        :class="
          props.modelValue.includes(op.min)
            ? 'border-ardosia-700/40 bg-ardosia-200 text-ardosia-700'
            : 'border-linha bg-papel text-grafite-suave hover:text-tinta'
        "
        @click="alternar(op.min)"
      >
        {{ op.rotulo }}
      </button>
    </div>
  </div>
</template>
