<script setup lang="ts">
import type { PausaEditavel } from '~/components/bloco/PausasEditor.vue'
import { extrairMensagemErro } from '~/composables/useApi'
import type { BlocoRead } from '~/stores/blocos'
import type { CategoriaRead } from '~/stores/categorias'
import { formatarDuracaoMinutos } from '~/utils/coresCategoria'
import { calcularMinutosLiquidos } from '~/utils/horasLiquidas'
import {
  criarTimestampUtcDeMinutosLocais,
  diaSemanaDeDataIso,
  horaInputParaMinutos,
  minutosDesdeMeiaNoiteNoFuso,
  minutosParaHoraInput,
} from '~/utils/tempo'

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

const titulo = ref('')
const categoriaId = ref('')
const tipo = ref<'rotina' | 'compromisso'>('rotina')
const horaInicio = ref('08:00')
const horaFim = ref('09:00')
const notas = ref('')
const pausas = ref<PausaEditavel[]>([])
const lembretes = ref<number[]>([10])
const repetirNaSemana = ref(false)
const salvando = ref(false)
const erro = ref<string | null>(null)

function preencherFormulario() {
  erro.value = null
  repetirNaSemana.value = false
  lembretes.value = [10]

  if (props.blocoEditando) {
    const b = props.blocoEditando
    titulo.value = b.titulo
    categoriaId.value = b.categoria_id
    tipo.value = b.tipo
    const iniMin = minutosDesdeMeiaNoiteNoFuso(b.inicio, props.dataIso, props.fuso)
    const fimMin = minutosDesdeMeiaNoiteNoFuso(b.fim, props.dataIso, props.fuso)
    horaInicio.value = minutosParaHoraInput(iniMin)
    horaFim.value = minutosParaHoraInput(fimMin)
    notas.value = b.notas ?? ''
    pausas.value = b.pausas_planejadas.map((p) => {
      const pIni = minutosDesdeMeiaNoiteNoFuso(p.inicio, props.dataIso, props.fuso)
      const pFim = minutosDesdeMeiaNoiteNoFuso(p.fim, props.dataIso, props.fuso)
      return {
        inicioHora: minutosParaHoraInput(pIni),
        fimHora: minutosParaHoraInput(pFim),
      }
    })
  }
  else {
    titulo.value = ''
    categoriaId.value = props.categorias[0]?.id ?? ''
    tipo.value = 'rotina'
    const ini = props.minutoInicialSugerido
    const fim = Math.min(1440, ini + 60)
    horaInicio.value = minutosParaHoraInput(ini)
    horaFim.value = minutosParaHoraInput(fim)
    notas.value = ''
    pausas.value = []
  }
}

watch(
  () => [props.aberto, props.blocoEditando, props.minutoInicialSugerido],
  ([ab]) => {
    if (ab) preencherFormulario()
  },
  { immediate: true },
)

const intervaloMinutos = computed(() => {
  const ini = horaInputParaMinutos(horaInicio.value)
  let fim = horaInputParaMinutos(horaFim.value)
  if (fim <= ini) {
    fim += 1440
  }
  return { ini, fim }
})

const minutosLiquidosPreview = computed(() => {
  const { ini, fim } = intervaloMinutos.value
  const intervalosPausa = pausas.value
    .map((p) => {
      let pIni = horaInputParaMinutos(p.inicioHora)
      let pFim = horaInputParaMinutos(p.fimHora)
      if (pIni < ini) pIni += 1440
      if (pFim < pIni) pFim += 1440
      return { inicioMin: pIni, fimMin: pFim }
    })
    .filter(p => p.fimMin > p.inicioMin)
  return calcularMinutosLiquidos(ini, fim, intervalosPausa)
})

