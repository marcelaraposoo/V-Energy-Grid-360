# Log de qualidade de dados

Registro de todos os problemas de qualidade encontrados e da decisão tomada para cada um.
Este arquivo alimenta o dicionário de dados e a seção de suposições do README.

**Regra:** todo problema tratado na Silver precisa de uma linha aqui.

## Problemas confirmados

| # | Tabela | Coluna | Problema | Nº de linhas afetadas | Decisão | Justificativa | Responsável |
|---|---|---|---|---|---|---|---|
| 1 | medidores | data_ultima_manutencao | Coluna 100% vazia | 51.812 (100%) | Manter a coluna, sem uso em métricas | Não há informação na origem; para avaliar o medidor, usar a idade calculada a partir de `data_instalacao` | Aimê |
| 2 | medidores | data_retirada | Valor coringa `9999-12-31` em medidor ATIVO | 13.649 (26,3%) | Converter para `null` | Significa "não retirado": 100% dos casos têm status ATIVO; os 6.367 RETIRADOS têm data real e nenhum ATIVO tem data real | Aimê |

## Achados a investigar na Silver

Observados na inspeção dos arquivos (notebook `00`), ainda sem contagem. Quem for fazer a silver da tabela confirma, quantifica e move para a tabela acima.

| Tabela | Coluna | Observação |
|---|---|---|
| leituras | data_leitura | Formatos de data misturados (`2022-07-25`, `10/09/2022`) |
| leituras | consumo_kwh | Consumo diferente de `leitura_atual − leitura_anterior` em alguns casos (ex.: 431 vs 432) |
| inspecoes | data | Formatos misturados (`2025-08-01`, `14.08.2025`, `09-01-2025`) |
| inspecoes | resultado | Mesmo valor escrito de formas diferentes (`CONFIRMADA`, `IRREGULARIDADE CONFIRMADA`, `irregularidade confirmada`) |
| inspecoes | kwh_recuperado | Decimal com vírgula e com ponto na mesma coluna (`1313,70` e `838.10`) |
| inspecoes | tipo_irregularidade | `"-"` usado no lugar de nulo |
| inspecoes | inspetor | Espaços sobrando (`" INSP-006"`) |
| medidores | tipo | Variação de grafia (`ELETROMECANICO` e `Eletromecanico`) |
| medidores | modelo | Espaços sobrando (`"  EL-3000 "`) |
| unidades_consumidoras | uf | `PE` e `Pernambuco` |
| unidades_consumidoras | logradouro | Espaços no fim do texto |
| unidades_consumidoras / medidores | — | 45.445 medidores ativos para 46.461 UCs: verificar UCs sem medidor ativo e UCs com mais de um |
| unidades_consumidoras | cpf_cnpj, nome_titular | Dados pessoais: mascarar na Gold e no portal (LGPD) |



## Tabela `leituras`

Fonte: `bronze.leituras` (5 arquivos CSV, um por ano, 2022 a 2026). 2.182.468 linhas na Bronze.
Exploração: `exploracao_leituras.ipynb`. As decisões marcadas como **proposta** aguardam confirmação do grupo.

### Resumo

| # | Problema | Linhas | Decisão 
|---|---|---|---|
| 1 | Cópias exatas de linhas | 21.523 | `dropDuplicates` por `id_leitura` | 
| 2 | Linhas órfãs (`id_medidor` inexistente) | 8.609 | Remover | 
| 3 | `leitura_anterior` ausente, em 4 formas | 32.285 | Nulo real + flag; manter o consumo | 
| 4 | Consumo negativo por sinal invertido | 1.717 | `abs(consumo)` + flag | 
| 5 | Consumo negativo por troca de medidor | 6.299 | `consumo = leitura_atual` + flag 
| 6 | `data_leitura` em 4 formatos | ~258 mil fora do ISO | Converter cada padrão com o seu formato 
| 7 | Consumo difere de `atual − anterior` em ±1 | ~525 mil | Não corrigir | 

Contagens dos itens 3 a 6 em `limpo` (sem cópias e sem órfãs: 2.152.336 linhas).

---

### 1. Cópias exatas de linhas
- **Problema:** 2.182.468 linhas para 2.160.945 `id_leitura` distintos. Contando só as colunas de origem (sem `source_file` e `ingestion_timestamp`), as linhas distintas também são 2.160.945, então as repetições são idênticas.
- **Linhas afetadas:** 21.523.
- **Decisão (proposta):** `dropDuplicates(["id_leitura"])`. Registrar contagem antes e depois.

