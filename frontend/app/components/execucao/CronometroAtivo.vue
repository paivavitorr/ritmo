<script setup lang="ts">
import { extrairMensagemErro } from '~/composables/useApi'
import { calcularSegundosLiquidosAoVivo } from '~/stores/execucoes'
import { ESTILOS_CATEGORIA } from '~/utils/coresCategoria'

const execucoesStore = useExecucoesStore()
const categoriasStore = useCategoriasStore()
const blocosStore = useBlocosStore()

const agoraMs = ref(Date.now())
const processando = ref(false)
const erro = ref<string | null>(null)
let intervalo: ReturnType<typeof setInterval> | null = null

const execucaoAtiva = computed(() => execucoesStore.ativa)

const estaPausada = computed(() => {
  if (!execucaoAtiva.value) return false
  return execucaoAtiva.value.pausas.some(p => p.fim == null)
})

const categoriaAtiva = computed(() => {
  if (!execucaoAtiva.value) return undefined
  return categoriasStore.mapaPorId.get(execucaoAtiva.value.categoria_id)
})

const estiloCor = computed(() => {
  const token = categoriaAtiva.value?.cor ?? 'ardosia'
  return ESTILOS_CATEGORIA[token]
})

const tituloExibido = computed(() => {
  const ex = execucaoAtiva.value
  if (!ex) return ''
  if (ex.bloco_id) {
    for (const lista of Object.values(blocosStore.porData)) {
      const b = lista.find(item => item.id === ex.bloco_id)
      if (b) return b.titulo
    }
  }
  return categoriaAtiva.value?.nome ?? 'Foco em andamento'
})

const relogioFormatado = computed(() => {
  if (!execucaoAtiva.value) return '00:00'
  const segs = calcularSegundosLiquidosAoVivo(execucaoAtiva.value, agoraMs.value)
  const h = Math.floor(segs / 3600)
  const m = Math.floor((segs % 3600) / 60)
  const s = segs % 60
  const mm = String(m).padStart(2, '0')
  const ss = String(s).padStart(2, '0')
  if (h > 0) {
    return `${String(h).padStart(2, '0')}:${mm}:${ss}`
  }
  return `${mm}:${ss}`
})

async function alternarPausa() {
  if (!execucaoAtiva.value || processando.value) return
  erro.value = null
  processando.value = true
  try {
    if (estaPausada.value) {
      await execucoesStore.retomarCronometro(execucaoAtiva.value.id)
    }
    else {
      await execucoesStore.pausarCronometro(execucaoAtiva.value.id)
    }
  }
  catch (e: unknown) {
    erro.value = extrairMensagemErro(e, 'Não foi possível alternar a pausa.')
  }
  finally {
    processando.value = false
  }
}

async function concluir() {
  if (!execucaoAtiva.value || processando.value) return
  erro.value = null
  processando.value = true
  try {
    await execucoesStore.concluirCronometro(execucaoAtiva.value.id, 'concluida')
  }
  catch (e: unknown) {
    erro.value = extrairMensagemErro(e, 'Não foi possível concluir o cronômetro.')
  }
  finally {
    processando.value = false
  }
}

onMounted(() => {
  intervalo = setInterval(() => {
    agoraMs.value = Date.now()
  }, 1000)
})

onBeforeUnmount(() => {
  if (intervalo) clearInterval(intervalo)
})
</script>

<template>
  <div
    v-if="execucaoAtiva"
    class="rounded-[var(--radius-bloco)] border px-4 py-3 shadow-[var(--shadow-elevado)] transition-colors"
    :class="estiloCor.blocoContorno"
    role="region"
    aria-label="Cronômetro ativo"
  >
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div class="flex min-w-0 items-center gap-3">
        <span
          class="h-2.5 w-2.5 shrink-0 rounded-full"
          :class="[estiloCor.ponto, estaPausada ? 'opacity-40' : 'animate-pulse']"
        />
        <div class="min-w-0">
          <p class="truncate text-xs font-semibold">
            {{ tituloExibido }}
          </p>
          <p class="text-[11px] opacity-80">
            {{ estaPausada ? 'Pausado · tempo líquido congelado' : 'Em andamento · horas líquidas ao vivo' }}
          </p>
        </div>
      </div>

      <div class="flex items-center gap-2.5">
        <span class="tabular text-lg font-semibold tracking-tight">
          {{ relogioFormatado }}
        </span>

        <button
          type="button"
          :disabled="processando"
          class="rounded-lg border border-current/25 bg-papel/80 px-2.5 py-1 text-xs font-medium text-tinta hover:bg-papel disabled:opacity-50"
          @click="alternarPausa"
        >
          {{ estaPausada ? 'Retomar' : 'Pausar' }}
        </button>

        <button
          type="button"
          :disabled="processando"
          class="rounded-lg bg-tinta px-3 py-1 text-xs font-medium text-papel hover:bg-tinta/90 disabled:opacity-50"
          @click="concluir"
        >
          Concluir
        </button>
      </div>
    </div>

    <p
      v-if="erro"
      class="mt-2 text-xs text-erro"
      role="alert"
    >
      {{ erro }}
    </p>
  </div>
</template>
