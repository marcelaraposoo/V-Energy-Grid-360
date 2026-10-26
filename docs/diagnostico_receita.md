# Diagnóstico da variação de receita · V-Energy Grid 360

**Versão 1 · frente de Dados.** Responde à pergunta do Henrique Duarte (Diretor Comercial) com os dados limpos das Silvers. Os números saem do notebook `analise_reconciliacao_diretor.ipynb`; cada decisão de limpeza que os afeta está no `data_quality_log.md`.

> "Comparando os últimos 12 meses com o primeiro ano da nossa base, o volume de energia faturada caiu quase 4% e a receita subiu só 8%. Ninguém nesta mesa sabe explicar por quê."

**Convenções.** Primeiro ano (P0) = competências `2022-07` a `2023-06`. Últimos 12 meses (P1) = `2025-07` a `2026-06`. **Volume** = soma de `consumo_kwh` (`silver.leituras`; a fatura não tem kWh). **Receita** = soma de `valor_energia` (`silver.faturas`, sem tributos). Tudo aqui é **associação medida nos dados**; as hipóteses estão marcadas.

---

## 1. Resposta em cinco pontos

1. **Os dados reproduzem os números do diretor:** receita **+8,00%** e volume **−3,95%**.
2. **A receita subiu porque o preço médio por kWh subiu 12,45%** (tarifa e bandeira tarifária), o que mais do que compensou o volume perdido: efeito-preço **+R$ 14,09 mi** e efeito-volume **−R$ 4,66 mi**, que somam a variação de **+R$ 9,43 mi**.
3. **A queda de volume vem das unidades com painel solar** (geração distribuída). As 3.510 UCs com GD (7,8% das UCs) consumiram **61% menos** da rede (−11,2 milhões de kWh, ≈ **R$ 5,8 milhões** de receita de energia), enquanto **todas as demais cresceram 1,1%**.
4. **A bandeira tarifária explica parte do preço:** no primeiro ano 100% das faturas eram Verde, e nos últimos 12 meses só 33%. Sem a bandeira, a receita teria subido cerca de 6%, e não 8% (estimativa).
5. **Dois meses fora da tendência** (novembro de 2025 e fevereiro de 2026) escondem parte da queda: se seguissem os outros dez meses, o volume teria caído ~6%, e não ~4% (hipótese).

---

## 2. Os números reproduzem o que o diretor viu

| Medida | P0 | P1 | Variação | Dito pelo diretor |
|---|---|---|---|---|
| Volume (kWh) | 227.052.927 | 218.079.054 | **−3,95%** | "quase −4%" |
| Receita de energia | R$ 117,83 mi | R$ 127,26 mi | **+8,00%** | "+8%" |
| Receita total (com tributos) | R$ 157,11 mi | R$ 169,68 mi | **+8,00%** | |

- `valor_energia` e `valor_total` dão a **mesma** variação, então a definição de receita não muda o diagnóstico.
- O volume só fecha o "quase −4%" com o tratamento das trocas de medidor (`consumo = leitura_atual`). Sem tratar, o consumo original daria −174%; deixando as trocas nulas, −5,12% (e com menos linhas).
- **Base de comparação:** as Silvers removem 32.285 faturas órfãs (UCs que não existem no cadastro). Com elas, a receita de energia variaria **+7,90%**, em vez de +8,00%. As duas arredondam para 8%.
- A base de clientes **não encolheu**: as UCs com fatura foram de 44.741 para 45.000 (+0,6%). Cada UC consome menos.

---

## 3. Receita: preço × volume

Com preço médio `P = receita / volume`: `efeito_volume = (V1 − V0) × P0` e `efeito_preço = (P1 − P0) × V1`. Os dois somam exatamente a variação.

| | Valor | % da variação |
|---|---|---|
| Preço médio P0 → P1 | R$ 0,5190 → R$ 0,5836 por kWh (**+12,45%**) | |
| Variação da receita de energia | **+R$ 9.432.201** | 100% |
| Efeito-preço | **+R$ 14.089.243** | 149,4% |
| Efeito-volume | **−R$ 4.657.042** | −49,4% |

