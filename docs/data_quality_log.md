# Log de qualidade de dados

Registro de todos os problemas de qualidade encontrados e da decisão tomada para cada um.
Este arquivo alimenta o dicionário de dados e a seção de suposições do README.

**Regra:** todo problema tratado na Silver precisa de uma linha aqui.

## Como usar este arquivo

- O arquivo tem **uma seção por tabela**. Cada pessoa edita **só a seção das suas tabelas**, para evitar conflito entre PRs.
- Antes de editar, faça **pull da `main`**.
- Cada problema tem um **código** com o prefixo da tabela e um número sequencial dentro dela:

| Prefixo | Tabela | Bloco | Responsável |
|---|---|---|---|
| `U` | unidades_consumidoras | A | Aimê |
| `M` | medidores | A | Aimê |
| `G` | geracao_distribuida | A | Aimê |
| `O` | ocorrencias_rede | A | Aimê |
| `L` | leituras | B | Marcela |
| `F` | faturas | B | Marcela |
| `A` | atendimentos | C | Maria |
| `I` | inspecoes | C | Maria |
| `X` | cruzamentos entre tabelas | C | Maria |

- Cada seção tem: **resumo** (tabela com uma linha por problema), **a investigar** (achados ainda sem contagem) e, quando necessário, **detalhes** (problema, decisão, alternativas, impacto na Gold).
- Ao confirmar um achado, mova-o de "a investigar" para o resumo da tabela com um código.

## Convenções adotadas (valem para todas as tabelas)

- Todo código de ausência (`N/A`, `NULL`, `-1`) e toda data coringa `9999-12-31` viram nulo real, com flag quando faz sentido.
- Datas viram `date`, com o formato de cada padrão confirmado contra um gabarito (`mes_referencia` em leituras, vencimento em faturas). Nos dois casos, o hífen é mês primeiro.
- Registros órfãos (ids fora do padrão, sem correspondência no cadastro) são removidos. A Bronze guarda as linhas.
- Linha de cabeçalho repetida é removida antes de qualquer contagem ou deduplicação.

---

# Bloco A — Cadastro e Rede (Aimê)

## `unidades_consumidoras` (U)

Fonte: `bronze.unidades_consumidoras` (`unidades_consumidoras.csv`). 46.461 linhas na Bronze; **45.000 UCs** na Silver.
Exploração: `exploracao_unidades_consumidoras.ipynb`. Silver: `02_silver_unidades_consumidoras.ipynb`.
**Decisões tomadas por Aimê**, responsável pela tabela, com a autonomia combinada com o grupo. Registro em 23/10/2026. Contagens de U1 a U3 na Bronze; de U4 em diante, nas 45.000 UCs finais (por isso podem ser menores que na exploração, que contava também as linhas repetidas e as UCs de teste).

### Resumo

| ID | Coluna | Problema | Linhas afetadas | Decisão | Justificativa |
|---|---|---|---|---|---|
| U1 | todas | Linha de cabeçalho repetida como dado (`id_uc = 'id_uc'`), presente no arquivo de origem (linha 27.536 do CSV) | 1 | Remover antes de contar linhas, deduplicar e fazer joins | Nulo estrutural; mesma convenção de F1. A Bronze preserva a origem |
| U2 | id_uc | Mesma UC repetida, com `nome_titular` e `cpf_cnpj` escritos de jeitos diferentes | 1.260 | Padronizar nome e documento e depois `dropDuplicates(["id_uc"])` | Depois da padronização, nenhum id tem versões diferentes: a deduplicação não perde informação |
| U3 | id_uc | UCs de teste: `ATIVA`, mas sem medidor, sem leitura e sem fatura | 200 | Remover | São registros de teste do sistema de origem, não clientes. Sem elas, o total é 45.000, o número do case. Mantidas, inflariam a base de clientes e o denominador do DEC/FEC |
| U4 | uf | `Pernambuco`, `P.E.` (1.666) e outras variações no lugar de `PE` | 6.750 | Padronizar para `PE`, ignorando pontos e espaços na comparação | Todas as UCs são de Pernambuco |
| U5 | classe, municipio, status, textos | Grafias diferentes para o mesmo valor; espaços no início, no fim e duplicados | várias | Mapa para valores canônicos (5 classes; 14 municípios com o nome oficial) + `trim` | Valor fora do mapa vira nulo e faz a checagem falhar, avisando grafia nova |
| U6 | bairro | Mojibake: UTF-8 lido como Windows-1252 (`JordÃ£o`, `BrasÃ­lia`) | 348 | Reverter a codificação; mapa manual para os valores em que um caractere invisível se perdeu (`Nossa Senhora do Ã` → `Nossa Senhora do Ó`) | Só `bairro` tem o problema. `Rio Âmbar` (32 linhas) está correto e não é alterado |
| U7 | cep | Valores que não são CEP, em 7 formas | 1.193 | Converter para `null`; os válidos ficam com 8 dígitos, sem hífen | Inventar um CEP seria pior que deixar vazio; o endereço continua identificado por logradouro e bairro |
| U8 | cpf_cnpj | Documento com e sem máscara | várias | Só dígitos + coluna `tipo_pessoa` (`PF` = 11 dígitos, `PJ` = 14) | Necessário para a deduplicação (U2) e para a máscara na Gold |
| U9 | data_ligacao | Datas antes de 1950, quase todas em `01/01` (valor de preenchimento) | 90 | Substituir pela instalação do 1º medidor e marcar `data_ligacao_estimada = true` | Nas outras 44.910 UCs, a ligação é igual à instalação do 1º medidor. Alternativa considerada: nulo + flag |
| U10 | cpf_cnpj, nome_titular | Dados pessoais | todas | Manter na Silver; mascarar na Gold, no portal e no agente | LGPD; a Silver é camada interna |

