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

const TEMPO_MAX_SW_MS = 5000
const CACHE_PENDENCIAS = 'ritmo-push-pendencias'
const CHAVE_PENDENCIA = '/__push-pendente__'

type Requisitar = ReturnType<typeof useApi>['requisitar']

/** `serviceWorker.ready` nunca resolve sem SW (ex.: dev); espera no máximo `ms`. */
async function swProntoComTimeout(ms = TEMPO_MAX_SW_MS): Promise<ServiceWorkerRegistration | null> {
  return await Promise.race([
    navigator.serviceWorker.ready,
    new Promise<null>(resolve => setTimeout(() => resolve(null), ms)),
  ])
}

function ehIos(): boolean {
  const ua = navigator.userAgent
  const ipadComoMac = navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1
  return /iPad|iPhone|iPod/.test(ua) || ipadComoMac
}

function emModoInstalado(): boolean {
  return window.matchMedia('(display-mode: standalone)').matches
    || (navigator as Navigator & { standalone?: boolean }).standalone === true
}

function mesmaChave(a: ArrayBuffer | null | undefined, b: Uint8Array): boolean {
  if (!a || a.byteLength !== b.byteLength) return false
  const va = new Uint8Array(a)
  return va.every((byte, i) => byte === b[i])
}

async function desassinarNoBackend(requisitar: Requisitar, endpoint: string) {
  try {
    await requisitar('/push/desassinar', { method: 'POST', body: { endpoint } })
  }
  catch {
    // O backend também descarta endpoints expirados ao receber 404/410 do serviço push.
  }
}

/**
 * Conclui no backend uma re-assinatura feita pelo service worker (`pushsubscriptionchange`),
 * que não tem token para chamar a API. Chamado quando há sessão.
 */
export async function sincronizarPendenciasPush(requisitar: Requisitar): Promise<void> {
  if (!import.meta.client || !('caches' in window)) return
  try {
    const cache = await caches.open(CACHE_PENDENCIAS)
    const resposta = await cache.match(CHAVE_PENDENCIA)
    if (!resposta) return
    const pendencia = await resposta.json() as {
      endpointAntigo: string | null
      assinatura: { endpoint?: string, keys?: { p256dh?: string, auth?: string } }
    }
    const { endpoint, keys } = pendencia.assinatura
    if (!endpoint || !keys?.p256dh || !keys.auth) {
      await cache.delete(CHAVE_PENDENCIA)
      return
    }
    const payload: PushAssinaturaCreate = {
      endpoint,
      p256dh: keys.p256dh,
      auth: keys.auth,
      user_agent: navigator.userAgent,
    }
    await requisitar<PushAssinaturaRead>('/push/assinar', {
      method: 'POST',
      body: payload as Record<string, unknown>,
    })
    if (pendencia.endpointAntigo && pendencia.endpointAntigo !== endpoint) {
      await desassinarNoBackend(requisitar, pendencia.endpointAntigo)
    }
    await cache.delete(CHAVE_PENDENCIA)
  }
  catch {
    // Mantém a pendência para a próxima tentativa.
  }
}

export function usePushNotification() {
  const { requisitar } = useApi()

  const suportado = ref(false)
  const permissao = ref<NotificationPermission>('default')
  const inscrito = ref(false)
  const carregando = ref(false)
  const erro = ref<string | null>(null)
  /** iOS só entrega push para apps instalados na tela inicial. */
  const requerInstalacaoIos = ref(false)

  function verificarSuporte(): boolean {
    if (!import.meta.client) return false
    return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window
  }

  async function atualizarStatus() {
    requerInstalacaoIos.value = import.meta.client && ehIos() && !emModoInstalado()
    if (!verificarSuporte()) {
      suportado.value = false
      return
    }
    suportado.value = true
    permissao.value = Notification.permission

    try {
      const reg = await swProntoComTimeout()
      if (!reg) {
        inscrito.value = false
        return
      }
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

      const reg = await swProntoComTimeout()
      if (!reg) {
        throw new Error('O service worker ainda não está ativo. Recarregue o app (use a versão instalada ou de produção) e tente novamente.')
      }
      const chave = urlBase64ToUint8Array(public_key)
      let sub = await reg.pushManager.getSubscription()
      if (sub && !mesmaChave(sub.options.applicationServerKey, chave)) {
        // Chave VAPID mudou: descarta a assinatura antiga também no backend.
        const endpointAntigo = sub.endpoint
        await sub.unsubscribe()
        await desassinarNoBackend(requisitar, endpointAntigo)
        sub = null
      }

      sub ??= await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: chave,
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
      const reg = await swProntoComTimeout()
      const sub = await reg?.pushManager.getSubscription()
      if (sub) {
        await desassinarNoBackend(requisitar, sub.endpoint)
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
    requerInstalacaoIos,
    atualizarStatus,
    ativar,
    desativar,
  }
}
