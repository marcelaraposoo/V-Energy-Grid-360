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
| `A` | atendimentos | C | Marcela |
| `I` | inspecoes | C | Aimê |
| `X` | cruzamentos entre tabelas | C | Aimê e Marcela |

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

# Bloco C — Atendimento (Marcela) e Inspeções (Aimê)

## `atendimentos` (A)

Fonte: `bronze.atendimentos` (`atendimentos.json`). 318.871 chamados e 636.857 tratativas na Bronze **e na Silver** (nenhum registro removido).
Exploração: `exploracao_atendimentos.ipynb`. Silver: `02_silver_atendimentos.ipynb` (grava `silver.atendimentos` e `silver.tratativas_atendimento`). Gold: `03_gold_fato_atendimento.ipynb` (tabela B1 do contrato).
**Decisões tomadas por Marcela**, responsável pela tabela (assumida depois da desistência da responsável original), com a autonomia combinada com o grupo para as tabelas de cada integrante. Registro em 27/10/2026.

**É a tabela mais limpa do projeto:** sem cópias, órfãs, cabeçalho repetido, datas misturadas, sentinelas nem códigos de ausência. Os itens abaixo são decisões de modelagem e de interpretação. Cabeçalho repetido, cópias e UC inexistente (0 casos) **não têm tratamento** na Silver: ficam só como checagens, que falham e impedem a gravação se aparecerem numa carga futura.

### Resumo

| ID | Coluna | Problema | Linhas afetadas | Decisão | Justificativa |
|---|---|---|---|---|---|
| A1 | nota_satisfacao | Nula: chamado não avaliado | 9.566 (3,0%) | Manter nula; converter para `decimal(3,1)` | Nulo de negócio (todos os chamados estão fechados). Preencher inventaria uma avaliação |
| A2 | nota_satisfacao | Acúmulo no teto: 6.160 notas em 5,0 contra 4.363 em 4,9 | 6.160 | Não alterar; documentar como hipótese | Compatível com notas acima de 5 cortadas em 5,0, mas sem evidência para corrigir |
| A3 | historico | Lista aninhada de tratativas dentro do chamado | 318.871 chamados / 636.857 tratativas | Abrir em `silver.tratativas_atendimento` (chave `(protocolo, sequencia)`); `qtd_tratativas` no chamado | Gold, portal e agente de SQL não leem listas. `sequencia` = posição + 1 e datas em ordem em 100% |
| A4 | data_abertura, data_fechamento, historico.data | Datas em texto: chamado com espaço (`yyyy-MM-dd HH:mm:ss`), tratativa com `T` | 318.871 / 636.857 | `try_to_timestamp` com o formato de cada coluna; guardar como `timestamp` | Formato único, sem ambiguidade dia/mês. Gabarito do histórico: abertura <= primeira tratativa e fechamento = última tratativa em 100% |
| A5 | historico.acao | A última ação **não indica o status** do chamado | 318.871 | Não derivar status de `ultima_acao`; o estado vem de `aberto` | Todos os chamados estão fechados, mas a última ação se divide entre as cinco ações |
| A6 | data_abertura | **Pico de julho de 2025:** 18.061 chamados (2,8× o normal de ~6.400) | ~11.660 acima do normal | Manter tudo; documentar como evento de rede | Dado consistente (protocolos contíguos, em todos os assuntos, canais e dias) e coerente com o evento climático na rede no mesmo mês |
| A7 | data_fechamento | Nulo significaria chamado aberto; `9999` seria sentinela | 0 hoje | Flag `aberto` (constante falsa hoje); sentinela `9999` vira nulo | Convenção do grupo; protege cargas futuras |

### Detalhes

#### A1. Nota de satisfação nula
- **Problema:** 9.566 chamados (3,0%) sem nota. Todos são de chamados fechados, então o nulo significa "o cliente não avaliou". A proporção é a mesma em julho de 2025 (3,13%) e nos demais meses (2,99%).
- **Decisão:** manter nulo e converter o texto para `decimal(3,1)` com `try_cast`. A faixa observada vai de 1,3 a 5,0, com média 4,043 e 309.305 notas preenchidas.
- **Alternativas consideradas:** preencher com a média (inventaria avaliação) ou com zero (puxaria a média para baixo).
- **Casas decimais:** a nota tem no máximo 1 casa decimal na origem (conferido na execução da Silver), então o cast não arredonda nada. A checagem da Silver exige isso.
- **Impacto na Gold:** `nota_satisfacao_media` é a média das notas **preenchidas**. A escala é de 1 a 5, fechada no contrato v4.

