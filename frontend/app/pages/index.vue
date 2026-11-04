<script setup lang="ts">
const conexao = useConexaoStore()
onMounted(conexao.verificar)

const categorias = [
  { token: 'ardosia', nome: 'Trabalho' },
  { token: 'glicinia', nome: 'Estudo' },
  { token: 'salvia', nome: 'Treino' },
  { token: 'ceu', nome: 'Descanso' },
  { token: 'manteiga', nome: 'Pessoal' },
  { token: 'rosa-cha', nome: 'Compromissos' },
] as const

// Classes completas e estáticas para o Tailwind detectar.
const estilos: Record<(typeof categorias)[number]['token'], string> = {
  'ardosia': 'bg-ardosia-200 text-ardosia-700',
  'glicinia': 'bg-glicinia-200 text-glicinia-700',
  'salvia': 'bg-salvia-200 text-salvia-700',
  'ceu': 'bg-ceu-200 text-ceu-700',
  'manteiga': 'bg-manteiga-200 text-manteiga-700',
  'rosa-cha': 'bg-rosa-cha-200 text-rosa-cha-700',
}

const textoApi = computed(() => ({
  verificando: 'Conectando à API…',
  ok: 'API conectada',
  indisponivel: 'API indisponível. Rode make run-api.',
})[conexao.api])
</script>

<template>
  <main class="mx-auto max-w-xl px-6 py-16">
    <h1 class="text-2xl font-semibold">
      Ritmo
    </h1>
    <p class="mt-2 text-grafite-suave">
      Sua rotina em blocos. Setup inicial pronto — a timeline chega na F4.
    </p>

    <ul class="mt-10 flex flex-wrap gap-2">
      <li
        v-for="c in categorias"
        :key="c.token"
        class="rounded-full px-3 py-1 text-sm font-medium"
        :class="estilos[c.token]"
      >
        {{ c.nome }}
      </li>
    </ul>

    <p
      class="mt-10 text-sm"
      :class="conexao.api === 'indisponivel' ? 'text-erro' : 'text-grafite-suave'"
      role="status"
    >
      {{ textoApi }}
    </p>
  </main>
</template>
