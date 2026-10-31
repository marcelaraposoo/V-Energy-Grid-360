# Dicionário de dados · `gold.dim_uc`

> Contrato: tabela **A1** do contrato da Gold (v4) · Notebook: `data-engineering/notebooks/03_gold_dim_uc.ipynb` · Status: executada; `PASS` em todas as checagens

## Para que serve

É a "fonte única de verdade" sobre cada cliente (seção 3 do case). Responde ao "quem é o cliente", "o medidor instalado" e "se ele tem painel solar" da Camila, e dá os filtros por município, bairro e classe que o Henrique pede. Também responde à pergunta da Patrícia: "quantas unidades com painel solar em Olinda tiveram queda de consumo acima de 30%?" (153 UCs).

**Quem usa:** todas as telas (cabeçalho da visão 360 e filtros), a `fila_inspecao` (perfil do medidor, GD e consumo de 12 meses) e o agente de IA.

**Grão:** 1 linha = 1 unidade consumidora (`id_uc`).

**Linhas:** 45.000 (1 por UC). **Validação do próprio notebook:** 26 checagens, todas `PASS`.

**Fontes (Silver):** `unidades_consumidoras`, `medidores`, `geracao_distribuida` e `leituras`.

## Colunas (35)

As definições seguem o contrato da Gold (v4). Os tipos são os lógicos do contrato; no `gold.db` (SQLite), texto e data viram `TEXT`, inteiro e booleano viram `INTEGER` (0/1) e decimal vira `REAL`.

### Cadastro

| Coluna | Tipo | Definição |
|---|---|---|
| `id_uc` | texto | identificador da UC (`UC` + 6 dígitos); chave da tabela e de todas as fatos |
| `nome_titular_mascarado` | texto | primeiro nome + inicial de cada sobrenome (`EDVALDO PEREIRA BARBOSA` → `EDVALDO P*** B***`); vale também para PJ (`COLEGIO C*** E***`) |
| `documento_mascarado` | texto | só os dígitos do meio. CPF: `***.816.240-**`; CNPJ: `**.***.816/0001-**` |
| `tipo_pessoa` | texto | `PF` (CPF, 11 dígitos) ou `PJ` (CNPJ, 14 dígitos) |
| `logradouro` | texto | rua |
| `numero` | texto | número |
| `bairro` | texto | bairro padronizado, com a acentuação corrigida. **Usar sempre junto com `municipio`** |
| `municipio` | texto | um dos 14 municípios, com o nome oficial (ex.: `Jaboatão dos Guararapes`) |
| `uf` | texto | sempre `PE` |
| `cep` | texto | 8 dígitos, sem hífen; nulo em 1.193 UCs com CEP inválido na origem |
| `latitude` | decimal | latitude (de −8,46 a −7,70) |
| `longitude` | decimal | longitude (de −35,14 a −34,78; as mais a leste são do litoral) |
| `classe` | texto | `RESIDENCIAL`, `COMERCIAL`, `INDUSTRIAL`, `RURAL` ou `PODER PUBLICO` |
| `subgrupo_tarifario` | texto | `B1` (residencial), `B2` (rural), `B3` (comercial e poder público) ou `A4` (industrial) |
| `alimentador` | texto | circuito que abastece a UC (`ALM-XXX-000`; as 3 letras do meio indicam o município) |
| `data_ligacao` | data | data de ligação da UC |
| `data_ligacao_estimada` | booleano | `true` nas 90 UCs cuja data de origem era impossível (antes de 1950); nelas, a data é a instalação do 1º medidor |
| `status` | texto | sempre `ATIVA` nesta base |

### Medidor

| Coluna | Tipo | Definição |
|---|---|---|
| `id_medidor_ativo` | texto | medidor instalado hoje (toda UC tem exatamente 1 medidor ativo) |
| `tipo_medidor_ativo` | texto | `ELETRONICO`, `ELETROMECANICO` ou `SMART` |
| `modelo_medidor_ativo` | texto | modelo (9 modelos; cada um pertence a um único tipo) |
| `data_instalacao_medidor` | data | instalação do medidor ativo |
| `idade_medidor_anos` | decimal | anos entre a instalação e o fim da base (`2026-06-30`), com 1 casa (dias ÷ 365,25) |
| `medidor_trocado_recentemente` | booleano | a UC teve um medidor `RETIRADO` entre `2025-09-01` e `2026-03-31`, o período das trocas (6.299 UCs) |

### Geração distribuída (painel solar)

| Coluna | Tipo | Definição |
|---|---|---|
| `possui_gd` | booleano | a UC tem registro de GD (3.510 UCs). **É fixa, e não "no mês"**: para saber se a GD já estava conectada em um mês, usar `possui_gd_no_mes` da `fato_consumo_faturamento` |
| `potencia_gd_kwp` | decimal | potência instalada (de 1,5 a 75 kWp); nula sem GD |
| `data_conexao_gd` | data | data de conexão da GD (de jan/2024 a jun/2026); nula sem GD |
| `modalidade_gd` | texto | `GERACAO NA PROPRIA UC`, `AUTOCONSUMO REMOTO` ou `GERACAO COMPARTILHADA`; nula sem GD |
| `energia_injetada_media_kwh` | decimal | energia injetada na rede, média por mês. **Não usar como medida quando `energia_injetada_atipica = true`** |
| `energia_injetada_atipica` | booleano | energia injetada provavelmente calculada, e não medida (109 UCs); `false` nas UCs sem GD |

### Consumo

