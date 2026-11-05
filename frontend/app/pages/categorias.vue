<script setup lang="ts">
import { extrairMensagemErro } from '~/composables/useApi'
import type { CategoriaRead } from '~/stores/categorias'
import {
  ESTILOS_CATEGORIA,
  LISTA_CORES_CATEGORIA,
  formatarDuracaoMinutos,
  type CorCategoria,
} from '~/utils/coresCategoria'

const categoriasStore = useCategoriasStore()
onMounted(async () => {
  try {
    await categoriasStore.carregar()
  }
  catch (e: unknown) {
    erroLista.value = extrairMensagemErro(e, 'Não foi possível carregar as categorias.')
  }
})

const sheetAberto = ref(false)
const editandoId = ref<string | null>(null)
const formNome = ref('')
const formCor = ref<CorCategoria>('ardosia')
const formProdutiva = ref(true)
const formMetaHoras = ref<string>('')
const formOrdem = ref<string>('10')
const salvando = ref(false)
const erroForm = ref<string | null>(null)
const erroLista = ref<string | null>(null)

function abrirNova() {
  editandoId.value = null
  formNome.value = ''
  formCor.value = 'ardosia'
  formProdutiva.value = true
  formMetaHoras.value = ''
  formOrdem.value = String((categoriasStore.itens.length + 1) * 10)
  erroForm.value = null
  sheetAberto.value = true
}

function abrirEdicao(cat: CategoriaRead) {
  editandoId.value = cat.id
  formNome.value = cat.nome
  formCor.value = cat.cor
  formProdutiva.value = cat.conta_como_produtiva
  formMetaHoras.value = cat.meta_semanal_min != null ? String(cat.meta_semanal_min / 60) : ''
  formOrdem.value = String(cat.ordem)
  erroForm.value = null
  sheetAberto.value = true
}

function fecharSheet() {
  sheetAberto.value = false
}

async function salvarCategoria() {
  erroForm.value = null
  salvando.value = true

  const horasNum = formMetaHoras.value.trim() === '' ? null : Number(formMetaHoras.value)
  const metaMin = horasNum != null && !Number.isNaN(horasNum) && horasNum > 0
    ? Math.round(horasNum * 60)
    : null
  const ordemNum = Number(formOrdem.value) || 0

  try {
    if (editandoId.value) {
      await categoriasStore.atualizar(editandoId.value, {
        nome: formNome.value.trim(),
        cor: formCor.value,
        conta_como_produtiva: formProdutiva.value,
        meta_semanal_min: metaMin,
        ordem: ordemNum,
      })
    }
    else {
      await categoriasStore.criar({
        nome: formNome.value.trim(),
        cor: formCor.value,
        conta_como_produtiva: formProdutiva.value,
        meta_semanal_min: metaMin,
        ordem: ordemNum,
      })
    }
    sheetAberto.value = false
  }
  catch (e: unknown) {
    erroForm.value = extrairMensagemErro(e, 'Não foi possível salvar a categoria.')
  }
  finally {
    salvando.value = false
  }
}

async function removerCategoria() {
  if (!editandoId.value) return
  erroForm.value = null
  salvando.value = true
  try {
    await categoriasStore.excluir(editandoId.value)
    sheetAberto.value = false
  }
  catch (e: unknown) {
    erroForm.value = extrairMensagemErro(
      e,
      'Não foi possível excluir esta categoria.',
    )
  }
  finally {
    salvando.value = false
  }
}
</script>

