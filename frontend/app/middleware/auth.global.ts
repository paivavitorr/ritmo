export default defineNuxtRouteMiddleware(async (to) => {
  const auth = useAuthStore()
  await auth.garantirHidratacao()

  const rotasPublicas = new Set(['/login', '/design-system'])
  if (rotasPublicas.has(to.path)) {
    if (to.path === '/login' && auth.autenticado) {
      return navigateTo('/')
    }
    return
  }

  if (!auth.autenticado) {
    return navigateTo('/login')
  }
})
