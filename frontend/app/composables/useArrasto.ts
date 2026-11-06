import { arredondarParaStep } from '~/utils/tempo'

const TEMPO_LONG_PRESS_MS = 300

export type ModoArrasto = 'mover' | 'redimensionar-topo' | 'redimensionar-base'

export interface EstadoArrastoAtivo {
  blocoId: string
  modo: ModoArrasto
  inicioMinOriginal: number
  fimMinOriginal: number
  inicioMinAtual: number
  fimMinAtual: number
}

interface OpcoesUseArrasto {
  pxPorMinuto: Ref<number>
  stepMinutos?: number
  duracaoMinimaMin?: number
  aoConcluir: (
    blocoId: string,
    novoInicioMin: number,
    novoFimMin: number,
  ) => Promise<void> | void
}

export interface LimitesBloco {
  inicioMin: number
  fimMin: number
}

/**
 * Cálculo puro dos novos limites de um bloco (em minutos desde 00:00 do dia exibido).
 *
 * - `mover` preserva a duração; o bloco pode ficar entre `min(0, início)` e `max(1440, fim)`,
 *   então blocos que cruzam a meia-noite nunca são truncados.
 * - `redimensionar-*` respeita a duração mínima só no lado redimensionado e nunca encolhe
 *   (nem estica) o bloco além do que ele já tinha quando for menor que o mínimo.
 */
export function calcularNovosLimites(
  modo: ModoArrasto,
  iniOrig: number,
  fimOrig: number,
  deltaMinBruto: number,
  opcoes: { step?: number, duracaoMinimaMin?: number } = {},
): LimitesBloco {
  const step = opcoes.step ?? 15
  const duracaoMin = opcoes.duracaoMinimaMin ?? 15
  const deltaSnap = arredondarParaStep(deltaMinBruto, step)
  const duracao = fimOrig - iniOrig
  const limiteInferior = Math.min(0, iniOrig)
  const limiteSuperior = Math.max(1440, fimOrig)

  if (modo === 'mover') {
    const novoIni = Math.max(limiteInferior, Math.min(limiteSuperior - duracao, iniOrig + deltaSnap))
    return { inicioMin: novoIni, fimMin: novoIni + duracao }
  }

  if (modo === 'redimensionar-topo') {
    const maxIni = Math.max(iniOrig, fimOrig - duracaoMin)
    const novoIni = Math.max(limiteInferior, Math.min(maxIni, iniOrig + deltaSnap))
    return { inicioMin: novoIni, fimMin: fimOrig }
  }

  const minFim = Math.min(fimOrig, iniOrig + duracaoMin)
  const novoFim = Math.max(minFim, Math.min(limiteSuperior, fimOrig + deltaSnap))
  return { inicioMin: iniOrig, fimMin: novoFim }
}

/**
 * Gerencia arrasto e redimensionamento de blocos na régua via Pointer Events
 * (com long-press de 300ms em touch para conviver com o scroll vertical).
 * `pointercancel` e `Esc` revertem o arrasto sem confirmar.
 */
