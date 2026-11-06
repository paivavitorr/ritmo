<script setup lang="ts">
import { extrairMensagemErro } from '~/composables/useApi'
import type { components } from '~/types/api'
import { formatarDuracaoSegundos } from '~/utils/coresCategoria'
import {
  hojeIsoNoFuso,
  inicioDaSemanaIso,
  somarDiasIso,
} from '~/utils/tempo'

type ResumoPeriodoResponse = components['schemas']['ResumoPeriodoResponse']

const auth = useAuthStore()
const { requisitar } = useApi()

const fusoUsuario = computed(() => auth.usuario?.fuso || Intl.DateTimeFormat().resolvedOptions().timeZone)
const tipoFiltro = ref<'hoje' | 'semana' | 'ultimos7'>('semana')
const carregando = ref(false)
const erro = ref<string | null>(null)
const resumo = ref<ResumoPeriodoResponse | null>(null)

const intervaloConsulta = computed(() => {
  const hoje = hojeIsoNoFuso(fusoUsuario.value)
  if (tipoFiltro.value === 'hoje') {
    return { de: hoje, ate: hoje }
  }
  if (tipoFiltro.value === 'ultimos7') {
    return { de: somarDiasIso(hoje, -6), ate: hoje }
  }
  // semana completa respeitando a preferência de início da semana do usuário
  const inicioSemanaPref = auth.usuario?.inicio_semana ?? 1
  const iniSemana = inicioDaSemanaIso(hoje, inicioSemanaPref)
  return { de: iniSemana, ate: somarDiasIso(iniSemana, 6) }
})

async function carregarResumo() {
  carregando.value = true
  erro.value = null
  try {
    const { de, ate } = intervaloConsulta.value
    const resposta = await requisitar<ResumoPeriodoResponse>(
      `/resumo?de=${encodeURIComponent(de)}&ate=${encodeURIComponent(ate)}&agrupar=dia`,
    )
    resumo.value = resposta
  }
  catch (e: unknown) {
    erro.value = extrairMensagemErro(e, 'Não foi possível carregar o resumo de horas e aderência.')
  }
  finally {
    carregando.value = false
  }
}

// O backend pode devolver null quando não há plano no período.
const aderenciaVolume = computed<number | null>(() => resumo.value?.aderencia_volume_geral ?? null)
const aderenciaTemporal = computed<number | null>(() => resumo.value?.aderencia_temporal_geral ?? null)

watch(tipoFiltro, carregarResumo)
onMounted(carregarResumo)
</script>

<template>
  <div class="space-y-6">
    <!-- Cabeçalho -->
    <header class="flex flex-wrap items-center justify-between gap-4">
      <div>
        <h1 class="text-2xl font-semibold text-tinta">
          Resumo e Aderência
        </h1>
        <p class="mt-1 text-sm text-grafite-suave">
          Acompanhe suas horas líquidas reais comparadas ao planejado e sua consistência.
        </p>
      </div>

      <!-- Filtro de período -->
      <div class="inline-flex rounded-[var(--radius-bloco)] border border-linha bg-papel p-0.5">
        <button
          type="button"
          class="min-h-11 rounded-lg px-3 text-sm font-medium transition-colors"
          :aria-pressed="tipoFiltro === 'hoje'"
          :class="tipoFiltro === 'hoje' ? 'bg-nevoa text-tinta' : 'text-grafite-suave hover:text-tinta'"
          @click="tipoFiltro = 'hoje'"
        >
          Hoje
        </button>
        <button
          type="button"
          class="min-h-11 rounded-lg px-3 text-sm font-medium transition-colors"
          :aria-pressed="tipoFiltro === 'semana'"
          :class="tipoFiltro === 'semana' ? 'bg-nevoa text-tinta' : 'text-grafite-suave hover:text-tinta'"
          @click="tipoFiltro = 'semana'"
        >
          Esta semana
        </button>
        <button
          type="button"
          class="min-h-11 rounded-lg px-3 text-sm font-medium transition-colors"
          :aria-pressed="tipoFiltro === 'ultimos7'"
          :class="tipoFiltro === 'ultimos7' ? 'bg-nevoa text-tinta' : 'text-grafite-suave hover:text-tinta'"
          @click="tipoFiltro = 'ultimos7'"
        >
          Últimos 7 dias
        </button>
      </div>
    </header>

    <!-- Carregando (primeira vez) -->
    <p
      v-if="carregando && !resumo"
      class="text-sm text-grafite-suave"
      role="status"
    >
      Carregando resumo…
    </p>

    <!-- Alerta de erro -->
    <p
      v-if="erro"
      class="rounded-[var(--radius-bloco)] border border-rosa-cha-200 bg-rosa-cha-50 px-4 py-3 text-sm text-erro"
      role="alert"
    >
      {{ erro }}
    </p>

    <!-- Indicadores gerais -->
    <div
      v-if="resumo"
      class="grid grid-cols-2 gap-3 sm:grid-cols-4"
    >
      <div class="rounded-[var(--radius-bloco)] border border-linha bg-papel p-4 shadow-sm">
        <span class="text-xs text-grafite-suave">Horas planejadas</span>
        <p class="tabular mt-1 text-xl font-semibold text-tinta">
          {{ formatarDuracaoSegundos(resumo.total_segundos_planejados) }}
        </p>
      </div>

      <div class="rounded-[var(--radius-bloco)] border border-linha bg-papel p-4 shadow-sm">
        <span class="text-xs text-grafite-suave">Horas líquidas executadas</span>
        <p class="tabular mt-1 text-xl font-semibold text-tinta">
          {{ formatarDuracaoSegundos(resumo.total_segundos_executados) }}
        </p>
      </div>

      <div class="rounded-[var(--radius-bloco)] border border-linha bg-papel p-4 shadow-sm">
        <span class="text-xs text-grafite-suave">Aderência de volume</span>
        <div class="mt-2">
          <AderenciaIndicador :valor="aderenciaVolume" />
        </div>
      </div>

      <div class="rounded-[var(--radius-bloco)] border border-linha bg-papel p-4 shadow-sm">
        <span class="text-xs text-grafite-suave">Aderência temporal</span>
        <div class="mt-2">
          <AderenciaIndicador :valor="aderenciaTemporal" />
        </div>
      </div>
    </div>

    <!-- Lista por Categoria -->
    <section
      v-if="resumo && resumo.categorias.length"
      class="space-y-3"
    >
      <h2 class="text-base font-semibold text-tinta">
        Distribuição por Área / Categoria
      </h2>
      <div class="space-y-2">
        <CategoriaLinha
          v-for="cat in resumo.categorias"
          :key="`${cat.categoria_id ?? 'avulso'}-${cat.eh_espontaneo ? 'e' : 'p'}`"
          :categoria="cat"
        />
      </div>
    </section>

    <!-- Faixas 24h dos Dias (Princípio da Faixa do Dia) -->
    <section
      v-if="resumo && resumo.faixas_dias.length"
      class="space-y-4"
    >
      <h2 class="text-base font-semibold text-tinta">
        Faixa do Dia (24h: Planejado vs Real)
      </h2>
      <div class="space-y-3">
        <FaixaDoDia
          v-for="dia in resumo.faixas_dias"
          :key="dia.data"
          :faixa="dia"
          :fuso="fusoUsuario"
        />
      </div>
    </section>
  </div>
</template>
