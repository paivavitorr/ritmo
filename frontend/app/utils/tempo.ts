export const NOMES_DIAS_SEMANA = [
  'Domingo',
  'Segunda',
  'Terça',
  'Quarta',
  'Quinta',
  'Sexta',
  'Sábado',
] as const

export const NOMES_DIAS_CURTOS = [
  'Dom',
  'Seg',
  'Ter',
  'Qua',
  'Qui',
  'Sex',
  'Sáb',
] as const

const cacheFormatadores = new Map<string, Intl.DateTimeFormat>()

/** Reaproveita `Intl.DateTimeFormat` por locale + opções (a criação é cara). */
function obterFormatador(locale: string, opcoes: Intl.DateTimeFormatOptions): Intl.DateTimeFormat {
  const chave = `${locale}|${JSON.stringify(opcoes)}`
  let formatador = cacheFormatadores.get(chave)
  if (!formatador) {
    formatador = new Intl.DateTimeFormat(locale, opcoes)
    cacheFormatadores.set(chave, formatador)
  }
  return formatador
}

/**
 * Formata um Date para `YYYY-MM-DD` no fuso IANA informado.
 */
export function dataIsoNoFuso(instante: Date, fuso: string): string {
  const partes = obterFormatador('en-CA', {
    timeZone: fuso,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(instante)

  const ano = partes.find(p => p.type === 'year')?.value ?? '2026'
  const mes = partes.find(p => p.type === 'month')?.value ?? '01'
  const dia = partes.find(p => p.type === 'day')?.value ?? '01'
  return `${ano}-${mes}-${dia}`
}

export function hojeIsoNoFuso(fuso: string): string {
  return dataIsoNoFuso(new Date(), fuso)
}

/**
 * Soma (ou subtrai) dias de uma string `YYYY-MM-DD` sem sofrer com horário de verão.
 */
export function somarDiasIso(dataIso: string, dias: number): string {
  const [ano = 2026, mes = 1, dia = 1] = dataIso.split('-').map(Number)
  const utc = new Date(Date.UTC(ano, mes - 1, dia + dias, 12, 0, 0))
  const a = utc.getUTCFullYear()
  const m = String(utc.getUTCMonth() + 1).padStart(2, '0')
  const d = String(utc.getUTCDate()).padStart(2, '0')
  return `${a}-${m}-${d}`
}

/**
 * Retorna o dia da semana na convenção Ritmo (`0=domingo .. 6=sábado`) para `YYYY-MM-DD`.
 */
export function diaSemanaDeDataIso(dataIso: string): number {
  const [ano = 2026, mes = 1, dia = 1] = dataIso.split('-').map(Number)
  const utc = new Date(Date.UTC(ano, mes - 1, dia, 12, 0, 0))
  return utc.getUTCDay()
}

/**
 * Retorna a data `YYYY-MM-DD` do início da semana contendo `dataIso`,
 * respeitando `inicioSemana` (`0=domingo`, `1=segunda`).
 */
export function inicioDaSemanaIso(dataIso: string, inicioSemana = 1): string {
  const ds = diaSemanaDeDataIso(dataIso)
  const diff = (ds - inicioSemana + 7) % 7
  return somarDiasIso(dataIso, -diff)
}

interface ParteRelogio {
  /** Relógio de parede do fuso, expresso como ms "UTC" (ano/mês/dia/hora/minuto). */
  paredeMs: number
  ano: number
  mes: number
  dia: number
  hora: number
  minuto: number
}

function relogioNoFuso(instanteMs: number, fuso: string): ParteRelogio {
  const partes = obterFormatador('en-US', {
    timeZone: fuso,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date(instanteMs))

  const valor = (tipo: string, padrao: number) =>
    Number(partes.find(p => p.type === tipo)?.value ?? padrao)
  const ano = valor('year', 2026)
  const mes = valor('month', 1)
  const dia = valor('day', 1)
  const hora = valor('hour', 0) % 24
  const minuto = valor('minute', 0)
  return { paredeMs: Date.UTC(ano, mes - 1, dia, hora, minuto), ano, mes, dia, hora, minuto }
}

/** Offset do fuso (minutos, `parede - UTC`) no instante informado. */
function offsetMinutosNoFuso(instanteMs: number, fuso: string): number {
  const minutoUtcMs = Math.floor(instanteMs / 60_000) * 60_000
  return (relogioNoFuso(instanteMs, fuso).paredeMs - minutoUtcMs) / 60_000
}

/**
 * Retorna os minutos desde `00:00` de `dataReferenciaIso` no fuso informado para um timestamp ISO.
 */
export function minutosDesdeMeiaNoiteNoFuso(
  isoTimestamp: string,
  dataReferenciaIso: string,
  fuso: string,
): number {
  const { ano, mes, dia, hora, minuto } = relogioNoFuso(new Date(isoTimestamp).getTime(), fuso)

  const [refAno = 2026, refMes = 1, refDia = 1] = dataReferenciaIso.split('-').map(Number)
  const utcData = Date.UTC(ano, mes - 1, dia)
  const utcRef = Date.UTC(refAno, refMes - 1, refDia)
  const diasDiff = Math.round((utcData - utcRef) / 86_400_000)

  return diasDiff * 1440 + hora * 60 + minuto
}

/**
 * Converte `(dataIso, minutosDesdeMeiaNoite)` no fuso IANA do usuário para string ISO UTC (`...Z`).
 * Suporta `minutosDesdeMeiaNoite >= 1440` (quando o fim do bloco cruza a meia-noite).
 *
 * Horário de verão:
 * - Horário ambíguo (relógio atrasa, ex.: America/New_York 2026-11-01 01:30): escolhe a
 *   primeira ocorrência (offset de verão, instante mais cedo).
 * - Horário inexistente (relógio adianta, ex.: America/New_York 2026-03-08 02:30 ou
 *   America/Sao_Paulo 2018-11-04 00:00): usa o offset anterior à transição, o que
 *   empurra o horário para frente (03:30 e 01:00, respectivamente).
 */
export function criarTimestampUtcDeMinutosLocais(
  dataIso: string,
  minutosDesdeMeiaNoite: number,
  fuso: string,
): string {
  const diasExtras = Math.floor(minutosDesdeMeiaNoite / 1440)
  const minRestantes = ((minutosDesdeMeiaNoite % 1440) + 1440) % 1440
  const hora = Math.floor(minRestantes / 60)
  const minuto = minRestantes % 60
  const dataAlvo = diasExtras !== 0 ? somarDiasIso(dataIso, diasExtras) : dataIso
  const [ano = 2026, mes = 1, dia = 1] = dataAlvo.split('-').map(Number)

  // Relógio de parede desejado tratado como UTC; subtrair o offset real dá o instante.
  const paredeMs = Date.UTC(ano, mes - 1, dia, hora, minuto, 0)
  const offsetAntes = offsetMinutosNoFuso(paredeMs - 86_400_000, fuso)
  const offsetDepois = offsetMinutosNoFuso(paredeMs + 86_400_000, fuso)

  const candidatos = [...new Set([offsetAntes, offsetDepois])]
    .map(offset => paredeMs - offset * 60_000)
    .filter(ms => relogioNoFuso(ms, fuso).paredeMs === paredeMs)
    .sort((a, b) => a - b)

  const instanteMs = candidatos[0] ?? paredeMs - offsetAntes * 60_000
  return new Date(instanteMs).toISOString()
}

export function minutosParaHoraInput(minutos: number): string {
  const normalizado = ((Math.round(minutos) % 1440) + 1440) % 1440
  const h = Math.floor(normalizado / 60)
  const m = normalizado % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}

export function horaInputParaMinutos(valor: string): number {
  const partes = valor.trim().split(':')
  const h = Number(partes[0] ?? 0)
  const m = Number(partes[1] ?? 0)
  if (Number.isNaN(h) || Number.isNaN(m)) return 0
  return Math.max(0, Math.min(1439, h * 60 + m))
}

/**
 * Soma `delta` minutos a um horário `HH:MM` de campo de início (0 a 23:55) ou de fim
 * (5 min a 24:00, exibido como `00:00`). Zero em `fim` com delta negativo vale 24:00.
 */
export function ajustarHorarioInput(valor: string, campo: 'inicio' | 'fim', delta: number): string {
  const bruto = horaInputParaMinutos(valor)
  if (campo === 'inicio') {
    return minutosParaHoraInput(Math.max(0, Math.min(1435, bruto + delta)))
  }
  const atual = bruto === 0 && delta < 0 ? 1440 : bruto
  return minutosParaHoraInput(Math.max(5, Math.min(1440, atual + delta)))
}

export function arredondarParaStep(minutos: number, step = 15): number {
  return Math.round(minutos / step) * step
}

export function formatarDataCabecalho(dataIso: string): string {
  const [ano = 2026, mes = 1, dia = 1] = dataIso.split('-').map(Number)
  const dt = new Date(Date.UTC(ano, mes - 1, dia, 12, 0, 0))
  return obterFormatador('pt-BR', {
    timeZone: 'UTC',
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  }).format(dt)
}

export function formatarDiaMesCurto(dataIso: string): string {
  const [ano = 2026, mes = 1, dia = 1] = dataIso.split('-').map(Number)
  const dt = new Date(Date.UTC(ano, mes - 1, dia, 12, 0, 0))
  return obterFormatador('pt-BR', {
    timeZone: 'UTC',
    day: '2-digit',
    month: '2-digit',
  }).format(dt)
}
