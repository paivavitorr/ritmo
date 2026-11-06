<script lang="ts">
// Contador compartilhado: vários sheets podem estar abertos ao mesmo tempo.
let travasAtivas = 0
let overflowOriginal = ''

function travarScrollDoBody() {
  if (travasAtivas === 0) {
    overflowOriginal = document.body.style.overflow
    document.body.style.overflow = 'hidden'
  }
  travasAtivas++
}

function liberarScrollDoBody() {
  travasAtivas = Math.max(0, travasAtivas - 1)
  if (travasAtivas === 0) document.body.style.overflow = overflowOriginal
}

const SELETOR_FOCAVEL
  = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
</script>

<script setup lang="ts">
interface Props {
  aberto: boolean
  titulo: string
  descricao?: string
}

const props = withDefaults(defineProps<Props>(), {
  descricao: '',
})

const emit = defineEmits<{
  fechar: []
}>()

const idTitulo = useId()
const painel = ref<HTMLElement | null>(null)
const corpo = ref<HTMLElement | null>(null)
let elementoAnterior: HTMLElement | null = null
let travado = false

function focaveis(): HTMLElement[] {
  if (!painel.value) return []
  return Array.from(painel.value.querySelectorAll<HTMLElement>(SELETOR_FOCAVEL))
    .filter(el => el.offsetParent !== null || el === document.activeElement)
}

function aoTeclar(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    e.stopPropagation()
    emit('fechar')
    return
  }
  if (e.key !== 'Tab') return

  const lista = focaveis()
  const primeiro = lista[0]
  const ultimo = lista[lista.length - 1]
  if (!primeiro || !ultimo) {
    e.preventDefault()
    painel.value?.focus()
    return
  }
  const ativo = document.activeElement
  if (e.shiftKey && (ativo === primeiro || ativo === painel.value)) {
    e.preventDefault()
    ultimo.focus()
  }
  else if (!e.shiftKey && ativo === ultimo) {
    e.preventDefault()
    primeiro.focus()
  }
}

async function aoAbrir() {
  elementoAnterior = document.activeElement instanceof HTMLElement ? document.activeElement : null
  if (!travado) {
    travarScrollDoBody()
    travado = true
  }
  await nextTick()
  // Foco inicial: primeiro campo do conteúdo; senão o próprio painel.
  const alvo = corpo.value?.querySelector<HTMLElement>(SELETOR_FOCAVEL) ?? painel.value
  alvo?.focus({ preventScroll: true })
}

function aoFechar() {
  if (travado) {
    liberarScrollDoBody()
    travado = false
  }
  const anterior = elementoAnterior
  elementoAnterior = null
  if (anterior?.isConnected) anterior.focus({ preventScroll: true })
}

watch(() => props.aberto, (aberto) => {
  if (aberto) void aoAbrir()
  else aoFechar()
}, { immediate: true, flush: 'post' })

onBeforeUnmount(() => {
  if (travado) liberarScrollDoBody()
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="props.aberto"
      class="fixed inset-0 z-50 flex items-end justify-center lg:items-stretch lg:justify-end"
    >
      <!-- Backdrop discreto -->
      <div
        class="fixed inset-0 bg-tinta/25 transition-opacity duration-200"
        aria-hidden="true"
        @click="emit('fechar')"
      />

      <!-- Painel: bottom sheet no mobile, painel lateral no desktop -->
      <div
        ref="painel"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="idTitulo"
        tabindex="-1"
        class="relative z-10 flex max-h-[90dvh] w-full flex-col rounded-t-[var(--radius-sheet)] border border-linha bg-papel p-6 pb-[max(1.5rem,env(safe-area-inset-bottom))] shadow-[var(--shadow-elevado)] outline-none lg:h-dvh lg:max-h-dvh lg:max-w-md lg:rounded-l-[var(--radius-sheet)] lg:rounded-tr-none"
        @keydown="aoTeclar"
      >
        <div
          class="mx-auto mb-3 h-1 w-10 rounded-full bg-linha lg:hidden"
          aria-hidden="true"
        />

        <header class="flex items-start justify-between gap-4 border-b border-linha pb-4">
          <div>
            <h2
              :id="idTitulo"
              class="text-lg font-semibold text-tinta"
            >
              {{ props.titulo }}
            </h2>
            <p
              v-if="props.descricao"
              class="mt-0.5 text-sm text-grafite-suave"
            >
              {{ props.descricao }}
            </p>
          </div>

          <button
            type="button"
            class="-mr-2 -mt-1 flex size-11 shrink-0 items-center justify-center rounded-lg text-grafite-suave hover:bg-nevoa hover:text-tinta"
            aria-label="Fechar painel"
            @click="emit('fechar')"
          >
            <span aria-hidden="true">✕</span>
          </button>
        </header>

        <div
          ref="corpo"
          class="flex-1 overflow-y-auto overscroll-contain py-5"
        >
          <slot />
        </div>

        <footer
          v-if="$slots.rodape"
          class="border-t border-linha pt-4"
        >
          <slot name="rodape" />
        </footer>
      </div>
    </div>
  </Teleport>
</template>
