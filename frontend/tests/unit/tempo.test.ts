import { describe, expect, it } from 'vitest'
import {
  ajustarHorarioInput,
  arredondarParaStep,
  criarTimestampUtcDeMinutosLocais,
  dataIsoNoFuso,
  diaSemanaDeDataIso,
  formatarDiaMesCurto,
  horaInputParaMinutos,
  inicioDaSemanaIso,
  minutosDesdeMeiaNoiteNoFuso,
  minutosParaHoraInput,
  somarDiasIso,
} from '~/utils/tempo'

describe('criarTimestampUtcDeMinutosLocais', () => {
  it('converte horário comum (Sao_Paulo, UTC-3)', () => {
    expect(criarTimestampUtcDeMinutosLocais('2026-06-10', 8 * 60, 'America/Sao_Paulo'))
      .toBe('2026-06-10T11:00:00.000Z')
  })

  it('suporta minutos >= 1440 (cruza a meia-noite)', () => {
    expect(criarTimestampUtcDeMinutosLocais('2026-06-10', 1440 + 30, 'America/Sao_Paulo'))
      .toBe('2026-06-11T03:30:00.000Z')
  })

  it('NY: horário normal antes e depois da transição de verão', () => {
    expect(criarTimestampUtcDeMinutosLocais('2026-03-08', 60, 'America/New_York'))
      .toBe('2026-03-08T06:00:00.000Z') // 01:00 EST
    expect(criarTimestampUtcDeMinutosLocais('2026-03-08', 4 * 60, 'America/New_York'))
      .toBe('2026-03-08T08:00:00.000Z') // 04:00 EDT
  })

  it('NY: horário inexistente (02:30 em 2026-03-08) avança para 03:30 EDT', () => {
    const iso = criarTimestampUtcDeMinutosLocais('2026-03-08', 2 * 60 + 30, 'America/New_York')
    expect(iso).toBe('2026-03-08T07:30:00.000Z')
    expect(minutosDesdeMeiaNoiteNoFuso(iso, '2026-03-08', 'America/New_York')).toBe(3 * 60 + 30)
  })

  it('NY: horário ambíguo (01:30 em 2026-11-01) usa a primeira ocorrência (EDT)', () => {
    expect(criarTimestampUtcDeMinutosLocais('2026-11-01', 60 + 30, 'America/New_York'))
      .toBe('2026-11-01T05:30:00.000Z')
  })

  it('NY: após a volta do horário (03:00 em 2026-11-01) usa EST', () => {
    expect(criarTimestampUtcDeMinutosLocais('2026-11-01', 3 * 60, 'America/New_York'))
      .toBe('2026-11-01T08:00:00.000Z')
  })

  it('Sao_Paulo 2018-11-04: meia-noite inexistente avança para 01:00 local', () => {
    const iso = criarTimestampUtcDeMinutosLocais('2018-11-04', 0, 'America/Sao_Paulo')
    expect(iso).toBe('2018-11-04T03:00:00.000Z')
    expect(minutosDesdeMeiaNoiteNoFuso(iso, '2018-11-04', 'America/Sao_Paulo')).toBe(60)
  })

  it('Sao_Paulo 2018-11-04: 01:30 (já em verão, UTC-2)', () => {
    expect(criarTimestampUtcDeMinutosLocais('2018-11-04', 90, 'America/Sao_Paulo'))
      .toBe('2018-11-04T03:30:00.000Z')
  })

  it('ida e volta é idempotente para horários válidos', () => {
    for (const min of [0, 59, 480, 725, 1439]) {
      const iso = criarTimestampUtcDeMinutosLocais('2026-09-15', min, 'Europe/Lisbon')
      expect(minutosDesdeMeiaNoiteNoFuso(iso, '2026-09-15', 'Europe/Lisbon')).toBe(min)
    }
  })
})

