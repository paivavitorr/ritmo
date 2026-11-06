<script setup lang="ts">
import type { CategoriaRead } from '~/stores/categorias'

interface Props {
  modelValue: string
  categorias: CategoriaRead[]
  label?: string
}

const props = withDefaults(defineProps<Props>(), {
  label: 'Categoria',
})

const emit = defineEmits<{
  'update:modelValue': [categoriaId: string]
}>()

const idRotulo = useId()
</script>

<template>
  <div>
    <span
      :id="idRotulo"
      class="block text-sm font-medium text-tinta"
    >
      {{ props.label }}
    </span>
    <div
      role="group"
      :aria-labelledby="idRotulo"
      class="mt-2 flex flex-wrap gap-2"
    >
      <BaseChip
        v-for="cat in props.categorias"
        :key="cat.id"
        :cor="cat.cor"
        :selecionado="props.modelValue === cat.id"
        interativo
        class="min-h-11"
        @click="emit('update:modelValue', cat.id)"
      >
        {{ cat.nome }}
      </BaseChip>
    </div>
  </div>
</template>
