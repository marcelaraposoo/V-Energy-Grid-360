# Log de qualidade de dados

Registro de todos os problemas de qualidade encontrados e da decisão tomada para cada um.
Este arquivo alimenta o dicionário de dados e a seção de suposições do README.

**Regra:** todo problema tratado na Silver precisa de uma linha aqui.

| # | Tabela | Coluna | Problema | Nº de linhas afetadas | Decisão | Justificativa | Responsável |
|---|---|---|---|---|---|---|---|
| 1 | _exemplo_ | _consumo_kwh_ | _valores negativos_ | _1.234 (0,06%)_ | _marcar flag_consumo_invalido e excluir das métricas_ | _virada de medidor; não dá para recuperar o valor real_ | _Aimê_ |
