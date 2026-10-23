# O que o portal precisa da camada Gold (requisitos do backend)

> **Fonte de verdade:** `docs/gold_contract.md`, mantido pela frente de Dados (ver `AGENTS.md` na `main`).
> Este arquivo é o outro lado do contrato: lista o que o backend (Dev) e o agente (IA) **consomem**, para a
> frente de Dados conferir se o modelo atende. Em caso de divergência, vale o contrato da Gold, e este arquivo
> deve ser atualizado.

Os nomes de coluna abaixo são **lógicos** (os que o backend usa hoje no mock). A Gold segue modelo dimensional
(`dim_*` com chave substituta `*_sk` e `fato_*`), então o `sqlite_repo.py` vai precisar mapear estes nomes
para os reais ou fazer os joins.

## 1. O que o portal consome

| Necessidade | Grão pedido | Colunas lógicas | Usada em |
|---|---|---|---|
| Faturamento | UC x competência | uc_id, competencia (`YYYY-MM`), consumo_kwh, valor, bandeira, vencimento, status (paga/aberta/atrasada) | dashboard, receita, visão 360 |
| **Receita agregada para o portal** | competência x município x bairro x classe | consumo_kwh, receita, n_ucs | dashboard, receita (preço x volume, drill-down) |
| Cadastro da UC | UC | uc_id, titular (**mascarado**), classe, município, bairro, alimentador_id, status, data_ligacao | busca, visão 360, filtros |
| Medidor | UC | medidor_id, tipo, data_instalacao, status | visão 360 |
| Geração distribuída | UC | potencia_kwp, data_conexao | visão 360, fila de perdas |
| Ocorrências de rede | alimentador x ocorrência | alimentador_id, município, data, competencia, ucs_afetadas, duracao_h, causa | DEC/FEC, visão 360 |
| DEC/FEC | alimentador x competência | dec, fec, ucs_total do alimentador | continuidade |
| Atendimentos | UC x chamado | protocolo, data, canal, assunto, status, nota_satisfacao | visão 360 |
| Suspeitas de perdas | UC | motivos, probabilidade (ou score), energia_recuperavel_kwh_mes | fila de inspeção |
| Inspeções | UC x inspeção | resultado (normalizado), tipo_irregularidade, kwh_recuperado, inspetor, data | registrar resultado, base da fila |

## 2. Por que pedir uma tabela agregada de receita

O faturamento real tem cerca de 2,18 milhões de linhas. Hoje o backend soma as faturas em Python sobre dados
de mentira (poucos milhares de linhas); com a base real isso fica lento e pesado. A tela de variação de receita
(efeito preço x volume, por município, bairro e classe) precisa de uma **tabela agregada** (o `AGENTS.md` já prevê
"tabelas agregadas adicionais para o portal") ou de consultas `GROUP BY` no SQLite. Em qualquer caso, o
`repositories/base.py` vai passar a expor métodos que devolvem agregados prontos, em vez de listas de faturas.

## 3. Pontos de atenção vindos do log de qualidade

Baseado em `docs/data_quality_log.md` (itens ainda em investigação podem mudar):

- **LGPD:** `cpf_cnpj` e `nome_titular` são dados pessoais e devem ser **mascarados na Gold e no portal**. O mock
  hoje usa nomes fictícios completos, e o backend não pode expor o dado real sem máscara.
- **Medidor sem última manutenção:** `data_ultima_manutencao` é 100% vazia na origem. O portal e o agente não devem
  contar com esse campo (o mock já foi ajustado). Para avaliar o medidor, usar a idade calculada de `data_instalacao`.
- **UCs x medidores:** a origem tem 45.445 medidores ativos para 46.461 UCs. A visão 360 precisa aceitar UC **sem**
  medidor ativo e, se houver, UC com mais de um (hoje o contrato devolve um único medidor).
- **Inspeções:** `resultado`, `tipo_irregularidade` e `kwh_recuperado` têm grafias e formatos misturados. Os valores
  de `tipo` que o backend aceita ao registrar resultado (`fraude`, `ligacao_clandestina`, `erro_leitura`,
  `erro_cadastro`, `nenhuma`) são **provisórios** e devem ser trocados pelo domínio que a Silver definir.

## 4. Perguntas para a frente de Dados

1. `competencia` sairá como texto `YYYY-MM`?
2. O faturamento terá município, bairro e classe já desnormalizados, ou o backend faz o join com as dimensões?
3. Haverá tabela agregada de receita por competência x município x bairro x classe?
4. Quem calcula DEC/FEC (Gold ou backend)? Quem calcula o score de suspeita de perdas?
5. Como será o mascaramento de `titular` e de documento?
6. Qual o nome e o local do arquivo SQLite gerado pelo `04_export_banco_local` (o backend espera `data/gold.db`)?

`ordens_inspecao` é do portal (não da Gold): será criada no SQLite do backend.
