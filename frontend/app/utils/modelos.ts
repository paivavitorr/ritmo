import { calcularMinutosLiquidos } from './horasLiquidas'

export interface ModeloParaDuracao {
  hora_inicio: string
  hora_fim: string
  pausas: Array<{ offset_min: number, duracao_min: number }>
}

/** Minutos líquidos de um bloco do modelo semanal (pausas sobrepostas são mescladas). */
export function duracaoModeloMin(modelo: ModeloParaDuracao): number {
  const [hi = 0, mi = 0] = modelo.hora_inicio.split(':').map(Number)
  const [hf = 0, mf = 0] = modelo.hora_fim.split(':').map(Number)
  const ini = hi * 60 + mi
  let fim = hf * 60 + mf
  if (fim <= ini) fim += 1440
  const pausas = modelo.pausas.map(p => ({
    inicioMin: ini + p.offset_min,
    fimMin: ini + p.offset_min + p.duracao_min,
  }))
  return calcularMinutosLiquidos(ini, fim, pausas)
}
