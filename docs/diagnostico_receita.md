# Diagnóstico da variação de receita · V-Energy Grid 360

**Versão 2 · frente de Dados.** Responde à pergunta do Henrique Duarte (Diretor Comercial) com os dados limpos das Silvers e das Golds. Os números saem dos notebooks `analise_reconciliacao_diretor.ipynb`, `03_gold_receita_decomposicao.ipynb` (efeitos por nível, município e bairro) e `analise_quatro_bairros.ipynb` (seção 5.5); cada decisão de limpeza que os afeta está no `data_quality_log.md`. **A versão 2 acrescenta** o efeito composição (3.1), a leitura por município e bairro (5.4) e o achado dos quatro bairros, **testado contra as inspeções de campo** (5.5).

> "Comparando os últimos 12 meses com o primeiro ano da nossa base, o volume de energia faturada caiu quase 4% e a receita subiu só 8%. Ninguém nesta mesa sabe explicar por quê."

**Convenções.** Primeiro ano (P0) = competências `2022-07` a `2023-06`. Últimos 12 meses (P1) = `2025-07` a `2026-06`. **Volume** = soma de `consumo_kwh` (`silver.leituras`; a fatura não tem kWh). **Receita** = soma de `valor_energia` (`silver.faturas`, sem tributos). Tudo aqui é **associação medida nos dados**; as hipóteses estão marcadas.

---

## 1. Resposta em seis pontos

1. **Os dados reproduzem os números do diretor:** receita **+8,00%** e volume **−3,95%**.
2. **A receita subiu porque o preço médio por kWh subiu 12,45%** (tarifa e bandeira tarifária), o que mais do que compensou o volume perdido: efeito-preço **+R$ 14,09 mi** e efeito-volume **−R$ 4,66 mi**, que somam a variação de **+R$ 9,43 mi**.
3. **A queda de volume vem das unidades com painel solar** (geração distribuída). As 3.510 UCs com GD (7,8% das UCs) consumiram **61% menos** da rede (−11,2 milhões de kWh, ≈ **R$ 5,8 milhões** de receita de energia), enquanto **todas as demais cresceram 1,1%**.
4. **A bandeira tarifária explica parte do preço:** no primeiro ano 100% das faturas eram Verde, e nos últimos 12 meses só 33%. Sem a bandeira, a receita teria subido cerca de 6%, e não 8% (estimativa).
5. **Dois meses fora da tendência** (novembro de 2025 e fevereiro de 2026) escondem parte da queda: se seguissem os outros dez meses, o volume teria caído ~6%, e não ~4% (hipótese).
6. **Fora da GD, há um grupo de cerca de 900 UCs sem painel nos mesmos quatro bairros** (Iputinga e Macaxeira, em Recife; Jardim Jordão e Prazeres, em Jaboatão): **601 residenciais e 300 comerciais** cujo consumo caiu, em mediana, cerca de 55% entre maio e junho de 2025. Somam **2,86 milhões de kWh por ano (≈ R$ 1,5 a 1,7 mi, de 1,2% a 1,3% da receita de energia)**. **A causa aparece nas inspeções de campo:** 898 dessas 901 UCs foram inspecionadas entre agosto e dezembro de 2025 e **831 (92,5%) tiveram irregularidade confirmada** (medidor adulterado, desvio, by-pass, ligação clandestina, lacre violado), contra ~8% nas UCs sem queda; nas residenciais, 98,8% têm medidor eletromecânico (23% na base). São **perdas não técnicas**, numa área delimitada e com início simultâneo. O consumo **não voltou depois das inspeções** (seção 5.5).

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

### 3.1 O efeito composição: por que os efeitos por classe não somam −R$ 4,66 mi

A conta acima trata todo kWh perdido como se valesse o **preço médio da empresa**. Aplicando as mesmas fórmulas em cada nível e somando os grupos (`gold.receita_decomposicao`, seção 8 do notebook):

