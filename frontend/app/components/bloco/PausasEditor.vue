<script setup lang="ts">
import { horaInputParaMinutos, minutosParaHoraInput } from '~/utils/tempo'

export interface PausaEditavel {
  inicioHora: string
  fimHora: string
}

interface Props {
  modelValue: PausaEditavel[]
  horaInicioBloco: string
}

const props = defineProps<Props>()
const emit = defineEmits<{
  'update:modelValue': [pausas: PausaEditavel[]]
}>()

function adicionarPausa() {
  const iniHora = props.horaInicioBloco || '10:00'
  const iniMin = horaInputParaMinutos(iniHora)
  const fimHora = minutosParaHoraInput((iniMin + 15) % 1440)
  const nova: PausaEditavel = {
    inicioHora: iniHora,
    fimHora,
  }
  emit('update:modelValue', [...props.modelValue, nova])
}

function atualizarItem(idx: number, campo: keyof PausaEditavel, valor: string) {
  const copia = props.modelValue.map((p, i) => (i === idx ? { ...p, [campo]: valor } : p))
  emit('update:modelValue', copia)
}

function removerPausa(idx: number) {
  emit(
    'update:modelValue',
    props.modelValue.filter((_, i) => i !== idx),
  )
}
</script>

<template>
  <div class="space-y-2.5">
    <div class="flex items-center justify-between">
      <span class="text-sm font-medium text-tinta">
        Pausas planejadas
      </span>
      <button
        type="button"
        class="text-xs font-medium text-ardosia-700 hover:underline"
        @click="adicionarPausa"
      >
        + Adicionar pausa
      </button>
    </div>

    <p
      v-if="!props.modelValue.length"
      class="text-xs text-grafite-suave"
    >
      Sem pausas planejadas — 100% da duração conta como horas líquidas.
    </p>

    <ul
      v-else
      class="space-y-2"
    >
      <li
        v-for="(p, idx) in props.modelValue"
        :key="idx"
        class="flex items-center gap-2 rounded-[var(--radius-bloco)] border border-linha bg-nevoa/60 px-3 py-2"
      >
        <input
          type="time"
          :value="p.inicioHora"
          aria-label="Início da pausa"
          class="tabular rounded border border-linha bg-papel px-2 py-1 text-xs text-tinta"
          @input="atualizarItem(idx, 'inicioHora', ($event.target as HTMLInputElement).value)"
        >
        <span class="text-xs text-grafite-suave">até</span>
        <input
          type="time"
          :value="p.fimHora"
          aria-label="Fim da pausa"
          class="tabular rounded border border-linha bg-papel px-2 py-1 text-xs text-tinta"
          @input="atualizarItem(idx, 'fimHora', ($event.target as HTMLInputElement).value)"
        >

        <button
          type="button"
          class="ml-auto rounded px-2 py-1 text-xs text-erro hover:bg-rosa-cha-50"
          aria-label="Remover pausa"
          @click="removerPausa(idx)"
        >
          Remover
        </button>
      </li>
    </ul>
  </div>
</template>
