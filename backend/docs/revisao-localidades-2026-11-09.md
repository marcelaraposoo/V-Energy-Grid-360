# Nomes parciais e bairros ambíguos — 09/11/2026

Alteração local na branch `ia/localidades-parciais`. Objetivo: reconhecer referências como “Caetés”, apresentar as opções do cadastro e preservar a escolha do usuário. Não há inclusão de dados Gold nem exceção codificada para uma cidade ou bairro específico.

## Diagnóstico

A consulta `SELECT DISTINCT municipio, bairro FROM dim_uc` no SQLite usado pelo Docker retornou **297 pares**. O contexto anterior encaminhava bairros apenas quando seu nome cadastrado completo aparecia na pergunta. “Caetés” não correspondia a “Caetés I”, “Caetés II”, “Caetés III” ou “Jardim Caetés”. O modelo podia interpretar o nome como município e encerrar pedindo um esclarecimento genérico, antes de o resolvedor geográfico ser executado.

Na auditoria original `5478cb5ca9a94ea4a91d7a8381335fb5`, o modelo registrou Caetés como município e pediu esclarecimento; não houve falha de provedor nem execução da consulta de consumo. Caruaru representa outro caso: não há esse município em `dim_uc` nem registros correspondentes em `fato_segmento_mensal`. Melhorar a busca não cria essa cobertura.

## Outros casos encontrados na Gold

As alternativas abaixo vieram de consulta ao cadastro real, não de uma lista fixa usada pelo agente.

| Nome parcial | Alternativas cadastradas | Município |
|---|---|---|
| Caetés | Caetés I, Caetés II, Caetés III, Jardim Caetés | Abreu e Lima |
| Maranguape | Maranguape I, Maranguape II, Jardim Maranguape, Engenho Maranguape | Paulista |
| Artur Lundgren | Artur Lundgren I e II | Paulista |
| Serrambi | Enseada de Serrambi e Ponta de Serrambi | Ipojuca |
| Camela | Camela Centro e Rurópolis de Camela | Ipojuca |
| Suape | Zona Industrial de Suape; Distrito Industrial de Ipojuca - Suape | Cabo de Santo Agostinho; Ipojuca |
| Bonança | Alto da Conquista, Alto do Pau D'arco, Bonança I, Bonança II, Jardim Massaranduba, Monte Sinai, Novo Horizonte e Várzea da Cruz, todos com “(Bonança)” no cadastro | Moreno |

Também foram encontrados **15 nomes exatos repetidos entre municípios**. Exemplos: Curado (Recife/Jaboatão dos Guararapes), Bela Vista (Igarassu/Ilha de Itamaracá/Ipojuca/Moreno), COHAB (Recife/Cabo de Santo Agostinho), Tabatinga (Camaragibe/Igarassu), Fragoso e Tabajara (Olinda/Paulista). Esses casos pedem município, não expansão automática do bairro.

## Implementação

- `context/place_search.py`: busca por sequências de palavras completas, com normalização de caixa, acentos e pontuação. Fragmentos identificáveis exigem ao menos uma palavra de quatro caracteres. Marcadores como “bairro” não bastam como nome. Preposições nas bordas não excluem candidatos: “de Suape” também encontra o nome que termina apenas em “Suape”.
- `context/runtime.py`: mantém `bairros_mencionados` para correspondências completas e adiciona `bairros_candidatos`, com o trecho informado e opções município/bairro. Até 30 opções são encaminhadas; truncamento é informado. Nomes completos têm precedência: “Macaxeira” não passa a incluir “Engenho Macaxeira”, e “Caetés II” não vira uma busca por Caetés I.
- `context/geography.py`: valida a interpretação e oferece alternativas cadastrais para referências parciais, nomes repetidos e confusão entre município/bairro. Correspondência parcial não autoriza trocar um nome, escolher um bairro ou somar candidatos. Uma proposta que complete indevidamente a referência também é interrompida antes da execução.
- `sql_execution_orchestrator.py`: enriquece esclarecimentos antes do retorno antecipado; mantém erro técnico quando o catálogo falha. Encontrar candidatos converte insuficiência geográfica em pedido de confirmação. Não exige uma nova chamada ao modelo.
- `prompts/sql_generation/output_contract.md`: orienta o modelo a preservar a referência parcial, mostrar alternativas e usar a escolha explícita posteriormente. A interpretação da pergunta continua no modelo; a busca cadastral não classifica métricas por palavras-chave.

