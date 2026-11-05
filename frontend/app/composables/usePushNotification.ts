import type { components } from '~/types/api'

type PushChavePublicaResponse = components['schemas']['PushChavePublicaResponse']
type PushAssinaturaCreate = components['schemas']['PushAssinaturaCreate']
type PushAssinaturaRead = components['schemas']['PushAssinaturaRead']

function urlBase64ToUint8Array(base64String: string): Uint8Array<ArrayBuffer> {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const rawData = window.atob(base64)
  const buffer = new ArrayBuffer(rawData.length)
  const outputArray = new Uint8Array(buffer)
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i)
  }
  return outputArray
}

export function usePushNotification() {
  const { requisitar } = useApi()

  const suportado = ref(false)
  const permissao = ref<NotificationPermission>('default')
  const inscrito = ref(false)
  const carregando = ref(false)
  const erro = ref<string | null>(null)

  function verificarSuporte(): boolean {
    if (!import.meta.client) return false
    return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window
  }

  async function atualizarStatus() {
    if (!verificarSuporte()) {
      suportado.value = false
      return
    }
    suportado.value = true
    permissao.value = Notification.permission

    try {
      const reg = await navigator.serviceWorker.ready
      const sub = await reg.pushManager.getSubscription()
      inscrito.value = Boolean(sub)
    }
    catch {
      inscrito.value = false
    }
  }

  async function ativar(): Promise<boolean> {
    erro.value = null
    if (!verificarSuporte()) {
      erro.value = 'Seu navegador não suporta notificações Web Push.'
      return false
    }

    carregando.value = true
    try {
      const perm = await Notification.requestPermission()
      permissao.value = perm
      if (perm !== 'granted') {
        erro.value = perm === 'denied'
          ? 'Permissão para notificações foi bloqueada no navegador.'
          : 'Permissão para notificações não foi concedida.'
        return false
      }

      const { public_key } = await requisitar<PushChavePublicaResponse>('/push/chave-publica')
      if (!public_key) {
        throw new Error('Chave pública VAPID não configurada no servidor.')
      }

      const reg = await navigator.serviceWorker.ready
      let sub = await reg.pushManager.getSubscription()
      if (sub) {
        await sub.unsubscribe()
      }

      sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(public_key),
      })

      const subJson = sub.toJSON()
      const p256dh = subJson.keys?.p256dh
      const auth = subJson.keys?.auth

      if (!p256dh || !auth) {
        throw new Error('Falha ao extrair chaves de criptografia da assinatura push.')
      }

      const payload: PushAssinaturaCreate = {
        endpoint: sub.endpoint,
        p256dh,
        auth,
        user_agent: navigator.userAgent,
      }

      await requisitar<PushAssinaturaRead>('/push/assinar', {
        method: 'POST',
        body: payload as Record<string, unknown>,
      })

      inscrito.value = true
      return true
    }
    catch (e: unknown) {
      erro.value = extrairMensagemErro(e, 'Não foi possível ativar as notificações.')
      return false
    }
    finally {
      carregando.value = false
    }
  }

  async function desativar(): Promise<boolean> {
    erro.value = null
    if (!verificarSuporte()) return false

    carregando.value = true
    try {
      const reg = await navigator.serviceWorker.ready
      const sub = await reg.pushManager.getSubscription()
      if (sub) {
        try {
          await requisitar('/push/desassinar', {
            method: 'POST',
            body: { endpoint: sub.endpoint },
          })
        }
        catch {
          // Prossegue com desinscrição local mesmo se a chamada de rede falhar
        }
        await sub.unsubscribe()
      }
      inscrito.value = false
      return true
    }
    catch (e: unknown) {
      erro.value = extrairMensagemErro(e, 'Não foi possível desativar as notificações.')
      return false
    }
    finally {
      carregando.value = false
    }
  }

  onMounted(() => {
    void atualizarStatus()
  })

  return {
    suportado,
    permissao,
    inscrito,
    carregando,
    erro,
    atualizarStatus,
    ativar,
    desativar,
  }
}
