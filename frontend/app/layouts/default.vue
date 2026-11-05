<script setup lang="ts">
const route = useRoute()
const auth = useAuthStore()
const conexao = useConexaoStore()
const syncStore = useSyncStore()

onMounted(() => {
  conexao.iniciarMonitoramento()
  conexao.verificar()
  syncStore.atualizarContadorPendencias()
})

const itensNavegacao = [
  { para: '/', rotulo: 'Hoje', descricao: 'Régua diária' },
  { para: '/semana', rotulo: 'Semana', descricao: 'Visão semanal' },
  { para: '/resumo', rotulo: 'Resumo', descricao: 'Horas líquidas' },
  { para: '/categorias', rotulo: 'Categorias', descricao: 'Áreas e metas' },
  { para: '/ajustes', rotulo: 'Ajustes', descricao: 'Conta e fuso' },
] as const

function rotaAtiva(caminho: string): boolean {
  if (caminho === '/') return route.path === '/'
  return route.path.startsWith(caminho)
}
</script>

<template>
  <div class="flex min-h-dvh flex-col bg-nevoa text-tinta lg:flex-row">
    <!-- Barra lateral no desktop (>= 1024px) -->
    <aside
      class="hidden lg:flex lg:w-64 lg:shrink-0 lg:flex-col lg:justify-between lg:border-r lg:border-linha lg:bg-papel lg:px-5 lg:py-7"
      aria-label="Navegação principal"
    >
      <div>
        <div class="flex items-baseline justify-between px-2">
          <NuxtLink
            to="/"
            class="text-xl font-semibold text-tinta"
          >
            Ritmo
          </NuxtLink>
          <span
            class="inline-flex items-center gap-1.5 text-xs text-grafite-suave"
            :title="conexao.api === 'ok' ? 'Conectado à API' : 'API indisponível (modo offline)'"
          >
            <span
              class="h-2 w-2 rounded-full"
              :class="conexao.api === 'ok' ? 'bg-salvia-700' : 'bg-manteiga-700'"
            />
            {{ conexao.api === 'ok' ? 'Online' : 'Offline' }}
            <span
              v-if="syncStore.pendenciasCount > 0"
              class="tabular text-[10px] font-semibold text-ardosia-700"
              :title="`${syncStore.pendenciasCount} alteração(ões) pendente(s) de sincronização`"
            >
              ({{ syncStore.pendenciasCount }})
            </span>
          </span>
        </div>

        <nav class="mt-8 flex flex-col gap-1">
          <NuxtLink
            v-for="item in itensNavegacao"
            :key="item.para"
            :to="item.para"
            class="flex items-center justify-between rounded-[var(--radius-bloco)] px-3 py-2.5 text-sm font-medium transition-colors duration-150"
            :class="
              rotaAtiva(item.para)
                ? 'bg-ardosia-200/70 text-ardosia-700'
                : 'text-tinta hover:bg-nevoa'
            "
          >
            <span>{{ item.rotulo }}</span>
            <span class="text-xs font-normal text-grafite-suave">{{ item.descricao }}</span>
          </NuxtLink>
        </nav>
      </div>

      <div
        v-if="auth.usuario"
        class="border-t border-linha pt-4"
      >
        <p class="truncate px-2 text-sm font-medium text-tinta">
          {{ auth.usuario.nome }}
        </p>
        <p class="truncate px-2 text-xs text-grafite-suave">
          {{ auth.usuario.fuso }}
        </p>
        <button
          type="button"
          class="mt-3 w-full rounded-[var(--radius-bloco)] px-2 py-1.5 text-left text-xs font-medium text-grafite-suave hover:bg-nevoa hover:text-tinta"
          @click="auth.sair()"
        >
          Sair da conta
        </button>
      </div>
    </aside>

    <!-- Conteúdo principal -->
    <div class="flex flex-1 flex-col pb-20 lg:pb-0">
      <!-- Cabeçalho compacto no mobile -->
      <header class="flex items-center justify-between border-b border-linha bg-papel px-5 py-3.5 lg:hidden">
        <NuxtLink
          to="/"
          class="text-lg font-semibold text-tinta"
        >
          Ritmo
        </NuxtLink>
        <div class="flex items-center gap-3">
          <span class="inline-flex items-center gap-1.5 text-xs text-grafite-suave">
            <span
              class="h-2 w-2 rounded-full"
              :class="conexao.api === 'ok' ? 'bg-salvia-700' : 'bg-manteiga-700'"
            />
            {{ conexao.api === 'ok' ? 'Online' : 'Offline' }}
            <span
              v-if="syncStore.pendenciasCount > 0"
              class="tabular text-[10px] font-semibold text-ardosia-700"
            >
              ({{ syncStore.pendenciasCount }})
            </span>
          </span>
        </div>
      </header>

      <main class="mx-auto w-full max-w-4xl flex-1 px-5 py-8 lg:px-10 lg:py-10">
        <slot />
      </main>
    </div>

    <!-- Barra inferior no mobile (< 1024px) -->
    <nav
      class="fixed inset-x-0 bottom-0 z-30 flex items-center justify-around border-t border-linha bg-papel/95 px-2 py-2 backdrop-blur lg:hidden"
      aria-label="Navegação inferior"
    >
      <NuxtLink
        v-for="item in itensNavegacao"
        :key="item.para"
        :to="item.para"
        class="flex flex-1 flex-col items-center rounded-[var(--radius-bloco)] py-1.5 text-xs font-medium transition-colors duration-150"
        :class="
          rotaAtiva(item.para)
            ? 'bg-ardosia-200/70 text-ardosia-700'
            : 'text-grafite-suave hover:text-tinta'
        "
      >
        <span>{{ item.rotulo }}</span>
      </NuxtLink>
    </nav>
  </div>
</template>