#### A2. Acúmulo de notas em 5,0
- **Observação:** a curva das notas desce de 4,1 a 4,9 (4.363 chamados em 4,9), mas há 6.160 em 5,0. Compatível com notas acima de 5 cortadas no teto (**hipótese**).
- **Decisão:** manter como veio. Sem a origem do sistema, qualquer correção seria inventar dado.
- **Impacto na Gold:** registrar a hipótese no dicionário de dados, junto da definição de `nota_satisfacao_media`.

#### A3. `historico` aberto em tabela
- **Estrutura:** `silver.atendimentos` (1 linha por chamado) e `silver.tratativas_atendimento` (1 linha por tratativa: `protocolo`, `sequencia`, `acao`, `canal`, `data_tratativa`, `source_file`).
- **Tamanho do histórico:** 1, 2 ou 3 tratativas por chamado, em partes iguais (106.717, 106.322 e 105.832 chamados), somando 636.857.
- **Alternativa considerada:** manter a lista na Silver. Descartada: a Gold, o portal (SQLite ou PostgreSQL) e o agente de SQL não leem listas. A Bronze continua com a lista original.
- **Impacto na Gold:** `qtd_tratativas` vem pronta no chamado; `ultima_acao` sai da maior `sequencia` de `silver.tratativas_atendimento`. As tratativas **não** entram na Gold (decisão da v4 do contrato).

#### A4. Datas
- **Formatos:** `yyyy-MM-dd HH:mm:ss` em `data_abertura` e `data_fechamento` (318.871 linhas cada) e `yyyy-MM-dd'T'HH:mm:ss` na data de cada tratativa (636.857). Nenhum valor começa com `9999`.
- **Por que não há risco dia/mês:** só existe o padrão ISO. O que valida a conversão é o gabarito do histórico (abertura <= primeira tratativa, fechamento = última tratativa), que vale em 318.871 de 318.871 chamados. Nenhuma tratativa fica fora do intervalo abertura–fechamento.
- **Período:** aberturas de 2022-07-01 a 2026-06-30; os fechamentos chegam a 2026-07-10 (chamados abertos no fim de junho).
- **Tempo de resolução (execução da Silver):** de 1,00 h a 719,00 h, média de 133,6 h, nenhum valor negativo. A média bate com a composição conhecida (~361 h em julho de 2025 e ~120 h nos demais meses).
- **Decisão:** `timestamp` na Silver, porque a hora é necessária para `tempo_resolucao_horas`.
- **Impacto na Gold:** o contrato (v3 em diante) pede **data e hora** em `data_hora_abertura` e `data_hora_fechamento`: a Gold **não** converte para `date` e só renomeia as colunas. `tempo_resolucao_horas` já vem calculado na Silver (horas, 2 casas). Os horários são locais, sem fuso (o `Z` que o Databricks exibe é só a exibição).

#### A5. A última ação não é o status
- **Observação:** todos os chamados estão fechados, mas a última ação registrada se divide entre DESPACHO (64.257), RETORNO AO CLIENTE (63.987), ABERTURA (63.903), ENCERRAMENTO (63.432) e ANALISE (63.292). O histórico parece uma amostra de ações, e não um processo completo.
- **Amostra da execução da Silver:** `AT000000020` tem uma única tratativa, `RETORNO AO CLIENTE`; `AT000000026` começa em `ENCERRAMENTO` e termina em `DESPACHO`. A primeira tratativa também nem sempre é `ABERTURA`.
- **Decisão:** o estado do chamado vem de `aberto` (data de fechamento nula). `ultima_acao` não deve ser lida como situação.
- **Impacto na Gold e no agente:** `ultima_acao` é a **última ação registrada**, e não a situação do chamado. Exemplo: "quantos chamados foram encerrados?" **não** se responde com `ultima_acao = 'ENCERRAMENTO'` (63.432 chamados), e sim com todos os chamados fechados (`aberto = false`: 318.871). Entra no dicionário de dados e no catálogo de métricas da IA.

