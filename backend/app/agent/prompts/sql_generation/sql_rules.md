## Regras de Geração SQL

Toda consulta deve ser exclusivamente de leitura e utilizar somente estruturas presentes no contexto fornecido.

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

Prefira SQL simples e verificável.