### Detalhes

#### U3. Por que as 200 UCs são de teste
Status `ATIVA`, mas nenhum medidor em `medidores`, nenhuma leitura e nenhuma fatura, e os dados cadastrais indicam registros de teste. Com elas removidas, a base fica com 45.000 UCs (o número do case), e **cada UC tem exatamente 1 medidor ativo**. A lista está na Silver (seção 6) e as linhas continuam na Bronze.

#### U9. Data de ligação estimada
Exemplo: `UC105409`, ligada em `1916-01-01`, com o primeiro medidor instalado em `2021-07-25`. Das 90 datas antes de 1950, só 1 tem o mesmo dia e mês da instalação, o que mostra que não são datas reais com o ano errado. Como em todas as outras UCs a ligação é igual à instalação do 1º medidor, essa é a melhor estimativa. A flag permite excluir essas 90 de qualquer análise que precise da data exata.

### Verificado e sem problema

- `id_uc` sempre no padrão `UC` + 6 dígitos.
- Classe × subgrupo segue o glossário: RESIDENCIAL = B1, RURAL = B2, COMERCIAL e PODER PUBLICO = B3, INDUSTRIAL = A4.
- Todo alimentador segue `ALM-XXX-000`, e o código corresponde ao município da UC (14 códigos, 14 municípios).
- Cada UC real tem exatamente 1 medidor ativo, e todo `id_uc` de `medidores` existe no cadastro.
- `status` é sempre `ATIVA`.
- Coordenadas numéricas e coerentes com o município: latitude de −8,46 a −7,70 e longitude de −35,14 a −34,78. As mais a leste (−34,78 e −34,79) são de Ilha de Itamaracá e da orla de Olinda, ou seja, são litoral, não erro.

**Impacto na Gold:** o mesmo nome de bairro existe em municípios diferentes, então a chave de bairro é **município + bairro**.


## `medidores` (M)

Fonte: `bronze.medidores` (`medidores.csv`). 51.812 linhas na Bronze, 51.299 depois de remover as cópias.
Exploração: `exploracao_medidores.ipynb`. Silver: `02_silver_medidores.ipynb`.
**Decisões tomadas por Aimê**, responsável pela tabela, com a autonomia combinada com o grupo. Registro em 21/10/2026. Contagens de M1, M2, M4, M5 e M6 na tabela sem cópias (51.299 linhas).

### Resumo

| ID | Coluna | Problema | Linhas afetadas | Decisão | Justificativa |
|---|---|---|---|---|---|
| M1 | data_ultima_manutencao | Coluna 100% vazia | 51.299 (100%) | Manter a coluna (tipo `date`), sem uso em métricas | Não há informação na origem; para avaliar o medidor, usar a idade calculada a partir de `data_instalacao` |
| M2 | data_retirada | Valor coringa `9999-12-31` em medidor ATIVO | 13.500 (26,3%) | Converter para `null` | Significa "não retirado": 100% dos casos têm status ATIVO; os 6.299 RETIRADOS têm data real e nenhum ATIVO tem data real. (Na Bronze, com as cópias, eram 13.649) |
| M3 | id_medidor | Cópias exatas de linhas | 513 (1,0%) | `dropDuplicates(["id_medidor"])`, antes de qualquer outro tratamento | 513 ids aparecem exatamente 2 vezes, com conteúdo idêntico em todas as colunas de origem |
| M4 | data_instalacao | 4 formatos: ISO, `MM-dd-yyyy`, `dd.MM.yyyy` e `dd/MM/yyyy` | 3.694 (7,2%) fora do ISO | Converter cada padrão com o seu formato e gravar como `date` | Ordem confirmada por 3 testes independentes (detalhes abaixo); mesmo mapeamento de leituras e faturas |
| M5 | tipo | 10 grafias para 3 tipos (maiúsculas, acento, hífen e `smart meter`) | 5.297 (10,3%) | Normalizar para `ELETRONICO`, `ELETROMECANICO` e `SMART` | Depois de normalizar, cada modelo tem um único tipo, o que confirma o mapeamento |
| M6 | modelo | Espaços no início e/ou no fim | 3.078 (6,0%) | `trim` | São os mesmos 9 modelos; o espaço não tem significado |

### Detalhes

#### M4. Ordem dia/mês de `data_instalacao`
- **Formatos:** ISO `yyyy-MM-dd` (47.605), `99-99-9999` (1.250), `99/99/9999` (1.235) e `99.99.9999` (1.209).
- **Teste 1, partes maiores que 12:** no hífen, 755 linhas têm a 2ª parte maior que 12 (só pode ser dia, então o hífen é mês primeiro). Na barra e no ponto, 723 e 726 linhas têm a 1ª parte maior que 12 (dia primeiro). Nenhum caso contradiz.
- **Teste 2, data de ligação da UC:** nos medidores em ISO, a instalação é igual à ligação da UC em 87,6% (41.678 de 47.605). Nos não ISO, o formato proposto bate com a ligação em 1.106 de 1.250 (hífen), 1.066 de 1.209 (ponto) e 1.060 de 1.235 (barra), cerca de 87%, a mesma taxa do ISO. A ordem trocada bate em no máximo 45.
- **Teste 3, troca de medidor:** nos medidores novos das trocas de `silver.leituras`, o mês de instalação é o mês da troca em **142 de 142** (hífen), **142 de 142** (ponto) e **173 de 173** (barra). A ordem trocada bate em no máximo 3.
- **Conclusão:** hífen = mês primeiro; ponto e barra = dia primeiro. É o mesmo mapeamento de `leituras` (L6) e `faturas` (F4), provavelmente uma convenção do sistema de origem.

