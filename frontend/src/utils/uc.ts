export function normalizarIdentificadorUC(value: string): string {
  return value.trim().toUpperCase()
}

export function identificadorUCValido(value: string): boolean {
  return /^UC\d{6}$/.test(normalizarIdentificadorUC(value))
}
