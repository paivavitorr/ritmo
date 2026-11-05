<script setup lang="ts">
import { extrairMensagemErro } from '~/composables/useApi'
import type { BlocoRead, ModeloBlocoRead } from '~/stores/blocos'
import {
  ESTILOS_CATEGORIA,
  formatarDuracaoMinutos,
  formatarDuracaoSegundos,
} from '~/utils/coresCategoria'
import {
  NOMES_DIAS_CURTOS,
  NOMES_DIAS_SEMANA,
  diaSemanaDeDataIso,
  formatarDiaMesCurto,
  hojeIsoNoFuso,
  inicioDaSemanaIso,
  minutosDesdeMeiaNoiteNoFuso,
  minutosParaHoraInput,
  somarDiasIso,
} from '~/utils/tempo'

const auth = useAuthStore()
const categoriasStore = useCategoriasStore()
const blocosStore = useBlocosStore()

const fusoUsuario = computed(() => auth.usuario?.fuso || 'America/Manaus')
const inicioSemanaPref = computed(() => auth.usuario?.inicio_semana ?? 1)

const inicioSemanaAtiva = ref(
  inicioDaSemanaIso(hojeIsoNoFuso(fusoUsuario.value), inicioSemanaPref.value),
)
const aba = ref<'agenda' | 'modelo'>('agenda')
const aplicandoModelo = ref(false)
const erro = ref<string | null>(null)
const mensagem = ref<string | null>(null)

// Sheet de bloco concreto
const sheetBlocoAberto = ref(false)
const dataSheetBloco = ref(inicioSemanaAtiva.value)
const blocoEditando = ref<BlocoRead | null>(null)

// Sheet de modelo semanal
const sheetModeloAberto = ref(false)
const modeloEditando = ref<ModeloBlocoRead | null>(null)
const modTitulo = ref('')
const modCategoriaId = ref('')
const modDiaSemana = ref(1)
const modHoraIni = ref('08:00')
const modHoraFim = ref('09:30')
const salvandoModelo = ref(false)

