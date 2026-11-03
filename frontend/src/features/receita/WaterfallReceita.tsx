import { useId, useRef, useState } from 'react'
import type { Periodo } from '../../api/types'
import { formatarPeriodo } from '../dashboard/formatacao'
import { kwhComSinal, reais, reaisComSinal, reaisCompletos, tendencia } from './formatacao'
import type { LinhaReceita } from './tipos'

const largura = 640
const altura = 300
const esquerda = 56
const direita = 16
const topo = 30
const base = 232
const larguraBarra = 48

function passoRedondo(bruto: number) {
  const ordem = 10 ** Math.floor(Math.log10(bruto))
  const fator = bruto / ordem
  return (fator <= 1 ? 1 : fator <= 2 ? 2 : fator <= 5 ? 5 : 10) * ordem
}

// Os totais são grandes perto dos efeitos: o eixo começa abaixo do menor nível para os efeitos ficarem legíveis.
function escala(niveis: number[]) {
  const menor = Math.min(...niveis)
  const maior = Math.max(...niveis)
  const amplitude = maior - menor || Math.abs(maior) * 0.05 || 1
  const passo = passoRedondo((maior - menor + amplitude * 1.4) / 5)
  const minimo = Math.max(0, Math.floor((menor - amplitude * 1.2) / passo) * passo)
  const maximo = Math.ceil((maior + amplitude * 0.2) / passo) * passo
  const marcacoes = Array.from({ length: Math.round((maximo - minimo) / passo) + 1 }, (_, i) => minimo + i * passo)
  return { minimo, maximo, marcacoes, passo }
}

type Barra = { titulo: string; subtitulo: string; de: number; ate: number; valor: string; tipo: 'base' | 'efeito' | 'atual'; detalhe: string; delta?: number }