#### M5. Mapeamento de `tipo`

| Tipo na Silver | Grafias na Bronze (linhas, sem cópias) |
|---|---|
| `ELETRONICO` | `ELETRONICO` (23.685), `Eletronico` (1.350), `eletrônico` (1.304) |
| `ELETROMECANICO` | `ELETROMECANICO` (14.703), `ELETRO-MECANICO` (601), `Eletromecanico` (598), `eletromecânico` (591) |
| `SMART` | `SMART` (7.614), `smart meter` (439), `Smart` (414) |

- **Validação:** depois da normalização, cada modelo tem um único tipo: `CG-500`, `EM-1200` e `EM-1400` são eletromecânicos; `EL-2200`, `EL-3000` e `NX-700` são eletrônicos; `IQ-900`, `SM-4100` e `SM-4500` são smart. Isso vira uma checagem na Silver.
- **Impacto na Gold:** totais por tipo: 26.339 eletrônicos, 16.493 eletromecânicos e 8.467 smart (todos os medidores, ativos e retirados).

#### Verificado e sem problema
- Todos os `id_medidor` no padrão `MD` + 6 dígitos e todos os `id_uc` no padrão `UC` + 6 dígitos.
- Todos os `id_uc` existem em `unidades_consumidoras`: não há medidores órfãos.
- `status`: só `ATIVO` (45.000) e `RETIRADO` (6.299), sem variações de grafia.
- `status` coerente com `data_retirada`: todo RETIRADO tem data real e nenhum ATIVO tem.
- Datas: nenhuma retirada antes da instalação e nenhuma data depois do fim da extração (2026-06).
- Os 51.299 medidores aparecem em `silver.leituras`, e não há leitura depois do mês de retirada do medidor.
- Nenhuma UC tem mais de um medidor ativo.

## `geracao_distribuida` (G)

Fonte: `bronze.geracao_distribuida` (`geracao_distribuida.csv`). 3.510 linhas na Bronze e na Silver (nenhuma removida).
Exploração: `exploracao_geracao_distribuida.ipynb`. Silver: `02_silver_geracao_distribuida.ipynb`.
**Decisões tomadas por Aimê**, responsável pela tabela, com a autonomia combinada com o grupo. Registro em 24/10/2026.

### Resumo

| ID | Coluna | Problema | Linhas afetadas | Decisão | Justificativa |
|---|---|---|---|---|---|
| G1 | potencia_kwp | Vírgula decimal (`5,87`) misturada com ponto | 316 (9,0%) | Trocar vírgula por ponto antes de converter | Um `cast` simples anularia esses valores |
| G2 | potencia_kwp | Valores registrados em **watts** (de 1.000 a 8.995) | 35 (1,0%) | Dividir por 1.000 + flag `potencia_convertida_de_w`; original em `potencia_kwp_original` no notebook | A energia injetada por kWp das 35 só fica igual à das outras UCs (33,3 contra 33,8 kWh/kWp/mês) se a potência for dividida por 1.000 |
| G3 | data_conexao | GD conectada antes da ligação da UC (de 55 a 473 dias antes) | 5 | Manter as datas + flag `conexao_antes_ligacao` | Não há gabarito para saber qual data está errada; trocar seria inventar dado |
| G4 | todas | Tudo como texto na Bronze | 3.510 | `data_conexao` → `date`; potência → `decimal(10,3)`; energia → `decimal(12,2)` | Necessário para cálculos e filtros |
| G5 | energia_injetada_kwh_media_mensal | Energia injetada acima de 60 kWh por kWp ao mês; 106 delas exatamente `potência × 110` | 109 (3,1%) | Manter o valor + flag `energia_injetada_atipica` | O valor parece calculado, não medido; não há como saber o real. A flag impede o uso como medida |

### Detalhes

#### G2. Potência em watts
- **Problema:** 35 potências (33 residenciais e 2 comerciais) estão entre 1.000 e 8.995 kWp. A mediana da tabela é 5,87 kWp, e uma residência com 9 mil kWp não existe (o limite da minigeração é 5.000 kW). Não há nenhum valor entre 75 e 1.000.
- **Marca:** são exatamente os valores com 4 dígitos antes do separador (`9999.99`, `9999.9`, `9999,9`, `9999,99`).
- **Como foi confirmado:** a energia injetada por kWp é de 33,8 kWh/mês (mediana) nas 3.475 UCs normais. Nas 35 suspeitas, dá 0,03; dividindo a potência por 1.000, dá 33,3. A energia injetada das suspeitas também é parecida com a das outras (mediana de 187 contra 199 kWh).
- **Decisão:** dividir por 1.000 as potências a partir de 1.000. Depois da conversão, todas ficam entre 1,5 e 75 kWp.
- **Alternativa considerada:** anular a potência. Descartada, porque o valor certo é recuperável com evidência forte.
- **Checagem na Silver:** energia por kWp entre 10 e 60 kWh/mês (ou marcada como atípica, ver G5).