function ajustarMinutos(campo: 'inicio' | 'fim', delta: number) {
  if (campo === 'inicio') {
    const atual = horaInputParaMinutos(horaInicio.value)
    horaInicio.value = minutosParaHoraInput(Math.max(0, Math.min(1435, atual + delta)))
  }
  else {
    const bruto = horaInputParaMinutos(horaFim.value)
    const atual = bruto === 0 && delta < 0 ? 1440 : bruto
    horaFim.value = minutosParaHoraInput(Math.max(5, Math.min(1440, atual + delta)))
  }
}

async function salvar() {
  erro.value = null
  if (!categoriaId.value) {
    erro.value = 'Selecione uma categoria para o bloco.'
    return
  }

  const { ini, fim } = intervaloMinutos.value
  if (fim <= ini) {
    erro.value = 'O horário de término deve ser posterior ao início.'
    return
  }

  const inicioIso = criarTimestampUtcDeMinutosLocais(props.dataIso, ini, props.fuso)
  const fimIso = criarTimestampUtcDeMinutosLocais(props.dataIso, fim, props.fuso)

  const pausasPayload = []
  for (const p of pausas.value) {
    let pIni = horaInputParaMinutos(p.inicioHora)
    let pFim = horaInputParaMinutos(p.fimHora)
    if (pIni < ini) pIni += 1440
    if (pFim < pIni) pFim += 1440
    if (pFim <= pIni) {
      erro.value = 'O término de cada pausa deve ser posterior ao início da pausa.'
      return
    }
    if (pIni < ini || pFim > fim) {
      erro.value = 'Todas as pausas devem ficar contidas dentro do horário do bloco.'
      return
    }
    pausasPayload.push({
      inicio: criarTimestampUtcDeMinutosLocais(props.dataIso, pIni, props.fuso),
      fim: criarTimestampUtcDeMinutosLocais(props.dataIso, pFim, props.fuso),
    })
  }

  salvando.value = true
  try {
    let blocoSalvo: BlocoRead
    if (props.blocoEditando) {
      blocoSalvo = await blocosStore.atualizarBloco(
        props.blocoEditando.id,
        {
          categoria_id: categoriaId.value,
          tipo: tipo.value,
          titulo: titulo.value.trim(),
          notas: notas.value.trim() || null,
          data_local: props.dataIso,
          inicio: inicioIso,
          fim: fimIso,
          pausas: pausasPayload,
        },
        props.blocoEditando.versao,
      )
    }
    else {
      blocoSalvo = await blocosStore.criarBloco({
        categoria_id: categoriaId.value,
        tipo: tipo.value,
        titulo: titulo.value.trim(),
        notas: notas.value.trim() || null,
        data_local: props.dataIso,
        inicio: inicioIso,
        fim: fimIso,
        pausas: pausasPayload,
      })

      if (repetirNaSemana.value) {
        await blocosStore.criarModelo({
          categoria_id: categoriaId.value,
          titulo: titulo.value.trim(),
          dia_semana: diaSemanaDeDataIso(props.dataIso),
          hora_inicio: `${horaInicio.value}:00`,
          hora_fim: `${horaFim.value}:00`,
          pausas: pausas.value.map((p) => {
            let pIni = horaInputParaMinutos(p.inicioHora)
            let pFim = horaInputParaMinutos(p.fimHora)
            if (pIni < ini) pIni += 1440
            if (pFim <= pIni) pFim += 1440
            return {
              offset_min: Math.max(0, pIni - ini),
              duracao_min: Math.max(1, pFim - pIni),
            }
          }),
          lembretes: lembretes.value,
          ativo: true,
        })
      }
    }

    emit('salvo', blocoSalvo)
    emit('fechar')
  }
  catch (e: unknown) {
    erro.value = extrairMensagemErro(e, 'Não foi possível salvar o bloco.')
  }
  finally {
    salvando.value = false
  }
}