#### A6. Pico de chamados em julho de 2025
- **Problema:** 18.061 chamados em 2025-07, contra ~6.400 por mês (de 6.237 a 6.624 nos outros 47 meses). O aumento é geral: todos os assuntos sobem de 2,67× a 3,06×, todos os canais de 2,79× a 2,88×, os 31 dias têm volume parecido e há 14.828 UCs distintas.
- **Por que parece um evento real, e não erro:** os protocolos são contíguos (230.048 a 248.108, exatamente 18.061 números seguidos); as ocorrências de rede do mesmo mês são 5,3× o normal (17.844 contra ~3.370), 97% de causa climática e 72% em três alimentadores (`ALM-REC-008`, `ALM-SAO-004` e `ALM-JAB-004`); o tempo até fechar sobe de ~120 h para ~361 h e a nota média cai de ~4,10 para ~3,11.
- **O consumo de julho é normal** (13,49 milhões de kWh, 3,2% abaixo de julho de 2024), então o evento **não explica a queda de volume** do diagnóstico.
- **Decisão:** manter os 18.061 chamados. Descartar apagaria um fato do negócio.
- **Impacto na Gold e no diagnóstico:** `qtd_atendimentos` de 2025-07 fica ~2,8× o normal e puxa a comparação entre períodos: de 76.561 chamados no primeiro ano para 88.823 nos últimos 12 meses (+16%). Sem o excesso de julho (~11.660 chamados), a alta seria de ~0,8%. Quem consome os KPIs precisa dessa explicação (dicionário de dados e insights de IA).

#### A7. Chamado aberto e sentinela
- **Regra:** `data_fechamento` nula significa chamado aberto, e `aberto = data_fechamento IS NULL`. Qualquer `data_fechamento` que comece com `9999` viraria nulo (convenção do grupo).
- **Hoje:** 0 chamados abertos e 0 sentinelas, então `aberto` é falsa em todas as linhas. A checagem "nenhum chamado aberto" é uma proteção desta extração: se falhar, conferir antes se a conversão da data quebrou.
- **Impacto na Gold:** `aberto` é falsa em todos os chamados desta base: **não há chamados em aberto**. O histórico de chamados de cada UC (todos os que ela já abriu) aparece normalmente na visão 360.

### Verificado e sem problema
- **Cabeçalho repetido** (`protocolo = 'protocolo'`): 0. **Cópias** por `protocolo`: 0. Protocolo nulo ou fora do padrão `AT` + 9 dígitos: 0. Chamados repetidos com protocolos diferentes (mesma UC, abertura e assunto): 0.
- **UCs:** todos os chamados têm `id_uc` no padrão `UC` + 6 dígitos, existente no cadastro e com leitura. Nenhum chamado nas 200 UCs de teste. 44.940 das 45.000 UCs têm ao menos um chamado (média de 7,1 por UC, máximo 20).
- **Ausência:** nenhuma coluna usa `N/A`, `NULL`, `-1`, vazio ou `9999-12-31`. O `historico` nunca é nulo nem vazio.
- **Categorias:** 5 canais, 6 assuntos, 15 subassuntos (17 pares assunto × subassunto) e 5 ações, sem variações de grafia (reconfirmado na execução da Silver). A Silver aplica `upper(trim)` e checa o domínio.
- **Histórico:** `sequencia` sempre numérica e igual à posição + 1; datas em ordem crescente; nenhuma tratativa antes da abertura nem depois do fechamento; os canais das tratativas são os mesmos 5 do chamado.
- **Resposta à pendência de "A investigar":** `data_fechamento` não tem sentinela `9999-12-31` e `id_uc` não tem órfãs com 7 dígitos.


---
## `inspecoes` (I)

Fonte: `bronze.inspecoes` (`inspecoes.xlsx`, 3 abas unidas na Bronze com a coluna `aba_origem`). 1.389 linhas na Bronze e na Silver (nenhuma removida): `ago-set` 511, `out-nov` 495 e `dez` 383.
Exploração: `exploracao_inspecoes.ipynb`. Silver: `02_silver_inspecoes.ipynb`.
**Decisões tomadas por Aimê**, responsável pela tabela, com a autonomia combinada com o grupo. Registro em 26/10/2026.

### Resumo

