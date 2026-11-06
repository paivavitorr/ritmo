<script setup lang="ts">
import type { PausaEditavel } from '~/components/bloco/PausasEditor.vue'
import { extrairMensagemErro } from '~/composables/useApi'
import type { BlocoRead } from '~/stores/blocos'
import { calcularSegundosLiquidosAoVivo } from '~/stores/execucoes'
import { formatarDuracaoMinutos } from '~/utils/coresCategoria'
import {
  intervaloParaPausaIso,
  pausaHoraParaIntervalo,
  pausasIsoParaHora,
  validarPausa,
} from '~/utils/pausas'
import {
  criarTimestampUtcDeMinutosLocais,
  horaInputParaMinutos,
  minutosDesdeMeiaNoiteNoFuso,
  minutosParaHoraInput,
} from '~/utils/tempo'

interface Props {
  bloco: BlocoRead
  dataIso: string
  fuso: string
  categoriaId: string
  /** Horário planejado atual, usado como sugestão quando ainda não há execução. */
  horaInicioPlanejada: string
  horaFimPlanejada: string
  pausasPlanejadas: PausaEditavel[]
  /** Quando o sheet fecha/abre, o editor manual é recolhido. */
  aberto: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  erro: [mensagem: string | null]
  fechar: []
}>()

const execucoesStore = useExecucoesStore()

const salvando = ref(false)
const mostrarEditor = ref(false)
const horaInicio = ref('08:00')
const horaFim = ref('09:00')
const status = ref<'concluida' | 'parcial' | 'pulada'>('concluida')
const pausas = ref<PausaEditavel[]>([])

const execucao = computed(() => execucoesStore.execucaoPrincipalDoBloco(props.bloco.id))

const minutosLiquidosRegistrados = computed(() => {
  const ex = execucao.value
  if (!ex) return 0
  const segundos
    = ex.status === 'em_andamento' && ex.fim == null
      ? calcularSegundosLiquidosAoVivo(ex, Date.now())
      : ex.segundos_liquidos
  return Math.round(segundos / 60)
})

watch(
  () => [props.aberto, props.bloco.id],
  () => {
    mostrarEditor.value = false
  },
)

function preencherEditor() {
  const ex = execucao.value
  if (!ex) {
    horaInicio.value = props.horaInicioPlanejada
    horaFim.value = props.horaFimPlanejada
    status.value = 'concluida'
    pausas.value = [...props.pausasPlanejadas]
    return
  }
  const iniMin = minutosDesdeMeiaNoiteNoFuso(ex.inicio, props.dataIso, props.fuso)
  const fimMin = minutosDesdeMeiaNoiteNoFuso(
    ex.fim ?? new Date().toISOString(),
    props.dataIso,
    props.fuso,
  )
  horaInicio.value = minutosParaHoraInput(iniMin)
  horaFim.value = minutosParaHoraInput(Math.max(iniMin + 5, fimMin))
  status.value = ex.status === 'em_andamento' ? 'concluida' : ex.status
  pausas.value = pausasIsoParaHora(
    ex.pausas.filter(p => p.fim != null).map(p => ({ inicio: p.inicio, fim: p.fim! })),
    props.dataIso,
    props.fuso,
  )
}

function alternarEditor() {
  preencherEditor()
  mostrarEditor.value = !mostrarEditor.value
}

async function executar(acao: () => Promise<void>, mensagemErro: string) {
  emit('erro', null)
  salvando.value = true
  try {
    await acao()
  }
  catch (e: unknown) {
    emit('erro', extrairMensagemErro(e, mensagemErro))
  }
  finally {
    salvando.value = false
  }
}

function confirmar(statusAlvo: 'concluida' | 'pulada') {
  return executar(async () => {
    await execucoesStore.confirmarBloco(props.bloco.id, statusAlvo)
    preencherEditor()
  }, 'Não foi possível registrar a execução.')
}

function iniciarCronometro() {
  return executar(async () => {
    await execucoesStore.iniciarCronometro({
      bloco_id: props.bloco.id,
      categoria_id: props.bloco.categoria_id,
    })
    emit('fechar')
  }, 'Não foi possível iniciar o cronômetro.')
}

