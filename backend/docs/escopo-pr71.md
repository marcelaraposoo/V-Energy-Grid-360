# Escopo reduzido do PR #71

O cache Redis, a reutilização segura de consultas e a observabilidade já estão
integrados à base pela entrega anterior. Este ajuste mantém essa implementação e
limita o incremento do PR à validação de intenção SQL e à orientação de perguntas
dependentes do histórico para a demo.

## Mantido

- Verificações existentes de TOP, receita de energia versus total faturado e
  contagem distinta de UCs afetadas na fonte de interrupções.
- Recusa de coluna móvel de 12 meses para outra janela explícita, compartilhada
  entre geração e conferência SQL na C5.
- Segurança C1/C4.2, execução read-only, fundamentação numérica C5, providers,
  cotas, timeouts, fallback e contratos públicos.
- Cache, isolamento por sessão e versão, TTL e auditoria da base.

## Retirado desta entrega

Os módulos `conversation`, `geography`, `aggregate_query` e `semantic_output`,
assim como suas integrações e testes específicos, foram retirados. Também saem
a recuperação conversacional de gráficos, a ampliação de gráficos para três
colunas, as mudanças de elegibilidade/representação da memória e a exceção de
texto numérico para períodos móveis. Não há flag experimental nesta versão.

Não se adiciona BusinessPlan, catálogo de respostas ou uma camada de interpretação.
A correção de composição de receita já integrada pela equipe à `main` não é
revertida: esses arquivos ficam sem delta próprio deste PR em relação ao ancestral
comum. Assim, o merge preserva as alterações da equipe no destino, sem copiá-las
como se fossem uma nova funcionalidade desta branch.

## Perguntas dependentes do histórico

Referências explícitas reconhecidas, como “E nos últimos 6 meses?”, “Agora FEC”,
“E no município de Olinda?” e “Mostre um gráfico disso”, recebem:

> Para responder com segurança, envie a pergunta completa, incluindo a métrica,
> o período e os filtros desejados.

A decisão ocorre após C1 e antes de buscar/entregar cache. Não gera SQL, não chama
provider, não publica resposta no cache e é auditada. A presença de histórico não
altera essa decisão. “Quantas UCs existem?” e outras perguntas curtas completas
continuam no fluxo normal.

O reconhecimento é conservador e não é um parser universal de português. Formas
não reconhecidas continuam sujeitas ao contrato da C4.1, instruído a pedir uma
pergunta completa em vez de reconstruir referências pelo histórico. A memória da
base continua disponível; não foi apagada, migrada ou substituída.

## Limites da validação

As verificações cobrem contradições identificáveis; não provam toda a semântica de
qualquer SQL. Não foram incluídos novos otimizadores, resolução de localidades,
síntese semântica ou interpretação de follow-ups para ampliar essa cobertura.

## Verificação

Backend completo: **1.903 aprovados, 19 ignorados**, sem chamadas a providers
externos. A suíte inclui cache, segurança, providers simulados, memória, API,
validação pergunta–SQL e a orientação fixa antes do cache. As integrações externas
opcionais permanecem ignoradas. Nenhum container foi alterado.

As mudanças estão preparadas no diretório de trabalho; o PR remoto só muda após
commit/push autorizados. Não houve rebase, reset destrutivo ou aplicação de stash.
