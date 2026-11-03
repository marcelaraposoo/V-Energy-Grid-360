import { useReducer } from 'react'
import { CalendarRange, RotateCcw } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { api, useApi } from '../../api'
import type { ClasseConsumo } from '../../api/types'
import { SelectField } from '../../components/ui/Controls'
import { DataCorte } from '../../components/ui/DataCorte'
import { EmptyState } from '../../components/ui/EmptyState'
import { ErrorState, LoadingState } from '../../components/ui/Feedback'
import { PageHeader } from '../../components/ui/PageHeader'
import { Panel } from '../../components/ui/Panel'
import { InfoTipContent } from '../../components/ui/InfoTip'
import { limitesDashboard as limites, quantidadeMeses, sugerirReferencia, validarPeriodo, validarPeriodosDashboard } from '../../utils/periodosDashboard'
import { formatarPeriodo } from '../dashboard/formatacao'
import { alterarPeriodos, estadoInicial } from '../dashboard/periodos'
import { SeletorPeriodo } from '../dashboard/SeletorPeriodo'
import { ContribuicaoReceita } from './ContribuicaoReceita'
import { alterarRecorte, filtrar, recorteInicial } from './drilldown'
import type { Recorte } from './drilldown'
import { EvolucaoReceita } from './EvolucaoReceita'
import { FatoresReceita } from './FatoresReceita'
import { periodosDaUrl, periodosDiagnostico } from './periodos'
import { RankingQuedas } from './RankingQuedas'
import { ResumoReceita } from './ResumoReceita'
import { parametrosReceita } from './tipos'
import { WaterfallReceita } from './WaterfallReceita'
import '../dashboard/dashboard.css'
import './receita.css'

const { periodo: periodoPadrao, referencia: referenciaPadrao } = periodosDiagnostico

