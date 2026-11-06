import Dexie, { type EntityTable } from 'dexie'
import type { components } from '~/types/api'
import { calcularMinutosLiquidos } from '~/utils/horasLiquidas'

export type BlocoLocal = components['schemas']['BlocoRead']
export type CategoriaLocal = components['schemas']['CategoriaRead']
export type ExecucaoLocal = components['schemas']['ExecucaoRead']
export type ModeloBlocoLocal = components['schemas']['ModeloBlocoRead']

export type EntidadeSync = 'bloco' | 'categoria' | 'execucao' | 'modelo_bloco'
export type AcaoSync = 'criar' | 'atualizar' | 'excluir'

export interface MutacaoOutbox {
  id: string
  entidade: EntidadeSync
  acao: AcaoSync
  entidadeId: string
  payload: Record<string, unknown>
  criadoEm: string
  /** Versão da entidade que o cliente conhecia ao editar (controle otimista). */
  versaoBase?: number | null
  tentativas: number
  /** Epoch ms a partir do qual a mutação pode ser reenviada (backoff). */
  proximaTentativaEm?: number
  ultimoErro?: string
}

export type StatusConflito = 'conflito' | 'ignorado' | 'falhou'

/** Mutação que o servidor rejeitou ou que falhou definitivamente; o usuário decide o destino. */
export interface ConflitoLocal {
  id: string
  mutacaoId: string
  entidade: EntidadeSync
  acao: AcaoSync
  entidadeId: string
  status: StatusConflito
  mensagem: string
  payload: Record<string, unknown>
  versaoBase?: number | null
  criadoEm: string
}

export interface MetaLocal {
  chave: string
  valor: unknown
}

export class RitmoDatabase extends Dexie {
  blocos!: EntityTable<BlocoLocal, 'id'>
  categorias!: EntityTable<CategoriaLocal, 'id'>
  execucoes!: EntityTable<ExecucaoLocal, 'id'>
  modelos_bloco!: EntityTable<ModeloBlocoLocal, 'id'>
  outbox!: EntityTable<MutacaoOutbox, 'id'>
  meta!: EntityTable<MetaLocal, 'chave'>
  conflitos!: EntityTable<ConflitoLocal, 'id'>

  constructor() {
    super('RitmoDB')
    this.version(1).stores({
      blocos: 'id, data_local, categoria_id, inicio',
      categorias: 'id, nome',
      execucoes: 'id, bloco_id, categoria_id, status, inicio',
      modelos: 'id, dia_semana',
      outbox: 'id, entidade, entidadeId, criadoEm',
    })
    // v2: `modelos` vira `modelos_bloco` (dados refeitos pelo pull); novas tabelas meta e conflitos.
    this.version(2).stores({
      blocos: 'id, data_local, categoria_id, inicio',
      categorias: 'id, nome',
      execucoes: 'id, bloco_id, categoria_id, status, inicio',
      modelos: null,
      modelos_bloco: 'id, dia_semana',
      outbox: 'id, entidade, entidadeId, criadoEm',
      meta: 'chave',
      conflitos: 'id, entidadeId, criadoEm',
    })
  }
}

export const dbLocal = new RitmoDatabase()

export async function lerMeta<T>(chave: string): Promise<T | undefined> {
  try {
    const item = await dbLocal.meta.get(chave)
    return item?.valor as T | undefined
  }
  catch {
    return undefined
  }
}

export async function gravarMeta(chave: string, valor: unknown): Promise<void> {
  try {
    await dbLocal.meta.put({ chave, valor })
  }
  catch {
    // Armazenamento local indisponível (ex.: modo privado): segue só com memória.
  }
}

/** Apaga todos os dados locais (logout ou troca de usuário). */
export async function limparBancoLocal(): Promise<void> {
  try {
    await Promise.all(dbLocal.tables.map(t => t.clear()))
  }
  catch {
    // Sem armazenamento local, não há o que limpar.
  }
}

/**
 * Segundos líquidos entre `inicioIso` e `fimIso` descontando pausas (mescladas, recortadas ao intervalo).
 * Pausas sem `fim` valem até `fimIso`.
 */
export function segundosLiquidosEntre(
  inicioIso: string,
  fimIso: string,
  pausas: { inicio: string, fim: string | null }[],
): number {
  const emMinutos = (iso: string) => new Date(iso).getTime() / 60000
  const minutos = calcularMinutosLiquidos(
    emMinutos(inicioIso),
    emMinutos(fimIso),
    pausas.map(p => ({ inicioMin: emMinutos(p.inicio), fimMin: emMinutos(p.fim ?? fimIso) })),
  )
  return Math.max(0, Math.round(minutos * 60))
}