#### G5. Energia injetada atípica
- **Faixa típica:** de 11,6 a ~50 kWh por kWp ao mês (mediana 33,8; percentis 1% e 95%: 22,3 e 44,3). Nenhuma UC fica abaixo de 10.
- **Problema:** 109 UCs passam de 60. **106 têm exatamente 110,0 kWh/kWp**: a energia foi calculada como `potência × 110`. 110 kWh/kWp por mês é a **geração** típica de um painel em Recife, e não a sobra injetada na rede. As outras 3 (114, 168 e 328) são UCs com potência convertida de watts (G2).
- **Perfil:** **101 das 109 foram conectadas em 2026** (28% das 361 conexões do ano), contra 7 em 2024 e 1 em 2025. **As 5 UCs de G3 (conexão antes da ligação) estão todas neste grupo.** Modalidade e classe seguem a mesma proporção do resto da base.
- **Hipóteses:** (a) estimativa teórica do sistema para conexões recentes, ainda sem histórico para calcular a média mensal real; (b) registros suspeitos, de interesse para a fila de perdas. A concentração em 2026 favorece (a); a coincidência com G3 e os 8 casos de 2024 e 2025 não se explicam por ela.
- **Decisão:** manter o valor e marcar `energia_injetada_atipica = true`. Substituir por uma estimativa seria inventar dado.
- **Impacto:** o diagnóstico da receita não usa esta coluna (a queda de volume vem das leituras). Na Gold, a energia injetada da `dim_uc` vai com a flag, e as 109 UCs podem entrar como sinal na fila de perdas.
- **Checagem na Silver:** energia por kWp entre 10 e 60, **ou** flag marcada. Uma anomalia nova, sem flag, faz a checagem falhar.

### Verificado e sem problema
- Sem cabeçalho repetido, cópias, nulos ou códigos de ausência (`N/A`, `NULL`, `-1`, `-`, `9999-12-31`).
- **1 registro por UC:** 3.510 linhas e 3.510 `id_uc` distintos.
- Todos os `id_uc` no padrão e existentes na Silver de UCs; nenhuma das 200 UCs de teste tem GD.
- `data_conexao` só em ISO, de jan/2024 a jun/2026.
- `modalidade` com 3 valores limpos: `GERACAO NA PROPRIA UC` (3.042), `AUTOCONSUMO REMOTO` (321) e `GERACAO COMPARTILHADA` (147).
- `energia_injetada_kwh_media_mensal` sempre com ponto decimal.

**Impacto no diagnóstico (exploração, seções 11 e 12):** nenhuma UC tinha GD no primeiro ano; nos últimos 12 meses são 3.510 (7,8% da base), só residenciais e comerciais. As UCs com GD perderam 11,2 milhões de kWh faturados, mais que a queda total de 9,0 milhões (−3,95%): **sem a GD, o volume teria crescido 1,07%**. Depois da conexão, o consumo faturado de cada UC cai 69,6%.


## `ocorrencias_rede` (O)

Fonte: `bronze.ocorrencias_rede` (`ocorrencias_rede.csv`). 180.000 linhas na Bronze e na Silver (nenhuma removida).
Exploração: `exploracao_ocorrencias_rede.ipynb`. Silver: `02_silver_ocorrencias_rede.ipynb`.
**Decisões tomadas por Aimê**, responsável pela tabela, com a autonomia combinada com o grupo. Registro em 24/10/2026.

### Resumo

| ID | Coluna | Problema | Linhas afetadas | Decisão | Justificativa |
|---|---|---|---|---|---|
| O1 | causa | Ausente em 4 formas: nulo real (1.356), `-` (1.363), `N/A` (1.341) e `NULL` (1.340) | 5.400 (3,0%) | Converter para nulo real; a ocorrência é mantida | Mesma convenção de L3. A ocorrência tem UC, datas e duração, então continua no DEC/FEC. `NAO IDENTIFICADA` é uma causa registrada e **não** é tratada como ausência |
| O2 | duracao_min | Texto ` min` junto do número (`28 min`) | 16.200 (9,0%) | Remover o sufixo e converter para inteiro | Um `cast` direto anularia 9% das durações e subestimaria o DEC. Validado: `fim − início = duração` em 100% das linhas |
| O3 | data_abertura, data_encerramento | Datas como texto | 180.000 | Converter para `timestamp`, mantendo o horário; derivar `mes_referencia` (`yyyy-MM` da abertura) | Sempre ISO com horário; o horário é necessário para a duração e para a visão 360 |

### Detalhes

#### O2. Duração com sufixo e o gabarito das datas
- **Formatos:** `99` (100.429), `999` (59.938), `9` (2.699), `9999` (734) e, com o sufixo, `99 min` (9.873), `999 min` (5.965), `9 min` (277) e `9999 min` (85).
- **Gabarito:** nas 163.800 linhas com duração numérica, `data_encerramento − data_abertura` bate com `duracao_min` em **100%**. A checagem da Silver repete o teste nas 180.000 linhas, incluindo as corrigidas.
- **Distribuição:** de 5 minutos a 48 horas (mediana de 72 min); 244 acima de 24 horas e nenhuma acima de 7 dias. Mantidas: são plausíveis em eventos climáticos.

### Verificado e sem problema
- Sem cabeçalho repetido, cópias, nulos fora de `causa` ou sentinela `9999-12-31`.
- **Nenhuma interrupção registrada em dobro:** 0 pares de mesma UC com mesma abertura.
- Todos os `id_uc` no padrão e existentes na Silver de UCs; nenhuma UC de teste.
- **O alimentador da ocorrência é sempre o mesmo do cadastro da UC.**
- Datas só em ISO com horário; nenhum fim antes do início; nenhuma ocorrência em aberto; tudo entre jul/2022 e jun/2026.
- `tipo` com 5 valores e `causa` com 6 valores, sem variações de grafia.
- 122 alimentadores, como o case informa (mais de 120).

**Para o contrato da Gold e o diagnóstico:**
- **Causas evitáveis por manutenção (proposta):** `VEGETACAO`, `FALHA DE EQUIPAMENTO` e `SOBRECARGA`. `CLIMATICA` e `TERCEIROS` não dependem da distribuidora; `NAO IDENTIFICADA` e as nulas ficam de fora.
- **Causa climática** responde por 36% das horas interrompidas (116.919 h), com duração mediana de 101 min, contra 65 a 67 min nas demais.
- **2025 teve 41% mais ocorrências** que 2023 e 2024 (57.068 contra ~40.300).
- **DEC com denominador pequeno:** os piores DEC são de alimentadores com 20 a 47 UCs. A tela da Beatriz deve mostrar o DEC junto com o número de UCs e as horas totais.
- **Suposição a registrar no README:** o tipo `OSCILACAO` (14.562) entra no DEC/FEC, porque o glossário do case diz que cada registro é uma UC interrompida.


