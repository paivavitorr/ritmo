import { describe, expect, it } from 'vitest'
import {
  intervaloParaPausaHora,
  intervaloParaPausaIso,
  intervaloParaPausaModelo,
  pausaHoraParaIntervalo,
  pausasIsoParaHora,
  recortarPausas,
  recortarPausasIso,
  validarPausa,
} from '~/utils/pausas'
import { duracaoModeloMin } from '~/utils/modelos'

describe('pausaHoraParaIntervalo', () => {
  it('converte HH:MM em minutos', () => {
    expect(pausaHoraParaIntervalo({ inicioHora: '12:00', fimHora: '12:30' }, 480))
      .toEqual({ inicioMin: 720, fimMin: 750 })
  })

  it('pausa antes do início do bloco vai para o dia seguinte', () => {
    expect(pausaHoraParaIntervalo({ inicioHora: '00:30', fimHora: '00:45' }, 22 * 60))
      .toEqual({ inicioMin: 1470, fimMin: 1485 })
  })

  it('fim menor que início cruza a meia-noite', () => {
    expect(pausaHoraParaIntervalo({ inicioHora: '23:50', fimHora: '00:10' }, 22 * 60))
      .toEqual({ inicioMin: 1430, fimMin: 1450 })
  })
})

describe('conversões hora, ISO e modelo', () => {
  it('intervaloParaPausaHora', () => {
    expect(intervaloParaPausaHora({ inicioMin: 725, fimMin: 1500 }))
      .toEqual({ inicioHora: '12:05', fimHora: '01:00' })
  })

  it('ida e volta ISO no fuso do usuário', () => {
    const iso = intervaloParaPausaIso({ inicioMin: 720, fimMin: 750 }, '2026-06-10', 'America/Sao_Paulo')
    expect(iso).toEqual({ inicio: '2026-06-10T15:00:00.000Z', fim: '2026-06-10T15:30:00.000Z' })
    expect(pausasIsoParaHora([iso], '2026-06-10', 'America/Sao_Paulo'))
      .toEqual([{ inicioHora: '12:00', fimHora: '12:30' }])
  })

  it('intervaloParaPausaModelo usa offset e duração mínima de 1', () => {
    expect(intervaloParaPausaModelo({ inicioMin: 540, fimMin: 555 }, 480))
      .toEqual({ offset_min: 60, duracao_min: 15 })
    expect(intervaloParaPausaModelo({ inicioMin: 400, fimMin: 400 }, 480))
      .toEqual({ offset_min: 0, duracao_min: 1 })
  })
})

describe('validarPausa', () => {
  it('detecta pausa invertida, fora e válida', () => {
    expect(validarPausa({ inicioMin: 600, fimMin: 600 }, 480, 720)).toBe('invertida')
    expect(validarPausa({ inicioMin: 470, fimMin: 500 }, 480, 720)).toBe('fora')
    expect(validarPausa({ inicioMin: 700, fimMin: 730 }, 480, 720)).toBe('fora')
    expect(validarPausa({ inicioMin: 600, fimMin: 630 }, 480, 720)).toBeNull()
  })
})

describe('recortarPausas', () => {
  const pausas = [
    { inicioMin: 400, fimMin: 500 },
    { inicioMin: 540, fimMin: 560 },
    { inicioMin: 650, fimMin: 700 },
    { inicioMin: 100, fimMin: 200 },
  ]

  it('recorta as parcialmente fora e descarta as totalmente fora', () => {
    expect(recortarPausas(pausas, 480, 660)).toEqual([
      { inicioMin: 480, fimMin: 500 },
      { inicioMin: 540, fimMin: 560 },
      { inicioMin: 650, fimMin: 660 },
    ])
  })

  it('descarta quando fica vazia', () => {
    expect(recortarPausas([{ inicioMin: 400, fimMin: 480 }], 480, 600)).toEqual([])
  })
})

describe('recortarPausasIso', () => {
  it('recorta pausas ISO ao novo intervalo', () => {
    const r = recortarPausasIso(
      [
        { inicio: '2026-06-10T10:00:00.000Z', fim: '2026-06-10T11:00:00.000Z' },
        { inicio: '2026-06-10T07:00:00.000Z', fim: '2026-06-10T08:00:00.000Z' },
      ],
      '2026-06-10T10:30:00.000Z',
      '2026-06-10T12:00:00.000Z',
    )
    expect(r).toEqual([{ inicio: '2026-06-10T10:30:00.000Z', fim: '2026-06-10T11:00:00.000Z' }])
  })
})

describe('duracaoModeloMin', () => {
  it('desconta pausas', () => {
    expect(duracaoModeloMin({
      hora_inicio: '08:00:00',
      hora_fim: '10:00:00',
      pausas: [{ offset_min: 30, duracao_min: 15 }],
    })).toBe(105)
  })

  it('mescla pausas sobrepostas', () => {
    expect(duracaoModeloMin({
      hora_inicio: '08:00:00',
      hora_fim: '10:00:00',
      pausas: [
        { offset_min: 30, duracao_min: 30 },
        { offset_min: 45, duracao_min: 30 },
      ],
    })).toBe(75)
  })

  it('fim anterior ao início cruza a meia-noite', () => {
    expect(duracaoModeloMin({ hora_inicio: '23:00:00', hora_fim: '01:00:00', pausas: [] })).toBe(120)
  })
})
