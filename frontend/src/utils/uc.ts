export function normalizarIdentificadorUC(value: string): string {
  const identificador = value.trim().toUpperCase()
  return /^\d{6}$/.test(identificador) ? `UC${identificador}` : identificador
}

export function identificadorUCValido(value: string): boolean {
  return /^UC\d{6}$/.test(normalizarIdentificadorUC(value))
}
