<script setup lang="ts">
import { useFormularioBloco } from '~/components/bloco/useFormularioBloco'
import { extrairMensagemErro } from '~/composables/useApi'
import type { BlocoRead } from '~/stores/blocos'
import type { CategoriaRead } from '~/stores/categorias'
import { formatarDuracaoMinutos } from '~/utils/coresCategoria'

interface Props {
  aberto: boolean
  dataIso: string
  fuso: string
  categorias: CategoriaRead[]
  blocoEditando: BlocoRead | null
  minutoInicialSugerido?: number
}

const props = withDefaults(defineProps<Props>(), {
  minutoInicialSugerido: 480,
})

const emit = defineEmits<{
  fechar: []
  salvo: [bloco: BlocoRead]
  excluido: [blocoRemovido: BlocoRead]
}>()

const blocosStore = useBlocosStore()

const form = useFormularioBloco(props)
const {
  titulo,
  categoriaId,
  tipo,
  horaInicio,
  horaFim,
  notas,
  pausas,
  lembretes,
  repetirNaSemana,
  minutosLiquidosPreview,
} = form

const salvando = ref(false)
const erro = ref<string | null>(null)

watch(
  () => [props.aberto, props.blocoEditando, props.minutoInicialSugerido],
  ([aberto]) => {
    if (aberto) erro.value = null
  },
)

const opcoesTipo = [
  { valor: 'rotina', rotulo: 'Bloco de rotina' },
  { valor: 'compromisso', rotulo: 'Compromisso fixo' },
] as const

async function executar(acao: () => Promise<void>, mensagemErro: string) {
  erro.value = null
  salvando.value = true
  try {
    await acao()
  }
  catch (e: unknown) {
    erro.value = extrairMensagemErro(e, mensagemErro)
  }
  finally {
    salvando.value = false
  }
}

async function salvar() {
  erro.value = null
  const montado = form.montarPayload()
  if (!montado.payload) {
    erro.value = montado.erro ?? null
    return
  }
  const { payload } = montado

  await executar(async () => {
    const atual = props.blocoEditando
    const blocoSalvo = atual
      ? await blocosStore.atualizarBloco(atual.id, payload, atual.versao)
      : await blocosStore.criarBloco(payload)

    if (!atual && repetirNaSemana.value) {
      await blocosStore.criarModelo(form.montarPayloadModelo())
    }

    emit('salvo', blocoSalvo)
    emit('fechar')
  }, 'Não foi possível salvar o bloco.')
}

async function excluir() {
  const copia = props.blocoEditando
  if (!copia) return
  await executar(async () => {
    await blocosStore.excluirBloco(copia.id)
    emit('excluido', copia)
    emit('fechar')
  }, 'Não foi possível excluir o bloco.')
}
</script>

<template>
  <BaseSheet
    :aberto="props.aberto"
    :titulo="props.blocoEditando ? 'Editar bloco' : 'Novo bloco'"
    descricao="Defina o horário, a categoria e eventuais pausas dentro do bloco."
    @fechar="emit('fechar')"
  >
    <form
      id="form-bloco"
      class="flex flex-col gap-5"
      @submit.prevent="salvar"
    >
      <!-- Execução real (apenas ao editar bloco existente) -->
      <BlocoExecucaoRealSecao
        v-if="props.blocoEditando"
        :bloco="props.blocoEditando"
        :data-iso="props.dataIso"
        :fuso="props.fuso"
        :categoria-id="categoriaId"
        :hora-inicio-planejada="horaInicio"
        :hora-fim-planejada="horaFim"
        :pausas-planejadas="pausas"
        :aberto="props.aberto"
        @erro="erro = $event"
        @fechar="emit('fechar')"
      />

      <BaseInput
        id="bloco-titulo"
        v-model="titulo"
        label="O que você vai fazer?"
        placeholder="Ex.: Desenvolvimento da API, Treino de força"
        obrigatorio
      />

      <BlocoCategoriaSelector
        v-model="categoriaId"
        :categorias="props.categorias"
      />

      <!-- Tipo -->
      <div>
        <span class="block text-sm font-medium text-tinta">
          Natureza do bloco
        </span>
        <div class="mt-2 grid grid-cols-2 rounded-[var(--radius-bloco)] bg-nevoa p-1">
          <button
            v-for="opcao in opcoesTipo"
            :key="opcao.valor"
            type="button"
            class="min-h-11 rounded-lg py-1.5 text-xs font-medium transition-colors"
            :class="tipo === opcao.valor ? 'bg-papel text-tinta' : 'text-grafite-suave hover:text-tinta'"
            :aria-pressed="tipo === opcao.valor"
            @click="tipo = opcao.valor"
          >
            {{ opcao.rotulo }}
          </button>
        </div>
      </div>

      <!-- Horários com stepper de 5 min -->
      <div class="grid grid-cols-2 gap-3">
        <BlocoHorarioStepper
          id="bloco-inicio"
          v-model="horaInicio"
          label="Início"
          campo="inicio"
        />
        <BlocoHorarioStepper
          id="bloco-fim"
          v-model="horaFim"
          label="Término"
          campo="fim"
        />
      </div>

      <!-- Pausas planejadas -->
      <PausasEditor
        v-model="pausas"
        :hora-inicio-bloco="horaInicio"
      />

      <!-- Repetir na rotina semanal (apenas na criação) -->
      <label
        v-if="!props.blocoEditando"
        class="flex min-h-11 cursor-pointer items-center gap-3 rounded-[var(--radius-bloco)] border border-linha bg-nevoa/60 p-3"
      >
        <input
          v-model="repetirNaSemana"
          type="checkbox"
          class="h-4 w-4 accent-tinta"
        >
        <span class="text-xs text-tinta">
          Repetir toda semana neste mesmo dia e horário
        </span>
      </label>

      <!-- Lembretes do modelo semanal -->
      <LembretesEditor
        v-if="!props.blocoEditando && repetirNaSemana"
        v-model="lembretes"
      />

      <BaseInput
        id="bloco-notas"
        v-model="notas"
        label="Notas (opcional)"
        placeholder="Detalhes ou links rápidos"
      />

      <p
        v-if="erro"
        class="rounded-[var(--radius-bloco)] border border-rosa-cha-200 bg-rosa-cha-50 px-3.5 py-2.5 text-sm text-erro"
        role="alert"
      >
        {{ erro }}
      </p>
    </form>

    <template #rodape>
      <div class="space-y-3">
        <!-- Resumo ao vivo de horas líquidas -->
        <div class="flex items-center justify-between text-xs text-grafite-suave">
          <span>Tempo líquido planejado</span>
          <strong class="tabular text-sm font-semibold text-tinta">
            {{ formatarDuracaoMinutos(minutosLiquidosPreview) }} líquidas
          </strong>
        </div>

        <div class="flex items-center justify-between gap-2">
          <BaseButton
            v-if="props.blocoEditando"
            variante="perigo"
            tamanho="sm"
            :carregando="salvando"
            @click="excluir"
          >
            Excluir bloco
          </BaseButton>
          <span v-else />

          <div class="flex items-center gap-2">
            <BaseButton
              variante="fantasma"
              tamanho="sm"
              @click="emit('fechar')"
            >
              Cancelar
            </BaseButton>
            <BaseButton
              tipo="submit"
              form="form-bloco"
              tamanho="sm"
              :carregando="salvando"
            >
              Salvar bloco
            </BaseButton>
          </div>
        </div>
      </div>
    </template>
  </BaseSheet>
</template>