async function excluir() {
  if (!props.blocoEditando) return
  erro.value = null
  salvando.value = true
  try {
    const copia = props.blocoEditando
    await blocosStore.excluirBloco(copia.id)
    emit('excluido', copia)
    emit('fechar')
  }
  catch (e: unknown) {
    erro.value = extrairMensagemErro(e, 'Não foi possível excluir o bloco.')
  }
  finally {
    salvando.value = false
  }
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
      <BaseInput
        id="bloco-titulo"
        v-model="titulo"
        label="O que você vai fazer?"
        placeholder="Ex.: Desenvolvimento da API, Treino de força"
        obrigatorio
      />

      <!-- Categoria -->
      <div>
        <span class="block text-sm font-medium text-tinta">
          Categoria
        </span>
        <div class="mt-2 flex flex-wrap gap-2">
          <BaseChip
            v-for="cat in props.categorias"
            :key="cat.id"
            :cor="cat.cor"
            :selecionado="categoriaId === cat.id"
            interativo
            @click="categoriaId = cat.id"
          >
            {{ cat.nome }}
          </BaseChip>
        </div>
      </div>

      <!-- Tipo -->
      <div>
        <span class="block text-sm font-medium text-tinta">
          Natureza do bloco
        </span>
        <div class="mt-2 grid grid-cols-2 rounded-[var(--radius-bloco)] bg-nevoa p-1">
          <button
            type="button"
            class="rounded-lg py-1.5 text-xs font-medium transition-colors"
            :class="tipo === 'rotina' ? 'bg-papel text-tinta' : 'text-grafite-suave hover:text-tinta'"
            @click="tipo = 'rotina'"
          >
            Bloco de rotina
          </button>
          <button
            type="button"
            class="rounded-lg py-1.5 text-xs font-medium transition-colors"
            :class="tipo === 'compromisso' ? 'bg-papel text-tinta' : 'text-grafite-suave hover:text-tinta'"
            @click="tipo = 'compromisso'"
          >
            Compromisso fixo
          </button>
        </div>
      </div>

      <!-- Horários com stepper de 5 min -->
      <div class="grid grid-cols-2 gap-3">
        <div>
          <BaseInput
            id="bloco-inicio"
            v-model="horaInicio"
            tipo="time"
            tabular
            label="Início"
            obrigatorio
          />
          <div class="mt-1 flex gap-1">
            <button
              type="button"
              class="tabular rounded border border-linha bg-nevoa px-2 py-0.5 text-xs text-grafite-suave hover:text-tinta"
              @click="ajustarMinutos('inicio', -5)"
            >
              -5m
            </button>
            <button
              type="button"
              class="tabular rounded border border-linha bg-nevoa px-2 py-0.5 text-xs text-grafite-suave hover:text-tinta"
              @click="ajustarMinutos('inicio', 5)"
            >
              +5m
            </button>
          </div>
        </div>

        <div>
          <BaseInput
            id="bloco-fim"
            v-model="horaFim"
            tipo="time"
            tabular
            label="Término"
            obrigatorio
          />
          <div class="mt-1 flex gap-1">
            <button
              type="button"
              class="tabular rounded border border-linha bg-nevoa px-2 py-0.5 text-xs text-grafite-suave hover:text-tinta"
              @click="ajustarMinutos('fim', -5)"
            >
              -5m
            </button>
            <button
              type="button"
              class="tabular rounded border border-linha bg-nevoa px-2 py-0.5 text-xs text-grafite-suave hover:text-tinta"
              @click="ajustarMinutos('fim', 5)"
            >
              +5m
            </button>
          </div>
        </div>
      </div>

      <!-- Pausas planejadas -->
      <PausasEditor
        v-model="pausas"
        :hora-inicio-bloco="horaInicio"
      />

      <!-- Repetir na rotina semanal (apenas na criação) -->
      <label
        v-if="!props.blocoEditando"
        class="flex cursor-pointer items-center gap-3 rounded-[var(--radius-bloco)] border border-linha bg-nevoa/60 p-3"
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
