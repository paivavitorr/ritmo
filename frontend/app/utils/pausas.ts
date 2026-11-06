import type { IntervaloMinutos } from './horasLiquidas'
import {
  criarTimestampUtcDeMinutosLocais,
  horaInputParaMinutos,
  minutosDesdeMeiaNoiteNoFuso,
  minutosParaHoraInput,
} from './tempo'

/** Pausa como editada na UI: horários `HH:MM` (mesmo formato de `PausaEditavel`). */
export interface PausaHora {
  inicioHora: string
  fimHora: string
}

export interface PausaIso {
  inicio: string
  fim: string
}

/**
 * Converte uma pausa `HH:MM` em intervalo de minutos relativo à meia-noite do dia do bloco.
 * Pausas que "voltam" no relógio em relação ao início do bloco são tratadas como
 * do dia seguinte (bloco que cruza a meia-noite).
 */
export function pausaHoraParaIntervalo(pausa: PausaHora, inicioBlocoMin: number): IntervaloMinutos {
  let inicioMin = horaInputParaMinutos(pausa.inicioHora)
  let fimMin = horaInputParaMinutos(pausa.fimHora)
  if (inicioMin < inicioBlocoMin) inicioMin += 1440
  if (fimMin < inicioMin) fimMin += 1440
  return { inicioMin, fimMin }
}

export function intervaloParaPausaHora(intervalo: IntervaloMinutos): PausaHora {
  return {
    inicioHora: minutosParaHoraInput(intervalo.inicioMin),
    fimHora: minutosParaHoraInput(intervalo.fimMin),
  }
}

/** Converte pausas ISO (UTC) em pausas `HH:MM` no fuso do usuário. */
export function pausasIsoParaHora(pausas: PausaIso[], dataIso: string, fuso: string): PausaHora[] {
  return pausas.map(p => intervaloParaPausaHora({
    inicioMin: minutosDesdeMeiaNoiteNoFuso(p.inicio, dataIso, fuso),
    fimMin: minutosDesdeMeiaNoiteNoFuso(p.fim, dataIso, fuso),
  }))
}

export type ErroPausa = 'invertida' | 'fora'

/** Valida um intervalo de pausa contra `[inicioMin, fimMin]` do bloco. */
export function validarPausa(
  pausa: IntervaloMinutos,
  inicioMin: number,
  fimMin: number,
): ErroPausa | null {
  if (pausa.fimMin <= pausa.inicioMin) return 'invertida'
  if (pausa.inicioMin < inicioMin || pausa.fimMin > fimMin) return 'fora'
  return null
}

export function intervaloParaPausaIso(
  intervalo: IntervaloMinutos,
  dataIso: string,
  fuso: string,
): PausaIso {
  return {
    inicio: criarTimestampUtcDeMinutosLocais(dataIso, intervalo.inicioMin, fuso),
    fim: criarTimestampUtcDeMinutosLocais(dataIso, intervalo.fimMin, fuso),
  }
}

/** Pausa no formato do modelo semanal (offset desde o início do bloco). */
export function intervaloParaPausaModelo(
  intervalo: IntervaloMinutos,
  inicioBlocoMin: number,
): { offset_min: number, duracao_min: number } {
  return {
    offset_min: Math.max(0, intervalo.inicioMin - inicioBlocoMin),
    duracao_min: Math.max(1, intervalo.fimMin - intervalo.inicioMin),
  }
}

/**
 * Recorta pausas ao novo intervalo `[inicio, fim]`: as parcialmente fora são
 * encurtadas; as totalmente fora (ou que ficariam vazias) são descartadas.
 */
export function recortarPausas(
  pausas: IntervaloMinutos[],
  inicio: number,
  fim: number,
): IntervaloMinutos[] {
  const resultado: IntervaloMinutos[] = []
  for (const p of pausas) {
    const inicioMin = Math.max(inicio, p.inicioMin)
    const fimMin = Math.min(fim, p.fimMin)
    if (fimMin > inicioMin) resultado.push({ inicioMin, fimMin })
  }
  return resultado
}

/** Variante de `recortarPausas` para pausas ISO (usada ao mover/redimensionar blocos). */
export function recortarPausasIso(pausas: PausaIso[], inicioIso: string, fimIso: string): PausaIso[] {
  const ini = new Date(inicioIso).getTime()
  const fim = new Date(fimIso).getTime()
  const resultado: PausaIso[] = []
  for (const p of pausas) {
    const pIni = Math.max(ini, new Date(p.inicio).getTime())
    const pFim = Math.min(fim, new Date(p.fim).getTime())
    if (pFim > pIni) {
      resultado.push({ inicio: new Date(pIni).toISOString(), fim: new Date(pFim).toISOString() })
    }
  }
  return resultado
}