---

# Bloco B — Medição e Faturamento (Marcela)

## `leituras` (L)

Fonte: `bronze.leituras` (5 arquivos CSV, um por ano, 2022 a 2026). 2.182.468 linhas na Bronze.
Exploração: `exploracao_leituras.ipynb`. Silver: `02_silver_leituras.ipynb`.
**Decisões tomadas por Marcela**, responsável pela tabela, com a autonomia combinada com o grupo para as tabelas de cada integrante. Registro em 20/10/2026. Contagens dos itens L3 a L6 em `limpo` (sem cópias e sem órfãs: 2.152.336 linhas).

### Resumo

| ID | Coluna | Problema | Linhas afetadas | Decisão | Justificativa |
|---|---|---|---|---|---|
| L1 | id_leitura | Cópias exatas de linhas | 21.523 (1,0%) | `dropDuplicates` por `id_leitura` | Linhas idênticas em todas as colunas de origem: manter uma não perde informação |
| L2 | id_medidor | Órfãs: id fora do padrão `MD` + 6 dígitos e inexistente em `medidores` | 8.609 (0,4%) | Remover | O cadastro não tem o medidor; mantê-las criaria trocas de medidor falsas (23.314 em vez de 6.299). A Bronze guarda as linhas |
| L3 | leitura_anterior | Ausente em 4 formas: nulo real, `N/A`, `NULL` e `-1` | 32.285 (1,5%) | Nulo real + flag `leitura_anterior_ausente`; consumo mantido | É dado que faltou (só 339 são a primeira leitura da UC) e o consumo está preenchido. Não se preenche com valor calculado |
| L4 | consumo_kwh | Sinal invertido: negativo escrito com `.0`, com leituras coerentes e sem troca de medidor | 1.717 | `abs(consumo)` + flag `consumo_corrigido` | As leituras confirmam o valor absoluto, inclusive nas 30 linhas com leitura anterior ausente |
| L5 | consumo_kwh | Troca de medidor (2025-09 a 2026-03): a leitura anterior é do medidor antigo | 6.299 | `consumo = leitura_atual` + flag `troca_medidor` | Cadastro (medidor antigo `RETIRADO` no mês da troca em 100%) e faturas (preço ~5% acima do típico) sustentam. Consumo nulo faria o volume recente parecer menor |
| L6 | data_leitura | 4 formatos: ISO, `dd.MM.yyyy`, `dd/MM/yyyy` e `MM-dd-yyyy` (hífen = mês primeiro) | ~258 mil fora do ISO | Converter cada padrão com o seu formato e gravar como `date` | Ordem confirmada contra `mes_referencia` em 100%; um formato único erraria o mês sem dar erro |
| L7 | consumo_kwh | Difere de `atual − anterior` em ±1 kWh | ~525 mil (~24%) | Não corrigir; usar ±1 como tolerância nas validações | Desvio simétrico, típico de arredondamento da origem; recalcular mudaria 24% das linhas |

### Detalhes

#### L1. Cópias exatas de linhas
- **Problema:** 2.182.468 linhas para 2.160.945 `id_leitura` distintos. Contando só as colunas de origem (sem `source_file` e `ingestion_timestamp`), as linhas distintas também são 2.160.945: as repetições são idênticas.
- **Linhas afetadas:** 21.523.
- **Decisão:** `dropDuplicates(["id_leitura"])`, registrando a contagem antes e depois.
- **Alternativas consideradas:** nenhuma razoável, já que as linhas são idênticas.
- **Impacto na Gold:** nenhum; não se perde informação.

#### L2. Linhas órfãs: `id_medidor` que não existe no cadastro
- **Problema:** o id válido é `MD` + 6 dígitos. 8.609 linhas têm id fora desse formato (7 dígitos), e nenhum existe em `medidores`. Cada uma está em par com uma linha válida da mesma UC e do mesmo mês, e é isso que gera pares `(id_uc, mes_referencia)` repetidos.
- **Linhas afetadas:** 8.609 (de 2.160.945 após remover cópias).
- **Efeito colateral:** se mantidas, o `id_medidor` "pula" para um id inválido e volta, criando mudanças de medidor falsas. Antes de remover havia 23.314 mudanças; depois, 6.299.
- **Decisão:** remover. Na Silver, usar `left_anti` contra os ids distintos de `medidores`, para não multiplicar linhas. Depois da remoção, `(id_uc, mes_referencia)` fica único (2.152.336 linhas).
- **Alternativa considerada:** quarentena (gravar as órfãs em tabela própria). Descartada porque a Bronze já guarda as 8.609 linhas intactas e elas se encontram filtrando o `id_medidor` fora do padrão. Ressalva: a Bronze é sobrescrita a cada carga, então, se o pipeline rodar com dados novos, a quarentena passaria a ser o único histórico do que foi rejeitado.
- **Impacto na Gold:** 8.609 leituras a menos (0,4%); a chave `(id_uc, mes_referencia)` fica única.
- **Verificado:** todos os `id_uc` de `limpo` existem em `unidades_consumidoras`.

