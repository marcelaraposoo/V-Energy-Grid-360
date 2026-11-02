## Regras de Geração SQL

Toda consulta deve ser exclusivamente de leitura e utilizar somente estruturas presentes no contexto fornecido.

Utilize exclusivamente o dialeto SQLite. Não use `DATE_TRUNC`, `EXTRACT`,
`INTERVAL` ou `ILIKE`; use as funções SQLite quando necessário.
Nunca use `SELECT *` no caminho normal: projete apenas as colunas necessárias.
`COUNT(*)` é permitido para contar registros no grão correto.

### Permitido

A complexidade suportada é intermediária.

São permitidos:

- `SELECT`;
- `WHERE`;
- `JOIN`;
- `GROUP BY`;
- `HAVING`;
- `ORDER BY`;
- `LIMIT`;
- aliases;
- `SUM`, `AVG`, `COUNT`, `MIN`, `MAX`;
- `CASE WHEN` simples.

### Proibido

Nunca gere operações que alterem dados, estrutura ou permissões.

Incluem:

- `INSERT`;
- `UPDATE`;
- `DELETE`;
- `DROP`;
- `ALTER`;
- `CREATE`;
- `TRUNCATE`;
- `GRANT`;
- `REVOKE`;
- comandos administrativos;
- múltiplas instruções SQL.

Gere no máximo uma consulta.

### Complexidade

Evite:

- CTEs complexas;
- subqueries profundamente aninhadas;
- window functions;
- consultas excessivamente difíceis de validar.

Se a pergunta exigir complexidade além do suportado e não houver alternativa segura, utilize `INSUFFICIENT_CONTEXT`.

### Schema

Utilize apenas tabelas, colunas e relacionamentos explicitamente fornecidos.

Nunca invente estruturas ou relacionamentos.

Consultas multidomínio são permitidas somente quando o relacionamento necessário estiver claro no schema.

Não autorize JOIN apenas por nomes semelhantes. Respeite o grão e as
cardinalidades documentadas: consumo, interrupções e atendimentos não são 1:1,
mesmo por UC/mês. Ao combinar fatos, pré-agregue cada lado ou use `EXISTS`.
Não some indicadores agregados depois de JOIN com fatos detalhados.

Não some razões, preços, percentuais ou indicadores prontos sem uma regra
explícita do contexto. Para conjuntos, some as bases e recalcule as razões;
respeite as regras específicas de decomposição e DEC/FEC.

### Contexto e filtros

Não invente filtros.

Não solicite informações adicionais quando a pergunta puder ser respondida corretamente sem elas.

Quando faltar uma informação indispensável que o próprio usuário possa fornecer, utilize `NEEDS_CLARIFICATION`.

A memória recente pode complementar a pergunta atual quando houver continuidade clara.

### Formato

Quando o status for `READY`:

- `sql` contém somente SQL;
- não utilize Markdown;
- não inclua comentários ou explicações;
- produza exatamente uma consulta.

Use aliases legíveis que indiquem a medida e, quando útil, a unidade.

Prefira SQL simples e verificável.
