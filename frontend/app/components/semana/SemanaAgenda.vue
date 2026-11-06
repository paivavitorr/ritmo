<script setup lang="ts">
import type { BlocoRead } from '~/stores/blocos'
import type { CategoriaRead } from '~/stores/categorias'
import { ESTILOS_CATEGORIA, formatarDuracaoSegundos } from '~/utils/coresCategoria'
import { minutosDesdeMeiaNoiteNoFuso, minutosParaHoraInput } from '~/utils/tempo'

interface DiaAgenda {
  dataIso: string
  nomeCurto: string
  diaMes: string
  blocos: BlocoRead[]
}

interface Props {
  dias: DiaAgenda[]
  fuso: string
  categoriaPorId: Map<string, CategoriaRead>
}

const props = defineProps<Props>()

const emit = defineEmits<{
  navegar: [deltaSemanas: number]
  semanaAtual: []
  novoBloco: [dataIso: string]
  abrirBloco: [bloco: BlocoRead]
}>()

function formatarHorario(bloco: BlocoRead): string {
  const ini = minutosDesdeMeiaNoiteNoFuso(bloco.inicio, bloco.data_local, props.fuso)
  const fim = minutosDesdeMeiaNoiteNoFuso(bloco.fim, bloco.data_local, props.fuso)
  return `${minutosParaHoraInput(ini)}–${minutosParaHoraInput(fim)}`
}

function classesDoBloco(bloco: BlocoRead): string {
  return ESTILOS_CATEGORIA[props.categoriaPorId.get(bloco.categoria_id)?.cor ?? 'ardosia'].blocoContorno
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <div class="inline-flex rounded-[var(--radius-bloco)] border border-linha bg-papel p-0.5">
        <button
          type="button"
          class="min-h-11 rounded-lg px-2.5 py-1 text-xs font-medium text-tinta hover:bg-nevoa"
          @click="emit('navegar', -1)"
        >
          ← Semana anterior
        </button>
        <button
          type="button"
          class="min-h-11 rounded-lg px-3 py-1 text-xs font-medium text-tinta hover:bg-nevoa"
          @click="emit('semanaAtual')"
        >
          Esta semana
        </button>
        <button
          type="button"
          class="min-h-11 rounded-lg px-2.5 py-1 text-xs font-medium text-tinta hover:bg-nevoa"
          @click="emit('navegar', 1)"
        >
          Próxima →
        </button>
      </div>
    </div>

    <div class="grid gap-3 md:grid-cols-2 lg:grid-cols-7">
      <div
        v-for="dia in props.dias"
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
                class="min-h-11 w-full rounded-lg p-2 text-left text-xs transition-opacity hover:opacity-90"
                :class="classesDoBloco(b)"
                @click="emit('abrirBloco', b)"
              >
                <p class="truncate font-semibold">
                  {{ b.titulo }}
                </p>
                <p class="tabular mt-0.5 text-[11px] opacity-85">
                  {{ formatarHorario(b) }} · {{ formatarDuracaoSegundos(b.segundos_liquidos_planejados) }}
                </p>
              </button>
            </li>
          </ul>
        </div>

        <button
          type="button"
          class="mt-3 min-h-11 w-full rounded-lg border border-dashed border-linha py-1.5 text-xs text-grafite-suave hover:border-grafite-suave hover:text-tinta"
          :aria-label="`Adicionar bloco em ${dia.nomeCurto} ${dia.diaMes}`"
          @click="emit('novoBloco', dia.dataIso)"
        >
          + Bloco
        </button>
      </div>
    </div>
  </div>
</template>
