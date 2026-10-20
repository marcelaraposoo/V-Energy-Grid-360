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