| Nível | Grupos | Efeito-volume | Efeito-preço |
|---|---|---|---|
| Empresa | 1 | −R$ 4.657.042 | +R$ 14.089.243 |
| Classe | 5 | −R$ 4.994.045 | +R$ 14.426.246 |
| Município | 14 | −R$ 4.662.467 | +R$ 14.094.669 |
| Município × classe | 70 | −R$ 4.994.034 | +R$ 14.426.235 |
| Linha (município × bairro × classe) | 1.106 | −R$ 4.993.510 | +R$ 14.425.712 |

A variação da receita (**+R$ 9.432.201**) é a mesma em todos os níveis; muda só a **divisão** entre preço e volume. A diferença de **cerca de R$ 337 mil** é o efeito composição: ela aparece quando o nível separa as **classes** (que têm preços por kWh diferentes) e quase desaparece por município (R$ 5 mil) e por bairro dentro de uma classe (R$ 524). O sinal indica que o volume caiu mais nas classes de preço acima da média da empresa (ou subiu nas de preço abaixo); não olhamos o preço de cada classe para confirmar.

**Qual número usar:** a resposta à pergunta do diretor é **−R$ 4,66 mi e +R$ 14,09 mi**, porque reproduz os números que ele viu. A tabela por classe da seção 5.1 usa o preço de cada classe e soma ≈ −R$ 5,0 mi; as duas leituras são corretas e respondem a perguntas diferentes.

---

## 4. O preço: tarifa e bandeira

| Período | Bandeira | % das faturas | Preço mediano (R$/kWh) |
|---|---|---|---|
| P0 | Verde | **100%** | 0,5309 |
| P1 | Verde | 33,2% | 0,5857 |
| P1 | Amarela | 25,1% | 0,6045 |
| P1 | Vermelha P1 | 25,0% | 0,6234 |
| P1 | Vermelha P2 | 16,7% | 0,6577 |

As faixas da tabela são arredondadas uma a uma e somam **66,8%** de faturas não verdes; o cálculo direto sobre as 539.768 faturas da `fato_consumo_faturamento` dá **66,7%**. A diferença é de arredondamento, e o texto usa **≈ 67%**.

- O preço mediano da **Verde** subiu 10,3% (R$ 0,5309 → R$ 0,5857), perto dos 10,5% de reajuste da tarifa residencial. Esse é o efeito da **tarifa**.
- O restante do aumento do preço médio (+12,45%) vem da **bandeira**: nos últimos 12 meses, 67% das faturas pagam adicional, contra 0% no primeiro ano. No residencial, o preço por kWh subiu 13,0% (contra 10,5% de tarifa), o que deixa **~2,3% para a bandeira** (1,130 ÷ 1,105 − 1: o preço total é a tarifa vezes a bandeira, e a subtração simples, 2,5 pontos, superestima porque as taxas se compõem).
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

A perda de volume está em duas classes (−R$ 5,32 mi), e as outras três compensam +R$ 0,33 mi. Os reajustes das outras classes não são conhecidos (o case cita só o residencial). **Os efeitos por classe somam ≈ −R$ 5,0 mi, e não os −R$ 4,66 mi da seção 3**: a diferença é o efeito composição (seção 3.1).

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

### 5.4 Onde: município e bairro

`gold.receita_decomposicao`, comparando os últimos 12 meses com o **primeiro ano**. Em cada município, os efeitos foram recalculados no próprio nível (somando volumes e receitas), e não somados a partir dos bairros.