As opções são agrupadas por município e respeitam o limite existente de 300 caracteres das mensagens de esclarecimento. Listas maiores mostram parte das alternativas e avisam que há outras, em vez de serem descartadas e substituídas por uma mensagem genérica. As barreiras SQL, o modo somente leitura, o cache e os limites de execução foram preservados. A mudança do prompt invalida respostas antigas pelo fingerprint que já integra a chave de cache.

## Validação

Os testes locais cobrem nomes parciais, nomes completos sobrepostos, preposições, limites de tamanho, localidades em vários municípios, seleção inventada pelo modelo, tentativa de somar candidatos, erro de catálogo e esclarecimento sem execução SQL/chamada adicional ao modelo.

A avaliação `benchmarks/geography_regression.py` testa 18 cenários pela API Docker: Caetés, escolha de Caetés I/2025, repetição com cache, mudança para Caetés II mantendo município/ano, grafia sem acento, Caetés explicitamente chamado de município, os seis outros nomes parciais da tabela, Curado/Bela Vista, escolha explícita de Curado/Recife, Prazeres, Macaxeira e Caruaru. As opções esperadas são consultadas diretamente em `dim_uc`; valores são conferidos por SQL independente em `fato_segmento_mensal`. O teste de cache exige zero chamadas de provedor e nenhuma execução SQL nova.

A primeira rodada HTTP aprovou 15/18. Ela revelou duas causas gerais adicionais: preposições selecionavam fragmentos excessivamente específicos em Camela/Suape, e a lista de Bonança excedia 300 caracteres e virava uma resposta genérica. Ambas foram corrigidas e ganharam regressões.

**Resultado final: 18/18 cenários HTTP aprovados**, com Gold, Redis e provedores reais. A suíte completa do backend terminou com **2.098 testes passando e 19 integrações opt-in puladas**, em 83,58 s. Isso inclui 27 testes adicionais desta tarefa. O frontend não foi modificado; o Docker foi reconstruído e iniciado com sucesso.

Na sequência real, a escolha de Caetés I/2025 retornou **241.911 kWh** e a mudança para Caetés II no mesmo município/ano retornou **97.389 kWh**, ambos conferidos por consultas independentes. A repetição idêntica de Caetés I teve hit comprovado, sem novas tentativas de provedor nem execução SQL, em **118,85 ms por HTTP**. Listas de opções não executaram consultas analíticas. A maior latência observada foi **24,81 s**, em Prazeres; os limites de provedor e SQL não foram aumentados.

Artefatos locais ignorados pelo Git: `.runtime/geography_http.json`, `.runtime/geography_http_final.json`, `.runtime/places_final_tests.txt`. Reprodução na pasta `backend`:

```powershell
.venv/Scripts/python.exe -m pytest -q --basetemp=.runtime/pytest_places
.venv/Scripts/python.exe -m benchmarks.geography_regression --allow-provider-calls --gold ../data/gold/gold.db --output .runtime/geography_check.json
```

O benchmark usa os provedores já configurados, com a autorização da sessão. Os resultados não são garantia de acerto de qualquer formulação. A busca nova cobre fragmentos formados por palavras completas; não é um serviço geral de geocodificação nem prova cobertura de localidades ausentes. Não houve mudança de frontend ou nova inspeção visual do navegador nesta tarefa.

## Como testar

No assistente, abra **Nova conversa** e pergunte “Qual o consumo de Caetés?”. A resposta deve apresentar Caetés I, II, III e Jardim Caetés em Abreu e Lima. Depois responda “Quero Caetés I, em Abreu e Lima, em 2025”. A consulta deve usar apenas esse bairro. Repita a segunda pergunta para conferir o hit na auditoria.

Outros testes: “Consumo de Maranguape?”, “Consumo de Serrambi?” e “Consumo do bairro Curado?”. Esses pedidos devem oferecer as alternativas pertinentes. “Consumo de Curado em Recife em 2025?” já identifica um par completo. Caruaru continua sem cobertura na Gold atual.