<template>
  <div>
    <header class="flex flex-wrap items-center justify-between gap-4">
      <div>
        <h1 class="text-2xl font-semibold text-tinta">
          Categorias
        </h1>
        <p class="mt-1 text-sm text-grafite-suave">
          Áreas da sua rotina, cores pastéis e metas semanais de horas líquidas.
        </p>
      </div>

      <BaseButton @click="abrirNova">
        Nova categoria
      </BaseButton>
    </header>

    <p
      v-if="erroLista"
      class="mt-6 rounded-[var(--radius-bloco)] border border-rosa-cha-200 bg-rosa-cha-50 px-4 py-3 text-sm text-erro"
      role="alert"
    >
      {{ erroLista }}
    </p>

    <div
      v-if="categoriasStore.carregando && !categoriasStore.itens.length"
      class="mt-10 text-sm text-grafite-suave"
    >
      Carregando suas categorias…
    </div>

    <div
      v-else-if="!categoriasStore.itens.length && !erroLista"
      class="mt-10 rounded-[var(--radius-bloco)] border border-linha bg-papel p-8 text-center"
    >
      <p class="text-base font-medium text-tinta">
        Nenhuma categoria cadastrada.
      </p>
      <p class="mt-1 text-sm text-grafite-suave">
        Crie categorias para organizar seus blocos de rotina.
      </p>
      <div class="mt-5">
        <BaseButton @click="abrirNova">
          Criar primeira categoria
        </BaseButton>
      </div>
    </div>

    <ul
      v-else
      class="mt-8 grid gap-3 sm:grid-cols-2"
    >
      <li
        v-for="cat in categoriasStore.itens"
        :key="cat.id"
        class="flex items-center justify-between gap-4 rounded-[var(--radius-bloco)] border border-linha bg-papel p-4 transition-colors duration-150 hover:border-grafite-suave/40"
      >
        <div class="flex flex-col gap-1.5">
          <div class="flex items-center gap-2">
            <BaseChip :cor="cat.cor">
              {{ cat.nome }}
            </BaseChip>
            <span
              v-if="!cat.conta_como_produtiva"
              class="text-xs text-grafite-suave"
            >
              Descanso / recomposição
            </span>
          </div>

          <p class="tabular text-xs text-grafite-suave">
            <template v-if="cat.meta_semanal_min">
              Meta semanal: {{ formatarDuracaoMinutos(cat.meta_semanal_min) }}
            </template>
            <template v-else>
              Sem meta semanal definida
            </template>
          </p>
        </div>

        <BaseButton
          variante="secundario"
          tamanho="sm"
          @click="abrirEdicao(cat)"
        >
          Editar
        </BaseButton>
      </li>
    </ul>

    <!-- Sheet de criação / edição -->
    <BaseSheet
      :aberto="sheetAberto"
      :titulo="editandoId ? 'Editar categoria' : 'Nova categoria'"
      descricao="Escolha um tom pastel e defina como essa área entra no cálculo do seu dia."
      @fechar="fecharSheet"
    >
      <form
        id="form-categoria"
        class="flex flex-col gap-5"
        @submit.prevent="salvarCategoria"
      >
        <BaseInput
          id="cat-nome"
          v-model="formNome"
          label="Nome da categoria"
          placeholder="Ex.: Trabalho, Estudo, Música"
          obrigatorio
        />

        <div>
          <span class="block text-sm font-medium text-tinta">
            Cor pastel
          </span>
          <div class="mt-2 flex flex-wrap gap-2">
            <BaseChip
              v-for="item in LISTA_CORES_CATEGORIA"
              :key="item.token"
              :cor="item.token"
              :selecionado="formCor === item.token"
              interativo
              @click="formCor = item.token"
            >
              {{ item.label }}
            </BaseChip>
          </div>

          <!-- Pré-visualização do bloco (contorno vs preenchimento) -->
          <div
            class="mt-3 rounded-[var(--radius-bloco)] p-3 text-xs"
            :class="ESTILOS_CATEGORIA[formCor].blocoContorno"
          >
            <div class="flex items-center justify-between font-medium">
              <span>{{ formNome || 'Exemplo de bloco' }}</span>
              <span class="tabular">1h 30min líquidas</span>
            </div>
          </div>
        </div>

        <BaseInput
          id="cat-meta"
          v-model="formMetaHoras"
          tipo="number"
          min="0"
          max="168"
          step="0.5"
          tabular
          label="Meta semanal (em horas, opcional)"
          placeholder="Ex.: 20"
          dica="Deixe em branco se não quiser acompanhar meta semanal nesta área."
        />

        <label class="flex cursor-pointer items-start gap-3 rounded-[var(--radius-bloco)] border border-linha bg-nevoa/60 p-3.5">
          <input
            v-model="formProdutiva"
            type="checkbox"
            class="mt-1 h-4 w-4 accent-tinta"
          >
          <span class="text-sm">
            <span class="block font-medium text-tinta">Conta como carga ativa</span>
            <span class="text-xs text-grafite-suave">
              Desmarque para áreas de sono ou descanso (elas aparecem na régua de 24h, mas não somam na carga de trabalho/estudo).
            </span>
          </span>
        </label>

        <p
          v-if="erroForm"
          class="rounded-[var(--radius-bloco)] border border-rosa-cha-200 bg-rosa-cha-50 px-3.5 py-2.5 text-sm text-erro"
          role="alert"
        >
          {{ erroForm }}
        </p>
      </form>

      <template #rodape>
        <div class="flex items-center justify-between gap-3">
          <BaseButton
            v-if="editandoId"
            variante="perigo"
            :carregando="salvando"
            @click="removerCategoria"
          >
            Excluir categoria
          </BaseButton>
          <span v-else />

          <div class="flex items-center gap-2">
            <BaseButton
              variante="fantasma"
              @click="fecharSheet"
            >
              Cancelar
            </BaseButton>
            <BaseButton
              tipo="submit"
              form="form-categoria"
              :carregando="salvando"
            >
              Salvar categoria
            </BaseButton>
          </div>
        </div>
      </template>
    </BaseSheet>
  </div>
</template>
