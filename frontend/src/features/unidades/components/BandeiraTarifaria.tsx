// Selo da bandeira tarifária da competência. A cor acompanha o custo (verde → vermelha P2).
const tons: Record<string, string> = {
  verde: 'verde', amarela: 'amarela', 'vermelha p1': 'vermelha-p1', 'vermelha p2': 'vermelha-p2',
}

export function BandeiraTarifaria({ bandeira }: { bandeira: string | null | undefined }) {
  if (!bandeira) return <span className="ucv-bandeira">Não informada</span>
  return (
    <span className="ucv-bandeira" data-tom={tons[bandeira.trim().toLowerCase()]}>
      <i aria-hidden="true" />
      {bandeira}
    </span>
  )
}
