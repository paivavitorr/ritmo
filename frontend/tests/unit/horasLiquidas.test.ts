import { describe, expect, it } from 'vitest'
import {
  calcularLayoutSobreposicao,
  calcularMinutosLiquidos,
  mesclarIntervalos,
} from '~/utils/horasLiquidas'

describe('mesclarIntervalos', () => {
  it('une sobrepostos e adjacentes, ordenando', () => {
    expect(
      mesclarIntervalos([
        { inicioMin: 30, fimMin: 50 },
        { inicioMin: 10, fimMin: 35 },
        { inicioMin: 50, fimMin: 60 },
        { inicioMin: 100, fimMin: 110 },
      ]),
    ).toEqual([
      { inicioMin: 10, fimMin: 60 },
      { inicioMin: 100, fimMin: 110 },
    ])
  })

  it('descarta vazios e não muta a entrada', () => {
    const entrada = [{ inicioMin: 5, fimMin: 5 }, { inicioMin: 1, fimMin: 2 }]
    expect(mesclarIntervalos(entrada)).toEqual([{ inicioMin: 1, fimMin: 2 }])
    expect(entrada[0]).toEqual({ inicioMin: 5, fimMin: 5 })
  })

  it('intervalo contido não encurta o maior', () => {
    expect(mesclarIntervalos([{ inicioMin: 0, fimMin: 100 }, { inicioMin: 10, fimMin: 20 }]))
      .toEqual([{ inicioMin: 0, fimMin: 100 }])
  })
})

describe('calcularMinutosLiquidos', () => {
  it('sem pausas devolve a duração bruta', () => {
    expect(calcularMinutosLiquidos(480, 600, [])).toBe(120)
  })

  it('duração negativa vira 0', () => {
    expect(calcularMinutosLiquidos(600, 480, [])).toBe(0)
  })

  it('desconta pausas simples', () => {
    expect(calcularMinutosLiquidos(480, 600, [{ inicioMin: 520, fimMin: 535 }])).toBe(105)
  })

  it('mescla pausas sobrepostas (não desconta duas vezes)', () => {
    expect(
      calcularMinutosLiquidos(480, 600, [
        { inicioMin: 500, fimMin: 530 },
        { inicioMin: 520, fimMin: 540 },
      ]),
    ).toBe(80)
  })

  it('recorta pausas parcialmente fora do intervalo', () => {
    expect(calcularMinutosLiquidos(480, 600, [{ inicioMin: 470, fimMin: 490 }])).toBe(110)
    expect(calcularMinutosLiquidos(480, 600, [{ inicioMin: 590, fimMin: 700 }])).toBe(110)
  })

  it('ignora pausas totalmente fora', () => {
    expect(calcularMinutosLiquidos(480, 600, [{ inicioMin: 0, fimMin: 100 }])).toBe(120)
  })

  it('nunca fica negativo', () => {
    expect(calcularMinutosLiquidos(480, 500, [{ inicioMin: 0, fimMin: 1000 }])).toBe(0)
  })
})

describe('calcularLayoutSobreposicao', () => {
  it('lista vazia gera mapa vazio', () => {
    expect(calcularLayoutSobreposicao([]).size).toBe(0)
  })

  it('blocos disjuntos ocupam coluna única', () => {
    const r = calcularLayoutSobreposicao([
      { id: 'a', inicioMin: 0, fimMin: 60 },
      { id: 'b', inicioMin: 60, fimMin: 120 },
    ])
    expect(r.get('a')).toMatchObject({ coluna: 0, totalColunas: 1 })
    expect(r.get('b')).toMatchObject({ coluna: 0, totalColunas: 1 })
  })

  it('blocos sobrepostos dividem colunas', () => {
    const r = calcularLayoutSobreposicao([
      { id: 'a', inicioMin: 0, fimMin: 90 },
      { id: 'b', inicioMin: 30, fimMin: 120 },
    ])
    expect(r.get('a')).toMatchObject({ coluna: 0, totalColunas: 2 })
    expect(r.get('b')).toMatchObject({ coluna: 1, totalColunas: 2 })
  })

  it('reaproveita coluna livre dentro do cluster e isola clusters', () => {
    const r = calcularLayoutSobreposicao([
      { id: 'a', inicioMin: 0, fimMin: 60 },
      { id: 'b', inicioMin: 30, fimMin: 90 },
      { id: 'c', inicioMin: 60, fimMin: 100 },
      { id: 'd', inicioMin: 200, fimMin: 260 },
    ])
    expect(r.get('c')).toMatchObject({ coluna: 0, totalColunas: 2 })
    expect(r.get('d')).toMatchObject({ coluna: 0, totalColunas: 1 })
  })
})