| Município | Volume | Receita | Efeito-volume | Efeito-preço | UCs com GD |
|---|---|---|---|---|---|
| Recife | −4,3% | +7,7% | −R$ 2,04 mi | +R$ 5,64 mi | 1.420 |
| Jaboatão dos Guararapes | **−6,8%** | +4,8% | −R$ 1,34 mi | +R$ 2,29 mi | 569 |
| Paulista | −2,6% | +9,5% | −R$ 0,27 mi | +R$ 1,23 mi | 304 |
| Cabo de Santo Agostinho | −3,2% | +8,8% | −R$ 0,23 mi | +R$ 0,86 mi | 218 |
| Igarassu | −4,1% | +8,4% | −R$ 0,14 mi | +R$ 0,41 mi | 127 |
| Olinda | −1,2% | **+10,7%** | −R$ 0,13 mi | +R$ 1,34 mi | 328 |
| Camaragibe | −2,4% | +9,7% | −R$ 0,12 mi | +R$ 0,60 mi | 127 |
| Ipojuca | −2,7% | +9,8% | −R$ 0,08 mi | +R$ 0,38 mi | 96 |
| São Lourenço da Mata | −2,0% | +10,1% | −R$ 0,07 mi | +R$ 0,46 mi | 114 |
| Moreno | −3,2% | +8,0% | −R$ 0,07 mi | +R$ 0,24 mi | 52 |
| Abreu e Lima | −2,7% | +10,4% | −R$ 0,07 mi | +R$ 0,32 mi | 90 |
| Itapissuma | −4,0% | +7,4% | −R$ 0,05 mi | +R$ 0,15 mi | 30 |
| Ilha de Itamaracá | −4,6% | +6,2% | −R$ 0,04 mi | +R$ 0,10 mi | 20 |
| Araçoiaba | −1,9% | +10,6% | −R$ 0,01 mi | +R$ 0,07 mi | 15 |

**Recife e Jaboatão concentram 73% do efeito-volume** (−R$ 3,38 mi de −R$ 4,66 mi) e **57% das UCs com GD** (1.989 de 3.510). Jaboatão é o pior município (volume −6,8%, receita só +4,8%), e Olinda o melhor.

**Qual bairro mais perdeu volume residencial?** (a pergunta do Henrique, comparando com o primeiro ano): **Iputinga, em Recife, −496 mil kWh (−22,1%)**. Os maiores, separando a perda das UCs com GD da do resto:

| Bairro | Perda | Variação | Perda das UCs com GD | Perda das UCs sem GD |
|---|---|---|---|---|
| Iputinga (Recife) | −496.099 kWh | −22,1% | −197.649 | **−298.450 (−15,6%)** |
| Jardim Jordão (Jaboatão) | −439.331 | −21,7% | −163.415 | **−275.916 (−15,7%)** |
| Macaxeira (Recife) | −232.678 | −21,9% | −69.401 | **−163.277 (−17,3%)** |
| Prazeres (Jaboatão) | −213.212 | −18,4% | −86.170 | **−127.042 (−12,4%)** |
| Brasília Teimosa (Recife) | −161.506 | −4,2% | −298.948 | +137.442 (+4,1%) |
| Barra de Jangada (Jaboatão) | −76.744 | −6,1% | −124.033 | +47.289 (+4,5%) |
| Pixete (São Lourenço da Mata) | −68.433 | −5,3% | −117.515 | +49.082 (+4,5%) |
| Fragoso (Paulista) | −67.489 | −4,1% | −133.017 | +65.528 (+4,6%) |

**Nos bairros do topo a partir do quinto, a GD explica a perda inteira**: o volume das UCs sem painel cresceu de 3,6% a 4,6%. **Nos quatro primeiros, não**: as UCs sem painel também caíram de 12% a 17%.

**Ressalva:** o diretor perguntou "no último ano". Esta tabela compara com o **primeiro ano** da base; contra o ano anterior (2024-07 a 2025-06), o ranking pode mudar, e o recorte sai da `fato_segmento_mensal`.

### 5.5 Quatro bairros com queda fora da GD: irregularidades confirmadas em campo

Iputinga, Macaxeira, Jardim Jordão e Prazeres perderam **1,38 milhão de kWh, 31,5% da perda de volume residencial** (4,38 milhões), com 3.025 UCs. **63% dessa perda (864.685 kWh) não vem das UCs com GD.** O que os dados mostram (`analise_quatro_bairros.ipynb`):

