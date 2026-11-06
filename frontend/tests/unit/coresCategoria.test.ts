import { describe, expect, it } from 'vitest'
import { formatarDuracaoMinutos, formatarDuracaoSegundos } from '~/utils/coresCategoria'

describe('formatarDuracaoMinutos', () => {
  it.each([
    [0, '0min'],
    [45, '45min'],
    [60, '1h'],
    [120, '2h'],
    [125, '2h 5min'],
    [185, '3h 5min'],
    [220, '3h 40min'],
    [-10, '0min'],
    [59.6, '1h'],
  ])('%s min -> %s', (entrada, esperado) => {
    expect(formatarDuracaoMinutos(entrada)).toBe(esperado)
  })
})

describe('formatarDuracaoSegundos', () => {
  it('converte segundos para o formato canônico', () => {
    expect(formatarDuracaoSegundos(13_200)).toBe('3h 40min')
    expect(formatarDuracaoSegundos(2_700)).toBe('45min')
  })
})