### 2. Linhas órfãs: `id_medidor` que não existe no cadastro
- **Problema:** o id válido é `MD` + 6 dígitos. 8.609 linhas têm id fora desse formato (7 dígitos), e nenhum existe em `medidores`. Cada uma está em par com uma linha válida da mesma UC e do mesmo mês, e é isso que gera pares `(id_uc, mes_referencia)` repetidos.
- **Linhas afetadas:** 8.609 (de 2.160.945 após remover cópias).
- **Efeito colateral:** se mantidas, o `id_medidor` "pula" para um id inválido e volta, criando mudanças de medidor falsas. Antes de remover havia 23.314 mudanças; depois, 6.299.
- **Decisão (proposta):** remover (ou mandar para quarentena, se o grupo quiser auditar). Na Silver, usar `left_anti` contra os ids distintos de `medidores`, para não multiplicar linhas. Depois da remoção, `(id_uc, mes_referencia)` fica único (2.152.336 linhas).
- **Verificado:** todos os `id_uc` de `limpo` existem em `unidades_consumidoras`.

### 3. `leitura_anterior` ausente, em quatro formas
- **Problema:** a leitura anterior aparece "vazia" de quatro formas: nulo real (8.101), texto `N/A` (8.149), texto `NULL` (8.073) e o código `-1` (7.962). Total: 32.285 linhas (1,5%) em `limpo`.
- **O consumo está preenchido** e numérico em todas essas linhas. As 8.042 linhas em que o consumo não bate com as leituras têm todas `leitura_anterior = -1`.
- **Não é primeira leitura da UC:** dos `N/A`/`NULL` (16.222), só 339 são a primeira leitura da UC. Distribuição uniforme no tempo (~340 por mês).
- **Decisão (proposta):** converter as quatro formas em nulo real, criar a flag `leitura_anterior_ausente` e manter o consumo. Não preencher a leitura com valor calculado.
- **Atenção:** a flag precisa ser calculada antes do cast para número.

### 4. Consumo negativo por sinal invertido
- **Problema:** consumos negativos em linhas cujas leituras estão coerentes (atual maior que anterior). O medidor não mudou nessas linhas. O consumo tem o valor correto com o sinal trocado.
- **Marca:** todos esses valores estão escritos com `.0` no texto original (ex.: `-85.0`). Todo consumo com `.0` na tabela é negativo.
- **Linhas afetadas:** 1.717 em `limpo` (1.687 + 22 + 8). Aparece em todos os anos, ~35 a 38 por mês.
- **Decisão (proposta):** `abs(consumo)` + flag `consumo_corrigido`.
- **Atenção:** o critério do `.0` depende do texto original, então a classificação precisa vir antes do cast. Como validação, esperar zero divergência entre o critério do `.0` e o do medidor.
- **Confirmado nas 30**: o consumo é negativo, termina em `.0` e `abs(consumo)` bate com a leitura recuperada (±1).

### 5. Consumo negativo por troca de medidor
- **Problema:** em 6.299 linhas o medidor da UC muda em relação ao mês anterior, e a `leitura_anterior` é a última do medidor antigo enquanto a `leitura_atual` é a do medidor novo. A subtração dá negativo e o consumo registrado não tem sentido (ex.: UC100011 em 2025-12: anterior 195.613, atual 4.698, consumo −190.915).
- **Período:** só de 2025-09 a 2026-03 (~900 por mês). Nenhuma troca antes disso.
- **Confirmado no cadastro:** o medidor antigo tem `status = RETIRADO` com `data_retirada` no mesmo mês da troca (100% dos casos), e o medidor novo pertence à mesma UC.
- **Confirmado nas faturas:** usando `leitura_atual` como consumo, o preço implícito fica ~5% acima do preço típico da UC (mediana 1,05, faixa de 1,03 a 1,15, em 6.215 linhas). Indica que a fatura desses meses foi calculada com a leitura atual. Evidência forte, não prova.
- **Decisão (proposta):** `consumo = leitura_atual` + flag `troca_medidor`. Alternativa: consumo nulo + flag.
- **Impacto na Gold:** essas linhas caem nos últimos 12 meses, os mesmos que o diretor compara com o primeiro ano. Consumo nulo faria o volume recente parecer menor do que foi.
- **Atenção:** calcular a troca só depois de remover cópias e órfãs.

### 6. `data_leitura` em quatro formatos
- **Problema:** `data_leitura` mistura formatos. Em `limpo`:

| Padrão | Formato | Linhas |
|---|---|---|
| `9999-99-99` | `yyyy-MM-dd` | 1.894.056 |
| `99.99.9999` | `dd.MM.yyyy` | 86.433 |
| `99/99/9999` | `dd/MM/yyyy` | 85.936 |
| `99-99-9999` | `MM-dd-yyyy` (**mês primeiro**) | 85.911 |