async function salvarManual() {
  emit('erro', null)
  const ini = horaInputParaMinutos(horaInicio.value)
  let fim = horaInputParaMinutos(horaFim.value)
  if (fim <= ini) fim += 1440

  const pausasPayload = []
  for (const p of pausas.value) {
    const intervalo = pausaHoraParaIntervalo(p, ini)
    if (validarPausa(intervalo, ini, fim)) {
      emit('erro', 'As pausas da execução devem estar dentro do horário real informado.')
      return
    }
    pausasPayload.push(intervaloParaPausaIso(intervalo, props.dataIso, props.fuso))
  }

  const dados = {
    categoria_id: props.categoriaId,
    bloco_id: props.bloco.id,
    inicio: criarTimestampUtcDeMinutosLocais(props.dataIso, ini, props.fuso),
    fim: criarTimestampUtcDeMinutosLocais(props.dataIso, fim, props.fuso),
    status: status.value,
    pausas: pausasPayload,
  }

  await executar(async () => {
    if (execucao.value) {
      await execucoesStore.atualizarManual(execucao.value.id, dados)
    }
    else {
      await execucoesStore.criarManual({ ...dados, origem: 'manual' })
    }
    mostrarEditor.value = false
  }, 'Não foi possível salvar o registro manual.')
}

function limpar() {
  const ex = execucao.value
  if (!ex) return
  return executar(async () => {
    await execucoesStore.excluirExecucao(ex.id)
    mostrarEditor.value = false
  }, 'Não foi possível remover a execução.')
}

const classeCampo
  = 'tabular mt-1 min-h-11 w-full rounded border border-linha bg-papel px-2.5 py-1.5 text-xs text-tinta'
</script>

<template>
  <section
    class="space-y-3 rounded-[var(--radius-bloco)] border border-linha bg-nevoa/60 p-3.5"
    aria-label="Execução real deste bloco"
  >
    <div class="flex flex-wrap items-center justify-between gap-2">
      <div>
        <p class="text-xs font-semibold text-tinta">
          Execução real deste bloco
        </p>
        <p class="tabular text-xs text-grafite-suave">
          <template v-if="execucao">
            Status:
            <strong class="text-tinta">{{ execucao.status }}</strong>
            · {{ formatarDuracaoMinutos(minutosLiquidosRegistrados) }} líquidas registradas
          </template>
          <template v-else>
            Ainda não registrado como executado.
          </template>
        </p>
      </div>

      <div class="flex flex-wrap items-center gap-1.5">
        <BaseButton
          tamanho="sm"
          class="min-h-11"
          :variante="execucao?.status === 'concluida' ? 'primario' : 'secundario'"
          :carregando="salvando"
          @click="confirmar('concluida')"
        >
          ✓ Fiz como planejado
        </BaseButton>
        <BaseButton
          v-if="execucao?.status !== 'em_andamento'"
          tamanho="sm"
          class="min-h-11"
          variante="secundario"
          :carregando="salvando"
          @click="iniciarCronometro"
        >
          ▶ Cronômetro
        </BaseButton>
        <BaseButton
          tamanho="sm"
          class="min-h-11"
          variante="fantasma"
          @click="alternarEditor"
        >
          {{ mostrarEditor ? 'Ocultar ajuste' : 'Ajustar real' }}
        </BaseButton>
      </div>
    </div>

    <div
      v-if="mostrarEditor"
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
            v-model="horaInicio"
            type="time"
            :class="classeCampo"
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
            v-model="horaFim"
            type="time"
            :class="classeCampo"
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
            v-model="status"
            :class="classeCampo"
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
        v-model="pausas"
        :hora-inicio-bloco="horaInicio"
      />

      <div class="flex items-center justify-between gap-2 pt-1">
        <button
          v-if="execucao"
          type="button"
          class="min-h-11 px-1 text-xs font-medium text-erro hover:underline"
          @click="limpar"
        >
          Limpar execução
        </button>
        <span v-else />

        <BaseButton
          tamanho="sm"
          class="min-h-11"
          variante="secundario"
          :carregando="salvando"
          @click="salvarManual"
        >
          Salvar tempo real
        </BaseButton>
      </div>
    </div>
  </section>
</template>
