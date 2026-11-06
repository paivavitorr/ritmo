// Web Push do Ritmo (importado pelo service worker do Workbox via importScripts).

const CACHE_PENDENCIAS = 'ritmo-push-pendencias'
const CHAVE_PENDENCIA = '/__push-pendente__'

self.addEventListener('push', (event) => {
  if (!event.data) {
    return
  }

  let data = {}
  try {
    data = event.data.json()
  }
  catch {
    data = { titulo: 'Ritmo', corpo: event.data.text() }
  }

  const titulo = data.titulo || 'Ritmo — Lembrete de Bloco'
  // Uma notificação por bloco: reenvios substituem a anterior em vez de duplicar.
  const tag = data.bloco_id ? `bloco-${data.bloco_id}` : (data.lembrete_id ? `lembrete-${data.lembrete_id}` : 'ritmo')
  const options = {
    body: data.corpo || 'Seu próximo bloco de rotina começa em breve.',
    icon: '/pwa-192x192.png',
    badge: '/pwa-badge-96x96.png',
    tag,
    renotify: false,
    data: {
      url: data.url || '/',
      lembrete_id: data.lembrete_id,
      bloco_id: data.bloco_id,
    },
  }

  event.waitUntil(self.registration.showNotification(titulo, options))
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const destino = new URL(event.notification.data?.url || '/', self.location.origin).href

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((janelas) => {
      const existente = janelas.find(j => j.url.startsWith(self.location.origin) && 'focus' in j)
      if (existente) {
        // Não usa navigate(): falha em clientes não controlados. A página decide a rota.
        existente.postMessage({ tipo: 'push-navegar', url: destino })
        return existente.focus()
      }
      return self.clients.openWindow(destino)
    }),
  )
})

function urlBase64ParaUint8Array(base64) {
  const padding = '='.repeat((4 - (base64.length % 4)) % 4)
  const bruto = atob((base64 + padding).replace(/-/g, '+').replace(/_/g, '/'))
  return Uint8Array.from(bruto, c => c.charCodeAt(0))
}

/**
 * O navegador invalidou a assinatura: reassina com a mesma chave pública.
 *
 * Limitação: a API exige Bearer token, que o service worker não possui (só há o cookie
 * de refresh). Por isso o SW NÃO consegue registrar a nova assinatura sozinho: ele a
 * entrega aos clientes abertos (postMessage) ou a guarda no Cache API, e o app
 * (usePushNotification) conclui o POST /push/assinar quando houver sessão.
 */
self.addEventListener('pushsubscriptionchange', (event) => {
  event.waitUntil((async () => {
    const antiga = event.oldSubscription
    const chave = antiga?.options?.applicationServerKey
      ?? event.newSubscription?.options?.applicationServerKey
    let nova = event.newSubscription ?? null
    if (!nova && chave) {
      nova = await self.registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: chave instanceof ArrayBuffer ? chave : urlBase64ParaUint8Array(String(chave)),
      })
    }
    if (!nova) return

    const registro = {
      tipo: 'push-reassinado',
      endpointAntigo: antiga?.endpoint ?? null,
      assinatura: nova.toJSON(),
    }

    const cache = await caches.open(CACHE_PENDENCIAS)
    await cache.put(CHAVE_PENDENCIA, new Response(JSON.stringify(registro)))

    const janelas = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
    for (const janela of janelas) janela.postMessage(registro)
  })())
})