describe('minutosDesdeMeiaNoiteNoFuso', () => {
  it('retorna minutos no dia de referência', () => {
    expect(minutosDesdeMeiaNoiteNoFuso('2026-06-10T11:00:00.000Z', '2026-06-10', 'America/Sao_Paulo'))
      .toBe(480)
  })

  it('meia-noite local vale 0 (não 1440)', () => {
    expect(minutosDesdeMeiaNoiteNoFuso('2026-06-10T03:00:00.000Z', '2026-06-10', 'America/Sao_Paulo'))
      .toBe(0)
  })

  it('virada de meia-noite: dia seguinte soma 1440', () => {
    expect(minutosDesdeMeiaNoiteNoFuso('2026-06-11T03:30:00.000Z', '2026-06-10', 'America/Sao_Paulo'))
      .toBe(1440 + 30)
  })

  it('dia anterior fica negativo', () => {
    expect(minutosDesdeMeiaNoiteNoFuso('2026-06-10T02:00:00.000Z', '2026-06-10', 'America/Sao_Paulo'))
      .toBe(-60)
  })
})

describe('datas ISO', () => {
  it('dataIsoNoFuso respeita o fuso', () => {
    const instante = new Date('2026-06-10T02:00:00.000Z')
    expect(dataIsoNoFuso(instante, 'America/Sao_Paulo')).toBe('2026-06-09')
    expect(dataIsoNoFuso(instante, 'UTC')).toBe('2026-06-10')
  })

  it('somarDiasIso cruza mês e ano', () => {
    expect(somarDiasIso('2026-01-31', 1)).toBe('2026-02-01')
    expect(somarDiasIso('2026-01-01', -1)).toBe('2025-12-31')
    expect(somarDiasIso('2026-03-08', 7)).toBe('2026-03-15')
  })

  it('diaSemanaDeDataIso usa 0=domingo', () => {
    expect(diaSemanaDeDataIso('2026-11-08')).toBe(0)
    expect(diaSemanaDeDataIso('2026-11-06')).toBe(5)
  })

  it('inicioDaSemanaIso com semana iniciando na segunda (padrão)', () => {
    expect(inicioDaSemanaIso('2026-11-06')).toBe('2026-11-02') // sexta
    expect(inicioDaSemanaIso('2026-11-02')).toBe('2026-11-02') // segunda
    expect(inicioDaSemanaIso('2026-11-08')).toBe('2026-11-02') // domingo
  })

  it('inicioDaSemanaIso com semana iniciando no domingo', () => {
    expect(inicioDaSemanaIso('2026-11-06', 0)).toBe('2026-11-01')
    expect(inicioDaSemanaIso('2026-11-08', 0)).toBe('2026-11-08')
    expect(inicioDaSemanaIso('2026-01-01', 0)).toBe('2025-12-28')
  })
})

describe('formatações', () => {
  it('minutosParaHoraInput normaliza e preenche zeros', () => {
    expect(minutosParaHoraInput(0)).toBe('00:00')
    expect(minutosParaHoraInput(65)).toBe('01:05')
    expect(minutosParaHoraInput(1440)).toBe('00:00')
    expect(minutosParaHoraInput(-60)).toBe('23:00')
  })

  it('horaInputParaMinutos faz parse e limita', () => {
    expect(horaInputParaMinutos('08:30')).toBe(510)
    expect(horaInputParaMinutos('abc')).toBe(0)
    expect(horaInputParaMinutos('25:00')).toBe(1439)
  })

  it('arredondarParaStep', () => {
    expect(arredondarParaStep(62)).toBe(60)
    expect(arredondarParaStep(68, 5)).toBe(70)
  })

  it('formatarDiaMesCurto', () => {
    expect(formatarDiaMesCurto('2026-11-06')).toBe('06/11')
  })

  it('ajustarHorarioInput respeita limites de início e fim', () => {
    expect(ajustarHorarioInput('08:00', 'inicio', 5)).toBe('08:05')
    expect(ajustarHorarioInput('23:55', 'inicio', 5)).toBe('23:55')
    expect(ajustarHorarioInput('00:00', 'inicio', -5)).toBe('00:00')
    expect(ajustarHorarioInput('00:00', 'fim', -5)).toBe('23:55')
    expect(ajustarHorarioInput('23:55', 'fim', 5)).toBe('00:00')
    expect(ajustarHorarioInput('00:05', 'fim', -5)).toBe('00:05')
  })
})
