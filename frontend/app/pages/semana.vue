<script setup lang="ts">
import { extrairMensagemErro } from '~/composables/useApi'
import type { BlocoRead, ModeloBlocoRead } from '~/stores/blocos'
import {
  NOMES_DIAS_CURTOS,
  NOMES_DIAS_SEMANA,
  diaSemanaDeDataIso,
  formatarDiaMesCurto,
  hojeIsoNoFuso,
  inicioDaSemanaIso,
  somarDiasIso,
} from '~/utils/tempo'

type Aba = 'agenda' | 'modelo'

const auth = useAuthStore()
const categoriasStore = useCategoriasStore()
const blocosStore = useBlocosStore()

const fusoUsuario = computed(() => auth.usuario?.fuso || 'America/Manaus')
const inicioSemanaPref = computed(() => auth.usuario?.inicio_semana ?? 1)

const inicioSemanaAtiva = ref(
  inicioDaSemanaIso(hojeIsoNoFuso(fusoUsuario.value), inicioSemanaPref.value),
)
const aba = ref<Aba>('agenda')
const aplicandoModelo = ref(false)
const erro = ref<string | null>(null)
const mensagem = ref<string | null>(null)

const abas: Array<{ id: Aba, rotulo: string }> = [
  { id: 'agenda', rotulo: 'Agenda da semana' },
  { id: 'modelo', rotulo: 'Modelo padrão' },
]

// Sheet de bloco concreto
const sheetBlocoAberto = ref(false)
const dataSheetBloco = ref(inicioSemanaAtiva.value)
const blocoEditando = ref<BlocoRead | null>(null)

// Sheet de modelo semanal
const sheetModeloAberto = ref(false)
const modeloEditando = ref<ModeloBlocoRead | null>(null)
const diaSemanaNovoModelo = ref(1)

const diasDaSemana = computed(() =>
  Array.from({ length: 7 }, (_, i) => {
    const dataIso = somarDiasIso(inicioSemanaAtiva.value, i)
    const ds = diaSemanaDeDataIso(dataIso)
    return {
      dataIso,
      nomeCurto: NOMES_DIAS_CURTOS[ds] ?? 'Dia',
      diaMes: formatarDiaMesCurto(dataIso),
      blocos: blocosStore.blocosDoDia(dataIso),
    }
  }),
)

const ordemDiasModelo = computed(() =>
  Array.from({ length: 7 }, (_, i) => {
    const ds = (inicioSemanaPref.value + i) % 7
    return {
      diaSemana: ds,
      nome: NOMES_DIAS_SEMANA[ds] ?? 'Dia',
      itens: blocosStore.modelos.filter(m => m.dia_semana === ds && m.ativo),
    }
  }),
)

async function carregarSemana() {
  erro.value = null
  const fimSemana = somarDiasIso(inicioSemanaAtiva.value, 6)
  try {
    await Promise.all([
      categoriasStore.carregar(),
      blocosStore.carregarPeriodo(inicioSemanaAtiva.value, fimSemana),
      blocosStore.carregarModelos(),
    ])
  }
  catch (e: unknown) {
    erro.value = extrairMensagemErro(e, 'Não foi possível carregar os dados da semana.')
  }
}

watch(inicioSemanaAtiva, carregarSemana)
onMounted(carregarSemana)

function navegarSemana(deltaSemanas: number) {
  inicioSemanaAtiva.value = somarDiasIso(inicioSemanaAtiva.value, deltaSemanas * 7)
}

function irParaSemanaAtual() {
  inicioSemanaAtiva.value = inicioDaSemanaIso(
    hojeIsoNoFuso(fusoUsuario.value),
    inicioSemanaPref.value,
  )
}

async function aplicarModelo() {
  erro.value = null
  mensagem.value = null
  aplicandoModelo.value = true
  try {
    const gerados = await blocosStore.aplicarModeloNaSemana(inicioSemanaAtiva.value)
    mensagem.value = `Modelo semanal aplicado (${gerados.length} bloco(s) sincronizados).`
  }
  catch (e: unknown) {
    erro.value = extrairMensagemErro(e, 'Não foi possível aplicar o modelo semanal.')
  }
  finally {
    aplicandoModelo.value = false
  }
}

function abrirNovoBlocoNoDia(dataIso: string) {
  dataSheetBloco.value = dataIso
  blocoEditando.value = null
  sheetBlocoAberto.value = true
}

function abrirBlocoExistente(bloco: BlocoRead) {
  dataSheetBloco.value = bloco.data_local
  blocoEditando.value = bloco
  sheetBlocoAberto.value = true
}