export function ReceitaPage() {
  const [busca] = useSearchParams()
  const [temporal, dispatch] = useReducer(
    (estado: ReturnType<typeof estadoInicial>, acao: Parameters<typeof alterarPeriodos>[1]) => alterarPeriodos(estado, acao, periodoPadrao, limites, referenciaPadrao),
    undefined, () => {
      // Vindo do Dashboard, abre nos mesmos períodos; "Limpar" volta ao recorte do diagnóstico.
      const inicial = periodosDaUrl(busca) ?? periodosDiagnostico
      return estadoInicial(inicial.periodo, inicial.referencia)
    },
  )
  const [historico, dispatchRecorte] = useReducer(alterarRecorte, { atual: recorteInicial, anteriores: [] })
  const recorte = historico.atual
  const setRecorte = (valor: Recorte) => dispatchRecorte({ tipo: 'selecionar', valor })
  const voltar = historico.anteriores.length ? () => dispatchRecorte({ tipo: 'voltar' }) : undefined
  const { periodo, referencia, aviso } = temporal
  const consulta = useApi(
    async (signal) => {
      if (!referencia) return null
      const dados = await api.receita.variacao(parametrosReceita({ ...recorte, periodo, referencia }), signal)
      return { dados, recorte, periodo, referencia }
    },
    [periodo.inicio, periodo.fim, referencia?.inicio, referencia?.fim, recorte.municipio, recorte.bairro, recorte.classe, recorte.agrupar_por],
    { manterDadosAnteriores: true },
  )
  // Mantém os gráficos montados durante a busca, com os filtros e períodos da resposta exibida.
  const analise = consulta.data?.dados
  const recorteExibido = consulta.data?.recorte ?? recorte
  const periodoExibido = consulta.data?.periodo ?? periodo
  const referenciaExibida = consulta.data?.referencia ?? referenciaPadrao
  const catalogo = useApi((signal) => api.filtros(signal), [])
  const bairros = catalogo.data?.municipios.find((m) => m.nome === recorte.municipio)?.bairros ?? []

  return (
    <div className="receita-page">
      <PageHeader
        title="Análise de Receita"
        description="Quanto da variação foi preço e quanto foi volume, e onde ela aconteceu."
      />

      <form className="panel receita-filtros" aria-label="Filtros da análise de receita"
        onSubmit={(event) => event.preventDefault()}
        onReset={() => { dispatch({ tipo: 'limpar' }); dispatchRecorte({ tipo: 'limpar' }) }}>
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
          options={catalogo.data?.municipios.map((m) => ({ value: m.nome, label: m.nome })) ?? []}
          onChange={(valor) => setRecorte(filtrar(recorte, { municipio: valor || null }))} />
        <SelectField label="Bairro" value={recorte.bairro ?? ''} placeholder={recorte.municipio ? 'Todos os bairros' : 'Escolha o município'}
          disabled={!recorte.municipio} options={bairros.map((b) => ({ value: b, label: b }))}
          onChange={(valor) => setRecorte(filtrar(recorte, { bairro: valor || null }))} />
        <SelectField label="Classe" value={recorte.classe ?? ''} placeholder="Todas as classes"
          options={catalogo.data?.classes.map((c) => ({ value: c.codigo, label: c.descricao })) ?? []}
          onChange={(valor) => setRecorte(filtrar(recorte, { classe: (valor || null) as ClasseConsumo | null }))} />
        <button type="reset" className="button button--secondary"><RotateCcw size={14} aria-hidden="true" /> Limpar</button>
        <DataCorte />
        {aviso && <p className="receita-filtros-nota" role="status" aria-live="polite">{aviso}</p>}
        {catalogo.error && <p className="receita-filtros-nota" role="alert">
          Não foi possível carregar os municípios e as classes.{' '}
          <button type="button" className="link-button" onClick={catalogo.reload}>Tentar novamente</button>
        </p>}
      </form>

      {!referencia ? <Panel title="Comparação indisponível">
        <EmptyState icon={CalendarRange} title="Escolha um período de referência"
          description="A decomposição compara dois períodos com a mesma quantidade de meses, sem sobreposição." compact />
      </Panel>
        : consulta.error ? <Panel title="Análise de receita"><ErrorState error={consulta.error} onRetry={consulta.reload} /></Panel>
          : !analise ? <Panel title="Análise de receita"><LoadingState label="Calculando a decomposição…" /></Panel>
            : <div className="receita-resultados" aria-busy={consulta.loading}>
              {consulta.loading && <div className="receita-atualizando"><LoadingState label="Atualizando análise…" /></div>}
              <div className="receita-resultados-conteudo" inert={consulta.loading}>
                <ResumoReceita total={analise.total} referencia={referenciaExibida} />

                <section className="receita-decomposicao" aria-label="Decomposição preço × volume">
                  <Panel title="Ponte da receita: volume × preço" className="receita-ponte"
                    description={`${formatarPeriodo(referenciaExibida)} → ${formatarPeriodo(periodoExibido)}`}
                    info={<InfoTipContent resumo="Veja como a receita de referência chega ao valor atual." itens={[
                      { rotulo: 'Volume', texto: 'Variação da energia × preço médio da referência.' },
                      { rotulo: 'Preço', texto: 'Variação do preço médio × energia atual.' },
                    ]} nota="O preço reúne reajuste, bandeira tarifária e mudança no mix de classes." />}>
                    <WaterfallReceita total={analise.total} periodo={periodoExibido} referencia={referenciaExibida} />
                  </Panel>
                  <FatoresReceita analise={analise} />
                </section>

                <ContribuicaoReceita analise={analise} recorte={recorteExibido} onRecorte={setRecorte} />

                <section className="receita-detalhe" aria-label="Quedas e evolução">
                  <RankingQuedas analise={analise} recorte={recorteExibido} onRecorte={setRecorte} onVoltar={voltar} />
                  <EvolucaoReceita serie={analise.serie} periodo={periodoExibido} referencia={referenciaExibida} />
                </section>
              </div>
            </div>}
    </div>
  )
}
