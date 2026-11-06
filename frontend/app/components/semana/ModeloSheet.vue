<script setup lang="ts">
import { extrairMensagemErro } from '~/composables/useApi'
import type { ModeloBlocoRead } from '~/stores/blocos'
import type { CategoriaRead } from '~/stores/categorias'
import { NOMES_DIAS_SEMANA } from '~/utils/tempo'

interface Props {
  aberto: boolean
  /** `null` cria um novo modelo. */
  modelo: ModeloBlocoRead | null
  /** Dia da semana sugerido ao criar (`0=domingo .. 6=sábado`). */
  diaSemanaInicial: number
  categorias: CategoriaRead[]
}

const props = defineProps<Props>()

const emit = defineEmits<{
  fechar: []
}>()

const blocosStore = useBlocosStore()

const titulo = ref('')
const categoriaId = ref('')
const diaSemana = ref(1)
const horaInicio = ref('08:00')
const horaFim = ref('09:30')
const salvando = ref(false)
const confirmandoExclusao = ref(false)
const erro = ref<string | null>(null)

function preencher() {
  erro.value = null
  confirmandoExclusao.value = false
  const m = props.modelo
  if (m) {
    titulo.value = m.titulo
    categoriaId.value = m.categoria_id
    diaSemana.value = m.dia_semana
    horaInicio.value = m.hora_inicio.slice(0, 5)
    horaFim.value = m.hora_fim.slice(0, 5)
    return
  }
  titulo.value = ''
  categoriaId.value = props.categorias[0]?.id ?? ''
  diaSemana.value = props.diaSemanaInicial
  horaInicio.value = '08:00'
  horaFim.value = '09:30'
}

watch(
  () => [props.aberto, props.modelo, props.diaSemanaInicial],
  ([aberto]) => {
    if (aberto) preencher()
  },
  { immediate: true },
)

async function executar(acao: () => Promise<void>, mensagemErro: string) {
  erro.value = null
  salvando.value = true
  try {
    await acao()
    emit('fechar')
  }
  catch (e: unknown) {
    erro.value = extrairMensagemErro(e, mensagemErro)
  }
  finally {
    salvando.value = false
  }
}

function salvar() {
  const dados = {
    categoria_id: categoriaId.value,
    titulo: titulo.value.trim(),
    dia_semana: diaSemana.value,
    hora_inicio: `${horaInicio.value}:00`,
    hora_fim: `${horaFim.value}:00`,
  }
  const atual = props.modelo
  return executar(async () => {
    if (atual) await blocosStore.atualizarModelo(atual.id, dados)
    else await blocosStore.criarModelo(dados)
  }, 'Não foi possível salvar o modelo semanal.')
}

function excluir() {
  const atual = props.modelo
  if (!atual) return
  return executar(async () => {
    await blocosStore.excluirModelo(atual.id)
  }, 'Não foi possível remover o modelo semanal.')
}
</script>

<template>
  <BaseSheet
    :aberto="props.aberto"
    :titulo="props.modelo ? 'Editar bloco do modelo' : 'Novo bloco no modelo semanal'"
    descricao="Este bloco será criado automaticamente quando você aplicar o modelo na semana."
    @fechar="emit('fechar')"
  >
    <form
      id="form-modelo"
      class="flex flex-col gap-5"
      @submit.prevent="salvar"
    >
      <BaseInput
        id="mod-titulo"
        v-model="titulo"
        label="Título"
        placeholder="Ex.: Estudo dirigido"
        obrigatorio
      />

      <BlocoCategoriaSelector
        v-model="categoriaId"
        :categorias="props.categorias"
      />

      <div>
        <label
          for="mod-dia"
          class="block text-sm font-medium text-tinta"
        >
          Dia da semana
        </label>
        <select
          id="mod-dia"
          v-model.number="diaSemana"
          class="mt-1.5 min-h-11 w-full rounded-[var(--radius-bloco)] border border-linha bg-papel px-3.5 py-2.5 text-sm text-tinta"
        >
          <option
            v-for="(nomeDia, idx) in NOMES_DIAS_SEMANA"
            :key="idx"
            :value="idx"
          >
            {{ nomeDia }}
          </option>
        </select>
      </div>

      <div class="grid grid-cols-2 gap-3">
        <BaseInput
          id="mod-ini"
          v-model="horaInicio"
          tipo="time"
          tabular
          label="Início"
          obrigatorio
        />
        <BaseInput
          id="mod-fim"
          v-model="horaFim"
          tipo="time"
          tabular
          label="Término"
          obrigatorio
        />
      </div>

      <p
        v-if="erro"
        class="rounded-[var(--radius-bloco)] border border-rosa-cha-200 bg-rosa-cha-50 px-3.5 py-2.5 text-sm text-erro"
        role="alert"
      >
        {{ erro }}
      </p>
    </form>

    <template #rodape>
      <div class="flex items-center justify-between gap-2">
        <template v-if="props.modelo">
          <div
            v-if="confirmandoExclusao"
            class="flex items-center gap-2"
            role="alertdialog"
            aria-label="Confirmar exclusão do modelo"
          >
            <span class="text-xs text-tinta">Excluir este modelo?</span>
            <BaseButton
              variante="perigo"
              tamanho="sm"
              class="min-h-11"
              :carregando="salvando"
              @click="excluir"
            >
              Sim, excluir
            </BaseButton>
            <BaseButton
              variante="fantasma"
              tamanho="sm"
              class="min-h-11"
              @click="confirmandoExclusao = false"
            >
              Não
            </BaseButton>
          </div>
          <BaseButton
            v-else
            variante="perigo"
            tamanho="sm"
            class="min-h-11"
            @click="confirmandoExclusao = true"
          >
            Excluir
          </BaseButton>
        </template>
        <span v-else />

        <div
          v-if="!confirmandoExclusao"
          class="flex items-center gap-2"
        >
          <BaseButton
            variante="fantasma"
            tamanho="sm"
            class="min-h-11"
            @click="emit('fechar')"
          >
            Cancelar
          </BaseButton>
          <BaseButton
            tipo="submit"
            form="form-modelo"
            tamanho="sm"
            class="min-h-11"
            :carregando="salvando"
          >
            Salvar modelo
          </BaseButton>
        </div>
      </div>
    </template>
  </BaseSheet>
</template>