| ID | Coluna | Problema | Linhas afetadas | Decisão | Justificativa |
|---|---|---|---|---|---|
| I1 | data | 4 formatos: ISO (1.256), `MM-dd-yyyy` (46), `dd.MM.yyyy` (44) e `dd/MM/yyyy` (43) | 133 fora do ISO | Converter cada padrão com o seu formato e gravar como `date` | A convenção do projeto converte 100%; a ordem trocada deixa sem converter de 26 a 33 linhas em cada padrão |
| I2 | data | Data fora do período da aba | 107 (7,7%), todas na aba `dez` | Manter a data + flag `data_fora_da_aba` | A aba indica o mês de lançamento: são inspeções de ago a nov lançadas em dezembro. Nenhuma ordem de leitura as coloca em dezembro |
| I3 | resultado | 8 grafias (4 textos com variações de maiúsculas) para 2 significados: `IRREGULARIDADE CONFIRMADA`, `CONFIRMADA`, `SEM IRREGULARIDADE` e `NADA CONSTA` | 164 fora dos 2 valores padrão | Mapa explícito, valor a valor, para `IRREGULARIDADE CONFIRMADA` e `SEM IRREGULARIDADE` + flag `irregularidade_confirmada` | `NADA CONSTA` tem tipo vazio e energia zero, igual a `SEM IRREGULARIDADE`. O mapa explícito evita que "NÃO CONFIRMADA" vire confirmada |
| I4 | tipo_irregularidade | Ausente em 2 formas: nulo real (441) e `-` (77) | 518 | Converter para nulo real | São exatamente as 518 inspeções sem irregularidade |
| I5 | kwh_recuperado | Vírgula decimal (`1313,70`) misturada com ponto (`838.10`) | 125 (9,0%) | Trocar vírgula por ponto e converter para `decimal(12,2)` | Um `cast` simples anularia esses valores |

### Detalhes

#### I2. Data fora do período da aba
- **Gabarito:** cada aba corresponde a um período (`ago-set`, `out-nov`, `dez`). As 1.256 datas ISO caem todas na própria aba.
- **Problema:** 107 datas não ISO estão na aba `dez`, mas são de agosto (24), setembro (23), outubro (34) e novembro (26). Nenhuma ordem dia/mês as coloca em dezembro.
- **Interpretação:** a aba `dez` recebeu também inspeções feitas nos meses anteriores e lançadas em dezembro. A data registrada é a da inspeção.
- **Decisão:** manter a data e marcar `data_fora_da_aba = true`. A checagem da Silver garante que isso só acontece na aba `dez`.
- **Alternativa considerada:** trocar a data para dezembro. Descartada: a data escrita é a da inspeção, e nenhuma leitura do formato a coloca em dezembro.
- **Impacto na Gold:** análises por mês usam `data_inspecao`, e não `aba_origem`.

#### I3. Mapa do resultado

| Resultado na Silver | Grafias na Bronze (linhas) |
|---|---|
| `IRREGULARIDADE CONFIRMADA` (871) | `IRREGULARIDADE CONFIRMADA` (777), `Irregularidade Confirmada` (32), `irregularidade confirmada` (27), `CONFIRMADA` (35) |
| `SEM IRREGULARIDADE` (518) | `SEM IRREGULARIDADE` (448), `sem irregularidade` (33), `Sem Irregularidade` (15), `NADA CONSTA` (22) |

- **Taxa de acerto:** 871 de 1.389 = **62,7%**, compatível com o "pouco mais da metade" do Rafael. É a referência para calibrar a `fila_inspecao`.
- **Por que mapa explícito:** uma regra por expressão regular (ex.: "contém CONFIRMADA") marcaria `IRREGULARIDADE NAO CONFIRMADA` como confirmada. Com o mapa, uma grafia nova vira nulo e a checagem falha.

### Verificado e sem problema
- Sem cabeçalho repetido e sem cópias: 1.389 linhas e 1.389 `id_inspecao` distintos; a mesma inspeção não aparece em duas abas.
- Todos os `id_uc` no padrão e existentes na Silver de UCs; nenhuma inspeção em UC de teste nem órfã com 7 dígitos.
- 40 inspetores, todos no padrão `INSP-000`. Alguns vêm com espaços sobrando (`" INSP-006"`); a Silver aplica `upper(trim)`, sem mudar nenhum código.
- **Tipo preenchido se e somente se a irregularidade foi confirmada.** 5 tipos sem variações: `DESVIO DIRETO` (182), `BY-PASS` (181), `MEDIDOR ADULTERADO` (180), `LACRE VIOLADO` (164) e `LIGACAO CLANDESTINA` (164).
- **Energia recuperada positiva em 100% das confirmadas** (mediana de ~1.072 kWh; máximo de 15.609) **e zero em 100% das sem irregularidade.**
- Todas as inspeções entre agosto e dezembro de 2025.
