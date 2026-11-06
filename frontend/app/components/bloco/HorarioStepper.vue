<script setup lang="ts">
import { ajustarHorarioInput } from '~/utils/tempo'

interface Props {
  id: string
  modelValue: string
  label: string
  /** `inicio` limita a 23:55; `fim` aceita até 24:00 (exibido como 00:00). */
  campo: 'inicio' | 'fim'
  passoMinutos?: number
}

const props = withDefaults(defineProps<Props>(), {
  passoMinutos: 5,
})

const emit = defineEmits<{
  'update:modelValue': [hora: string]
}>()

function ajustar(delta: number) {
  emit('update:modelValue', ajustarHorarioInput(props.modelValue, props.campo, delta))
}

const classeBotao
  = 'tabular inline-flex min-h-11 min-w-11 items-center justify-center rounded border border-linha bg-nevoa px-2 text-xs text-grafite-suave hover:text-tinta'
</script>

<template>
  <div>
    <BaseInput
      :id="props.id"
      :model-value="props.modelValue"
      tipo="time"
      tabular
      :label="props.label"
      obrigatorio
      @update:model-value="emit('update:modelValue', $event)"
    />
    <div class="mt-1 flex gap-1">
      <button
        type="button"
        :class="classeBotao"
        :aria-label="`${props.label}: ${props.passoMinutos} minutos a menos`"
        @click="ajustar(-props.passoMinutos)"
      >
        -{{ props.passoMinutos }}m
      </button>
      <button
        type="button"
        :class="classeBotao"
        :aria-label="`${props.label}: ${props.passoMinutos} minutos a mais`"
        @click="ajustar(props.passoMinutos)"
      >
        +{{ props.passoMinutos }}m
      </button>
    </div>
  </div>
</template>
