<script setup lang="ts">
interface Props {
  variante?: 'primario' | 'secundario' | 'fantasma' | 'perigo'
  tamanho?: 'sm' | 'md' | 'lg'
  tipo?: 'button' | 'submit' | 'reset'
  carregando?: boolean
  desabilitado?: boolean
  bloco?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  variante: 'primario',
  tamanho: 'md',
  tipo: 'button',
  carregando: false,
  desabilitado: false,
  bloco: false,
})

const classesVariante: Record<NonNullable<Props['variante']>, string> = {
  primario: 'bg-tinta text-papel hover:opacity-92 active:opacity-85',
  secundario: 'bg-papel text-tinta border border-linha hover:bg-ardosia-50',
  fantasma: 'bg-transparent text-tinta hover:bg-linha/50',
  perigo: 'bg-rosa-cha-50 text-erro border border-rosa-cha-200 hover:bg-rosa-cha-200/60',
}

const classesTamanho: Record<NonNullable<Props['tamanho']>, string> = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2.5 text-sm',
  lg: 'px-5 py-3 text-base',
}
</script>

<template>
  <button
    :type="props.tipo"
    :disabled="props.desabilitado || props.carregando"
    class="inline-flex items-center justify-center gap-2 rounded-[var(--radius-bloco)] font-medium transition-opacity duration-150 disabled:cursor-not-allowed disabled:opacity-50"
    :class="[
      classesVariante[props.variante],
      classesTamanho[props.tamanho],
      props.bloco ? 'w-full' : '',
    ]"
  >
    <span
      v-if="props.carregando"
      class="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
      aria-hidden="true"
    />
    <slot />
  </button>
</template>
