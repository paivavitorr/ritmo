<script setup lang="ts">
/** Lista conflitos e falhas de sincronização, com ações "Tentar novamente" e "Descartar". */
const sync = useSyncStore()

const emit = defineEmits<{ fechar: [] }>()

onMounted(() => {
  void sync.carregarConflitos()
})

const ROTULO_ENTIDADE = {
  bloco: 'Bloco',
  categoria: 'Categoria',
  execucao: 'Execução',
  modelo_bloco: 'Modelo de bloco',
} as const

const ROTULO_ACAO = {
  criar: 'criação',
  atualizar: 'edição',
  excluir: 'exclusão',
} as const

const ROTULO_STATUS = {
  conflito: 'Conflito: o servidor manteve outra versão',
  ignorado: 'Ignorado pelo servidor',
  falhou: 'Falhou após várias tentativas',
} as const

function titulo(payload: Record<string, unknown>): string | null {
  const t = payload.titulo ?? payload.nome
  return typeof t === 'string' ? t : null
}
</script>

<template>
  <section
    class="rounded-2xl border border-ardosia-200 bg-white p-4"
    aria-labelledby="titulo-pendencias"
  >
    <header class="mb-3 flex items-center justify-between gap-2">
      <h2
        id="titulo-pendencias"
        class="text-base font-semibold text-tinta"
      >
        Sincronização
      </h2>
      <div class="flex items-center gap-2">
        <button
          v-if="sync.conflitos.length > 1"
          type="button"
          class="rounded-lg px-2 py-1 text-sm text-ardosia-700 hover:bg-ardosia-50"
          @click="sync.descartarTodosConflitos()"
        >
          Descartar todos
        </button>
        <button
          type="button"
          class="rounded-lg px-2 py-1 text-sm text-ardosia-700 hover:bg-ardosia-50"
          @click="emit('fechar')"
        >
          Fechar
        </button>
      </div>
    </header>

    <p class="mb-3 text-sm text-ardosia-700">
      <span class="tabular">{{ sync.pendenciasCount }}</span>
      {{ sync.pendenciasCount === 1 ? 'alteração aguardando envio' : 'alterações aguardando envio' }}
    </p>

    <p
      v-if="sync.ultimoErro"
      class="mb-3 rounded-lg bg-pessego-50 p-2 text-sm text-pessego-700"
      role="alert"
    >
      {{ sync.ultimoErro }}
    </p>

    <p
      v-if="!sync.conflitos.length"
      class="text-sm text-ardosia-700"
    >
      Nenhum conflito ou falha.
    </p>

    <ul
      v-else
      class="flex flex-col gap-2"
    >
      <li
        v-for="c in sync.conflitos"
        :key="c.id"
        class="rounded-xl border border-pessego-200 bg-pessego-50 p-3"
      >
        <p class="text-sm font-medium text-pessego-700">
          {{ ROTULO_ENTIDADE[c.entidade] }}: {{ ROTULO_ACAO[c.acao] }}
          <span
            v-if="titulo(c.payload)"
            class="font-normal"
          >({{ titulo(c.payload) }})</span>
        </p>
        <p class="text-sm text-ardosia-700">
          {{ ROTULO_STATUS[c.status] }}
        </p>
        <p
          v-if="c.mensagem"
          class="text-xs text-ardosia-700"
        >
          {{ c.mensagem }}
        </p>
        <div class="mt-2 flex gap-2">
          <button
            type="button"
            class="rounded-lg bg-white px-3 py-1 text-sm font-medium text-tinta ring-1 ring-ardosia-200 hover:bg-ardosia-50"
            @click="sync.tentarNovamente(c.id)"
          >
            Tentar novamente
          </button>
          <button
            type="button"
            class="rounded-lg px-3 py-1 text-sm text-pessego-700 hover:bg-white"
            @click="sync.descartarConflito(c.id)"
          >
            Descartar
          </button>
        </div>
      </li>
    </ul>
  </section>
</template>
