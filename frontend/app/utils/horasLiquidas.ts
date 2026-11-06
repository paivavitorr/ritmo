export interface IntervaloMinutos {
  inicioMin: number
  fimMin: number
}

export interface PosicaoBlocoLayout {
  id: string
  inicioMin: number
  fimMin: number
  coluna: number
  totalColunas: number
}

/**
 * Ordena e funde intervalos que se tocam ou se sobrepõem. Não muta a entrada.
 */
export function mesclarIntervalos(intervalos: IntervaloMinutos[]): IntervaloMinutos[] {
  const ordenados = intervalos
    .filter(i => i.fimMin > i.inicioMin)
    .sort((a, b) => a.inicioMin - b.inicioMin || a.fimMin - b.fimMin)
  const unidos: IntervaloMinutos[] = []
  for (const atual of ordenados) {
    const ultimo = unidos[unidos.length - 1]
    if (ultimo && atual.inicioMin <= ultimo.fimMin) {
      if (atual.fimMin > ultimo.fimMin) {
        unidos[unidos.length - 1] = { inicioMin: ultimo.inicioMin, fimMin: atual.fimMin }
      }
    }
    else {
      unidos.push({ ...atual })
    }
  }
  return unidos
}

/**
 * Mescla intervalos de pausa sobrepostos e calcula os minutos líquidos planejados
 * dentro de `[inicioMin, fimMin)`. Pausas fora do intervalo são recortadas/ignoradas.
 */
export function calcularMinutosLiquidos(
  inicioMin: number,
  fimMin: number,
  pausas: IntervaloMinutos[],
): number {
  const duracaoBruta = Math.max(0, fimMin - inicioMin)
  if (duracaoBruta === 0 || pausas.length === 0) return duracaoBruta

  const recortadas = pausas.map(p => ({
    inicioMin: Math.max(inicioMin, p.inicioMin),
    fimMin: Math.min(fimMin, p.fimMin),
  }))
  const totalPausas = mesclarIntervalos(recortadas).reduce(
    (acc, p) => acc + (p.fimMin - p.inicioMin),
    0,
  )
  return Math.max(0, duracaoBruta - totalPausas)
}

/**
 * Agrupa blocos que se sobrepõem no tempo em clusters e atribui colunas lado a lado
 * (`coluna` de `0` a `totalColunas - 1`) para renderização limpa na régua.
 */
export function calcularLayoutSobreposicao(
  itens: Array<{ id: string, inicioMin: number, fimMin: number }>,
): Map<string, PosicaoBlocoLayout> {
  const resultado = new Map<string, PosicaoBlocoLayout>()
  if (itens.length === 0) return resultado

  const ordenados = [...itens].sort(
    (a, b) => a.inicioMin - b.inicioMin || b.fimMin - a.fimMin,
  )

  // Separa em clusters disjuntos de sobreposição
  const clusters: Array<typeof ordenados> = []
  let clusterAtual: typeof ordenados = []
  let fimMaxCluster = -Infinity

  for (const item of ordenados) {
    if (clusterAtual.length === 0 || item.inicioMin < fimMaxCluster) {
      clusterAtual.push(item)
      fimMaxCluster = Math.max(fimMaxCluster, item.fimMin)
    }
    else {
      clusters.push(clusterAtual)
      clusterAtual = [item]
      fimMaxCluster = item.fimMin
    }
  }
  if (clusterAtual.length > 0) {
    clusters.push(clusterAtual)
  }

  for (const cluster of clusters) {
    const fimPorColuna: number[] = []
    const atribuicoes: Array<{ item: (typeof ordenados)[number], coluna: number }> = []

    for (const item of cluster) {
      let colEncontrada = fimPorColuna.findIndex(fimCol => fimCol <= item.inicioMin)
      if (colEncontrada === -1) {
        colEncontrada = fimPorColuna.length
        fimPorColuna.push(item.fimMin)
      }
      else {
        fimPorColuna[colEncontrada] = item.fimMin
      }
      atribuicoes.push({ item, coluna: colEncontrada })
    }

    const totalColunas = Math.max(1, fimPorColuna.length)
    for (const { item, coluna } of atribuicoes) {
      resultado.set(item.id, {
        id: item.id,
        inicioMin: item.inicioMin,
        fimMin: item.fimMin,
        coluna,
        totalColunas,
      })
    }
  }

  return resultado
}
