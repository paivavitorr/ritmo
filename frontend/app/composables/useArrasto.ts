import { arredondarParaStep } from '~/utils/tempo'

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

/**
 * Gerencia arrasto e redimensionamento de blocos na régua via Pointer Events
 * (com long-press de 250ms em touch para conviver com o scroll vertical).
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

  function calcularNovosLimites(
    modo: ModoArrasto,
    iniOrig: number,
    fimOrig: number,
    deltaMinBruto: number,
  ): { inicioMin: number, fimMin: number } {
    const deltaSnap = arredondarParaStep(deltaMinBruto, step)
    const duracao = fimOrig - iniOrig

    if (modo === 'mover') {
      const novoIni = Math.max(0, Math.min(1440 - duracao, iniOrig + deltaSnap))
      return {
        inicioMin: novoIni,
        fimMin: novoIni + duracao,
      }
    }

    if (modo === 'redimensionar-topo') {
      const novoIni = Math.max(0, Math.min(fimOrig - duracaoMin, iniOrig + deltaSnap))
      return {
        inicioMin: novoIni,
        fimMin: fimOrig,
      }
    }

    // redimensionar-base
    const novoFim = Math.max(iniOrig + duracaoMin, Math.min(1440, fimOrig + deltaSnap))
    return {
      inicioMin: iniOrig,
      fimMin: novoFim,
    }
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

    startY = evento.clientY
    movidoSignificativamente = false

    const ativarAgora = () => {
      ativo.value = {
        blocoId,
        modo,
        inicioMinOriginal: inicioMin,
        fimMinOriginal: fimMin,
        inicioMinAtual: inicioMin,
        fimMinAtual: fimMin,
      }
    }

    if (evento.pointerType === 'touch') {
      limparTimer()
      timerLongPress = setTimeout(ativarAgora, 250)
    }
    else {
      ativarAgora()
    }

    const aoMover = (evMove: PointerEvent) => {
      const dy = evMove.clientY - startY
      if (!ativo.value) {
        if (Math.abs(dy) > 8) {
          limparTimer()
        }
        return
      }

      if (Math.abs(dy) > 3) {
        movidoSignificativamente = true
      }

      const deltaMin = dy / opcoes.pxPorMinuto.value
      const { inicioMin: novoIni, fimMin: novoFim } = calcularNovosLimites(
        ativo.value.modo,
        ativo.value.inicioMinOriginal,
        ativo.value.fimMinOriginal,
        deltaMin,
      )
      ativo.value = {
        ...ativo.value,
        inicioMinAtual: novoIni,
        fimMinAtual: novoFim,
      }
    }

    const finalizar = async () => {
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

    removerListenersAtivos = () => {
      window.removeEventListener('pointermove', aoMover)
      window.removeEventListener('pointerup', finalizar)
      window.removeEventListener('pointercancel', finalizar)
    }

    window.addEventListener('pointermove', aoMover)
    window.addEventListener('pointerup', finalizar)
    window.addEventListener('pointercancel', finalizar)
  }

  onBeforeUnmount(limparListeners)

  return {
    ativo,
    iniciarPointer,
  }
}
