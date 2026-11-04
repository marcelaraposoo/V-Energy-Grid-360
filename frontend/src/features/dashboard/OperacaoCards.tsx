import { ArrowDownRight, ArrowRight, ArrowUpRight, Clock3, Headset, Minus, Smile, ZapOff } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { ApiState, OperacaoResponse, Periodo } from '../../api'
import { ErrorState, LoadingState } from '../../components/ui/Feedback'
import { KpiCard } from '../../components/ui/KpiCard'
import { tendencia } from '../../utils/indicadores'
import { horas, vezes } from '../qualidade/formatacao'
import { atendimentos, disponivel, formatarPeriodo, pontosNota, quantidade, satisfacao } from './formatacao'

type Props = {
  estado: ApiState<OperacaoResponse>
  referencia: Periodo | null
  municipio: string | null
  linkQualidade: string
}

// Operação e atendimento: chamados e satisfação (B1) e DEC/FEC (A8). Nos quatro, subir é ruim, exceto a satisfação.
export function OperacaoCards({ estado: { data, loading, error, reload }, referencia, municipio, linkQualidade }: Props) {
  const atual = data?.atual
  const base = referencia ? data?.base : null
  const periodoReferencia = referencia ? formatarPeriodo(referencia) : ''
  const comReferencia = (valor: number | null | undefined, formatar: (v: number) => string) =>
    referencia ? { valor: disponivel(valor) ? formatar(valor) : '—', periodo: periodoReferencia } : null
  const alimentadores = municipio
    ? ` Em ${municipio}, entram os alimentadores cujo município principal é ${municipio}, como na Qualidade do Serviço.` : ''

  return (
    <section className="dashboard-operacao" aria-label="Operação e atendimento" aria-busy={loading}>
      <div className="dashboard-operacao-cards">
        {loading ? <div className="dashboard-kpis-feedback"><LoadingState label="Carregando operação e atendimento…" /></div>
          : error ? <div className="dashboard-kpis-feedback"><ErrorState error={error} onRetry={reload} title="Não foi possível consultar operação e atendimento" /></div>
            : <>
              <KpiCard titulo="Atendimentos" icone={Headset} menorMelhor
                info="Chamados abertos no período, em todos os canais. Mais chamados costuma indicar mais problemas percebidos pelo cliente."
                valor={atual ? atendimentos(atual.qtd_atendimentos) : '—'}
                referencia={comReferencia(base?.qtd_atendimentos, atendimentos)}
                variacao={base ? data?.variacao_atendimentos_pct ?? null : null} />
              <KpiCard titulo="Satisfação" icone={Smile}
                info={`Média das notas (1 a 5) dos chamados avaliados.${atual ? ` ${quantidade(atual.qtd_avaliacoes)} de ${quantidade(atual.qtd_atendimentos)} chamados tiveram nota.` : ''}`}
                valor={disponivel(atual?.nota_satisfacao_media) ? satisfacao(atual.nota_satisfacao_media) : '—'}>
                {referencia && <ComparacaoNota base={base?.nota_satisfacao_media} diferenca={base ? data?.variacao_satisfacao ?? null : null} periodo={periodoReferencia} />}
              </KpiCard>
              <KpiCard titulo="DEC" icone={Clock3} menorMelhor
                info={`Horas sem energia por UC no período: soma dos DEC mensais, com os alimentadores ponderados pelas UCs em cada mês.${alimentadores}`}
                valor={disponivel(atual?.dec_horas) ? horas(atual.dec_horas) : '—'}
                referencia={comReferencia(base?.dec_horas, horas)}
                variacao={base ? data?.variacao_dec_pct ?? null : null} />
              <KpiCard titulo="FEC" icone={ZapOff} menorMelhor
                info={`Vezes em que cada UC ficou sem energia, em média, no período (mesma agregação do DEC).${alimentadores}`}
                valor={disponivel(atual?.fec_vezes) ? vezes(atual.fec_vezes) : '—'}
                referencia={comReferencia(base?.fec_vezes, vezes)}
                variacao={base ? data?.variacao_fec_pct ?? null : null} />
            </>}
      </div>
      <footer className="dashboard-operacao-rodape">
        <Link className="link-button" to={linkQualidade}>
          Ver na Qualidade do Serviço <ArrowRight size={14} aria-hidden="true" />
        </Link>
      </footer>
    </section>
  )
}

// A satisfação compara em pontos da nota, não em percentual.
function ComparacaoNota({ base, diferenca, periodo }: { base: number | null | undefined; diferenca: number | null; periodo: string }) {
  const Seta = diferenca === null || diferenca === 0 ? Minus : diferenca < 0 ? ArrowDownRight : ArrowUpRight
  return <>
    <p className="kpi-card-referencia">Referência: {disponivel(base) ? satisfacao(base) : '—'}</p>
    <p className="kpi-comparacao" title={`Referência: ${periodo}`}>
      {diferenca !== null
        ? <span data-tendencia={tendencia(diferenca)}><Seta size={15} aria-hidden="true" />{pontosNota(diferenca)}</span>
        : 'Sem dados para comparação'}
    </p>
  </>
}
