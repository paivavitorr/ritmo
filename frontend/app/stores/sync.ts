import { defineStore } from 'pinia'
import { v4 as uuidv4 } from 'uuid'
import type { components } from '~/types/api'
import { dbLocal, type MutacaoOutbox } from '~/utils/dbLocal'

type ItemMutacaoSync = components['schemas']['ItemMutacaoSync']
type SyncBatchResponse = components['schemas']['SyncBatchResponse']

export const useSyncStore = defineStore('sync', () => {
  const sincronizando = ref(false)
  const pendenciasCount = ref(0)
  const ultimoSyncSucesso = ref<Date | null>(null)
  const erroSync = ref<string | null>(null)

  async function atualizarContadorPendencias() {
    pendenciasCount.value = await dbLocal.outbox.count()
  }

  async function enfileirarMutacao(
    entidade: MutacaoOutbox['entidade'],
    acao: MutacaoOutbox['acao'],
    entidadeId: string,
    payload: Record<string, unknown>,
  ): Promise<void> {
    const mutacao: MutacaoOutbox = {
      id: uuidv4(),
      entidade,
      acao,
      entidadeId,
      payload,
      criadoEm: new Date().toISOString(),
      tentativas: 0,
    }
    await dbLocal.outbox.add(mutacao)
    await atualizarContadorPendencias()

    // Se estiver online, tenta enviar imediatamente em segundo plano
    const conexao = useConexaoStore()
    if (conexao.api === 'ok') {
      void sincronizarOutbox()
    }
  }

  async function sincronizarOutbox(): Promise<number> {
    if (sincronizando.value) return 0
    const pendentes = await dbLocal.outbox.orderBy('criadoEm').toArray()
    if (!pendentes.length) {
      pendenciasCount.value = 0
      return 0
    }

    const { requisitar } = useApi()
    sincronizando.value = true
    erroSync.value = null

    try {
      const payloadEnvio: ItemMutacaoSync[] = pendentes.map(p => ({
        id: p.id,
        entidade: p.entidade,
        acao: p.acao,
        entidade_id: p.entidadeId,
        payload: p.payload,
        criado_em: p.criadoEm,
      }))

      const resposta = await requisitar<SyncBatchResponse>('/sync/batch', {
        method: 'POST',
        body: { mutacoes: payloadEnvio } as unknown as Record<string, unknown>,
      })

      // Remove da outbox local apenas as mutações processadas com sucesso ou ignoradas
      // Se tiver mais de 5 tentativas com erro, expurga para não travar a outbox
      const idsRemover: string[] = []
      for (const res of resposta.resultados) {
        if (res.status === 'aplicado' || res.status === 'ignorado') {
          idsRemover.push(res.mutacao_id)
        }
        else {
          const item = pendentes.find(x => x.id === res.mutacao_id)
          const novasTentativas = (item?.tentativas ?? 0) + 1
          if (novasTentativas >= 5) {
            idsRemover.push(res.mutacao_id)
          }
          else {
            await dbLocal.outbox.update(res.mutacao_id, {
              tentativas: novasTentativas,
              ultimoErro: res.mensagem ?? 'Erro no servidor',
            })
          }
        }
      }

      if (idsRemover.length) {
        await dbLocal.outbox.bulkDelete(idsRemover)
      }

      ultimoSyncSucesso.value = new Date()
      await atualizarContadorPendencias()
      return idsRemover.length
    }
    catch {
      erroSync.value = 'Falha ao sincronizar dados com o servidor.'
      return 0
    }
    finally {
      sincronizando.value = false
    }
  }

  return {
    sincronizando,
    pendenciasCount,
    ultimoSyncSucesso,
    erroSync,
    enfileirarMutacao,
    sincronizarOutbox,
    atualizarContadorPendencias,
  }
})