**A queda.**
- **Mudança de patamar, e não queda gradual.** O consumo médio por UC dos quatro bairros, dividido pelo dos demais bairros residenciais (meses sem GD), ficou entre **1,005 e 1,011** de 2022-07 a 2025-04, caiu para **0,914** em 2025-05 e ficou entre **0,813 e 0,822** de 2025-06 a 2026-06. O consumo médio por UC e mês foi de 180,2 para 144,3 kWh (**−19,9%**) nos quatro bairros, contra 178,7 para 176,7 (−1,1%) nos demais. O padrão sazonal é o mesmo nos dois grupos, **inclusive o salto de novembro e fevereiro** (seção 6).
- **Concentrada em parte das UCs.** Entre as UCs **sem GD**, **601 de 2.774 (21,7%)** dos quatro bairros caíram 40% ou mais, com queda mediana de **55%**; nos demais bairros foram 7 de 32.370 (**0,02%**, uma taxa mil vezes menor). O p90 da variação anual é parecido nos dois grupos (+12% e +14%): as outras UCs desses bairros não mudaram.
- **Magnitude:** as 601 UCs deixaram de consumir cerca de **1,06 milhão de kWh por ano** (média mensal da diferença × 12, nos meses comparáveis), **≈ R$ 0,55 mi a R$ 0,62 mi por ano** a R$ 0,519 e R$ 0,584 por kWh. A perda **líquida** do grupo sem GD (864.685 kWh, ≈ R$ 0,45 mi) é menor porque as demais UCs cresceram cerca de 4%.

**O que a queda não é.** Não é GD (as UCs com painel foram retiradas); não é troca de medidor (as trocas são de setembro de 2025 a março de 2026, depois da mudança, e são menos frequentes nesses bairros: 10,8 por 100 UCs, contra 14,2 nos demais bairros do topo); não é o evento de julho de 2025 (a queda começa antes); não é mudança no tipo de leitura (≈ 23% de leituras não reais contra ≈ 18% nos demais, já antes da mudança); e não é um alimentador comum (são seis, nenhum comum aos quatro bairros e nenhum dos três do evento de julho).

**A causa: o que as inspeções mostram.** Cruzando as 601 UCs com as 1.389 inspeções de campo (agosto a dezembro de 2025):

| Grupo de UCs | Inspeções | Confirmadas | Taxa de acerto |
|---|---|---|---|
| Quatro bairros, queda de 40% ou mais | 599 | 549 | **91,7%** |
| Quatro bairros, sem queda forte | 23 | 2 | 8,7% |
| Demais bairros, sem queda forte | 380 | 29 | 7,6% |
| Fora desta análise (com GD, outra classe ou sem dados) | 387 | 291 | 75,2% |

- **599 das 601 UCs foram inspecionadas** (99,7%), então não há seleção dentro do grupo: quase todas passaram por campo. Das 601, 549 tiveram irregularidade confirmada, 50 não e 2 nunca foram inspecionadas.
- **Os tipos são os de perdas não técnicas:** medidor adulterado (119), desvio direto (117), by-pass (116), ligação clandestina (105) e lacre violado (92). A taxa de acerto é de 88% a 95% em todos os meses, de agosto a dezembro.
- **O sinal funciona:** em todas as UCs inspecionadas desta análise, a taxa de acerto é de **91,7%** entre as que caíram 40% ou mais (599 inspeções) e de **7,7%** entre as estáveis (401). Uma queda forte de consumo sem GD é um forte indício de irregularidade.
- **O perfil do medidor aponta o mecanismo:** **98,8%** das 601 UCs têm medidor eletromecânico, contra 23,8% nas outras UCs dos quatro bairros e 22,5% nos demais bairros; a idade média é de 15,9 anos (contra 14,1 e 14,3) e só 1,0% têm medidor `SMART` (contra ~19%).
- **O que mudou na leitura do problema:** a taxa de acerto histórica de 62,7% **esconde duas populações**. Este grupo responde por **549 das 871 irregularidades confirmadas (63%)** e por 43% das inspeções.

**O consumo não voltou depois da inspeção.** Se as inspeções tivessem regularizado a medição, o consumo das UCs deveria subir nos meses seguintes. Medido UC a UC, nas 549 com irregularidade confirmada, em meses relativos ao mês da inspeção e como razão ao consumo dos demais bairros residenciais no mesmo mês (para descontar a sazonalidade):

