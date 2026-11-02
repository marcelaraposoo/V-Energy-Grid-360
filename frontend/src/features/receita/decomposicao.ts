// Fórmulas da A4 (contrato da Gold), com P = receita / volume:
//   efeito_volume = (V1 − V0) × P0      efeito_preco = (P1 − P0) × V1
// A soma é exata. Sem volume em um dos períodos, o preço dele fica nulo e toda a variação é volume.
export type Decomposicao = {
  preco_base_kwh: number | null
  preco_atual_kwh: number | null
  efeito_volume: number
  efeito_preco: number
}

export function decompor(volumeBase: number, receitaBase: number, volumeAtual: number, receitaAtual: number): Decomposicao {
  const precoBase = volumeBase ? receitaBase / volumeBase : null
  const precoAtual = volumeAtual ? receitaAtual / volumeAtual : null
  if (precoBase === null || precoAtual === null) {
    return { preco_base_kwh: precoBase, preco_atual_kwh: precoAtual, efeito_volume: receitaAtual - receitaBase, efeito_preco: 0 }
  }
  return {
    preco_base_kwh: precoBase,
    preco_atual_kwh: precoAtual,
    efeito_volume: (volumeAtual - volumeBase) * precoBase,
    efeito_preco: (precoAtual - precoBase) * volumeAtual,
  }
}

export function variacaoPct(base: number, atual: number): number | null {
  return base ? (atual / base - 1) * 100 : null
}
