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

function aoTeclar(e: KeyboardEvent) {
  if (e.key === 'Escape' && props.aberto) {
    emit('fechar')
  }
}

onMounted(() => window.addEventListener('keydown', aoTeclar))
onBeforeUnmount(() => window.removeEventListener('keydown', aoTeclar))
</script>

<template>
  <Teleport to="body">
    <div
      v-if="props.aberto"
      class="fixed inset-0 z-50 flex items-end justify-center lg:items-stretch lg:justify-end"
      role="dialog"
      aria-modal="true"
      :aria-label="props.titulo"
    >
      <!-- Backdrop discreto -->
      <div
        class="fixed inset-0 bg-tinta/25 transition-opacity duration-200"
        aria-hidden="true"
        @click="emit('fechar')"
      />

      <!-- Painel: bottom sheet no mobile, painel lateral no desktop -->
      <div
        class="relative z-10 flex max-h-[90dvh] w-full flex-col rounded-t-[var(--radius-sheet)] border border-linha bg-papel p-6 shadow-[var(--shadow-elevado)] lg:h-dvh lg:max-h-dvh lg:max-w-md lg:rounded-l-[var(--radius-sheet)] lg:rounded-tr-none"
      >
        <div class="mx-auto mb-3 h-1 w-10 rounded-full bg-linha lg:hidden" />

        <header class="flex items-start justify-between gap-4 border-b border-linha pb-4">
          <div>
            <h2 class="text-lg font-semibold text-tinta">
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
            class="rounded-lg p-1.5 text-grafite-suave hover:bg-nevoa hover:text-tinta"
            aria-label="Fechar painel"
            @click="emit('fechar')"
          >
            ✕
          </button>
        </header>

        <div class="flex-1 overflow-y-auto py-5">
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