| Meses em relação à inspeção | −6 | −4 | −2 | 0 | +2 | +4 | +6 | +8 |
|---|---|---|---|---|---|---|---|---|
| Consumo ÷ consumo dos demais bairros | 1,34 | 0,98 | 0,72 | 0,72 | 0,72 | 0,72 | 0,73 | 0,73 |

O consumo caiu até dois meses antes da inspeção e **ficou parado em 0,72 a 0,73 nos oito meses seguintes**, sem sinal de recuperação até o fim da base (os meses +7 e +8 têm 445 e 343 UCs, porque a base termina em 2026-06). Os dados só mostram o **consumo faturado**: não sabemos se o medidor foi trocado, se houve regularização ou cobrança retroativa. A energia recuperada informada nas inspeções do grupo é de **1.011 kWh por irregularidade confirmada** (≈ 555 mil kWh no total, ≈ R$ 0,32 mi a R$ 0,584 por kWh), bem abaixo de um ano de perda (≈ 1,06 milhão de kWh).

**O mesmo grupo no comércio.** A seção 9 do notebook mostrou 338 inspeções em UCs comerciais sem GD, com 84,9% de acerto. Aplicando a elas o mesmo teste do residencial (seção 10):
- **300 de 4.518 UCs comerciais sem GD (6,6%) caíram 40% ou mais**, com queda mediana de **54%**: cerca de **1,80 milhão de kWh por ano** (≈ R$ 0,93 a 1,05 mi, ao preço médio da empresa de R$ 0,519 a R$ 0,584 por kWh).
- **Estão nos mesmos quatro bairros:** Iputinga, 90 de 107 UCs comerciais (84,1%); Jardim Jordão, 95 de 116 (81,9%); Prazeres, 71 de 87 (81,6%); Macaxeira, 43 de 55 (78,2%). **Fora deles, só 1** das outras 4.153 UCs comerciais.
- **Mesmo mês e mesmo tamanho de queda.** A razão entre o consumo das afetadas e o das demais UCs comerciais ficou entre 1,13 e 1,15 até 2025-04, caiu para 0,82 em 2025-05 e para **0,51 a 0,52 de 2025-06 a 2026-06**, uma queda de ≈ 55% em relação ao patamar anterior: a mesma data e a mesma ordem de grandeza do grupo residencial (mediana de 55%).
- **Inspeções:** 299 das 300 foram inspecionadas, e **282 (94,3%)** tiveram irregularidade confirmada; as UCs comerciais estáveis (37 inspeções) tiveram 8,1% (3 de 37).

**Os dois grupos juntos:** 901 UCs (601 residenciais e 300 comerciais), **898 inspecionadas e 831 com irregularidade confirmada (92,5%)**, o que equivale a **95% das 871 irregularidades confirmadas** no período (as inspeções de UCs sem queda, e as de UCs com GD, que confirmaram 1 de 31, respondem pelo resto). A **área**, a **data** (maio e junho de 2025) e o **tamanho da queda** (≈ 55%) são os mesmos nas duas classes, o que sugere um **mesmo mecanismo**.

**Por que tantas UCs mudaram ao mesmo tempo.** A queda se completa em cerca de dois meses (maio e junho de 2025), em centenas de UCs de uma área delimitada, o que é incomum para fraude isolada e sugere uma **ação coordenada**. É uma hipótese: os dados não dizem quem nem como.

**O que continua em aberto.**
- **No comércio, o consumo depois da inspeção** foi medido só pela série agregada (a razão fica em 0,51 a 0,52 até junho de 2026, com 299 das 300 UCs inspecionadas até dezembro de 2025); o teste UC a UC, como o do residencial, não foi feito. O **perfil do medidor** das UCs comerciais também não foi medido.
- **A coordenação**, descrita acima.

