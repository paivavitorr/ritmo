import { hojeIsoNoFuso, minutosDesdeMeiaNoiteNoFuso } from '~/utils/tempo'

const LIMITE_TIMEOUT_MS = 2 ** 31 - 1

/**
 * Data ativa da tela "Hoje". Quando o usuário está vendo o dia corrente, a data acompanha a
 * virada da meia-noite (no fuso informado) e a volta do app ao primeiro plano.
 */
export function useDiaAtual(fuso: Ref<string>) {
  const hojeIso = ref(hojeIsoNoFuso(fuso.value))
  const dataAtivaIso = ref(hojeIso.value)
  let timerMeiaNoite: ReturnType<typeof setTimeout> | null = null

  function verificarVirada() {
    const novoHoje = hojeIsoNoFuso(fuso.value)
    if (novoHoje !== hojeIso.value) {
      // Só acompanha se o usuário estava olhando o "hoje" que acabou de passar.
      if (dataAtivaIso.value === hojeIso.value) dataAtivaIso.value = novoHoje
      hojeIso.value = novoHoje
    }
    agendarProximaMeiaNoite()
  }

  function agendarProximaMeiaNoite() {
    if (timerMeiaNoite) clearTimeout(timerMeiaNoite)
    const minutosDecorridos = minutosDesdeMeiaNoiteNoFuso(
      new Date().toISOString(),
      hojeIsoNoFuso(fuso.value),
      fuso.value,
    )
    const msRestantes = Math.max(1000, (1440 - minutosDecorridos) * 60_000 + 1000)
    timerMeiaNoite = setTimeout(verificarVirada, Math.min(msRestantes, LIMITE_TIMEOUT_MS))
  }

  function aoMudarVisibilidade() {
    if (document.visibilityState === 'visible') verificarVirada()
  }

  function irParaHoje() {
    verificarVirada()
    dataAtivaIso.value = hojeIso.value
  }

  watch(fuso, () => {
    const eraHoje = dataAtivaIso.value === hojeIso.value
    hojeIso.value = hojeIsoNoFuso(fuso.value)
    if (eraHoje) dataAtivaIso.value = hojeIso.value
    agendarProximaMeiaNoite()
  })

  onMounted(() => {
    document.addEventListener('visibilitychange', aoMudarVisibilidade)
    window.addEventListener('focus', verificarVirada)
    verificarVirada()
  })

  onBeforeUnmount(() => {
    document.removeEventListener('visibilitychange', aoMudarVisibilidade)
    window.removeEventListener('focus', verificarVirada)
    if (timerMeiaNoite) clearTimeout(timerMeiaNoite)
  })

  return { dataAtivaIso, hojeIso, irParaHoje }
}