- **Como foi confirmada a ordem:** comparando o mês de cada data com `mes_referencia`. Os quatro formatos acima convertem sem falhas e batem em 100% das linhas. Com `dd-MM-yyyy` no padrão com hífen, 49.082 das 85.911 linhas não convertiam e só 3.132 batiam.
- **Risco:** aplicar um formato único converteria datas para o mês errado, sem dar erro.
- **Decisão (proposta):** converter cada padrão com o seu formato e gravar como `date`.
- `mes_referencia` está limpo: todas as linhas seguem `yyyy-MM`.

### 7. Consumo difere de `atual − anterior` em ±1 kWh
- **Observação:** entre os consumos não negativos, 1.616.562 batem exatamente, 262.570 têm diferença de +1 e 262.566 de −1 (~24% das linhas). O ±1 é simétrico e parece arredondamento da origem.
- **Decisão (proposta):** **não corrigir.** Usar ±1 como tolerância nas validações da Silver. Recalcular o consumo mudaria ~24% das linhas em 1 kWh.

---

### Verificado e sem problema
- `tipo_leitura`: sem variações de grafia.
- `mes_referencia`: formato único `yyyy-MM`.
- `id_uc`: todos existem em `unidades_consumidoras`.
- Não há consumo igual a zero.
- Não é virada de mostrador: nas regressões de leitura, a leitura anterior tem mediana ~55 mil (não perto de um teto como 99999).

### Pendências levadas a `medidores`
- 513 linhas com `id_medidor` repetido (51.812 linhas para 51.299 ids distintos). Confirmar se são cópias exatas.
- `data_instalacao` em formatos mistos (entre os medidores novos das trocas, 460 de 6.367 não estão em ISO). A ordem dia/mês desses formatos não foi conferida.
- Um join com `medidores` sem deduplicar multiplica linhas.


## Tabela `faturas`

Fonte: `bronze.faturas` (`faturas.csv`, separador `;`). 2.184.623 linhas na Bronze, 2.184.621 depois de remover o cabeçalho repetido.
Exploração: `exploracao_faturas.ipynb`. As decisões marcadas como **proposta** aguardam confirmação do grupo.

### Resumo

| # | Problema | Linhas | Decisão | Status |
|---|---|---|---|---|
| 1 | Linhas de cabeçalho repetido nos dados | 2 | Remover, antes da deduplicação | proposta |
| 2 | Faturas órfãs (UC inexistente, ids fora do padrão) | 32.285 | Remover ou quarentena | proposta |
| 3 | `valor_total` escrito como moeda (`R$ 9,9`) | 196.622 | Normalizar o texto antes do cast | proposta |
| 4 | `data_emissao` em 4 formatos | 183.361 fora do ISO | Converter cada padrão com o seu formato | proposta |
| 5 | `data_pagamento` ausente em 2 formas | 175.168 | `9999-12-31` vira nulo; flag `em_aberto` | proposta |

As contagens dos itens 3 e 4 são da tabela bruta (incluem as órfãs). As demais são indicadas em cada item.

---

### 1. Linhas de cabeçalho repetido
- **Problema:** 2 linhas em que o valor de cada coluna é o nome da própria coluna (`id_fatura = 'id_fatura'`, `data_emissao = 'data_emissao'` e assim por diante). Ambas vêm do `faturas.csv`.
- **Onde mais ocorre:** `unidades_consumidoras` (1 linha). Não ocorre em `leituras`, `medidores`, `ocorrencias_rede` nem `geracao_distribuida`. `atendimentos` e `inspecoes` não foram testadas.
- **Decisão (proposta):** remover na Silver (nulo estrutural: registro inutilizável), filtrando `id_fatura != 'id_fatura'`. Deve vir **antes** da deduplicação: se deduplicar primeiro, uma das duas linhas sobra.
- **A verificar com quem fez a ingestão:** se o cabeçalho está repetido no arquivo de origem ou se é efeito da leitura da Bronze. Corrigir na Bronze evitaria o tratamento em cada Silver.

### 2. Faturas órfãs
- **Problema:** 32.285 faturas (1,5%) com as três condições ao mesmo tempo: `id_fatura` fora do padrão `FT` + 9 dígitos (prefixo `FTX`, ex.: `FTX0031810`), `id_uc` com 7 dígitos (ex.: `UC9305662`) e UC inexistente em `unidades_consumidoras`. As outras 2.152.336 faturas estão todas no padrão e com UC existente. Nenhuma fatura tem só uma das três condições.
- **Duplicatas:** 21 pares `(id_uc, mes_referencia)` com mais de uma fatura, todos formados por duas órfãs (42 linhas). Entre as faturas válidas, nenhuma repete UC + mês.
- **Peso em valor:** a soma de `valor_energia` das órfãs é R$ 7.644.280,57, contra R$ 499.862.082,73 das válidas (1,5% do total). O valor médio por fatura é parecido (R$ 236,78 nas órfãs e R$ 232,24 nas válidas).
- **Decisão (proposta):** remover (ou guardar numa tabela de quarentena, se o grupo quiser auditar). Padrão análogo às leituras órfãs (`id_medidor` fora do padrão).
- **Efeito na Gold:** a receita total fica ~1,5% menor sem as órfãs. Registrar no dicionário de dados.
- **Não verificado:** se as órfãs de `faturas` e de `leituras` correspondem às mesmas UCs ou meses.