export function WaterfallReceita({ total, periodo, referencia }: { total: LinhaReceita; periodo: Periodo; referencia: Periodo }) {
  const [ativa, setAtiva] = useState<{ indice: number; x: number; y: number } | null>(null)
  const figuraRef = useRef<HTMLElement>(null)
  const tooltipRef = useRef<HTMLDivElement>(null)
  const tooltipId = useId()
  const aposVolume = total.receita_base + total.efeito_volume
  const barras: Barra[] = [
    { titulo: 'Receita', subtitulo: formatarPeriodo(referencia), de: 0, ate: total.receita_base, valor: reais(total.receita_base), tipo: 'base',
      detalhe: 'Receita de energia no período de referência, com bandeira tarifária e sem tributos.' },
    { titulo: 'Efeito volume', subtitulo: kwhComSinal(total.energia_atual_kwh - total.energia_base_kwh), de: total.receita_base, ate: aposVolume,
      valor: reaisComSinal(total.efeito_volume), tipo: 'efeito', delta: total.efeito_volume,
      detalhe: 'Mudança na energia faturada, calculada ao preço médio da referência.' },
    { titulo: 'Efeito preço', subtitulo: 'reajuste, bandeira e mix', de: aposVolume, ate: total.receita_atual,
      valor: reaisComSinal(total.efeito_preco), tipo: 'efeito', delta: total.efeito_preco,
      detalhe: 'Mudança no preço médio aplicada à energia atual. Reúne reajuste, bandeira e mix de classes.' },
    { titulo: 'Receita', subtitulo: formatarPeriodo(periodo), de: 0, ate: total.receita_atual, valor: reais(total.receita_atual), tipo: 'atual',
      detalhe: 'Receita de energia no período analisado, com bandeira tarifária e sem tributos.' },
  ]
  const { minimo, maximo, marcacoes, passo } = escala([total.receita_base, aposVolume, total.receita_atual])
  const y = (valor: number) => base - ((Math.max(valor, minimo) - minimo) / (maximo - minimo)) * (base - topo)
  const faixa = (largura - esquerda - direita) / barras.length
  const centro = (i: number) => esquerda + faixa * (i + 0.5)
  const divisor = maximo >= 1e9 ? 1e9 : maximo >= 1e6 ? 1e6 : 1e3
  // Casas decimais pelo passo do eixo, para dois rótulos nunca saírem iguais (ex.: 0,85 e 0,90).
  const numeroEixo = new Intl.NumberFormat('pt-BR', {
    minimumFractionDigits: Math.max(0, -Math.floor(Math.log10(passo / divisor))),
    maximumFractionDigits: Math.max(0, -Math.floor(Math.log10(passo / divisor))),
  })
  const unidade = divisor === 1e9 ? 'R$ bilhões' : divisor === 1e6 ? 'R$ milhões' : 'R$ mil'

  function mostrar(indice: number, clientX: number, clientY: number) {
    const figura = figuraRef.current?.getBoundingClientRect()
    if (!figura) return
    const larguraTooltip = tooltipRef.current?.offsetWidth ?? Math.min(260, figura.width - 24)
    const alturaTooltip = tooltipRef.current?.offsetHeight ?? 120
    const cursorX = clientX - figura.left
    const cursorY = clientY - figura.top
    const x = cursorX + larguraTooltip + 12 > figura.width ? cursorX - larguraTooltip - 12 : cursorX + 12
    const y = cursorY - alturaTooltip - 12 < 0 ? cursorY + 12 : cursorY - alturaTooltip - 12
    setAtiva({
      indice,
      x: Math.max(8, Math.min(x, figura.width - larguraTooltip - 8)),
      y: Math.max(8, Math.min(y, figura.height - alturaTooltip - 8)),
    })
  }

  function mostrarDaBarra(indice: number, alvo: Element) {
    const caixa = alvo.getBoundingClientRect()
    mostrar(indice, caixa.left + caixa.width / 2, caixa.top)
  }

  return (
    <figure ref={figuraRef} className="dashboard-chart receita-waterfall">
      <div className="dashboard-chart-scroll" onScroll={() => setAtiva(null)}>
        <svg viewBox={`0 0 ${largura} ${altura}`} role="group" aria-roledescription="gráfico de cascata"
          aria-label={`Ponte da receita: ${barras.map((b) => `${b.titulo} ${b.subtitulo}, ${b.valor}`).join('; ')}. Eixo em ${unidade}${minimo > 0 ? `, a partir de ${reais(minimo)}` : ''}.`}>
          {marcacoes.map((valor) => (
            <g key={valor}>
              <line x1={esquerda} x2={largura - direita} y1={y(valor)} y2={y(valor)} className="dashboard-chart-grid" />
              <text x={esquerda - 10} y={y(valor) + 4} textAnchor="end">{numeroEixo.format(valor / divisor)}</text>
            </g>
          ))}
          {minimo > 0 && <path d={`M${esquerda - 6} ${base + 4} l4 -4 l4 4 l4 -4`} className="receita-waterfall-quebra" aria-hidden="true" />}
          {barras.slice(0, -1).map((barra, i) => (
            <line key={`conector-${i}`} x1={centro(i) + larguraBarra / 2} x2={centro(i + 1) - larguraBarra / 2}
              y1={y(barra.ate)} y2={y(barra.ate)} className="receita-waterfall-conector" />
          ))}
          {barras.map((barra, i) => {
            const alto = y(Math.max(barra.de, barra.ate))
            const baixo = barra.tipo === 'efeito' ? y(Math.min(barra.de, barra.ate)) : base
            return (
              <g key={i} role="button" tabIndex={0} data-active={ativa?.indice === i}
                aria-label={`${barra.titulo} (${barra.subtitulo}): ${barra.valor}`} aria-describedby={ativa?.indice === i ? tooltipId : undefined}
                onPointerEnter={(e) => { if (e.pointerType === 'mouse') mostrar(i, e.clientX, e.clientY) }}
                onPointerMove={(e) => { if (e.pointerType === 'mouse') mostrar(i, e.clientX, e.clientY) }}
                onPointerLeave={(e) => { if (e.pointerType === 'mouse') setAtiva(null) }}
                onFocus={(e) => mostrarDaBarra(i, e.currentTarget)} onBlur={() => setAtiva(null)}
                onClick={(e) => { if (e.detail > 0) mostrar(i, e.clientX, e.clientY) }}
                onKeyDown={(e) => {
                  if (e.key === 'Escape') setAtiva(null)
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    mostrarDaBarra(i, e.currentTarget)
                  }
                }}>
                <rect x={centro(i) - faixa / 2} y={topo - 20} width={faixa} height={base - topo + 20} fill="transparent" />
                <rect x={centro(i) - larguraBarra / 2} y={alto} width={larguraBarra} height={Math.max(2, baixo - alto)} rx={3}
                  className={`receita-waterfall-barra receita-waterfall-barra--${barra.tipo}`} data-tendencia={barra.tipo === 'efeito' ? tendencia(barra.delta ?? null) : undefined} />
                <text x={centro(i)} y={alto - 8} textAnchor="middle" className="dashboard-chart-bar-value">{barra.valor}</text>
                <text x={centro(i)} y={base + 22} textAnchor="middle" className="receita-waterfall-titulo">{barra.titulo}</text>
                <text x={centro(i)} y={base + 38} textAnchor="middle">{barra.subtitulo}</text>
              </g>
            )
          })}
        </svg>
      </div>
     
      {ativa && (
        <div ref={tooltipRef} id={tooltipId} role="tooltip" className="dashboard-chart-tooltip receita-waterfall-tooltip"
          style={{ left: ativa.x, top: ativa.y }}>
          <span className="receita-tooltip-titulo">{barras[ativa.indice].titulo}</span>
          <strong className="receita-tooltip-valor">{reaisCompletos(barras[ativa.indice].delta ?? barras[ativa.indice].ate)}</strong>
          <span className="receita-tooltip-contexto">{barras[ativa.indice].subtitulo}</span>
          <span className="receita-tooltip-descricao">{barras[ativa.indice].detalhe}</span>
        </div>
      )}
    </figure>
  )
}