#### L3. `leitura_anterior` ausente, em quatro formas
- **Problema:** a leitura anterior aparece "vazia" de quatro formas: nulo real (8.101), texto `N/A` (8.149), texto `NULL` (8.073) e o código `-1` (7.962). Total: 32.285 linhas (1,5%).
- **O consumo está preenchido** e numérico em todas essas linhas. As 8.042 linhas em que o consumo não bate com as leituras têm todas `leitura_anterior = -1`.
- **Não é primeira leitura da UC:** dos `N/A`/`NULL` (16.222), só 339 são a primeira leitura da UC. Distribuição uniforme no tempo (~340 por mês).
- **Decisão:** converter as quatro formas em nulo real, criar a flag `leitura_anterior_ausente` e manter o consumo. Não preencher a leitura com valor calculado.
- **Alternativas consideradas:**
  - Coluna `leitura_anterior_recuperada` (leitura atual do mês anterior, mesma UC e mesmo medidor). A regra bate em 100% das 2.069.533 linhas com leitura anterior válida e recuperaria 31.504 das 32.285 ausências (97,6%); nessas, o consumo bate com a leitura recuperada em 99,9% (±1). As 781 restantes são a primeira leitura do medidor. **Não incluída por ora:** o consumo já está preenchido e a Gold usa o consumo; a leitura anterior só serviria para conferência. Pode ser acrescentada depois, sem alterar as outras colunas.
  - Preencher com `atual − consumo`: descartada por ser circular (o valor só reescreve o consumo).
- **Impacto na Gold:** `leitura_anterior` nula em 32.285 linhas, identificadas pela flag.
- **Atenção:** a flag precisa ser calculada antes do cast para número.

#### L4. Consumo negativo por sinal invertido
- **Problema:** consumos negativos em linhas cujas leituras estão coerentes (atual maior que anterior). O medidor não mudou. O consumo tem o valor correto com o sinal trocado.
- **Marca:** todos esses valores estão escritos com `.0` no texto original (ex.: `-85.0`). Todo consumo com `.0` na tabela é negativo.
- **Linhas afetadas:** 1.717 em `limpo` com consumo negativo, sem troca de medidor e com `.0`. Em 1.687, `abs(consumo)` bate com `atual − anterior` (±1). Nas outras 30 (22 + 8), a `leitura_anterior` está ausente, e a confirmação vem da leitura recuperada pelo mês anterior: `abs(consumo)` bate com `atual − leitura recuperada` (±1). Aparece em todos os anos, ~33 a 38 por mês (tabela bruta).
- **Decisão:** `abs(consumo)` + flag `consumo_corrigido`. O valor original fica em `consumo_kwh_original`.
- **Alternativas consideradas:** consumo nulo (perderia um consumo que existe e está confirmado) e recalcular `atual − anterior` (mudaria ~24% das linhas em 1 kWh, por causa do ±1).
- **Impacto na Gold:** 1.717 consumos passam de negativos a positivos, identificados pela flag.
- **Atenção:** o critério do `.0` depende do texto original, então a classificação vem antes do cast. Como validação, a classificação pelo `.0` e a pelo medidor não podem divergir.

#### L5. Consumo negativo por troca de medidor
- **Problema:** em 6.299 linhas o medidor da UC muda em relação ao mês anterior, e a `leitura_anterior` é a última do medidor antigo enquanto a `leitura_atual` é a do medidor novo. A subtração dá negativo e o consumo registrado não tem sentido (ex.: UC100011 em 2025-12: anterior 195.613, atual 4.698, consumo −190.915).
- **Período:** só de 2025-09 a 2026-03 (~900 por mês). Nenhuma troca antes disso.
- **Confirmado no cadastro:** o medidor antigo tem `status = RETIRADO` com `data_retirada` no mesmo mês da troca (100% dos casos), e o medidor novo pertence à mesma UC.
- **Confirmado nas faturas:** usando `leitura_atual` como consumo, o preço implícito fica ~5% acima do preço típico da UC (mediana 1,05, faixa de 1,03 a 1,15, em 6.215 linhas). Indica que a fatura desses meses foi calculada com a leitura atual. Evidência forte, não prova.
- **Decisão:** `consumo = leitura_atual` + flag `troca_medidor`. O valor original fica em `consumo_kwh_original`.
- **Alternativa considerada:** consumo nulo + flag. Descartada porque faria o volume dos meses recentes parecer menor do que foi.
- **Impacto na Gold:** essas linhas caem nos últimos 12 meses, os mesmos que o diretor compara com o primeiro ano. Quem precisar de uma série "pura" pode excluí-las pela flag `troca_medidor`.
- **Atenção:** calcular a troca só depois de remover cópias e órfãs.

#### L6. `data_leitura` em quatro formatos
- **Problema:** `data_leitura` mistura formatos. Em `limpo`:

| Padrão | Formato | Linhas |
|---|---|---|
| `9999-99-99` | `yyyy-MM-dd` | 1.894.056 |
| `99.99.9999` | `dd.MM.yyyy` | 86.433 |
| `99/99/9999` | `dd/MM/yyyy` | 85.936 |
| `99-99-9999` | `MM-dd-yyyy` (**mês primeiro**) | 85.911 |

- **Como foi confirmada a ordem:** comparando o mês de cada data com `mes_referencia`. Os quatro formatos convertem sem falhas e batem em 100% das linhas. Com `dd-MM-yyyy` no padrão com hífen, 49.082 das 85.911 linhas não convertiam e só 3.132 batiam.
- **Risco:** aplicar um formato único converteria datas para o mês errado, sem dar erro.
- **Decisão:** converter cada padrão com o seu formato e gravar como `date`.
- **Impacto na Gold:** `data_leitura` passa a ser `date`. `mes_referencia` já está limpo (todas as linhas seguem `yyyy-MM`) e permanece como texto.

