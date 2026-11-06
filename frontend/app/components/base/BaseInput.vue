<script setup lang="ts">
interface Props {
  id: string
  label: string
  modelValue: string | number | null | undefined
  tipo?: 'text' | 'email' | 'password' | 'number' | 'time' | 'date'
  placeholder?: string
  obrigatorio?: boolean
  desabilitado?: boolean
  dica?: string
  erro?: string | null
  min?: number | string
  max?: number | string
  step?: number | string
  tabular?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  tipo: 'text',
  placeholder: '',
  obrigatorio: false,
  desabilitado: false,
  dica: '',
  erro: null,
  min: undefined,
  max: undefined,
  step: undefined,
  tabular: false,
})

const emit = defineEmits<{
  'update:modelValue': [valor: string]
}>()

function aoDigitar(evento: Event) {
  const alvo = evento.target as HTMLInputElement
  emit('update:modelValue', alvo.value)
}
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <label
      :for="props.id"
      class="text-sm font-medium text-tinta"
    >
      {{ props.label }}
    </label>

    <input
      :id="props.id"
      :type="props.tipo"
      :value="props.modelValue ?? ''"
      :placeholder="props.placeholder"
      :required="props.obrigatorio"
      :disabled="props.desabilitado"
      :min="props.min"
      :max="props.max"
      :step="props.step"
      :aria-invalid="Boolean(props.erro)"
      :aria-describedby="props.erro ? `${props.id}-erro` : props.dica ? `${props.id}-dica` : undefined"
      class="min-h-11 w-full rounded-[var(--radius-bloco)] border bg-papel px-3.5 py-2.5 text-base text-tinta placeholder:text-grafite-suave/70 disabled:opacity-60"
      :class="[
        props.erro ? 'border-erro' : 'border-linha',
        props.tabular ? 'tabular' : '',
      ]"
      @input="aoDigitar"
    >

    <p
      v-if="props.erro"
      :id="`${props.id}-erro`"
      class="text-xs text-erro"
    >
      {{ props.erro }}
    </p>
    <p
      v-else-if="props.dica"
      :id="`${props.id}-dica`"
      class="text-xs text-grafite-suave"
    >
      {{ props.dica }}
    </p>
  </div>
</template>