const diasDaSemana = computed(() =>
  Array.from({ length: 7 }, (_, i) => {
    const dataIso = somarDiasIso(inicioSemanaAtiva.value, i)
    const ds = diaSemanaDeDataIso(dataIso)
    return {
      dataIso,
      diaSemana: ds,
      nomeCurto: NOMES_DIAS_CURTOS[ds] ?? 'Dia',
      nomeCompleto: NOMES_DIAS_SEMANA[ds] ?? 'Dia',
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
  modTitulo.value = ''
  modCategoriaId.value = categoriasStore.itens[0]?.id ?? ''
  modDiaSemana.value = diaSemana
  modHoraIni.value = '08:00'
  modHoraFim.value = '09:30'
  sheetModeloAberto.value = true
}

function abrirEdicaoModelo(m: ModeloBlocoRead) {
  modeloEditando.value = m
  modTitulo.value = m.titulo
  modCategoriaId.value = m.categoria_id
  modDiaSemana.value = m.dia_semana
  modHoraIni.value = m.hora_inicio.slice(0, 5)
  modHoraFim.value = m.hora_fim.slice(0, 5)
  sheetModeloAberto.value = true
}

async function salvarModelo() {
  erro.value = null
  salvandoModelo.value = true
  try {
    if (modeloEditando.value) {
      await blocosStore.atualizarModelo(modeloEditando.value.id, {
        categoria_id: modCategoriaId.value,
        titulo: modTitulo.value.trim(),
        dia_semana: modDiaSemana.value,
        hora_inicio: `${modHoraIni.value}:00`,
        hora_fim: `${modHoraFim.value}:00`,
      })
    }
    else {
      await blocosStore.criarModelo({
        categoria_id: modCategoriaId.value,
        titulo: modTitulo.value.trim(),
        dia_semana: modDiaSemana.value,
        hora_inicio: `${modHoraIni.value}:00`,
        hora_fim: `${modHoraFim.value}:00`,
      })
    }
    sheetModeloAberto.value = false
  }
  catch (e: unknown) {
    erro.value = extrairMensagemErro(e, 'Não foi possível salvar o modelo semanal.')
  }
  finally {
    salvandoModelo.value = false
  }
}

async function removerModelo() {
  if (!modeloEditando.value) return
  salvandoModelo.value = true
  try {
    await blocosStore.excluirModelo(modeloEditando.value.id)
    sheetModeloAberto.value = false
  }
  catch (e: unknown) {
    erro.value = extrairMensagemErro(e, 'Não foi possível remover o modelo semanal.')
  }
  finally {
    salvandoModelo.value = false
  }
}

function formatarHorarioBloco(bloco: BlocoRead): string {
  const ini = minutosDesdeMeiaNoiteNoFuso(bloco.inicio, bloco.data_local, fusoUsuario.value)
  const fim = minutosDesdeMeiaNoiteNoFuso(bloco.fim, bloco.data_local, fusoUsuario.value)
  return `${minutosParaHoraInput(ini)}–${minutosParaHoraInput(fim)}`
}

function duracaoModeloMin(m: ModeloBlocoRead): number {
  const [hi = 0, mi = 0] = m.hora_inicio.split(':').map(Number)
  const [hf = 0, mf = 0] = m.hora_fim.split(':').map(Number)
  const ini = hi * 60 + mi
  let fim = hf * 60 + mf
  if (fim <= ini) fim += 1440
  const pausasMin = m.pausas.reduce((acc, p) => acc + p.duracao_min, 0)
  return Math.max(0, fim - ini - pausasMin)
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
        >
          <button
            type="button"
            role="tab"
            :aria-selected="aba === 'agenda'"
            class="rounded-lg px-3 py-1.5 text-xs font-medium transition-colors"
            :class="aba === 'agenda' ? 'bg-ardosia-200 text-ardosia-700' : 'text-grafite-suave hover:text-tinta'"
            @click="aba = 'agenda'"
          >
            Agenda da semana
          </button>
          <button
            type="button"
            role="tab"
            :aria-selected="aba === 'modelo'"
            class="rounded-lg px-3 py-1.5 text-xs font-medium transition-colors"
            :class="aba === 'modelo' ? 'bg-ardosia-200 text-ardosia-700' : 'text-grafite-suave hover:text-tinta'"
            @click="aba = 'modelo'"
          >
            Modelo padrão
          </button>
        </div>

        <BaseButton
          variante="secundario"
          tamanho="sm"
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

    <!-- ABA 1: Agenda concreta dos 7 dias -->
    <section
      v-if="aba === 'agenda'"
      class="space-y-4"
    >
      <div class="flex items-center justify-between">
        <div class="inline-flex rounded-[var(--radius-bloco)] border border-linha bg-papel p-0.5">
          <button
            type="button"
            class="rounded-lg px-2.5 py-1 text-xs font-medium text-tinta hover:bg-nevoa"
            @click="navegarSemana(-1)"
          >
            ← Semana anterior
          </button>
          <button
            type="button"
            class="rounded-lg px-3 py-1 text-xs font-medium text-tinta hover:bg-nevoa"
            @click="irParaSemanaAtual"
          >
            Esta semana
          </button>
          <button
            type="button"
            class="rounded-lg px-2.5 py-1 text-xs font-medium text-tinta hover:bg-nevoa"
            @click="navegarSemana(1)"
          >
            Próxima →
          </button>
        </div>
      </div>

      <div class="grid gap-3 md:grid-cols-2 lg:grid-cols-7">
        <div
          v-for="dia in diasDaSemana"
          :key="dia.dataIso"
          class="flex flex-col justify-between rounded-[var(--radius-bloco)] border border-linha bg-papel p-3"
        >
          <div>
            <div class="flex items-baseline justify-between border-b border-linha pb-2">
              <span class="text-xs font-semibold text-tinta">{{ dia.nomeCurto }}</span>
              <span class="tabular text-xs text-grafite-suave">{{ dia.diaMes }}</span>
            </div>

            <ul class="mt-2.5 space-y-2">
              <li
                v-for="b in dia.blocos"
                :key="b.id"
              >
                <button
                  type="button"
                  class="w-full rounded-lg p-2 text-left text-xs transition-opacity hover:opacity-90"
                  :class="
                    ESTILOS_CATEGORIA[
                      categoriasStore.mapaPorId.get(b.categoria_id)?.cor ?? 'ardosia'
                    ].blocoContorno
                  "
                  @click="abrirBlocoExistente(b)"
                >
                  <p class="truncate font-semibold">
                    {{ b.titulo }}
                  </p>
                  <p class="tabular mt-0.5 text-[11px] opacity-85">
                    {{ formatarHorarioBloco(b) }} · {{ formatarDuracaoSegundos(b.segundos_liquidos_planejados) }}
                  </p>
                </button>
              </li>
            </ul>
          </div>

          <button
            type="button"
            class="mt-3 w-full rounded-lg border border-dashed border-linha py-1.5 text-xs text-grafite-suave hover:border-grafite-suave hover:text-tinta"
            @click="abrirNovoBlocoNoDia(dia.dataIso)"
          >
            + Bloco
          </button>
        </div>
      </div>
    </section>

    <!-- ABA 2: Modelo semanal padrão -->
    <section
      v-else
      class="space-y-4"
    >
      <div class="flex items-center justify-between">
        <p class="text-sm text-grafite-suave">
          Configure os blocos que se repetem toda semana e aplique na agenda com um clique.
        </p>
        <BaseButton
          tamanho="sm"
          @click="abrirNovoModelo(1)"
        >
          + Bloco no modelo
        </BaseButton>
      </div>

      <div class="grid gap-3 md:grid-cols-2 lg:grid-cols-7">
        <div
          v-for="col in ordemDiasModelo"
          :key="col.diaSemana"
          class="flex flex-col justify-between rounded-[var(--radius-bloco)] border border-linha bg-papel p-3"
        >
          <div>
            <div class="border-b border-linha pb-2">
              <span class="text-xs font-semibold text-tinta">{{ col.nome }}</span>
            </div>

            <ul class="mt-2.5 space-y-2">
              <li
                v-for="m in col.itens"
                :key="m.id"
              >
                <button
                  type="button"
                  class="w-full rounded-lg p-2 text-left text-xs transition-opacity hover:opacity-90"
                  :class="
                    ESTILOS_CATEGORIA[
                      categoriasStore.mapaPorId.get(m.categoria_id)?.cor ?? 'ardosia'
                    ].blocoContorno
                  "
                  @click="abrirEdicaoModelo(m)"
                >
                  <p class="truncate font-semibold">
                    {{ m.titulo }}
                  </p>
                  <p class="tabular mt-0.5 text-[11px] opacity-85">
                    {{ m.hora_inicio.slice(0, 5) }}–{{ m.hora_fim.slice(0, 5) }} · {{ formatarDuracaoMinutos(duracaoModeloMin(m)) }}
                  </p>
                </button>
              </li>
            </ul>
          </div>

          <button
            type="button"
            class="mt-3 w-full rounded-lg border border-dashed border-linha py-1.5 text-xs text-grafite-suave hover:border-grafite-suave hover:text-tinta"
            @click="abrirNovoModelo(col.diaSemana)"
          >
            + Modelo
          </button>
        </div>
      </div>
    </section>

    <!-- Sheet de bloco concreto -->
    <BlocoSheet
      :aberto="sheetBlocoAberto"
      :data-iso="dataSheetBloco"
      :fuso="fusoUsuario"
      :categorias="categoriasStore.itens"
      :bloco-editando="blocoEditando"
      @fechar="sheetBlocoAberto = false"
    />

    <!-- Sheet de modelo semanal -->
    <BaseSheet
      :aberto="sheetModeloAberto"
      :titulo="modeloEditando ? 'Editar bloco do modelo' : 'Novo bloco no modelo semanal'"
      descricao="Este bloco será criado automaticamente quando você aplicar o modelo na semana."
      @fechar="sheetModeloAberto = false"
    >
      <form
        id="form-modelo"
        class="flex flex-col gap-5"
        @submit.prevent="salvarModelo"
      >
        <BaseInput
          id="mod-titulo"
          v-model="modTitulo"
          label="Título"
          placeholder="Ex.: Estudo dirigido"
          obrigatorio
        />

        <div>
          <span class="block text-sm font-medium text-tinta">Categoria</span>
          <div class="mt-2 flex flex-wrap gap-2">
            <BaseChip
              v-for="cat in categoriasStore.itens"
              :key="cat.id"
              :cor="cat.cor"
              :selecionado="modCategoriaId === cat.id"
              interativo
              @click="modCategoriaId = cat.id"
            >
              {{ cat.nome }}
            </BaseChip>
          </div>
        </div>

        <div>
          <label
            for="mod-dia"
            class="block text-sm font-medium text-tinta"
          >
            Dia da semana
          </label>
          <select
            id="mod-dia"
            v-model.number="modDiaSemana"
            class="mt-1.5 w-full rounded-[var(--radius-bloco)] border border-linha bg-papel px-3.5 py-2.5 text-sm text-tinta"
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
            v-model="modHoraIni"
            tipo="time"
            tabular
            label="Início"
            obrigatorio
          />
          <BaseInput
            id="mod-fim"
            v-model="modHoraFim"
            tipo="time"
            tabular
            label="Término"
            obrigatorio
          />
        </div>
      </form>

      <template #rodape>
        <div class="flex items-center justify-between gap-2">
          <BaseButton
            v-if="modeloEditando"
            variante="perigo"
            tamanho="sm"
            :carregando="salvandoModelo"
            @click="removerModelo"
          >
            Excluir
          </BaseButton>
          <span v-else />

          <div class="flex items-center gap-2">
            <BaseButton
              variante="fantasma"
              tamanho="sm"
              @click="sheetModeloAberto = false"
            >
              Cancelar
            </BaseButton>
            <BaseButton
              tipo="submit"
              form="form-modelo"
              tamanho="sm"
              :carregando="salvandoModelo"
            >
              Salvar modelo
            </BaseButton>
          </div>
        </div>
      </template>
    </BaseSheet>
  </div>
</template>
