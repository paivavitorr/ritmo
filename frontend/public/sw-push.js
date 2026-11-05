// Listener de Web Push para notificações em segundo plano do Ritmo
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
  const options = {
    body: data.corpo || 'Seu próximo bloco de rotina começa em breve.',
    icon: '/pwa-192x192.png',
    badge: '/pwa-192x192.png',
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
  const destino = event.notification.data?.url || '/'

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((janelas) => {
      for (const janela of janelas) {
        if (janela.url.includes(self.location.origin) && 'focus' in janela) {
          return janela.navigate(destino).then((w) => (w && 'focus' in w ? w.focus() : null))
        }
      }
      if (self.clients.openWindow) {
        return self.clients.openWindow(destino)
      }
    }),
  )
})