**Leitura:** o volume perdido custou R$ 4,66 mi, e o preço trouxe R$ 14,09 mi. Sem o aumento do preço, a receita teria **caído** cerca de 4%.

---

## 4. O preço: tarifa e bandeira

| Período | Bandeira | % das faturas | Preço mediano (R$/kWh) |
|---|---|---|---|
| P0 | Verde | **100%** | 0,5309 |
| P1 | Verde | 33,2% | 0,5857 |
| P1 | Amarela | 25,1% | 0,6045 |
| P1 | Vermelha P1 | 25,0% | 0,6234 |
| P1 | Vermelha P2 | 16,7% | 0,6577 |

- O preço mediano da **Verde** subiu 10,3% (R$ 0,5309 → R$ 0,5857), perto dos 10,5% de reajuste da tarifa residencial. Esse é o efeito da **tarifa**.
- O restante do aumento do preço médio (+12,45%) vem da **bandeira**: nos últimos 12 meses, 67% das faturas pagam adicional, contra 0% no primeiro ano. No residencial, o preço por kWh subiu 13,0% (contra 10,5% de tarifa), o que deixa ~2,3% para a bandeira.
- **Conta de ordem de grandeza:** com a tarifa (+10,3%) e o volume (−3,95%), a receita teria subido ≈ 6%. A bandeira responde pelos ≈ 2 pontos percentuais restantes até os 8%.
- **Método e limite:** as faturas trazem só o **nome** da bandeira, e não o valor do adicional. O efeito é **estimado** pelo preço implícito (`valor_energia ÷ consumo_kwh`), tomando a Verde como referência. A mediana mistura as classes, e os 10,5% valem só para a residencial.

---

## 5. O volume: onde e por quê

### 5.1 Onde: comercial e residencial

| Classe | Volume (P1 vs P0) | Preço por kWh | Receita | Efeito-volume |
|---|---|---|---|---|
| Comercial | **−10,2%** | +18,8% | +6,7% | **−R$ 2,98 mi** |
| Residencial | **−5,4%** | +13,0% | +7,0% | **−R$ 2,35 mi** |
| Industrial | +0,6% | +8,0% | +8,7% | +R$ 0,24 mi |
| Rural | +2,5% | +26,0% | +29,1% | +R$ 0,03 mi |
| Poder público | +2% a +3% | +19% | +22% | +R$ 0,06 mi |

A perda de volume está em duas classes (−R$ 5,32 mi), e as outras três compensam +R$ 0,33 mi. Os reajustes das outras classes não são conhecidos (o case cita só o residencial).

### 5.2 Por quê: geração distribuída

O glossário do case diz que a energia gerada pelo painel solar é **abatida do consumo faturado**. As UCs com GD explicam a queda:

| Grupo | P0 | P1 | Variação |
|---|---|---|---|
| UCs **com** GD (3.510) | 18,30 mi kWh | 7,10 mi kWh | **−61,2%** |
| UCs **sem** GD | 208,75 mi kWh | 210,98 mi kWh | **+1,1%** |
| Total | 227,05 mi kWh | 218,08 mi kWh | −3,95% |

- Por classe, as UCs com GD caem **−61,4% no residencial** e **−60,9% no comercial**. As demais ficam estáveis: residencial sem GD +3,0%, industrial +0,6%, rural +2,5%, poder público +2,4%, comercial sem GD −1,3%. As três classes que não têm GD (industrial, rural e poder público) são as que não caíram.
- As UCs com GD **perdem mais do que a queda total** (−11,2 mi kWh contra −8,97 mi): o resto da base cresceu +2,2 mi kWh. **Sem os painéis, o volume teria subido ~1%.**
- **Em reais:** o efeito-volume de −R$ 4,66 mi se divide em **−R$ 5,81 mi nas UCs com GD** (a R$ 0,519/kWh, o preço do primeiro ano) e **+R$ 1,15 mi nas demais**. A R$ 0,584/kWh, o preço atual, a perda das UCs com GD seria de R$ 6,5 mi.
- **Quem instala painel já consumia mais que a média.** No primeiro ano, antes de qualquer painel, as residências que depois instalaram consumiam ~282 kWh por mês, contra ~169 das demais; no comercial, ~1.678 contra ~814 (contas aproximadas). Isso amplifica o impacto na receita.

