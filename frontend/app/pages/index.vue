<script setup lang="ts">
const auth = useAuthStore()
const categoriasStore = useCategoriasStore()

onMounted(() => {
  categoriasStore.carregar()
})

const hojeFormatado = computed(() =>
  new Intl.DateTimeFormat('pt-BR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  }).format(new Date()),
)
</script>

<template>
  <div>
    <header class="flex flex-wrap items-baseline justify-between gap-4">
      <div>
        <h1 class="text-2xl font-semibold capitalize text-tinta">
          {{ hojeFormatado }}
        </h1>
        <p class="mt-1 text-sm text-grafite-suave">
          Olá, {{ auth.usuario?.nome }}. Suas áreas já estão prontas — a régua interativa entra na F4.
        </p>
      </div>

      <NuxtLink to="/categorias">
        <BaseButton
          variante="secundario"
          tamanho="sm"
        >
          Gerenciar categorias
        </BaseButton>
      </NuxtLink>
    </header>

    <!-- Áreas ativas do usuário -->
    <section class="mt-8 rounded-[var(--radius-bloco)] border border-linha bg-papel p-6">
      <h2 class="text-base font-semibold text-tinta">
        Suas áreas de rotina
      </h2>
      <p class="mt-1 text-sm text-grafite-suave">
        Cada bloco planejado usa o contorno pastel da categoria e vai sendo preenchido conforme a execução.
      </p>

      <div class="mt-4 flex flex-wrap gap-2">
        <BaseChip
          v-for="cat in categoriasStore.itens"
          :key="cat.id"
          :cor="cat.cor"
        >
          {{ cat.nome }}
        </BaseChip>
      </div>
    </section>

    <!-- Convite para a timeline (F4) -->
    <section class="mt-6 rounded-[var(--radius-bloco)] border border-dashed border-linha bg-papel/60 p-8 text-center">
      <p class="text-base font-medium text-tinta">
        Seu dia está livre.
      </p>
      <p class="mt-1 text-sm text-grafite-suave">
        Na próxima fase (F4), você poderá arrastar diretamente na régua de 24 horas para criar e ajustar seus blocos.
      </p>
    </section>
  </div>
</template>
