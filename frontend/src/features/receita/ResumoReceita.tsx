import { Banknote, CircleDollarSign, Scale, Zap } from 'lucide-react'
import type { Periodo } from '../../api/types'
import { KpiCard } from '../../components/ui/KpiCard'
import { InfoTipContent } from '../../components/ui/InfoTip'
import { explicacoes } from '../../utils/indicadores'
import { formatarPeriodo } from '../dashboard/formatacao'
import { kwh, reais, reaisComSinal, tarifa, tendencia } from './formatacao'
import type { LinhaReceita } from './tipos'

// Mesmos cards do Dashboard (KpiCard), mais a variação da receita separada em volume e preço.
export function ResumoReceita({ total, referencia }: { total: LinhaReceita; referencia: Periodo }) {
  const periodo = formatarPeriodo(referencia)
  const variacaoPreco = total.preco_base_kwh && total.preco_atual_kwh !== null
    ? (total.preco_atual_kwh / total.preco_base_kwh - 1) * 100 : null
  return (
    <section className="receita-resumo" aria-label="Resumo da variação">
      <KpiCard titulo="Receita de energia" icone={Banknote} info={explicacoes.receita} valor={reais(total.receita_atual)}
        referencia={{ valor: reais(total.receita_base), periodo }} variacao={total.variacao_receita_pct} />
      <KpiCard titulo="Energia faturada" icone={Zap} info={explicacoes.energia} valor={kwh(total.energia_atual_kwh)}
        referencia={{ valor: kwh(total.energia_base_kwh), periodo }} variacao={total.variacao_energia_pct} />
      <KpiCard titulo="Preço médio por kWh" icone={CircleDollarSign} info={explicacoes.preco} valor={tarifa(total.preco_atual_kwh)}
        referencia={{ valor: tarifa(total.preco_base_kwh), periodo }} variacao={variacaoPreco} colorir={false} />
      <KpiCard titulo="Variação da receita" icone={Scale} valor={reaisComSinal(total.variacao_receita)}
        tendenciaValor={tendencia(total.variacao_receita)}
        info={<InfoTipContent resumo="Diferença entre a receita atual e a receita de referência." itens={[
          { rotulo: 'Efeito volume', texto: 'Quanto a mudança na energia faturada representa em receita.' },
          { rotulo: 'Efeito preço', texto: 'Quanto a mudança no preço médio representa em receita.' },
        ]} nota="Os dois efeitos somam a variação da receita." />}>
        <dl className="receita-resumo-efeitos">
          <div><dt>Efeito volume</dt><dd data-tendencia={tendencia(total.efeito_volume)}>{reaisComSinal(total.efeito_volume)}</dd></div>
          <div><dt>Efeito preço</dt><dd data-tendencia={tendencia(total.efeito_preco)}>{reaisComSinal(total.efeito_preco)}</dd></div>
        </dl>
      </KpiCard>
    </section>
  )
}
