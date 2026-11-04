import type { ReactNode } from 'react'

// Lista de registros da Visão 360 (faturas, atendimentos, interrupções): cabeçalho visual e linhas em cartão.
// A grade de colunas vem da variante (`ucv-registro--faturas` etc.), igual no cabeçalho e nas linhas.
export function ListaRegistros({ titulo, variante, colunas, children }: {
  titulo: string
  variante: 'faturas' | 'atendimentos' | 'interrupcoes'
  colunas: string[]
  children: ReactNode
}) {
  return (
    <div className="ucv-registros-scroll">
      <div className={`ucv-registro ucv-registro--${variante} ucv-registro--cabecalho`} aria-hidden="true">
        {colunas.map(coluna => <span key={coluna}>{coluna}</span>)}
      </div>
      <ul className="ucv-registros" aria-label={titulo}>{children}</ul>
    </div>
  )
}
