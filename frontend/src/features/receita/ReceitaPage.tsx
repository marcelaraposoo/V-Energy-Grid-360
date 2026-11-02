import { useReducer, useState } from 'react'
import { CalendarRange, RotateCcw } from 'lucide-react'
import { useApi } from '../../api'
import type { ClasseConsumo } from '../../api/types'
import { SelectField } from '../../components/ui/Controls'
import { EmptyState } from '../../components/ui/EmptyState'
import { ErrorState, LoadingState } from '../../components/ui/Feedback'
import { PageHeader } from '../../components/ui/PageHeader'
import { Panel } from '../../components/ui/Panel'
import { limitesDashboard as limites, quantidadeMeses, sugerirReferencia, validarPeriodo, validarPeriodosDashboard } from '../../utils/periodosDashboard'
import { formatarPeriodo } from '../dashboard/formatacao'
import { alterarPeriodos, estadoInicial } from '../dashboard/periodos'
import { SeletorPeriodo } from '../dashboard/SeletorPeriodo'
import { ContribuicaoReceita } from './ContribuicaoReceita'
import { filtrar, recorteInicial } from './drilldown'
import type { Recorte } from './drilldown'
import { EvolucaoReceita } from './EvolucaoReceita'
import { FatoresReceita } from './FatoresReceita'
import { nomesClasse } from './formatacao'
import { catalogoReceitaMock, consultarReceitaMock } from './mockData'
import { periodosDiagnostico } from './periodos'
import { RankingQuedas } from './RankingQuedas'
import { ResumoReceita } from './ResumoReceita'
import { WaterfallReceita } from './WaterfallReceita'
import '../dashboard/dashboard.css'
import './receita.css'

const { periodo: periodoPadrao, referencia: referenciaPadrao } = periodosDiagnostico

export function ReceitaPage() {
  const [temporal, dispatch] = useReducer(
    (estado: ReturnType<typeof estadoInicial>, acao: Parameters<typeof alterarPeriodos>[1]) => alterarPeriodos(estado, acao, periodoPadrao, limites, referenciaPadrao),
    undefined, () => estadoInicial(periodoPadrao, referenciaPadrao),
  )
  const [recorte, setRecorte] = useState<Recorte>(recorteInicial)
  const { periodo, referencia, aviso } = temporal
  const analise = useApi(
    (signal) => referencia ? consultarReceitaMock({ ...recorte, periodo, referencia }, signal) : Promise.resolve(null),
    [periodo.inicio, periodo.fim, referencia?.inicio, referencia?.fim, recorte.municipio, recorte.bairro, recorte.classe, recorte.agrupar_por],
  )
  const bairros = catalogoReceitaMock.municipios.find((m) => m.nome === recorte.municipio)?.bairros ?? []

  return (
    <div className="receita-page">
      <PageHeader
        title="Análise de Receita"
        description="Quanto da variação foi preço e quanto foi volume, e onde ela aconteceu."
      />

      <form className="panel receita-filtros" aria-label="Filtros da análise de receita"
        onSubmit={(event) => event.preventDefault()}
        onReset={() => { dispatch({ tipo: 'limpar' }); setRecorte(recorteInicial) }}>
        <SeletorPeriodo key="atual" label="Período analisado" valor={periodo}
          minimo={limites.minimo} maximo={limites.maximo}
          validar={(valor) => validarPeriodo(valor, 12, limites)}
          onChange={(valor) => dispatch({ tipo: 'periodo', valor })} />
        <SeletorPeriodo key={`base-${periodo.inicio}-${periodo.fim}`} label="Período de referência" valor={referencia}
          minimo={limites.minimo} maximo={limites.maximo} mesesFixos={quantidadeMeses(periodo)}
          sugestao={sugerirReferencia(periodo, limites)}
          validar={(base) => validarPeriodosDashboard(periodo, base, true, limites)}
          onChange={(valor) => dispatch({ tipo: 'referencia', valor })} />
        <SelectField label="Município" value={recorte.municipio ?? ''} placeholder="Todos os municípios"
          options={catalogoReceitaMock.municipios.map((m) => ({ value: m.nome, label: m.nome }))}
          onChange={(valor) => setRecorte(filtrar(recorte, { municipio: valor || null }))} />
        <SelectField label="Bairro" value={recorte.bairro ?? ''} placeholder={recorte.municipio ? 'Todos os bairros' : 'Escolha o município'}
          disabled={!recorte.municipio} options={bairros.map((b) => ({ value: b, label: b }))}
          onChange={(valor) => setRecorte(filtrar(recorte, { bairro: valor || null }))} />
        <SelectField label="Classe" value={recorte.classe ?? ''} placeholder="Todas as classes"
          options={catalogoReceitaMock.classes.map((c) => ({ value: c, label: nomesClasse[c] }))}
          onChange={(valor) => setRecorte(filtrar(recorte, { classe: (valor || null) as ClasseConsumo | null }))} />
        <button type="reset" className="button button--secondary"><RotateCcw size={14} aria-hidden="true" /> Limpar</button>
        {aviso && <p className="receita-filtros-nota" role="status" aria-live="polite">{aviso}</p>}
      </form>

      {!referencia ? <Panel title="Comparação indisponível">
        <EmptyState icon={CalendarRange} title="Escolha um período de referência"
          description="A decomposição compara dois períodos com a mesma quantidade de meses, sem sobreposição." compact />
      </Panel>
        : analise.error ? <Panel title="Análise de receita"><ErrorState error={analise.error} onRetry={analise.reload} /></Panel>
          : !analise.data ? <Panel title="Análise de receita"><LoadingState label="Calculando a decomposição…" /></Panel>
            : <>
              <ResumoReceita total={analise.data.total} referencia={referencia} />

              <section className="receita-decomposicao" aria-label="Decomposição preço × volume">
                <Panel title="Ponte da receita: volume × preço" className="receita-ponte"
                  description={`${formatarPeriodo(referencia)} → ${formatarPeriodo(periodo)} · efeito volume + efeito preço = variação total`}>
                  <WaterfallReceita total={analise.data.total} periodo={periodo} referencia={referencia} />
                </Panel>
                <FatoresReceita analise={analise.data} />
              </section>

              <ContribuicaoReceita analise={analise.data} recorte={recorte} onRecorte={setRecorte} />

              <section className="receita-detalhe" aria-label="Quedas e evolução">
                <RankingQuedas analise={analise.data} recorte={recorte} onRecorte={setRecorte} />
                <EvolucaoReceita serie={analise.data.serie} periodo={periodo} referencia={referencia} />
              </section>
            </>}
    </div>
  )
}
