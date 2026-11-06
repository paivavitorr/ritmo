import { defineStore } from 'pinia'
import type { components } from '~/types/api'
import { dbLocal } from '~/utils/dbLocal'
import { novoId } from '~/utils/id'

export type CategoriaRead = components['schemas']['CategoriaRead']
export type CategoriaCreate = Omit<
  components['schemas']['CategoriaCreate'],
  'conta_como_produtiva' | 'ordem'
> & {
  conta_como_produtiva?: boolean
  ordem?: number
}
export type CategoriaUpdate = components['schemas']['CategoriaUpdate']

function ordenar(lista: CategoriaRead[]): CategoriaRead[] {
  return [...lista].sort((a, b) => a.ordem - b.ordem || a.nome.localeCompare(b.nome))
}

export const useCategoriasStore = defineStore('categorias', () => {
  const itens = ref<CategoriaRead[]>([])
  const carregando = ref(false)
  const carregado = ref(false)

  const mapaPorId = computed(() => {
    const mapa = new Map<string, CategoriaRead>()
    for (const c of itens.value) {
      mapa.set(c.id, c)
    }
    return mapa
  })

  async function recarregarLocal() {
    itens.value = ordenar(await dbLocal.categorias.toArray())
  }

  /** Lê do Dexie na hora e, se houver rede, puxa mudanças do servidor e atualiza a tela. */
  async function carregar(forcar = false): Promise<CategoriaRead[]> {
    if (carregado.value && !forcar) return itens.value
    carregando.value = true
    try {
      await recarregarLocal()
      carregado.value = true
      if (await useSyncStore().puxarMudancas()) {
        await recarregarLocal()
      }
      return itens.value
    }
    finally {
      carregando.value = false
    }
  }

  async function criar(dados: CategoriaCreate): Promise<CategoriaRead> {
    const agora = new Date().toISOString()
    const nova: CategoriaRead = {
      id: dados.id ?? novoId(),
      usuario_id: useAuthStore().usuario?.id ?? '',
      nome: dados.nome,
      cor: dados.cor,
      icone: dados.icone ?? null,
      conta_como_produtiva: dados.conta_como_produtiva ?? true,
      meta_semanal_min: dados.meta_semanal_min ?? null,
      ordem: dados.ordem ?? itens.value.length,
      versao: 0,
      criado_em: agora,
      atualizado_em: agora,
    }
    await dbLocal.categorias.put(nova)
    itens.value = ordenar([...itens.value, nova])
    await useSyncStore().enfileirarMutacao('categoria', 'criar', nova.id, {
      id: nova.id,
      nome: nova.nome,
      cor: nova.cor,
      icone: nova.icone,
      conta_como_produtiva: nova.conta_como_produtiva,
      meta_semanal_min: nova.meta_semanal_min,
      ordem: nova.ordem,
    })
    return nova
  }

  async function atualizar(id: string, dados: CategoriaUpdate): Promise<CategoriaRead> {
    const atual = itens.value.find(c => c.id === id) ?? await dbLocal.categorias.get(id)
    if (!atual) throw new Error('Categoria não encontrada.')
    const atualizada: CategoriaRead = {
      ...atual,
      ...Object.fromEntries(Object.entries(dados).filter(([, v]) => v !== undefined && v !== null)),
      ...(dados.icone !== undefined ? { icone: dados.icone } : {}),
      ...(dados.meta_semanal_min !== undefined ? { meta_semanal_min: dados.meta_semanal_min } : {}),
      atualizado_em: new Date().toISOString(),
    }
    await dbLocal.categorias.put(atualizada)
    itens.value = ordenar(itens.value.map(c => (c.id === id ? atualizada : c)))
    await useSyncStore().enfileirarMutacao(
      'categoria',
      'atualizar',
      id,
      dados as Record<string, unknown>,
      atual.versao,
    )
    return atualizada
  }

  async function excluir(id: string): Promise<void> {
    const atual = itens.value.find(c => c.id === id) ?? await dbLocal.categorias.get(id)
    await dbLocal.categorias.delete(id)
    itens.value = itens.value.filter(c => c.id !== id)
    await useSyncStore().enfileirarMutacao('categoria', 'excluir', id, {}, atual?.versao ?? null)
  }

  function limpar() {
    itens.value = []
    carregado.value = false
  }

  return {
    itens,
    carregando,
    carregado,
    mapaPorId,
    carregar,
    recarregarLocal,
    criar,
    atualizar,
    excluir,
    limpar,
  }
})