export function useArrasto(opcoes: OpcoesUseArrasto) {
  const step = opcoes.stepMinutos ?? 15
  const duracaoMin = opcoes.duracaoMinimaMin ?? 15

  const ativo = ref<EstadoArrastoAtivo | null>(null)
  let timerLongPress: ReturnType<typeof setTimeout> | null = null
  let startY = 0
  let movidoSignificativamente = false
  let removerListenersAtivos: (() => void) | null = null

  function limparTimer() {
    if (timerLongPress) {
      clearTimeout(timerLongPress)
      timerLongPress = null
    }
  }

  function limparListeners() {
    limparTimer()
    if (removerListenersAtivos) {
      removerListenersAtivos()
      removerListenersAtivos = null
    }
  }

  function suprimirProximoClick() {
    const bloquearClick = (ev: MouseEvent) => {
      ev.stopPropagation()
      ev.preventDefault()
      window.removeEventListener('click', bloquearClick, true)
    }
    window.addEventListener('click', bloquearClick, true)
    setTimeout(() => {
      window.removeEventListener('click', bloquearClick, true)
    }, 120)
  }

  function iniciarPointer(
    evento: PointerEvent,
    blocoId: string,
    modo: ModoArrasto,
    inicioMin: number,
    fimMin: number,
  ) {
    if (evento.button !== 0 && evento.pointerType === 'mouse') return
    evento.stopPropagation()
    limparListeners()

    const alvo = evento.currentTarget as HTMLElement | null
    const pointerId = evento.pointerId
    startY = evento.clientY
    let ultimoY = evento.clientY
    movidoSignificativamente = false

    const ativarAgora = () => {
      // Arrasto começa de onde o dedo está agora, sem salto.
      startY = ultimoY
      ativo.value = {
        blocoId,
        modo,
        inicioMinOriginal: inicioMin,
        fimMinOriginal: fimMin,
        inicioMinAtual: inicioMin,
        fimMinAtual: fimMin,
      }
      try {
        alvo?.setPointerCapture(pointerId)
      }
      catch {
        // captura é só um reforço; o listener na window continua valendo
      }
      navigator.vibrate?.(10)
    }

    // Long-press só para mover com o dedo no corpo do bloco; alças têm touch-action: none.
    if (evento.pointerType === 'touch' && modo === 'mover') {
      limparTimer()
      timerLongPress = setTimeout(ativarAgora, TEMPO_LONG_PRESS_MS)
    }
    else {
      ativarAgora()
    }

    const aoMover = (evMove: PointerEvent) => {
      if (evMove.pointerId !== pointerId) return
      ultimoY = evMove.clientY
      const dy = evMove.clientY - startY
      if (!ativo.value) {
        if (Math.abs(evMove.clientY - evento.clientY) > 8) {
          limparTimer()
        }
        return
      }

      if (Math.abs(dy) > 3) {
        movidoSignificativamente = true
      }

      const { inicioMin: novoIni, fimMin: novoFim } = calcularNovosLimites(
        ativo.value.modo,
        ativo.value.inicioMinOriginal,
        ativo.value.fimMinOriginal,
        dy / opcoes.pxPorMinuto.value,
        { step, duracaoMinimaMin: duracaoMin },
      )
      ativo.value = {
        ...ativo.value,
        inicioMinAtual: novoIni,
        fimMinAtual: novoFim,
      }
    }

    // Enquanto o arrasto está ativo, impede o scroll nativo no toque.
    const aoTouchMove = (ev: TouchEvent) => {
      if (ativo.value && ev.cancelable) ev.preventDefault()
    }
    const aoMenuContexto = (ev: Event) => ev.preventDefault()

    const cancelar = () => {
      limparListeners()
      const estavaAtivo = ativo.value !== null
      ativo.value = null
      if (estavaAtivo && movidoSignificativamente) suprimirProximoClick()
    }

    const aoTeclar = (ev: KeyboardEvent) => {
      if (ev.key === 'Escape') cancelar()
    }

    const finalizar = async (evUp: PointerEvent) => {
      if (evUp.pointerId !== pointerId) return
      limparListeners()

      const estadoFinal = ativo.value
      ativo.value = null

      if (movidoSignificativamente) {
        suprimirProximoClick()
      }

      if (
        estadoFinal
        && movidoSignificativamente
        && (estadoFinal.inicioMinAtual !== estadoFinal.inicioMinOriginal
          || estadoFinal.fimMinAtual !== estadoFinal.fimMinOriginal)
      ) {
        await opcoes.aoConcluir(
          estadoFinal.blocoId,
          estadoFinal.inicioMinAtual,
          estadoFinal.fimMinAtual,
        )
      }
    }

    const aoCancelarPointer = (evCancel: PointerEvent) => {
      if (evCancel.pointerId === pointerId) cancelar()
    }

    removerListenersAtivos = () => {
      window.removeEventListener('pointermove', aoMover)
      window.removeEventListener('pointerup', finalizar)
      window.removeEventListener('pointercancel', aoCancelarPointer)
      window.removeEventListener('touchmove', aoTouchMove)
      window.removeEventListener('contextmenu', aoMenuContexto, true)
      window.removeEventListener('keydown', aoTeclar)
      try {
        alvo?.releasePointerCapture(pointerId)
      }
      catch {
        // já liberado
      }
    }

    window.addEventListener('pointermove', aoMover)
    window.addEventListener('pointerup', finalizar)
    window.addEventListener('pointercancel', aoCancelarPointer)
    window.addEventListener('touchmove', aoTouchMove, { passive: false })
    window.addEventListener('contextmenu', aoMenuContexto, true)
    window.addEventListener('keydown', aoTeclar)
  }

  onBeforeUnmount(limparListeners)

  return {
    ativo,
    iniciarPointer,
  }
}