### 3. `valor_total` escrito como moeda
- **Problema:** `valor_energia` e `tributos` têm formato único (`9.9`, ponto decimal). `valor_total` tem três:

| Formato | Exemplo | Linhas |
|---|---|---|
| `9.9` | `102.57` | 1.987.999 |
| `R$ 9,9` | `R$ 100,64` | 188.571 |
| `R$ 9.9,9` | `R$ 1.234,56` (ponto de milhar) | 8.051 |

- **Risco:** um `cast` simples anularia 196.622 faturas (9,0%), e a receita ficaria subestimada em cerca de 9%.
- **Decisão (proposta):** remover `R$` e o ponto de milhar, trocar a vírgula decimal por ponto e converter para `decimal(12,2)`.
- **Validado:** nas 2.152.336 faturas válidas, todos os totais convertem e `valor_total = valor_energia + tributos` em 100% (diferença zero).

### 4. `data_emissao` em quatro formatos
- **Problema:** 

| Padrão | Formato | Linhas |
|---|---|---|
| `9999-99-99` | `yyyy-MM-dd` | 2.001.260 |
| `99/99/9999` | `dd/MM/yyyy` | 61.291 |
| `99.99.9999` | `dd.MM.yyyy` | 61.252 |
| `99-99-9999` | `MM-dd-yyyy` (**mês primeiro**) | 60.818 |

- **Como foi confirmada a ordem:** o vencimento é sempre a emissão + 12 dias. Com os formatos acima, isso vale em 100% das linhas e nenhuma deixa de converter. Os formatos alternativos falham (por exemplo, `dd-MM-yyyy` não converte 38.615 linhas).
- **Mesmo mapeamento de `leituras`:** hífen é mês primeiro, ponto e barra são dia primeiro.
- **O `mes_referencia` não serve de gabarito:** mesmo no ISO, o mês da emissão só bate com a competência em 99,5% das linhas (provavelmente faturas emitidas no mês seguinte; não verificado).
- **Decisão (proposta):** converter cada padrão com o seu formato e gravar como `date`.
- `data_vencimento` (`yyyy-MM-dd`) e `mes_referencia` (`yyyy-MM`) têm formato único.

### 5. `data_pagamento` ausente em duas formas
- **Problema:** `data_pagamento` ausente aparece como nulo real (113.835) e como a data sentinela `9999-12-31` (61.333). Total: 175.168 faturas em aberto (8,0%).
- **Confirmado:** todas as 113.835 com nulo real e todas as 61.333 com `9999-12-31` estão `EM ABERTO`. Todas as 2.009.453 `PAGA` têm data real. Distribuição regular: ~1.275 por mês com a sentinela, em todos os anos.
- **Decisão (proposta):** converter `9999-12-31` em nulo real e derivar a flag `em_aberto`. Isso evita que contas como "dias entre vencimento e pagamento" usem o ano 9999.
- **Mesmo padrão de:** `leitura_anterior` (4 formas de ausência) e `data_retirada` em `medidores` (`9999-12-31`).
- **Efeito na tela do atendente:** a lista de "faturas em aberto" deve usar o `status`, e não a presença da data.

---

### Verificado e sem problema
- Sem cópias exatas: 2.184.621 linhas e 2.184.621 `id_fatura` distintos.
- `status`: só `PAGA` e `EM ABERTO`, sem variações de grafia. Em aberto e pago têm a mesma última competência (2026-06).
- Datas: 0 emissões depois do vencimento e 0 pagamentos antes da emissão, depois de converter cada formato.
- **Uma fatura por leitura:** depois de remover as órfãs das duas tabelas, `faturas` e `leituras` têm exatamente os mesmos 2.152.336 pares `(id_uc, mes_referencia)`: 0 faturas sem leitura e 0 leituras sem fatura.

### Transversais (para as outras Silvers)
- Cabeçalho repetido nos dados: conferir todas as tabelas, em especial `atendimentos` e `inspecoes`.
- `9999-12-31` como data sentinela: aparece em `medidores` e `faturas`. Procurar em `ocorrencias_rede` (`data_encerramento`) e `atendimentos` (`data_fechamento`). Convenção proposta: vira nulo real.
- Registros órfãos com ids fora do padrão (`MD` com 7 dígitos, `FTX`, `UC` com 7 dígitos): procurar nas demais tabelas que referenciam UC.
