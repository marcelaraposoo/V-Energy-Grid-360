"""Valida e otimiza a estrutura proposta; não interpreta palavras da pergunta."""
from sqlglot import exp, parse_one


def metric_grain_problem(intent, sql):
    """Contrato DEC/FEC: primeiro ponderar alimentadores no mês, depois somar meses."""
    if intent is None:
        return None
    tree = parse_one(sql, read='sqlite')
    for select in tree.find_all(exp.Select):
        direct_tables = {table.name for table in select.find_all(exp.Table)
                         if table.find_ancestor(exp.Select) is select}
        if 'dec_fec_alimentador_mensal' not in direct_tables:
            continue
        group = select.args.get('group')
        grouped = {c.name for c in group.find_all(exp.Column)} if group else set()
        direct_columns = {c.name for c in select.find_all(exp.Column)
                          if c.find_ancestor(exp.Select) is select}
        ratios_across_months = (
            'qtd_ucs_alimentador_mes' in direct_columns
            and bool(direct_columns & {'horas_interrompidas','qtd_interrupcoes'})
            and any(True for _ in select.find_all(exp.Div))
            and 'mes_referencia' not in grouped
            and intent.period is not None
            and intent.period.granularity != 'month'
        )
        single_feeder = 'alimentador' in grouped or any(
            isinstance(p.this,exp.Column) and p.this.name=='alimentador'
            and isinstance(p.expression,exp.Literal) for p in select.find_all(exp.EQ)
        )
        unweighted_feeders = not single_feeder and any(
            isinstance(a,(exp.Sum,exp.Avg)) and isinstance(a.this,exp.Column)
            and a.this.name in {'fec','dec_horas'} for a in select.find_all(exp.AggFunc)
            if a.find_ancestor(exp.Select) is select
        )
        if ratios_across_months or unweighted_feeders:
            return (
                'Não some nem tire média simples dos índices de alimentadores para obter o índice municipal/empresa. '
                'O denominador de DEC/FEC é mensal. Não divida numeradores acumulados por '
                'soma de UC-mês: isso devolve média mensal, não o indicador do período. '
                'Em uma subconsulta, agrupe por município e mes_referencia (ou apenas mês para empresa), '
                'calcule SUM(horas_interrompidas)/SUM(qtd_ucs_alimentador_mes) para DEC ou '
                'SUM(qtd_interrupcoes)*1.0/SUM(qtd_ucs_alimentador_mes) para FEC; '
                'na consulta externa some esses indicadores mensais por município/empresa. '
                'Mantenha o período e ordene pelo indicador acumulado quando houver ranking.'
            )
    return None


def period_problem(intent, sql):
    period = intent.period if intent else None
    if period is None or period.granularity in {"all", "latest"}:
        return None
    tree = parse_one(sql, read="sqlite")
    start, end = period.start, period.end
    date_columns = {"mes_referencia", "data_hora_inicio", "data_hora_abertura", "data_emissao", "ano"}
    predicates = [p for w in tree.find_all(exp.Where) for p in w.find_all(exp.Between,exp.EQ,exp.GTE,exp.GT,exp.LTE,exp.LT)]
    dates = []
    for predicate in predicates:
        if not any(c.name in date_columns for c in predicate.this.find_all(exp.Column)):
            continue
        if isinstance(predicate,exp.Between):
            low, high = predicate.args['low'],predicate.args['high']
            if isinstance(low,exp.Literal) and isinstance(high,exp.Literal) and low.this[:7] == start and high.this[:7] == end:
                return None
        else:
            literal = predicate.expression
            if not isinstance(literal,exp.Literal): continue
            if isinstance(predicate,exp.EQ) and (
                    (period.granularity=='year' and literal.this==start[:4]) or
                    (period.granularity=='month' and literal.this[:7]==start)):
                return None
            dates.append((type(predicate),literal.this[:7]))
    year,month = map(int,end.split('-'))
    following = f"{year + (month==12):04d}-{1 if month==12 else month+1:02d}"
    if (exp.GTE,start) in dates and ((exp.LTE,end) in dates or (exp.LT,following) in dates):
        return None
    return (f"O plano solicita {period.granularity}: {start} a {end}. O SQL deve filtrar esse intervalo inteiro; "
            "a cobertura encontrada é outra informação. Não reduza o pedido aos meses existentes. "
            f"Use limites literais compatíveis, por exemplo mes_referencia BETWEEN '{start}' AND '{end}'.")


def use_equivalent_rollup(sql):
    """Somas por dimensões preservadas no contrato A3; nenhum COUNT/AVG/UC.

    Apenas SELECT simples sobre uma tabela, sem DISTINCT nem joins/subqueries.
    Uma otimização conservadora: outros planos continuam na tabela escolhida.
    """
    tree = parse_one(sql,read='sqlite')
    tables=list(tree.find_all(exp.Table))
    if len(tables)!=1 or tables[0].name!='fato_consumo_faturamento' or len(list(tree.find_all(exp.Select)))!=1:
        return sql, None
    if tree.args.get('distinct') or tree.args.get('joins'):
        return sql,None
    dimensions={'municipio','bairro','classe','mes_referencia'}
    metrics={'consumo_kwh':'consumo_kwh','valor_total':'receita_total','valor_energia':'receita_energia'}
    aggregates=list(tree.find_all(exp.AggFunc))
    if not aggregates: return sql,None
    for aggregate in aggregates:
        if isinstance(aggregate,exp.Sum) and isinstance(aggregate.this,exp.Column) and aggregate.this.name in metrics:
            continue
        if isinstance(aggregate,(exp.Min,exp.Max)) and isinstance(aggregate.this,exp.Column) and aggregate.this.name in dimensions:
            continue
        return sql,None
    for column in tree.find_all(exp.Column):
        if column.name in dimensions: continue
        if column.name in metrics and isinstance(column.parent,exp.Sum): continue
        if column.name in {a.alias for a in tree.find_all(exp.Alias)} and column.find_ancestor(exp.Order): continue
        return sql,None
    for column in tree.find_all(exp.Column):
        if column.name in metrics and isinstance(column.parent,exp.Sum):
            column.set('this',exp.to_identifier(metrics[column.name]))
        if column.table=='fato_consumo_faturamento':
            column.set('table',exp.to_identifier('fato_segmento_mensal'))
    tables[0].set('this',exp.to_identifier('fato_segmento_mensal'))
    return tree.sql(dialect='sqlite'), 'Somas por dimensões preservadas: agregado mensal A3, equivalente ao fato detalhado.'
