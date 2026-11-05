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

/**
 * Formata um Date para `YYYY-MM-DD` no fuso IANA informado.
 */
export function dataIsoNoFuso(instante: Date, fuso: string): string {
  const partes = new Intl.DateTimeFormat('en-CA', {
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

/**
 * Retorna os minutos desde `00:00` de `dataReferenciaIso` no fuso informado para um timestamp ISO.
 */
export function minutosDesdeMeiaNoiteNoFuso(
  isoTimestamp: string,
  dataReferenciaIso: string,
  fuso: string,
): number {
  const dt = new Date(isoTimestamp)
  const partes = new Intl.DateTimeFormat('en-US', {
    timeZone: fuso,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(dt)

  const ano = Number(partes.find(p => p.type === 'year')?.value ?? 2026)
  const mes = Number(partes.find(p => p.type === 'month')?.value ?? 1)
  const dia = Number(partes.find(p => p.type === 'day')?.value ?? 1)
  const horaBruta = Number(partes.find(p => p.type === 'hour')?.value ?? 0)
  const hora = horaBruta === 24 ? 0 : horaBruta
  const minuto = Number(partes.find(p => p.type === 'minute')?.value ?? 0)

  const [refAno = 2026, refMes = 1, refDia = 1] = dataReferenciaIso.split('-').map(Number)
  const utcData = Date.UTC(ano, mes - 1, dia)
  const utcRef = Date.UTC(refAno, refMes - 1, refDia)
  const diasDiff = Math.round((utcData - utcRef) / 86_400_000)

  return diasDiff * 1440 + hora * 60 + minuto
}

/**
 * Converte `(dataIso, minutosDesdeMeiaNoite)` no fuso IANA do usuário para string ISO UTC (`...Z`).
 * Suporta `minutosDesdeMeiaNoite >= 1440` (quando o fim do bloco cruza a meia-noite).
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

  // Chute inicial assumindo UTC e ajuste pelo offset real do fuso naquele instante
  const chuteUtcMs = Date.UTC(ano, mes - 1, dia, hora, minuto, 0)
  const minNoFusoDoChute = minutosDesdeMeiaNoiteNoFuso(
    new Date(chuteUtcMs).toISOString(),
    dataAlvo,
    fuso,
  )
  const erroMinutos = minNoFusoDoChute - (hora * 60 + minuto)
  const ajustadoMs = chuteUtcMs - erroMinutos * 60_000
  return new Date(ajustadoMs).toISOString()
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

export function arredondarParaStep(minutos: number, step = 15): number {
  return Math.round(minutos / step) * step
}

export function formatarDataCabecalho(dataIso: string): string {
  const [ano = 2026, mes = 1, dia = 1] = dataIso.split('-').map(Number)
  const dt = new Date(Date.UTC(ano, mes - 1, dia, 12, 0, 0))
  return new Intl.DateTimeFormat('pt-BR', {
    timeZone: 'UTC',
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  }).format(dt)
}

export function formatarDiaMesCurto(dataIso: string): string {
  const [ano = 2026, mes = 1, dia = 1] = dataIso.split('-').map(Number)
  const dt = new Date(Date.UTC(ano, mes - 1, dia, 12, 0, 0))
  return new Intl.DateTimeFormat('pt-BR', {
    timeZone: 'UTC',
    day: '2-digit',
    month: '2-digit',
  }).format(dt)
}