### 5.3 O antes e depois da conexão

Alinhando cada UC com GD pela data de conexão (mês 0), o consumo médio:

| Meses relativos à conexão | Consumo médio (kWh por UC e mês) |
|---|---|
| −12 a −1 | de 415 a 461 (média ~438) |
| 0 (mês da conexão) | 292 |
| +1 a +12 | de 128 a 143 (média ~135) |

O consumo **cai ~69% logo no mês seguinte à conexão** e não volta. O padrão (estável antes, queda brusca depois, na mesma UC) é o que se esperaria se o painel abatesse o consumo faturado, e indica que o `consumo_kwh` já vem **líquido da GD**. Ainda é uma associação: nenhum campo confirma a causa. Limites: a estação do ano mexe no consumo (as conexões acontecem em meses diferentes, o que dilui o efeito sem eliminá-lo), e o número de UCs por ponto cai de ~3.500 para 2.592 no mês +12.

---

## 6. Fatores que atrapalham a leitura

**Meses atípicos: novembro de 2025 e fevereiro de 2026.** Comparando cada mês com o mesmo mês do ano anterior, dez dos doze meses de P1 variam de −1,2% a −3,6% (média −2,94%). Novembro (**+8,5%**) e fevereiro (**+8,0%**) destoam, **em todas as classes** (residencial +14%, poder público +11%, rural +9%, comercial +5%, industrial +4%), e nesses meses as ocorrências de rede também têm um pico menor (~1,6× o normal, em todas as causas). Se os dois meses seguissem a tendência dos outros dez, o consumo de P1 seria de ~213,4 milhões de kWh, e a queda sobre o primeiro ano seria de **~−6%**. Isso supõe que os dois meses "deveriam" ter caído como os demais. A causa (calor? outra?) **não está nos dados**.

**Evento de rede em julho de 2025.** Nesse mês, as ocorrências de rede foram 5,3× o normal (17.844 contra ~3.370), 97% com causa climática e 72% em três alimentadores (`ALM-REC-008`, `ALM-SAO-004`, `ALM-JAB-004`). Os chamados do call center foram 2,8× o normal (18.061), o tempo até fechar subiu de 120 para 361 horas e a nota caiu de 4,10 para 3,11. O **consumo de julho é normal**, então o evento não explica a queda de volume. Ele explica a alta de 16% nos chamados entre os dois períodos: sem esse mês, a alta seria de ~0,8%.

**Troca de medidor.** São 6.299 UC-meses (1,17% do P1), entre setembro de 2025 e março de 2026. O consumo desses meses é a `leitura_atual` (a Silver). A escolha pouco muda o consumo por UC (−4,58% com a leitura atual contra −4,62% com consumo nulo), mas é a única que reproduz o −4% no total.

**Sazonalidade.** O consumo é forte no verão (janeiro e fevereiro, ~22 mi kWh) e fraco no inverno (julho e agosto, ~14 mi). Só se comparam meses iguais entre anos, ou períodos de 12 meses.

---

## 7. Recomendações (a validar com a V-Energy)

São **propostas para a diretoria avaliar**, com a ordem de grandeza que os dados permitem. Não foram validadas com as áreas regulatória e tarifária.

