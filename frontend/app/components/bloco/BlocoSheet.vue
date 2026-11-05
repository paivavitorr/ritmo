<script setup lang="ts">
import type { PausaEditavel } from '~/components/bloco/PausasEditor.vue'
import { extrairMensagemErro } from '~/composables/useApi'
import type { BlocoRead } from '~/stores/blocos'
import type { CategoriaRead } from '~/stores/categorias'
import { calcularSegundosLiquidosAoVivo } from '~/stores/execucoes'
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
const execucoesStore = useExecucoesStore()

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

// Edição de execução manual vinculada ao bloco
const mostrarEditorExecucao = ref(false)
const execHoraInicio = ref('08:00')
const execHoraFim = ref('09:00')
const execStatus = ref<'concluida' | 'parcial' | 'pulada'>('concluida')
const execPausas = ref<PausaEditavel[]>([])

const execucaoDoBloco = computed(() =>
  props.blocoEditando
    ? execucoesStore.execucaoPrincipalDoBloco(props.blocoEditando.id)
    : undefined,
)

function preencherEditorExecucao() {
  if (!props.blocoEditando) return
  const ex = execucaoDoBloco.value
  if (ex) {
    const iniMin = minutosDesdeMeiaNoiteNoFuso(ex.inicio, props.dataIso, props.fuso)
    const fimMin = ex.fim
      ? minutosDesdeMeiaNoiteNoFuso(ex.fim, props.dataIso, props.fuso)
      : minutosDesdeMeiaNoiteNoFuso(new Date().toISOString(), props.dataIso, props.fuso)
    execHoraInicio.value = minutosParaHoraInput(iniMin)
    execHoraFim.value = minutosParaHoraInput(Math.max(iniMin + 5, fimMin))
    execStatus.value = ex.status === 'em_andamento' ? 'concluida' : ex.status
    execPausas.value = ex.pausas
      .filter(p => p.fim != null)
      .map((p) => {
        const pIni = minutosDesdeMeiaNoiteNoFuso(p.inicio, props.dataIso, props.fuso)
        const pFim = minutosDesdeMeiaNoiteNoFuso(p.fim!, props.dataIso, props.fuso)
        return {
          inicioHora: minutosParaHoraInput(pIni),
          fimHora: minutosParaHoraInput(pFim),
        }
      })
  }
  else {
    execHoraInicio.value = horaInicio.value
    execHoraFim.value = horaFim.value
    execStatus.value = 'concluida'
    execPausas.value = [...pausas.value]
  }
}

async function confirmarNoSheet(statusAlvo: 'concluida' | 'pulada') {
  if (!props.blocoEditando) return
  erro.value = null
  salvando.value = true
  try {
    await execucoesStore.confirmarBloco(props.blocoEditando.id, statusAlvo)
    preencherEditorExecucao()
  }
  catch (e: unknown) {
    erro.value = extrairMensagemErro(e, 'Não foi possível registrar a execução.')
  }
  finally {
    salvando.value = false
  }
}

async function iniciarCronometroNoSheet() {
  if (!props.blocoEditando) return
  erro.value = null
  salvando.value = true
  try {
    await execucoesStore.iniciarCronometro({
      bloco_id: props.blocoEditando.id,
      categoria_id: props.blocoEditando.categoria_id,
    })
    emit('fechar')
  }
  catch (e: unknown) {
    erro.value = extrairMensagemErro(e, 'Não foi possível iniciar o cronômetro.')
  }
  finally {
    salvando.value = false
  }
}

async function salvarExecucaoManual() {
  if (!props.blocoEditando) return
  erro.value = null
  const ini = horaInputParaMinutos(execHoraInicio.value)
  let fim = horaInputParaMinutos(execHoraFim.value)
  if (fim <= ini) fim += 1440

  const pausasPayload = []
  for (const p of execPausas.value) {
    let pIni = horaInputParaMinutos(p.inicioHora)
    let pFim = horaInputParaMinutos(p.fimHora)
    if (pIni < ini) pIni += 1440
    if (pFim < pIni) pFim += 1440
    if (pFim <= pIni || pIni < ini || pFim > fim) {
      erro.value = 'As pausas da execução devem estar dentro do horário real informado.'
      return
    }
    pausasPayload.push({
      inicio: criarTimestampUtcDeMinutosLocais(props.dataIso, pIni, props.fuso),
      fim: criarTimestampUtcDeMinutosLocais(props.dataIso, pFim, props.fuso),
    })
  }

  const inicioIso = criarTimestampUtcDeMinutosLocais(props.dataIso, ini, props.fuso)
  const fimIso = criarTimestampUtcDeMinutosLocais(props.dataIso, fim, props.fuso)

  salvando.value = true
  try {
    if (execucaoDoBloco.value) {
      await execucoesStore.atualizarManual(execucaoDoBloco.value.id, {
        categoria_id: categoriaId.value,
        bloco_id: props.blocoEditando.id,
        inicio: inicioIso,
        fim: fimIso,
        status: execStatus.value,
        pausas: pausasPayload,
      })
    }
    else {
      await execucoesStore.criarManual({
        categoria_id: categoriaId.value,
        bloco_id: props.blocoEditando.id,
        inicio: inicioIso,
        fim: fimIso,
        status: execStatus.value,
        origem: 'manual',
        pausas: pausasPayload,
      })
    }
    mostrarEditorExecucao.value = false
  }
  catch (e: unknown) {
    erro.value = extrairMensagemErro(e, 'Não foi possível salvar o registro manual.')
  }
  finally {
    salvando.value = false
  }
}

