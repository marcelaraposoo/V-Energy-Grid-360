"""Distingue uma agregação sem registros de valores zero legítimos."""
from sqlglot import exp, parse_one


def has_no_data(sql, result):
    if not result.rows:
        return result.row_count == 0
    if all(value is None for row in result.rows for value in row):
        return True
    if len(result.rows) != 1:
        return False
    try:
        tree = parse_one(sql, read='sqlite')
        projections = tree.expressions if isinstance(tree, exp.Select) else []
        if len(projections) != len(result.rows[0]):
            return False
        # Rótulos constantes de período/local não tornam SUM(NULL) uma medida.
        indices = [i for i, p in enumerate(projections) if not isinstance(p.unalias(), exp.Literal)]
        aggregated = any(p.find(exp.AggFunc) is not None for p in projections)
        return bool(aggregated and indices and all(result.rows[0][i] is None for i in indices))
    except Exception:
        return False
