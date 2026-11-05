import Dexie, { type EntityTable } from 'dexie'
import type { components } from '~/types/api'

export type BlocoLocal = components['schemas']['BlocoRead']
export type CategoriaLocal = components['schemas']['CategoriaRead']
export type ExecucaoLocal = components['schemas']['ExecucaoRead']
export type ModeloBlocoLocal = components['schemas']['ModeloBlocoRead']

export interface MutacaoOutbox {
  id: string
  entidade: 'bloco' | 'categoria' | 'execucao' | 'modelo_bloco'
  acao: 'criar' | 'atualizar' | 'excluir'
  entidadeId: string
  payload: Record<string, unknown>
  criadoEm: string
  tentativas: number
  ultimoErro?: string
}

export class RitmoDatabase extends Dexie {
  blocos!: EntityTable<BlocoLocal, 'id'>
  categorias!: EntityTable<CategoriaLocal, 'id'>
  execucoes!: EntityTable<ExecucaoLocal, 'id'>
  modelos!: EntityTable<ModeloBlocoLocal, 'id'>
  outbox!: EntityTable<MutacaoOutbox, 'id'>

  constructor() {
    super('RitmoDB')
    this.version(1).stores({
      blocos: 'id, data_local, categoria_id, inicio',
      categorias: 'id, nome',
      execucoes: 'id, bloco_id, categoria_id, status, inicio',
      modelos: 'id, dia_semana',
      outbox: 'id, entidade, entidadeId, criadoEm',
    })
  }
}

export const dbLocal = new RitmoDatabase()
