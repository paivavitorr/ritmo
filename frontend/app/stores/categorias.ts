import { defineStore } from 'pinia'
import type { components } from '~/types/api'

export type CategoriaRead = components['schemas']['CategoriaRead']
export type CategoriaCreate = Omit<
  components['schemas']['CategoriaCreate'],
  'conta_como_produtiva' | 'ordem'
> & {
  conta_como_produtiva?: boolean
  ordem?: number
}
export type CategoriaUpdate = components['schemas']['CategoriaUpdate']

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

  async function carregar(forcar = false): Promise<CategoriaRead[]> {
    if (carregado.value && !forcar) return itens.value
    const { requisitar } = useApi()
    carregando.value = true
    try {
      const lista = await requisitar<CategoriaRead[]>('/categorias')
      itens.value = lista
      carregado.value = true
      return lista
    }
    finally {
      carregando.value = false
    }
  }

  async function criar(dados: CategoriaCreate): Promise<CategoriaRead> {
    const { requisitar } = useApi()
    const nova = await requisitar<CategoriaRead>('/categorias', {
      method: 'POST',
      body: dados as unknown as Record<string, unknown>,
    })
    itens.value = [...itens.value, nova].sort(
      (a, b) => a.ordem - b.ordem || a.nome.localeCompare(b.nome),
    )
    return nova
  }

  async function atualizar(id: string, dados: CategoriaUpdate): Promise<CategoriaRead> {
    const { requisitar } = useApi()
    const atualizada = await requisitar<CategoriaRead>(`/categorias/${id}`, {
      method: 'PATCH',
      body: dados as unknown as Record<string, unknown>,
    })
    itens.value = itens.value
      .map(c => (c.id === id ? atualizada : c))
      .sort((a, b) => a.ordem - b.ordem || a.nome.localeCompare(b.nome))
    return atualizada
  }

  async function excluir(id: string): Promise<void> {
    const { requisitar } = useApi()
    await requisitar(`/categorias/${id}`, { method: 'DELETE' })
    itens.value = itens.value.filter(c => c.id !== id)
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
    criar,
    atualizar,
    excluir,
    limpar,
  }
})
