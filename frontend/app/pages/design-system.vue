<script setup lang="ts">
import {
  ESTILOS_CATEGORIA,
  LISTA_CORES_CATEGORIA,
  formatarDuracaoMinutos,
  type CorCategoria,
} from '~/utils/coresCategoria'

const corAtiva = ref<CorCategoria>('salvia')
const textoDemo = ref('Estudo de arquitetura')
const sheetDemo = ref(false)
</script>

<template>
  <div class="space-y-10">
    <header>
      <h1 class="text-2xl font-semibold text-tinta">
        Design System — Ritmo
      </h1>
      <p class="mt-1 text-sm text-grafite-suave">
        Direção visual: papel de agenda sob luz da manhã, trios pastéis e algarismos tabulares em Figtree.
      </p>
    </header>

    <!-- Paleta de categorias -->
    <section class="rounded-[var(--radius-bloco)] border border-linha bg-papel p-6">
      <h2 class="text-lg font-semibold text-tinta">
        Trios de categoria (Lavado 50 · Pastel 200 · Tinta 700)
      </h2>
      <div class="mt-4 flex flex-wrap gap-2">
        <BaseChip
          v-for="item in LISTA_CORES_CATEGORIA"
          :key="item.token"
          :cor="item.token"
          :selecionado="corAtiva === item.token"
          interativo
          @click="corAtiva = item.token"
        >
          {{ item.label }}
        </BaseChip>
      </div>

      <!-- Demonstração: Plano em contorno, real em preenchimento -->
      <div class="mt-6">
        <p class="text-sm font-medium text-tinta">
          Princípio 1 — Plano em contorno, real em preenchimento:
        </p>
        <div
          class="relative mt-2 overflow-hidden rounded-[var(--radius-bloco)] p-4"
          :class="ESTILOS_CATEGORIA[corAtiva].blocoContorno"
        >
          <div
            class="absolute inset-y-0 left-0 w-2/3 rounded-l-[8px] opacity-65"
            :class="ESTILOS_CATEGORIA[corAtiva].blocoPreenchimento"
          />
          <div class="relative flex items-center justify-between text-sm font-medium">
            <span>{{ textoDemo }}</span>
            <span class="tabular">{{ formatarDuracaoMinutos(95) }} de {{ formatarDuracaoMinutos(120) }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- Componentes base -->
    <section class="grid gap-6 rounded-[var(--radius-bloco)] border border-linha bg-papel p-6 sm:grid-cols-2">
      <div class="space-y-4">
        <h2 class="text-lg font-semibold text-tinta">
          Botões
        </h2>
        <div class="flex flex-wrap gap-2">
          <BaseButton variante="primario">
            Salvar bloco
          </BaseButton>
          <BaseButton variante="secundario">
            Editar
          </BaseButton>
          <BaseButton variante="fantasma">
            Cancelar
          </BaseButton>
          <BaseButton variante="perigo">
            Excluir bloco
          </BaseButton>
        </div>
      </div>

      <div class="space-y-4">
        <h2 class="text-lg font-semibold text-tinta">
          Campos e Sheet
        </h2>
        <BaseInput
          id="demo-titulo"
          v-model="textoDemo"
          label="Título do bloco"
          dica="Texto atualizado ao vivo no bloco acima."
        />
        <BaseButton
          variante="secundario"
          @click="sheetDemo = true"
        >
          Abrir BaseSheet (modal responsivo)
        </BaseButton>
      </div>
    </section>

    <BaseSheet
      :aberto="sheetDemo"
      titulo="Exemplo de BaseSheet"
      descricao="Bottom sheet no mobile e painel lateral a partir de 1024px."
      @fechar="sheetDemo = false"
    >
      <p class="text-sm text-tinta">
        Este componente serve de base para o editor de categorias (F3) e para o <code>BlocoSheet</code> na timeline (F4).
      </p>
      <template #rodape>
        <div class="flex justify-end">
          <BaseButton @click="sheetDemo = false">
            Fechar
          </BaseButton>
        </div>
      </template>
    </BaseSheet>
  </div>
</template>