| Coluna | Tipo | Definição |
|---|---|---|
| `primeiro_mes_leitura` | texto | primeiro `mes_referencia` com leitura (`yyyy-MM`) |
| `ultimo_mes_leitura` | texto | último `mes_referencia` com leitura (`yyyy-MM`) |
| `consumo_medio_12m_kwh` | decimal | consumo médio mensal de `2025-07` a `2026-06` (os mesmos 12 meses do diagnóstico) |
| `consumo_medio_12m_anterior_kwh` | decimal | consumo médio mensal de `2024-07` a `2025-06` |
| `variacao_consumo_12m_pct` | decimal | `(consumo_medio_12m_kwh ÷ consumo_medio_12m_anterior_kwh − 1) × 100`, com 2 casas. Negativa quando o consumo caiu. Nula se a UC não tem leitura nos 12 meses anteriores (61 UCs) |

## Decisões de limpeza que afetam esta tabela

Os itens são do `docs/data_quality_log.md`.

| Item | O que foi encontrado | O que foi feito, e o efeito aqui |
|---|---|---|
| U2 | Mesma UC repetida, com nome e documento escritos de jeitos diferentes (1.260) | padronizados e deduplicados; `id_uc` único |
| U3 | 200 UCs de teste (`ATIVA`, sem medidor, leitura nem fatura) | removidas na Silver. **A tabela tem 45.000 UCs, o número do case** |
| U4, U5 | `uf`, classe e município com várias grafias | padronizados; `uf` sempre `PE`, 5 classes e 14 municípios com o nome oficial |
| U6 | Bairro com acentuação corrompida (348) | corrigido; o mesmo nome de bairro existe em municípios diferentes (297 pares, 272 nomes) |
| U7 | CEP inválido em 7 formas (1.193) | vira nulo; o endereço continua identificado por logradouro e bairro |
| U8, U10 | CPF/CNPJ com e sem máscara; dados pessoais | só dígitos na Silver + `tipo_pessoa`; **mascarados nesta tabela** (LGPD). As colunas originais não entram na Gold |
| U9 | Data de ligação impossível, antes de 1950 (90) | substituída pela instalação do 1º medidor; flag `data_ligacao_estimada` |
| M2 | `data_retirada` com a sentinela `9999-12-31` nos medidores ativos | vira nulo; a troca recente usa só medidores `RETIRADO` com data real |
| M3 | Medidores copiados (513) | removidos; cada medidor aparece uma vez |
| M4 | `data_instalacao` em 4 formatos | convertida (hífen = mês primeiro); é a base da `idade_medidor_anos` |
| M5 | Tipo do medidor com 10 grafias | normalizado para os 3 tipos |
| G1, G2 | Potência com vírgula decimal (316) e em watts (35) | convertida; as 35 em watts foram divididas por 1.000 |
| G3 | GD conectada antes da ligação da UC (5) | mantido; a flag `conexao_antes_ligacao` fica só na Silver |
| G5 | Energia injetada atípica, quase toda exatamente `potência × 110` (109) | valor mantido + flag `energia_injetada_atipica` |
| L2, L4, L5 | Leituras órfãs removidas; sinal invertido corrigido; troca de medidor com `consumo = leitura_atual` | as médias de 12 meses usam o consumo já tratado da Silver de leituras |

## Cuidados de uso

- **LGPD:** nome e documento só existem mascarados. Nenhuma tela, exportação ou resposta do agente deve tentar reconstruir o dado original.
- **Bairro só vale junto com o município** (297 pares, 272 nomes de bairro). Filtrar só por `bairro` mistura bairros de municípios diferentes.
- **`possui_gd` é fixa:** diz se a UC tem GD, e não desde quando. As 3.510 UCs foram conectadas entre jan/2024 e jun/2026, então a GD de uma UC conectada em 2026 aparece em poucos meses da janela de 12 meses. Para análises mensais, usar `possui_gd_no_mes` da `fato_consumo_faturamento` (inclui o mês da conexão).
- **GD só existe em residencial (3.127) e comercial (383).** Industrial, rural e poder público têm zero UCs com GD.
- **`variacao_consumo_12m_pct` compara janelas fixas** (`2025-07` a `2026-06` contra `2024-07` a `2025-06`). A pergunta "queda acima de 30%" depende do período escolhido; o agente deve dizer qual período usou. Uma UC que conectou a GD antes de `2024-07` já tinha o consumo reduzido nas duas janelas e pode não aparecer como queda.
- **Quedas de maio e junho de 2025 aparecem atenuadas:** esses dois meses estão na janela anterior. Nas UCs dos quatro bairros do diagnóstico (queda de ~55% nesse período), a variação de 12 meses fica menor que a queda real.
- **`energia_injetada_media_kwh`** não é medida confiável nas 109 UCs com `energia_injetada_atipica = true` (101 delas conectadas em 2026).
- **`medidor_trocado_recentemente`** marca as UCs com troca entre set/2025 e mar/2026. Nesses meses, o consumo da `fato_consumo_faturamento` é a leitura atual do medidor novo (log L5), e o preço por kWh fica ~5% acima do típico.
- **`idade_medidor_anos`** é medida até o fim da base (`2026-06-30`), e não até a data de hoje.

## Como foi validada

- 45.000 linhas, `id_uc` único; 14 municípios, 297 pares município + bairro e 122 alimentadores, como no case.
- Nenhuma coluna com dado pessoal sem máscara; documento sempre no formato mascarado de CPF ou CNPJ; nome sem sobrenome por extenso.
- Toda UC com medidor ativo, bairro, município, classe, alimentador e consumo dos últimos 12 meses.
- 3.510 UCs com GD, todas com potência e data de conexão; nenhuma UC sem GD com potência.
- 6.299 UCs com troca recente, o mesmo número de meses com troca da `fato_consumo_faturamento`.
- Conexão testada pelas outras Golds: 0 UCs da `fato_consumo_faturamento`, da `fato_atendimento` e da `fila_inspecao` fora desta tabela, e 0 com município, bairro ou classe diferentes.
