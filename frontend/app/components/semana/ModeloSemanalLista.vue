<script setup lang="ts">
import type { ModeloBlocoRead } from '~/stores/blocos'
import type { CategoriaRead } from '~/stores/categorias'
import { ESTILOS_CATEGORIA, formatarDuracaoMinutos } from '~/utils/coresCategoria'
import { duracaoModeloMin } from '~/utils/modelos'

interface ColunaModelo {
  diaSemana: number
  nome: string
  itens: ModeloBlocoRead[]
}

interface Props {
  colunas: ColunaModelo[]
  categoriaPorId: Map<string, CategoriaRead>
}

const props = defineProps<Props>()

const emit = defineEmits<{
  novo: [diaSemana: number]
  editar: [modelo: ModeloBlocoRead]
}>()

function classesDoModelo(modelo: ModeloBlocoRead): string {
  return ESTILOS_CATEGORIA[props.categoriaPorId.get(modelo.categoria_id)?.cor ?? 'ardosia'].blocoContorno
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <p class="text-sm text-grafite-suave">
        Configure os blocos que se repetem toda semana e aplique na agenda com um clique.
      </p>
      <BaseButton
        tamanho="sm"
        class="min-h-11"
        @click="emit('novo', 1)"
      >
        + Bloco no modelo
      </BaseButton>
    </div>

    <div class="grid gap-3 md:grid-cols-2 lg:grid-cols-7">
      <div
        v-for="col in props.colunas"
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
                class="min-h-11 w-full rounded-lg p-2 text-left text-xs transition-opacity hover:opacity-90"
                :class="classesDoModelo(m)"
                @click="emit('editar', m)"
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
          class="mt-3 min-h-11 w-full rounded-lg border border-dashed border-linha py-1.5 text-xs text-grafite-suave hover:border-grafite-suave hover:text-tinta"
          :aria-label="`Adicionar modelo em ${col.nome}`"
          @click="emit('novo', col.diaSemana)"
        >
          + Modelo
        </button>
      </div>
    </div>
  </div>
</template>
