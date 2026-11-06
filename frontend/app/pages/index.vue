<script setup lang="ts">
import { extrairMensagemErro } from '~/composables/useApi'
import type { BlocoRead } from '~/stores/blocos'
import type { ExecucaoRead } from '~/stores/execucoes'
import { formatarDuracaoSegundos } from '~/utils/coresCategoria'
import { formatarDataCabecalho, somarDiasIso } from '~/utils/tempo'

const TEMPO_TOAST_DESFAZER_MS = 6000

const auth = useAuthStore()
const categoriasStore = useCategoriasStore()
const blocosStore = useBlocosStore()
const execucoesStore = useExecucoesStore()

const fusoUsuario = computed(() => auth.usuario?.fuso || Intl.DateTimeFormat().resolvedOptions().timeZone)
const { dataAtivaIso, irParaHoje } = useDiaAtual(fusoUsuario)
const tickRelogio = ref(0)
let timerTick: ReturnType<typeof setInterval> | null = null

const sheetAberto = ref(false)
const blocoSelecionado = ref<BlocoRead | null>(null)
const minutoSugerido = ref(480)
const erroOperacao = ref<string | null>(null)
const ultimoExcluido = ref<BlocoRead | null>(null)
const carregouUmaVez = ref(false)
const blocosOcupados = ref<Set<string>>(new Set())
const desmarcarPendente = ref<{ bloco: BlocoRead, execucao: ExecucaoRead } | null>(null)
let timerToastDesfazer: ReturnType<typeof setTimeout> | null = null

// Evita o falso "Seu dia está livre" enquanto os blocos ainda carregam.
const carregandoDia = computed(() => blocosStore.carregando || !carregouUmaVez.value)

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
  finally {
    carregouUmaVez.value = true
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
  if (timerToastDesfazer) clearTimeout(timerToastDesfazer)
})

function navegarDia(delta: number) {
  dataAtivaIso.value = somarDiasIso(dataAtivaIso.value, delta)
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

/** Só a execução criada por "Fiz como planejado" (sem pausas) pode ser desfeita sem aviso. */
function ehConfirmacaoSimples(ex: ExecucaoRead): boolean {
  return ex.origem === 'confirmacao' && ex.pausas.length === 0
}

async function executarComTrava(blocoId: string, acao: () => Promise<unknown>, mensagemErro: string) {
  if (blocosOcupados.value.has(blocoId)) return
  blocosOcupados.value = new Set(blocosOcupados.value).add(blocoId)
  erroOperacao.value = null
  try {
    await acao()
  }
  catch (e: unknown) {
    erroOperacao.value = extrairMensagemErro(e, mensagemErro)
  }
  finally {
    const restante = new Set(blocosOcupados.value)
    restante.delete(blocoId)
    blocosOcupados.value = restante
  }
}

async function alternarConfirmacaoBloco(bloco: BlocoRead) {
  const ex = execucoesStore.execucaoPrincipalDoBloco(bloco.id)
  if (ex && ex.status === 'concluida') {
    if (!ehConfirmacaoSimples(ex)) {
      desmarcarPendente.value = { bloco, execucao: ex }
      return
    }
    await executarComTrava(
      bloco.id,
      () => execucoesStore.excluirExecucao(ex.id),
      'Não foi possível alterar a confirmação do bloco.',
    )
    return
  }
  await executarComTrava(
    bloco.id,
    () => execucoesStore.confirmarBloco(bloco.id, 'concluida'),
    'Não foi possível alterar a confirmação do bloco.',
  )
}

async function confirmarDesmarcar() {
  const pendente = desmarcarPendente.value
  if (!pendente) return
  desmarcarPendente.value = null
  await executarComTrava(
    pendente.bloco.id,
    () => execucoesStore.excluirExecucao(pendente.execucao.id),
    'Não foi possível excluir o registro de execução.',
  )
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
  if (timerToastDesfazer) clearTimeout(timerToastDesfazer)
  timerToastDesfazer = setTimeout(() => {
    ultimoExcluido.value = null
  }, TEMPO_TOAST_DESFAZER_MS)
}

async function desfazerExclusao() {
  if (!ultimoExcluido.value) return
  const b = ultimoExcluido.value
  ultimoExcluido.value = null
  if (timerToastDesfazer) clearTimeout(timerToastDesfazer)
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
          <span
            v-if="carregandoDia"
            class="inline-block h-4 w-64 max-w-full animate-pulse rounded bg-linha align-middle"
            role="status"
            aria-label="Carregando blocos do dia"
          />
          <template v-else-if="blocosDoDia.length">
            {{ blocosDoDia.length }} bloco(s) · {{ formatarDuracaoSegundos(totalPlanejadoSegundos) }} planejadas
            <template v-if="totalExecutadoSegundos > 0">
              · <span class="font-medium text-tinta">{{ formatarDuracaoSegundos(totalExecutadoSegundos) }} executadas</span>
            </template>
          </template>
          <template v-else>
            Seu dia está livre. Adicione o primeiro bloco pela régua ou pelo botão "Novo bloco".
          </template>
        </p>
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <div class="inline-flex rounded-[var(--radius-bloco)] border border-linha bg-papel p-0.5">
          <button
            type="button"
            class="min-h-11 min-w-11 rounded-lg px-2.5 text-sm font-medium text-tinta hover:bg-nevoa"
            aria-label="Dia anterior"
            @click="navegarDia(-1)"
          >
            ←
          </button>
          <button
            type="button"
            class="min-h-11 rounded-lg px-3 text-sm font-medium text-tinta hover:bg-nevoa"
            @click="irParaHoje"
          >
            Hoje
          </button>
          <button
            type="button"
            class="min-h-11 min-w-11 rounded-lg px-2.5 text-sm font-medium text-tinta hover:bg-nevoa"
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
        class="min-h-11 px-2 font-medium text-ardosia-700 hover:underline"
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
      :blocos-ocupados="blocosOcupados"
      :aria-busy="carregandoDia"
      @criar-em-minuto="abrirNovoBloco"
      @selecionar-bloco="abrirEdicaoBloco"
      @mover-ou-redimensionar="aoMoverOuRedimensionar"
      @alternar-confirmacao="alternarConfirmacaoBloco"
      @iniciar-cronometro="iniciarCronometroBloco"
    />

    <!-- Confirmação ao desmarcar uma execução que não veio de "Fiz como planejado" -->
    <BaseSheet
      :aberto="desmarcarPendente !== null"
      titulo="Excluir registro de execução?"
      descricao="Este bloco foi registrado com cronômetro, pausas ou horários ajustados. Desmarcar apaga esse registro."
      @fechar="desmarcarPendente = null"
    >
      <p
        v-if="desmarcarPendente"
        class="text-sm text-tinta"
      >
        {{ desmarcarPendente.bloco.titulo }}:
        <span class="tabular">{{ formatarDuracaoSegundos(desmarcarPendente.execucao.segundos_liquidos) }}</span>
        registradas serão perdidas.
      </p>
      <template #rodape>
        <div class="flex justify-end gap-2">
          <BaseButton
            variante="secundario"
            @click="desmarcarPendente = null"
          >
            Manter registro
          </BaseButton>
          <BaseButton
            variante="perigo"
            @click="confirmarDesmarcar"
          >
            Excluir registro
          </BaseButton>
        </div>
      </template>
    </BaseSheet>

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