#### L7. Consumo difere de `atual − anterior` em ±1 kWh
- **Observação:** entre os consumos não negativos, 1.616.562 batem exatamente, 262.570 têm diferença de +1 e 262.566 de −1 (~24% das linhas). O ±1 é simétrico e parece arredondamento da origem.
- **Decisão:** **não corrigir.** Usar ±1 como tolerância nas validações da Silver.
- **Alternativa considerada:** recalcular o consumo como `atual − anterior`. Descartada: mudaria ~24% das linhas em 1 kWh, sem garantia de ficar mais correto.
- **Impacto na Gold:** nenhum.

#### Verificado e sem problema
- `tipo_leitura`: sem variações de grafia.
- `mes_referencia`: formato único `yyyy-MM`.
- `id_uc`: todos existem em `unidades_consumidoras`.
- Não há consumo igual a zero.
- Não é virada de mostrador: nas regressões de leitura, a leitura anterior tem mediana ~55 mil (não perto de um teto como 99999).

## `faturas` (F)

Fonte: `bronze.faturas` (`faturas.csv`, separador `;`). 2.184.623 linhas na Bronze, 2.184.621 depois de remover o cabeçalho repetido.
Exploração: `exploracao_faturas.ipynb`.
**Decisões tomadas por Marcela**, responsável pela tabela, com a autonomia combinada com o grupo para as tabelas de cada integrante. Registro em 20/10/2026. As contagens dos itens F3 e F4 são da tabela bruta (incluem as órfãs); as demais estão indicadas em cada item.

### Resumo

| ID | Coluna | Problema | Linhas afetadas | Decisão | Justificativa |
|---|---|---|---|---|---|
| F1 | todas | Linha de cabeçalho repetida como dado | 2 | Remover, antes da deduplicação | Registro inutilizável (nulo estrutural) |
| F2 | id_fatura, id_uc | Órfãs: `FTX...`, `id_uc` de 7 dígitos e UC inexistente | 32.285 (1,5%) | Remover | UC não existe no cadastro; as três condições coincidem em todas. A Bronze guarda as linhas |
| F3 | valor_total | Escrito como moeda (`R$ 100,64`, `R$ 1.234,56`) | 196.622 (9,0%) | Remover `R$` e ponto de milhar, vírgula vira ponto, `decimal(12,2)` | Um cast simples anularia 9% dos totais. Validado: total = energia + tributos em 100% |
| F4 | data_emissao | 4 formatos (mesmo mapeamento de leituras) | 183.361 fora do ISO | Converter cada padrão com o seu formato e gravar como `date` | Confirmado: vencimento = emissão + 12 dias em 100% |
| F5 | data_pagamento | Ausente em 2 formas: nulo real e `9999-12-31` | 175.168 (8,0%) | `9999-12-31` vira nulo; flag `em_aberto` | A sentinela só aparece em faturas EM ABERTO; mesmo padrão de `data_retirada` em `medidores` |

### Detalhes

#### F1. Linhas de cabeçalho repetido
- **Problema:** 2 linhas em que o valor de cada coluna é o nome da própria coluna (`id_fatura = 'id_fatura'`, `data_emissao = 'data_emissao'` e assim por diante). Ambas vêm do `faturas.csv`.
- **Onde mais ocorre:** `unidades_consumidoras` (1 linha, ver U1). Não ocorre em `leituras`, `medidores`, `ocorrencias_rede`, `geracao_distribuida`, `atendimentos` nem `inspecoes`.
- **Decisão:** remover na Silver (nulo estrutural: registro inutilizável), filtrando `id_fatura != 'id_fatura'`. Deve vir **antes** da deduplicação: se deduplicar primeiro, uma das duas linhas sobra.
- **Alternativas consideradas:** corrigir na Bronze, o que evitaria o tratamento em cada Silver. **Descartada após verificação:** o cabeçalho repetido está no arquivo de origem (`faturas.csv`, linhas 1.005.328 e 1.749.118; `unidades_consumidoras.csv`, linha 27.536), não é efeito da leitura. As contagens do arquivo e da Bronze batem. Como a Bronze deve preservar a origem, a remoção fica na Silver. Verificado por Aimê em 21/10/2026.
- **Impacto na Gold:** nenhum (2 linhas sem informação).

#### F2. Faturas órfãs
- **Problema:** 32.285 faturas (1,5%) com as três condições ao mesmo tempo: `id_fatura` fora do padrão `FT` + 9 dígitos (prefixo `FTX`, ex.: `FTX0031810`), `id_uc` com 7 dígitos (ex.: `UC9305662`) e UC inexistente em `unidades_consumidoras`. As outras 2.152.336 faturas estão todas no padrão e com UC existente. Nenhuma fatura tem só uma das três condições.
- **Duplicatas:** 21 pares `(id_uc, mes_referencia)` com mais de uma fatura, todos formados por duas órfãs (42 linhas). Entre as faturas válidas, nenhuma repete UC + mês.
- **Peso em valor:** a soma de `valor_energia` das órfãs é R$ 7.644.280,57, contra R$ 499.862.082,73 das válidas (1,5% do total). O valor médio por fatura é parecido (R$ 236,78 nas órfãs e R$ 232,24 nas válidas).
- **Decisão:** remover. Padrão análogo às leituras órfãs (L2).
- **Alternativa considerada:** quarentena. Descartada pelos mesmos motivos de L2: a Bronze guarda as linhas, e a quarentena só ganharia sentido se o pipeline rodar com dados novos.
- **Impacto na Gold:** a receita total fica ~1,5% menor sem as órfãs. Registrar no dicionário de dados.
- **Não verificado:** se as órfãs de `faturas` e de `leituras` correspondem às mesmas UCs ou meses.

#### F3. `valor_total` escrito como moeda
- **Problema:** `valor_energia` e `tributos` têm formato único (`9.9`, ponto decimal). `valor_total` tem três:

| Formato | Exemplo | Linhas |
|---|---|---|
| `9.9` | `102.57` | 1.987.999 |
| `R$ 9,9` | `R$ 100,64` | 188.571 |
| `R$ 9.9,9` | `R$ 1.234,56` (ponto de milhar) | 8.051 |

- **Risco:** um `cast` simples anularia 196.622 faturas (9,0%), e a receita ficaria subestimada em cerca de 9%.
- **Decisão:** remover `R$` e o ponto de milhar, trocar a vírgula decimal por ponto e converter para `decimal(12,2)`.
- **Alternativa considerada:** recalcular o total como `valor_energia + tributos`. Descartada por ser desnecessária: a normalização converte todos os totais e bate com a soma.
- **Validado:** nas 2.152.336 faturas válidas, todos os totais convertem e `valor_total = valor_energia + tributos` em 100% (diferença zero).
- **Impacto na Gold:** `valor_total` passa a ser numérico em todas as linhas.

#### F4. `data_emissao` em quatro formatos
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
- **Decisão:** converter cada padrão com o seu formato e gravar como `date`.
- **Impacto na Gold:** `data_emissao` passa a ser `date`. `data_vencimento` (`yyyy-MM-dd`) e `mes_referencia` (`yyyy-MM`) têm formato único.

#### F5. `data_pagamento` ausente em duas formas
- **Problema:** `data_pagamento` ausente aparece como nulo real (113.835) e como a data sentinela `9999-12-31` (61.333). Total: 175.168 faturas em aberto (8,0%).
- **Confirmado:** todas as 113.835 com nulo real e todas as 61.333 com `9999-12-31` estão `EM ABERTO`. Todas as 2.009.453 `PAGA` têm data real. Distribuição regular: ~1.275 por mês com a sentinela, em todos os anos.
- **Decisão:** converter `9999-12-31` em nulo real e derivar a flag `em_aberto`. Isso evita que contas como "dias entre vencimento e pagamento" usem o ano 9999.
- **Alternativa considerada:** manter a sentinela. Descartada: qualquer média ou diferença de datas ficaria distorcida.
- **Impacto na Gold:** a lista de "faturas em aberto" (tela do atendente) deve usar o `status` ou a flag `em_aberto`, e não a presença da data.
- **Mesmo padrão de:** `leitura_anterior` (4 formas de ausência) e `data_retirada` em `medidores` (`9999-12-31`).

#### Verificado e sem problema
- Sem cópias exatas: 2.184.621 linhas e 2.184.621 `id_fatura` distintos.
- `status`: só `PAGA` e `EM ABERTO`, sem variações de grafia. Em aberto e pago têm a mesma última competência (2026-06).
- Datas: 0 emissões depois do vencimento e 0 pagamentos antes da emissão, depois de converter cada formato.
- **Uma fatura por leitura:** depois de remover as órfãs das duas tabelas, `faturas` e `leituras` têm exatamente os mesmos 2.152.336 pares `(id_uc, mes_referencia)`: 0 faturas sem leitura e 0 leituras sem fatura.

---

# Bloco C — Atendimento e Inspeções (Maria)

## `atendimentos` (A)

### Resumo

| ID | Coluna | Problema | Linhas afetadas | Decisão | Justificativa |
|---|---|---|---|---|---|
| | | | | | |

### A investigar

| Coluna | Observação |
|---|---|
| data_fechamento | Procurar a data sentinela `9999-12-31` (convenção adotada em faturas e medidores: vira nulo) |
| id_uc | Procurar órfãs com id fora do padrão (`UC` com 7 dígitos) |

### Verificado e sem problema
- Sem linha de cabeçalho repetida (`protocolo = 'protocolo'`: 0 linhas na Bronze).

## `inspecoes` (I)

### Resumo

| ID | Coluna | Problema | Linhas afetadas | Decisão | Justificativa |
|---|---|---|---|---|---|
| | | | | | |

### A investigar

| Coluna | Observação |
|---|---|
| data | Formatos misturados (`2025-08-01`, `14.08.2025`, `09-01-2025`) |
| resultado | Mesmo valor escrito de formas diferentes (`CONFIRMADA`, `IRREGULARIDADE CONFIRMADA`, `irregularidade confirmada`) |
| kwh_recuperado | Decimal com vírgula e com ponto na mesma coluna (`1313,70` e `838.10`) |
| tipo_irregularidade | `"-"` usado no lugar de nulo |
| inspetor | Espaços sobrando (`" INSP-006"`) |
| id_uc | Procurar órfãs com id fora do padrão (`UC` com 7 dígitos) |

### Verificado e sem problema
- Sem linha de cabeçalho repetida (`id_inspecao = 'id_inspecao'`: 0 linhas na Bronze, nas 3 abas).

## Cruzamentos entre tabelas (X)

### Resumo

| ID | Tabelas | Problema | Linhas afetadas | Decisão | Justificativa |
|---|---|---|---|---|---|
| | | | | | |

### A investigar

| Tabelas | Observação |
|---|---|
| unidades_consumidoras / medidores / leituras | **200 UCs fantasmas:** status `ATIVA` no cadastro, sem medidor ativo e sem nenhuma leitura. As outras 45.000 UCs têm exatamente 1 medidor ativo. Decidir em grupo: manter com flag (ex.: `possui_medidor_ativo`) ou excluir das métricas. Possível erro de cadastro ou UC ligada sem medição (interesse para a fila de perdas) |
| faturas / leituras | Verificar se as órfãs das duas tabelas correspondem às mesmas UCs ou meses (pendência de F2) |

### Verificado e sem problema
- **medidores / leituras:** depois de deduplicar `medidores`, todos os 51.299 ids continuam existindo e todos aparecem em `silver.leituras`. A regra de órfãs de L2 não muda.
