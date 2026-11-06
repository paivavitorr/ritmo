import type { components } from '~/types/api'

export type CorCategoria = components['schemas']['CategoriaRead']['cor']

export interface EstiloCategoria {
  token: CorCategoria
  label: string
  chip: string
  chipAtivo: string
  blocoContorno: string
  blocoPreenchimento: string
  ponto: string
}

/**
 * Mapa estático de classes Tailwind v4 para os 7 tokens de cor pastel.
 * Todas as classes são escritas por extenso para que o scanner do Tailwind as detecte.
 */
export const ESTILOS_CATEGORIA: Record<CorCategoria, EstiloCategoria> = {
  'ardosia': {
    token: 'ardosia',
    label: 'Ardósia',
    chip: 'bg-ardosia-50 text-ardosia-700 border border-ardosia-200',
    chipAtivo: 'bg-ardosia-200 text-ardosia-700 ring-2 ring-ardosia-700/30',
    blocoContorno: 'bg-ardosia-50/75 border-2 border-ardosia-200 text-ardosia-700',
    blocoPreenchimento: 'bg-ardosia-200 text-ardosia-700',
    ponto: 'bg-ardosia-700',
  },
  'glicinia': {
    token: 'glicinia',
    label: 'Glicínia',
    chip: 'bg-glicinia-50 text-glicinia-700 border border-glicinia-200',
    chipAtivo: 'bg-glicinia-200 text-glicinia-700 ring-2 ring-glicinia-700/30',
    blocoContorno: 'bg-glicinia-50/75 border-2 border-glicinia-200 text-glicinia-700',
    blocoPreenchimento: 'bg-glicinia-200 text-glicinia-700',
    ponto: 'bg-glicinia-700',
  },
  'salvia': {
    token: 'salvia',
    label: 'Sálvia',
    chip: 'bg-salvia-50 text-salvia-700 border border-salvia-200',
    chipAtivo: 'bg-salvia-200 text-salvia-700 ring-2 ring-salvia-700/30',
    blocoContorno: 'bg-salvia-50/75 border-2 border-salvia-200 text-salvia-700',
    blocoPreenchimento: 'bg-salvia-200 text-salvia-700',
    ponto: 'bg-salvia-700',
  },
  'ceu': {
    token: 'ceu',
    label: 'Céu',
    chip: 'bg-ceu-50 text-ceu-700 border border-ceu-200',
    chipAtivo: 'bg-ceu-200 text-ceu-700 ring-2 ring-ceu-700/30',
    blocoContorno: 'bg-ceu-50/75 border-2 border-ceu-200 text-ceu-700',
    blocoPreenchimento: 'bg-ceu-200 text-ceu-700',
    ponto: 'bg-ceu-700',
  },
  'manteiga': {
    token: 'manteiga',
    label: 'Manteiga',
    chip: 'bg-manteiga-50 text-manteiga-700 border border-manteiga-200',
    chipAtivo: 'bg-manteiga-200 text-manteiga-700 ring-2 ring-manteiga-700/30',
    blocoContorno: 'bg-manteiga-50/75 border-2 border-manteiga-200 text-manteiga-700',
    blocoPreenchimento: 'bg-manteiga-200 text-manteiga-700',
    ponto: 'bg-manteiga-700',
  },
  'rosa-cha': {
    token: 'rosa-cha',
    label: 'Rosa-chá',
    chip: 'bg-rosa-cha-50 text-rosa-cha-700 border border-rosa-cha-200',
    chipAtivo: 'bg-rosa-cha-200 text-rosa-cha-700 ring-2 ring-rosa-cha-700/30',
    blocoContorno: 'bg-rosa-cha-50/75 border-2 border-rosa-cha-200 text-rosa-cha-700',
    blocoPreenchimento: 'bg-rosa-cha-200 text-rosa-cha-700',
    ponto: 'bg-rosa-cha-700',
  },
  'pessego': {
    token: 'pessego',
    label: 'Pêssego',
    chip: 'bg-pessego-50 text-pessego-700 border border-pessego-200',
    chipAtivo: 'bg-pessego-200 text-pessego-700 ring-2 ring-pessego-700/30',
    blocoContorno: 'bg-pessego-50/75 border-2 border-pessego-200 text-pessego-700',
    blocoPreenchimento: 'bg-pessego-200 text-pessego-700',
    ponto: 'bg-pessego-700',
  },
}

export const LISTA_CORES_CATEGORIA: EstiloCategoria[] = Object.values(ESTILOS_CATEGORIA)

export function formatarDuracaoMinutos(totalMinutos: number): string {
  const min = Math.max(0, Math.round(totalMinutos))
  const horas = Math.floor(min / 60)
  const resto = min % 60
  if (horas === 0) return `${resto}min`
  if (resto === 0) return `${horas}h`
  return `${horas}h ${resto}min`
}

export function formatarDuracaoSegundos(totalSegundos: number): string {
  return formatarDuracaoMinutos(Math.round(totalSegundos / 60))
}