**Limites:** é associação medida nas UCs inspecionadas, e os grupos de comparação foram inspecionados por critérios que não conhecemos; o limiar de 40% é nosso; os valores em reais usam o preço médio e são estimativas.

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
| 8 | **Investigar por que o consumo das ~900 UCs** (601 residenciais e 300 comerciais) **não voltou** depois das inspeções (831 com irregularidade confirmada; no residencial, consumo parado em 0,72 a 0,73 do dos demais bairros por oito meses): conferir se o medidor foi trocado ou regularizado e se a energia foi cobrada, **reinspecionar** as que seguem com consumo baixo e **inspecionar as 3** que nunca foram. | Cerca de **2,86 milhões de kWh por ano (≈ R$ 1,5 a 1,7 mi, de 1,2% a 1,3% da receita de energia)** seguem sem ser faturados enquanto o consumo ficar no patamar baixo (estimativa); a energia recuperada informada nas inspeções do grupo residencial soma ≈ 555 mil kWh (≈ R$ 0,32 mi), e a do comercial não foi somada. |
| 9 | **Usar a queda de consumo de 40% ou mais, sem GD, como sinal principal da fila de inspeção** (`fila_inspecao`). Nas inspeções históricas, **91,7% das UCs residenciais e 94,3% das comerciais** com essa queda tiveram irregularidade confirmada, contra **7,7% e 8,1%** das estáveis; e **rebaixar as UCs com GD**, em que 1 de 31 inspeções achou algo. Incluir também o perfil do medidor (eletromecânico e antigo) e a reincidência. | A taxa de acerto do sinal é ~12 vezes a das UCs estáveis; cada inspeção evitada em UC sem irregularidade é um dia de equipe. |
| 10 | **Tratar o caso como um evento de uma área, e não como UCs isoladas**: quatro bairros, ~900 UCs, início em maio e junho de 2025 e queda de ≈ 55% nas duas classes. Levar à área de perdas e à de segurança do patrimônio, e verificar outras áreas com o mesmo desenho (a queda sem GD, de ≈ 55%, em UCs de medidor eletromecânico antigo). | Mesma ordem de grandeza da recomendação 8; o ganho de olhar outras áreas não foi medido (nenhuma outra apareceu na análise de bairros). |

---

## 8. Limites e o que não sabemos

- **A causa da queda é uma associação.** A GD concentra a queda e o consumo cai na conexão, mas nenhum campo diz que foi o painel. A geração abatida do consumo faturado é o que o case descreve, e o padrão combina.
- **Município e bairro** foram analisados (5.4), **comparando com o primeiro ano**. A pergunta "no último ano" (contra 2024-07 a 2025-06) exige a `fato_segmento_mensal`.
- **A causa da queda nos quatro bairros** foi **identificada nas inspeções** (5.5): irregularidades confirmadas em 91,7% das UCs inspecionadas. **Não sabemos** por que o consumo não voltou depois delas (os dados só mostram o faturado), nem por que a mudança foi simultânea. No comércio, o consumo depois da inspeção e o perfil do medidor ainda não foram medidos UC a UC.
- **O efeito composição** (3.1, ≈ R$ 337 mil) faz o efeito-volume por classe (≈ −R$ 5,0 mi) diferir do da empresa (−R$ 4,66 mi); a leitura por classe usa o preço de cada classe.
- **Reajuste das outras classes** (comercial +18,8%, rural +26%) não é conhecido: o case cita só o residencial.
- **A causa dos meses atípicos** (nov/2025 e fev/2026) e do evento de julho de 2025 não está nos dados.
- **O "+8%" do diretor aceita as duas bases** (com e sem as faturas órfãs: +7,90% e +8,00%). O +8,00% exato na base limpa sugere que ela é a referência do case, mas não prova.
- As contas de ordem de grandeza (R$ 2 mil por UC, R$ 1,8 mi por ano, 6% sem bandeira, −6% sem os meses atípicos, e os R$ 0,55 a 0,62 mi do grupo de 601 UCs) são **estimativas** feitas a partir das tabelas deste documento, com as premissas indicadas.

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
3. Rodar as Golds `dim_uc`, `fato_consumo_faturamento` e `receita_decomposicao` (seções 3.1 e 5.4) e o notebook `analise_quatro_bairros.ipynb` (seção 5.5).