async function limparExecucaoDoBloco() {
  if (!execucaoDoBloco.value) return
  erro.value = null
  salvando.value = true
  try {
    await execucoesStore.excluirExecucao(execucaoDoBloco.value.id)
    mostrarEditorExecucao.value = false
  }
  catch (e: unknown) {
    erro.value = extrairMensagemErro(e, 'Não foi possível remover a execução.')
  }
  finally {
    salvando.value = false
  }
}

function preencherFormulario() {
  erro.value = null
  repetirNaSemana.value = false
  lembretes.value = [10]
  mostrarEditorExecucao.value = false

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
    preencherEditorExecucao()
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
      <!-- Seção de execução real (apenas ao editar bloco existente) -->
      <section
        v-if="props.blocoEditando"
        class="space-y-3 rounded-[var(--radius-bloco)] border border-linha bg-nevoa/60 p-3.5"
      >
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p class="text-xs font-semibold text-tinta">
              Execução real deste bloco
            </p>
            <p class="tabular text-xs text-grafite-suave">
              <template v-if="execucaoDoBloco">
                Status:
                <strong class="text-tinta">{{ execucaoDoBloco.status }}</strong>
                · {{
                  formatarDuracaoMinutos(
                    Math.round(
                      (execucaoDoBloco.status === 'em_andamento' && execucaoDoBloco.fim == null
                        ? calcularSegundosLiquidosAoVivo(execucaoDoBloco, Date.now())
                        : execucaoDoBloco.segundos_liquidos) / 60,
                    ),
                  )
                }} líquidas registradas
              </template>
              <template v-else>
                Ainda não registrado como executado.
              </template>
            </p>
          </div>

          <div class="flex flex-wrap items-center gap-1.5">
            <BaseButton
              tamanho="sm"
              :variante="execucaoDoBloco?.status === 'concluida' ? 'primario' : 'secundario'"
              :carregando="salvando"
              @click="confirmarNoSheet('concluida')"
            >
              ✓ Fiz como planejado
            </BaseButton>
            <BaseButton
              v-if="execucaoDoBloco?.status !== 'em_andamento'"
              tamanho="sm"
              variante="secundario"
              :carregando="salvando"
              @click="iniciarCronometroNoSheet"
            >
              ▶ Cronômetro
            </BaseButton>
            <BaseButton
              tamanho="sm"
              variante="fantasma"
              @click="
                () => {
                  preencherEditorExecucao()
                  mostrarEditorExecucao = !mostrarEditorExecucao
                }
              "
            >
              {{ mostrarEditorExecucao ? 'Ocultar ajuste' : 'Ajustar real' }}
            </BaseButton>
          </div>
        </div>

        <!-- Editor manual de execução -->
        <div
          v-if="mostrarEditorExecucao"
          class="space-y-3 border-t border-linha pt-3"
        >
          <div class="grid grid-cols-3 gap-2">
            <div>
              <label
                for="exec-inicio"
                class="block text-xs font-medium text-grafite-suave"
              >
                Início real
              </label>
              <input
                id="exec-inicio"
                v-model="execHoraInicio"
                type="time"
                class="tabular mt-1 w-full rounded border border-linha bg-papel px-2.5 py-1.5 text-xs text-tinta"
              >
            </div>
            <div>
              <label
                for="exec-fim"
                class="block text-xs font-medium text-grafite-suave"
              >
                Fim real
              </label>
              <input
                id="exec-fim"
                v-model="execHoraFim"
                type="time"
                class="tabular mt-1 w-full rounded border border-linha bg-papel px-2.5 py-1.5 text-xs text-tinta"
              >
            </div>
            <div>
              <label
                for="exec-status"
                class="block text-xs font-medium text-grafite-suave"
              >
                Status
              </label>
              <select
                id="exec-status"
                v-model="execStatus"
                class="mt-1 w-full rounded border border-linha bg-papel px-2.5 py-1.5 text-xs text-tinta"
              >
                <option value="concluida">
                  Concluída
                </option>
                <option value="parcial">
                  Parcial
                </option>
                <option value="pulada">
                  Pulada
                </option>
              </select>
            </div>
          </div>

          <PausasEditor
            v-model="execPausas"
            :hora-inicio-bloco="execHoraInicio"
          />

          <div class="flex items-center justify-between gap-2 pt-1">
            <button
              v-if="execucaoDoBloco"
              type="button"
              class="text-xs font-medium text-erro hover:underline"
              @click="limparExecucaoDoBloco"
            >
              Limpar execução
            </button>
            <span v-else />

            <BaseButton
              tamanho="sm"
              variante="secundario"
              :carregando="salvando"
              @click="salvarExecucaoManual"
            >
              Salvar tempo real
            </BaseButton>
          </div>
        </div>
      </section>
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
