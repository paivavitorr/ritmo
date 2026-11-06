<script setup lang="ts">
/**
 * Badge compacto de estado de sincronização: offline, sincronizando, pendências ou conflitos.
 * Emite `abrir` ao clicar (ex.: para abrir o PainelPendencias).
 */
const conexao = useConexaoStore()
const sync = useSyncStore()

const emit = defineEmits<{ abrir: [] }>()

type Estado = 'conflitos' | 'offline' | 'sincronizando' | 'pendencias' | 'ok'

const estado = computed<Estado>(() => {
  if (sync.conflitos.length > 0) return 'conflitos'
  if (conexao.api === 'indisponivel') return 'offline'
  if (sync.sincronizando) return 'sincronizando'
  if (sync.pendenciasCount > 0) return 'pendencias'
  return 'ok'
})

const texto = computed(() => {
  switch (estado.value) {
    case 'conflitos': {
      const n = sync.conflitos.length
      return n === 1 ? '1 conflito' : `${n} conflitos`
    }
    case 'offline':
      return sync.pendenciasCount > 0 ? `Offline · ${sync.pendenciasCount} pendentes` : 'Offline'
    case 'sincronizando':
      return 'Sincronizando…'
    case 'pendencias':
      return sync.pendenciasCount === 1 ? '1 pendente' : `${sync.pendenciasCount} pendentes`
    default:
      return 'Sincronizado'
  }
})

const classes = computed(() => {
  switch (estado.value) {
    case 'conflitos': return 'bg-pessego-50 text-pessego-700 border-pessego-200'
    case 'offline': return 'bg-manteiga-50 text-manteiga-700 border-manteiga-200'
    case 'sincronizando': return 'bg-ceu-50 text-ceu-700 border-ceu-200'
    case 'pendencias': return 'bg-glicinia-50 text-glicinia-700 border-glicinia-200'
    default: return 'bg-salvia-50 text-salvia-700 border-salvia-200'
  }
})

const classePonto = computed(() => {
  switch (estado.value) {
    case 'conflitos': return 'bg-pessego-700'
    case 'offline': return 'bg-manteiga-700'
    case 'sincronizando': return 'bg-ceu-700 animate-pulse'
    case 'pendencias': return 'bg-glicinia-700'
    default: return 'bg-salvia-700'
  }
})
</script>

<template>
  <button
    type="button"
    class="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium"
    :class="classes"
    aria-live="polite"
    role="status"
    @click="emit('abrir')"
  >
    <span
      class="size-2 rounded-full"
      :class="classePonto"
      aria-hidden="true"
    />
    <span class="tabular">{{ texto }}</span>
  </button>
</template>