function abrirNovoModelo(diaSemana = 1) {
  modeloEditando.value = null
  diaSemanaNovoModelo.value = diaSemana
  sheetModeloAberto.value = true
}

function abrirEdicaoModelo(modelo: ModeloBlocoRead) {
  modeloEditando.value = modelo
  sheetModeloAberto.value = true
}

// Abas: setas, Home e End movem a seleção e o foco (padrão WAI-ARIA tabs)
function aoTeclarNaAba(evento: KeyboardEvent, indice: number) {
  const passos: Record<string, number> = { ArrowRight: 1, ArrowLeft: -1 }
  let destino: number
  if (evento.key in passos) destino = (indice + passos[evento.key]! + abas.length) % abas.length
  else if (evento.key === 'Home') destino = 0
  else if (evento.key === 'End') destino = abas.length - 1
  else return

  evento.preventDefault()
  aba.value = abas[destino]!.id
  nextTick(() => document.getElementById(`aba-${aba.value}`)?.focus())
}
</script>

<template>
  <div class="space-y-6">
    <header class="flex flex-wrap items-center justify-between gap-4">
      <div>
        <h1 class="text-2xl font-semibold text-tinta">
          Semana
        </h1>
        <p class="tabular mt-1 text-sm text-grafite-suave">
          {{ formatarDiaMesCurto(inicioSemanaAtiva) }} a {{ formatarDiaMesCurto(somarDiasIso(inicioSemanaAtiva, 6)) }}
        </p>
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <!-- Alternador Agenda vs Modelo -->
        <div
          class="inline-flex rounded-[var(--radius-bloco)] border border-linha bg-papel p-0.5"
          role="tablist"
          aria-label="Visão da semana"
        >
          <button
            v-for="(item, indice) in abas"
            :id="`aba-${item.id}`"
            :key="item.id"
            type="button"
            role="tab"
            :aria-selected="aba === item.id"
            :aria-controls="`painel-${item.id}`"
            :tabindex="aba === item.id ? 0 : -1"
            class="min-h-11 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors"
            :class="aba === item.id ? 'bg-ardosia-200 text-ardosia-700' : 'text-grafite-suave hover:text-tinta'"
            @click="aba = item.id"
            @keydown="aoTeclarNaAba($event, indice)"
          >
            {{ item.rotulo }}
          </button>
        </div>

        <BaseButton
          variante="secundario"
          tamanho="sm"
          class="min-h-11"
          :carregando="aplicandoModelo"
          @click="aplicarModelo"
        >
          Aplicar modelo nesta semana
        </BaseButton>
      </div>
    </header>

    <p
      v-if="erro"
      class="rounded-[var(--radius-bloco)] border border-rosa-cha-200 bg-rosa-cha-50 px-4 py-3 text-sm text-erro"
      role="alert"
    >
      {{ erro }}
    </p>
    <p
      v-if="mensagem"
      class="rounded-[var(--radius-bloco)] border border-salvia-200 bg-salvia-50 px-4 py-3 text-sm text-salvia-700"
      role="status"
    >
      {{ mensagem }}
    </p>

    <div
      v-if="aba === 'agenda'"
      id="painel-agenda"
      role="tabpanel"
      aria-labelledby="aba-agenda"
    >
      <SemanaAgenda
        :dias="diasDaSemana"
        :fuso="fusoUsuario"
        :categoria-por-id="categoriasStore.mapaPorId"
        @navegar="navegarSemana"
        @semana-atual="irParaSemanaAtual"
        @novo-bloco="abrirNovoBlocoNoDia"
        @abrir-bloco="abrirBlocoExistente"
      />
    </div>
    <div
      v-else
      id="painel-modelo"
      role="tabpanel"
      aria-labelledby="aba-modelo"
    >
      <SemanaModeloSemanalLista
        :colunas="ordemDiasModelo"
        :categoria-por-id="categoriasStore.mapaPorId"
        @novo="abrirNovoModelo"
        @editar="abrirEdicaoModelo"
      />
    </div>

    <BlocoSheet
      :aberto="sheetBlocoAberto"
      :data-iso="dataSheetBloco"
      :fuso="fusoUsuario"
      :categorias="categoriasStore.itens"
      :bloco-editando="blocoEditando"
      @fechar="sheetBlocoAberto = false"
    />

    <SemanaModeloSheet
      :aberto="sheetModeloAberto"
      :modelo="modeloEditando"
      :dia-semana-inicial="diaSemanaNovoModelo"
      :categorias="categoriasStore.itens"
      @fechar="sheetModeloAberto = false"
    />
  </div>
</template>
