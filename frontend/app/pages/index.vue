<script setup lang="ts">
import { extrairMensagemErro } from '~/composables/useApi'
import type { BlocoRead } from '~/stores/blocos'
import { formatarDuracaoSegundos } from '~/utils/coresCategoria'
import {
  formatarDataCabecalho,
  hojeIsoNoFuso,
  somarDiasIso,
} from '~/utils/tempo'

const auth = useAuthStore()
const categoriasStore = useCategoriasStore()
const blocosStore = useBlocosStore()
const execucoesStore = useExecucoesStore()

const fusoUsuario = computed(() => auth.usuario?.fuso || 'America/Manaus')
const dataAtivaIso = ref(hojeIsoNoFuso(fusoUsuario.value))
const tickRelogio = ref(0)
let timerTick: ReturnType<typeof setInterval> | null = null

const sheetAberto = ref(false)
const blocoSelecionado = ref<BlocoRead | null>(null)
const minutoSugerido = ref(480)
const erroOperacao = ref<string | null>(null)
const ultimoExcluido = ref<BlocoRead | null>(null)

const blocosDoDia = computed(() => blocosStore.blocosDoDia(dataAtivaIso.value))

const totalPlanejadoSegundos = computed(() =>
  blocosDoDia.value.reduce((acc, b) => acc + b.segundos_liquidos_planejados, 0),
)

const totalExecutadoSegundos = computed(() => {
  const _tick = tickRelogio.value
  void _tick
  return blocosDoDia.value.reduce((acc, b) => {
    const lista = execucoesStore.porBlocoId.get(b.id) ?? []
    return (
      acc
      + lista.reduce((s, e) => {
        if (e.status === 'pulada') return s
        if (e.status === 'em_andamento' && e.fim == null) {
          return s + calcularSegundosLiquidosAoVivo(e, Date.now())
        }
        return s + e.segundos_liquidos
      }, 0)
    )
  }, 0)
})

async function carregarDadosDoDia() {
  erroOperacao.value = null
  try {
    await Promise.all([
      categoriasStore.carregar(),
      blocosStore.carregarPeriodo(dataAtivaIso.value, dataAtivaIso.value),
      execucoesStore.carregarPeriodo(dataAtivaIso.value, dataAtivaIso.value),
    ])
  }
  catch (e: unknown) {
    erroOperacao.value = extrairMensagemErro(e, 'Não foi possível carregar os blocos do dia.')
  }
}

watch(dataAtivaIso, carregarDadosDoDia)
onMounted(() => {
  carregarDadosDoDia()
  timerTick = setInterval(() => {
    tickRelogio.value++
  }, 1000)
})

onBeforeUnmount(() => {
  if (timerTick) clearInterval(timerTick)
})

function navegarDia(delta: number) {
  dataAtivaIso.value = somarDiasIso(dataAtivaIso.value, delta)
}

function irParaHoje() {
  dataAtivaIso.value = hojeIsoNoFuso(fusoUsuario.value)
}

function abrirNovoBloco(inicioMin = 480) {
  blocoSelecionado.value = null
  minutoSugerido.value = inicioMin
  sheetAberto.value = true
}

function abrirEdicaoBloco(bloco: BlocoRead) {
  blocoSelecionado.value = bloco
  sheetAberto.value = true
}

async function aoMoverOuRedimensionar(
  bloco: BlocoRead,
  novoIniIso: string,
  novoFimIso: string,
) {
  erroOperacao.value = null
  try {
    await blocosStore.moverOuRedimensionarOtimista(bloco, novoIniIso, novoFimIso)
  }
  catch (e: unknown) {
    erroOperacao.value = extrairMensagemErro(
      e,
      'Não foi possível mover o bloco. A posição original foi restaurada.',
    )
  }
}

async function alternarConfirmacaoBloco(bloco: BlocoRead) {
  erroOperacao.value = null
  const ex = execucoesStore.execucaoPrincipalDoBloco(bloco.id)
  try {
    if (ex && ex.status === 'concluida') {
      await execucoesStore.excluirExecucao(ex.id)
    }
    else {
      await execucoesStore.confirmarBloco(bloco.id, 'concluida')
    }
  }
  catch (e: unknown) {
    erroOperacao.value = extrairMensagemErro(e, 'Não foi possível alterar a confirmação do bloco.')
  }
}

async function iniciarCronometroBloco(bloco: BlocoRead) {
  erroOperacao.value = null
  try {
    await execucoesStore.iniciarCronometro({
      bloco_id: bloco.id,
      categoria_id: bloco.categoria_id,
    })
  }
  catch (e: unknown) {
    erroOperacao.value = extrairMensagemErro(e, 'Não foi possível iniciar o cronômetro.')
  }
}