| # | Proposta | Ordem de grandeza |
|---|---|---|
| 1 | **Tratar a geração distribuída como fator estrutural de volume.** Incluir as UCs com GD e o consumo líquido nos indicadores mensais e no planejamento de receita. | A perda já materializada é de **R$ 5,8 a 6,5 mi por ano** de receita de energia (~5% da receita de energia de P1). Cada UC que instala painel reduz ~300 kWh por mês, ≈ **R$ 2 mil por ano** (mistura residencial e comercial). |
| 2 | **Projetar o ritmo de adoção.** O padrão de conexões sugere ~860 UCs conectadas em 12 meses (estimativa, a partir das UCs por mês relativo). Mantido o ritmo e o perfil, cada ano adicionaria ≈ **R$ 1,8 mi** de perda. | ≈ R$ 1,8 mi por ano a cada ano de adoção (≈ R$ 2 mi por mil UCs). Premissa: mesmo perfil e mesmo preço. |
| 3 | **Avaliar, com a área regulatória, a política de preço para clientes com GD** (por exemplo, um componente fixo ou de disponibilidade), já que a receita de uma UC com painel cai mesmo com a tarifa maior. | Parte dos R$ 6 mi por ano; depende de regra regulatória (não quantificado). |
| 4 | **Separar tarifa e bandeira nos relatórios comerciais.** A bandeira é exógena e volátil, e responde por ~2 pontos percentuais dos 8%. Sem ela, a receita teria subido ~6%. | ≈ 2 pp da variação (estimado). |
| 5 | **Investigar novembro de 2025 e fevereiro de 2026** (consumo +8% contra −3% nos outros meses): se for clima, a receita é sensível a ele, e a previsão deve considerar isso. | ≈ 4,7 mi kWh em dois meses, ≈ **R$ 2,7 mi** de energia. |
| 6 | **Reconciliar com a V-Energy as 32.285 faturas** ligadas a UCs que não existem no cadastro (nem em nenhuma outra tabela). Parecem registros espúrios, mas só a V-Energy confirma. | **R$ 7,64 mi** em energia (1,5% do total). |
| 7 | **Revisar a resposta a eventos climáticos** (julho de 2025: tempo de atendimento 3× e nota −1,0 ponto). | Qualidade do serviço, não receita. |

---

## 8. Limites e o que não sabemos

- **A causa da queda é uma associação.** A GD concentra a queda e o consumo cai na conexão, mas nenhum campo diz que foi o painel. A geração abatida do consumo faturado é o que o case descreve, e o padrão combina.
- **Município e bairro ainda não foram analisados** (dependem da Silver de UCs). A pergunta "qual bairro mais perdeu volume residencial?" fica em aberto.
- **Reajuste das outras classes** (comercial +18,8%, rural +26%) não é conhecido: o case cita só o residencial.
- **A causa dos meses atípicos** (nov/2025 e fev/2026) e do evento de julho de 2025 não está nos dados.
- **O "+8%" do diretor aceita as duas bases** (com e sem as faturas órfãs: +7,90% e +8,00%). O +8,00% exato na base limpa sugere que ela é a referência do case, mas não prova.
- As contas de ordem de grandeza (R$ 2 mil por UC, R$ 1,8 mi por ano, 6% sem bandeira, −6% sem os meses atípicos) são **estimativas** feitas a partir das tabelas deste documento, com as premissas indicadas.

---

## 9. Decisões de limpeza que afetam estes números

| Decisão (item do `data_quality_log.md`) | Efeito nos números |
|---|---|
| Faturas órfãs removidas (**F2**, 32.285) e leituras órfãs removidas (**L2**, 8.609) | Receita +8,00% (com as faturas órfãs, +7,90%). Uma fatura para cada leitura. |
| Troca de medidor: `consumo = leitura_atual` (**L5**, 6.299) | Reproduz o −3,95% de volume. Sem o tratamento, o consumo original dá −174%. |
| Sinal invertido: `abs(consumo)` (**L4**, 1.717) | Corrige consumos negativos; sem isso o volume sai subestimado. |
| `valor_total` como moeda normalizado (**F3**, 196.622) | Sem a normalização, ~9% dos totais seriam nulos. O diagnóstico usa `valor_energia`. |
| `leitura_anterior` ausente em 4 formas (**L3**, 32.285) | Consumo mantido; a leitura anterior não entra nas contas. |
| Datas em 4 formatos (**L6**, **F4**) | Os períodos P0 e P1 usam `mes_referencia`, que já vinha limpo. |

---

## 10. Como reproduzir

1. Rodar `01_ingestao_bronze` e as Silvers `02_silver_leituras` e `02_silver_faturas`.
2. Rodar `analise_reconciliacao_diretor.ipynb` do início ao fim (as seções 5 e 8 usam as Silvers de UCs e de geração distribuída, se existirem; senão, a Bronze).
3. Os cortes por município e bairro ficam disponíveis quando a Silver de UCs estiver no workspace.
