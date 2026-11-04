"""Substituição comprovada de SUM(consumo_kwh) no grão aditivo publicado."""
from sqlglot import parse, exp

DIMENSIONS = {"mes_referencia", "municipio", "bairro", "classe"}


def optimize_consumption(sql):
    try:
        statements = parse(sql, read="sqlite")
        if len(statements) != 1 or not isinstance(statements[0], exp.Select):
            return sql
        tree = statements[0]
        # SUBSTR(competência,1,4) = ano é outra forma equivalente de
        # selecionar um ano completo. Não aceitar outras funções/posições.
        for predicate in list(tree.find_all(exp.EQ)):
            expression, year = predicate.this, predicate.expression
            if isinstance(year, exp.Substring):
                expression, year = year, expression
            if (isinstance(expression, exp.Substring)
                and isinstance(expression.this, exp.Column) and expression.this.name == "mes_referencia"
                and isinstance(expression.args.get("start"), exp.Literal) and expression.args["start"].this == "1"
                and isinstance(expression.args.get("length"), exp.Literal) and expression.args["length"].this == "4"
                and isinstance(year, exp.Literal) and year.is_string
                and len(year.this) == 4 and year.this.isdigit() and 1000 <= int(year.this) <= 9999):
                predicate.replace(exp.Between(this=expression.this.copy(),
                    low=exp.Literal.string(year.this + "-01"), high=exp.Literal.string(year.this + "-12")))
        tables = list(tree.find_all(exp.Table))
        if len(tables) != 1 or tables[0].name != "fato_consumo_faturamento" or tables[0].db or tables[0].catalog:
            return sql
        if len(list(tree.find_all(exp.Select))) != 1 or any(tree.args.get(k) for k in ("joins", "with_", "distinct", "having")):
            return sql
        sums = list(tree.find_all(exp.Sum))
        if len(sums) != 1 or not isinstance(sums[0].this, exp.Column) or sums[0].this.name != "consumo_kwh":
            return sql
        if any(isinstance(n, exp.Func) and not isinstance(n, (exp.Sum, exp.And, exp.Or)) for n in tree.walk()):
            return sql
        group = tree.args.get("group")
        grouped = set()
        if group:
            if any(not isinstance(e, exp.Column) or e.name not in DIMENSIONS for e in group.expressions):
                return sql
            grouped = {e.name for e in group.expressions}
        aliases = set()
        for projection in tree.expressions:
            e = projection.unalias()
            if isinstance(e, exp.Sum):
                aliases.add(projection.alias_or_name)
            elif not isinstance(e, exp.Column) or e.name not in grouped:
                return sql
        where = tree.args.get("where")
        if where:
            # ano é derivado da competência na Gold reconciliada. Restrinja a
            # tradução a igualdade com ano inteiro; outras formas ficam intactas.
            for predicate in list(where.find_all(exp.EQ)):
                column, year = predicate.this, predicate.expression
                if isinstance(year, exp.Column) and year.name == "ano":
                    column, year = year, column
                if (isinstance(column, exp.Column) and column.name == "ano"
                    and isinstance(year, exp.Literal) and year.is_int
                    and 1000 <= int(year.this) <= 9999):
                    month = column.copy()
                    month.set("this", exp.to_identifier("mes_referencia"))
                    predicate.replace(exp.Between(this=month,
                        low=exp.Literal.string(f"{int(year.this):04}-01"),
                        high=exp.Literal.string(f"{int(year.this):04}-12")))
        if where and any(c.name not in DIMENSIONS for c in where.find_all(exp.Column)):
            return sql
        if any(c.name not in DIMENSIONS | {"consumo_kwh"} | aliases for c in tree.find_all(exp.Column)):
            return sql
        table = tables[0]
        old = table.name
        table.set("this", exp.to_identifier("fato_segmento_mensal"))
        if not table.alias:
            for col in tree.find_all(exp.Column):
                if col.table == old:
                    col.set("table", exp.to_identifier("fato_segmento_mensal"))
        return tree.sql(dialect="sqlite")
    except Exception:
        return sql