function aoExcluirBloco(removido: BlocoRead) {
  ultimoExcluido.value = removido
}

async function desfazerExclusao() {
  if (!ultimoExcluido.value) return
  const b = ultimoExcluido.value
  ultimoExcluido.value = null
  try {
    await blocosStore.criarBloco({
      categoria_id: b.categoria_id,
      tipo: b.tipo,
      titulo: b.titulo,
      notas: b.notas,
      data_local: b.data_local,
      inicio: b.inicio,
      fim: b.fim,
      pausas: b.pausas_planejadas.map(p => ({
        inicio: p.inicio,
        fim: p.fim,
      })),
    })
  }
  catch (e: unknown) {
    erroOperacao.value = extrairMensagemErro(e, 'Não foi possível desfazer a exclusão.')
  }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Cabeçalho do dia -->
    <header class="flex flex-wrap items-center justify-between gap-4">
      <div>
        <div class="flex items-center gap-2">
          <h1 class="text-2xl font-semibold capitalize text-tinta">
            {{ formatarDataCabecalho(dataAtivaIso) }}
          </h1>
        </div>
        <p class="tabular mt-1 text-sm text-grafite-suave">
          <template v-if="blocosDoDia.length">
            {{ blocosDoDia.length }} bloco(s) · {{ formatarDuracaoSegundos(totalPlanejadoSegundos) }} planejadas
            <template v-if="totalExecutadoSegundos > 0">
              · <span class="font-medium text-tinta">{{ formatarDuracaoSegundos(totalExecutadoSegundos) }} executadas</span>
            </template>
          </template>
          <template v-else>
            Seu dia está livre. Clique na régua ou use o botão para criar o primeiro bloco.
          </template>
        </p>
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <div class="inline-flex rounded-[var(--radius-bloco)] border border-linha bg-papel p-0.5">
          <button
            type="button"
            class="rounded-lg px-2.5 py-1.5 text-xs font-medium text-tinta hover:bg-nevoa"
            aria-label="Dia anterior"
            @click="navegarDia(-1)"
          >
            ←
          </button>
          <button
            type="button"
            class="rounded-lg px-3 py-1.5 text-xs font-medium text-tinta hover:bg-nevoa"
            @click="irParaHoje"
          >
            Hoje
          </button>
          <button
            type="button"
            class="rounded-lg px-2.5 py-1.5 text-xs font-medium text-tinta hover:bg-nevoa"
            aria-label="Próximo dia"
            @click="navegarDia(1)"
          >
            →
          </button>
        </div>

        <BaseButton
          tamanho="sm"
          @click="abrirNovoBloco(480)"
        >
          + Novo bloco
        </BaseButton>
      </div>
    </header>

    <!-- Widget flutuante de cronômetro ativo -->
    <CronometroAtivo />

    <!-- Alerta de erro ou toast de desfazer exclusão -->
    <p
      v-if="erroOperacao"
      class="rounded-[var(--radius-bloco)] border border-rosa-cha-200 bg-rosa-cha-50 px-4 py-3 text-sm text-erro"
      role="alert"
    >
      {{ erroOperacao }}
    </p>

    <div
      v-if="ultimoExcluido"
      class="flex items-center justify-between gap-4 rounded-[var(--radius-bloco)] border border-linha bg-papel px-4 py-3 text-sm"
      role="status"
    >
      <span>Bloco "{{ ultimoExcluido.titulo }}" excluído.</span>
      <button
        type="button"
        class="font-medium text-ardosia-700 hover:underline"
        @click="desfazerExclusao"
      >
        Desfazer
      </button>
    </div>

    <!-- Régua vertical interativa de 24h -->
    <TimelineDia
      :data-iso="dataAtivaIso"
      :fuso="fusoUsuario"
      :blocos="blocosDoDia"
      :categorias-por-id="categoriasStore.mapaPorId"
      :execucoes-por-bloco-id="execucoesStore.porBlocoId"
      @criar-em-minuto="abrirNovoBloco"
      @selecionar-bloco="abrirEdicaoBloco"
      @mover-ou-redimensionar="aoMoverOuRedimensionar"
      @alternar-confirmacao="alternarConfirmacaoBloco"
      @iniciar-cronometro="iniciarCronometroBloco"
    />

    <!-- Modal responsivo de criação / edição -->
    <BlocoSheet
      :aberto="sheetAberto"
      :data-iso="dataAtivaIso"
      :fuso="fusoUsuario"
      :categorias="categoriasStore.itens"
      :bloco-editando="blocoSelecionado"
      :minuto-inicial-sugerido="minutoSugerido"
      @fechar="sheetAberto = false"
      @excluido="aoExcluirBloco"
    />
  </div>
</template>
