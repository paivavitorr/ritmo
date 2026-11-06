<script setup lang="ts">
// Nova versão do app: o usuário decide quando recarregar (registerType: 'prompt').
const { $pwa } = useNuxtApp()

const atualizando = ref(false)

async function atualizar() {
  if (!$pwa || atualizando.value) return
  atualizando.value = true
  try {
    await $pwa.updateServiceWorker(true)
  }
  finally {
    atualizando.value = false
  }
}

function dispensar() {
  void $pwa?.cancelPrompt()
}
</script>

<template>
  <div
    v-if="$pwa?.needRefresh"
    role="status"
    aria-live="polite"
    class="fixed inset-x-4 bottom-[calc(5.5rem+env(safe-area-inset-bottom))] z-40 mx-auto flex max-w-md items-center gap-3 rounded-[var(--radius-bloco)] border border-linha bg-papel px-4 py-3 shadow-[var(--shadow-elevado)] lg:bottom-6 lg:left-auto lg:right-6 lg:mx-0"
  >
    <p class="flex-1 text-sm text-tinta">
      Nova versão disponível
    </p>
    <button
      type="button"
      class="min-h-11 rounded-[var(--radius-bloco)] bg-ardosia-700 px-4 text-sm font-medium text-papel hover:bg-ardosia-700/90 disabled:opacity-60"
      :disabled="atualizando"
      @click="atualizar"
    >
      {{ atualizando ? 'Atualizando…' : 'Atualizar' }}
    </button>
    <button
      type="button"
      class="min-h-11 min-w-11 rounded-[var(--radius-bloco)] text-sm text-grafite-suave hover:bg-nevoa hover:text-tinta"
      aria-label="Dispensar aviso de atualização"
      @click="dispensar"
    >
      <span aria-hidden="true">✕</span>
    </button>
  </div>
</template>
