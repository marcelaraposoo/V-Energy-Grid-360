# Frontend — V-Energy Grid 360

React + TypeScript + Vite.

Requisitos: Node.js 24+ e npm. Com nvm, use `nvm use` neste diretório.

```bash
npm ci
npm run dev
```

Acesse http://localhost:5173 ou o endereço indicado no terminal.

- `npm run lint`: analisar o código com Oxlint.
- `npm test`: executar os testes automatizados.
- `npm run build`: verificar tipos e gerar o build em `dist/`.
- `npm run preview`: visualizar o build localmente.

## Visão 360 da UC

A tela em `/uc/{id}` consulta a API do backend. Em desenvolvimento, o adaptador de unidades
usa o proxy `/api` do Vite para `http://127.0.0.1:8000`; `VITE_API_URL` permite informar outro endereço.
Os tipos ficam em `src/api/types.ts` e são reexportados por `features/unidades/types.ts`,
sem manter uma segunda definição. Veja o [mapeamento da Gold](../backend/docs/contrato-gold.md).

- Consumo: últimas 12 competências disponíveis, referência anual opcional e comparação de
  conta alta por dois meses selecionados, com marcação de troca de medidor.
- Faturas: abas Recentes e Histórico completo; paginação de 10 registros no backend,
  resumo de pendências de todo o histórico e modal ao clicar na competência.
- Medidor e GD: equipamento atual, histórico de trocas e modalidade de geração distribuída.
- Interrupções: filtro de 6/12 meses ou todos, compartilhado com o contexto do alimentador.
- Atendimentos: histórico completo, filtros Todos/Abertos/Fechados com contagens e paginação
  de 10 registros no frontend. O protocolo abre os detalhes; não há filtro de período na tela.
- Os modais de fatura e atendimento fecham pelo botão, pela tecla Esc ou ao clicar fora.

Com `DATA_SOURCE=mock` no backend, os dados são fictícios. Há exemplos de troca em
`UC000001` (09/2025) e `UC000007` (03/2026). SQLite fictício nos testes não substitui
a homologação da exportação oficial.

## Dashboard Executivo — versão base

A tela inicial (`/`) é a **versão base do Dashboard Executivo**: uma visão geral da
distribuidora, com indicadores consolidados e acompanhamento mensal. Ela já consulta a API;
não utiliza os mocks locais de apresentação. A fonte dos dados é definida no backend
(`DATA_SOURCE=mock` ou `sqlite`). A homologação com a exportação oficial da Gold permanece pendente.

O Dashboard permanece dedicado à visão geral, somente com filtros temporais. Os recortes por
município, bairro e classe ficam na [Análise de Receita](#análise-de-receita).

### Padrão comum com a Análise de Receita

- **Explicações** de método e definição ficam no "i" do canto de cada card ou painel (`components/ui/InfoTip.tsx`),
  e não no texto principal.
- **Formatação e textos** dos indicadores comuns vêm de `utils/indicadores.ts`, para as duas telas mostrarem os
  mesmos números do mesmo jeito.
- **Data de corte** ("Dados até 30/06/2026") junto aos filtros (`components/ui/DataCorte.tsx`).
- **"Investigar na Análise de Receita"** abre a outra tela com os mesmos períodos, pela URL.

### Períodos e comparação

O período inicial é jul/2025–jun/2026, comparado com jul/2022–jun/2023 (os períodos do
diagnóstico no contrato da Gold); “Limpar” restaura essa seleção.
Os limites disponíveis são jul/2022 a jun/2026, contando competências mensais inclusivas.

- Sem comparação: de 1 a 24 meses contínuos.
- Com comparação: mês × mês ou intervalos de 2 a 12 meses, de mesma duração e sem sobreposição.
- A referência é opcional, pode ser removida pelo X e não é enviada à API quando desativada.
  O seletor preenche seu fim conforme a duração principal e permite meses de calendário diferentes.
- A sugestão prioriza o mesmo intervalo do ano anterior quando válido. Uma referência manual
  válida é preservada; seleções incompatíveis precisam ser ajustadas antes da consulta.

### Organização e indicadores

A primeira linha mostra receita de energia, energia faturada e preço médio por kWh em três
colunas iguais, com o mesmo card de KPI da Análise de Receita (`components/ui/KpiCard.tsx`): valor,
valor da referência e variação. A segunda divide a largura entre faturamento em aberto e cadastro/GD empilhados
à esquerda, e consumo por classe à direita. A terceira mantém os gráficos de evolução mensal.
Em telas menores, as seções ficam em uma coluna.

UCs cadastradas e GD usam a última competência selecionada (A5), incluindo a posição final
da referência quando há comparação. O consumo por classe soma as competências da A3, ordena
as cinco classes pelo volume principal e mantém uma única barra por classe. Faltar um mês
de uma classe deixa seu consolidado indisponível; a participação exige um total completo.

Receita e consumo nos KPIs são totais dos meses selecionados; preço médio é a razão entre
receita de energia e consumo, exibida com duas casas nas duas telas. Faturamento em aberto mostra
o consolidado ponderado pelo faturamento total, incluindo tributos, e a comparação em pontos
percentuais. A taxa da última competência não aparece: é o mês com mais faturas ainda não vencidas
na data de corte, que a definição do contrato conta como em aberto (o "i" do card explica isso).
UCs cadastradas e GD não são somadas entre meses; a participação é `UCs com GD / UCs cadastradas × 100`.

Os quatro carregamentos usam `useApi`, com cancelamento de consultas anteriores e tratamento
de erro, loading e dados indisponíveis. A consulta `indicador=executivo` compartilha a resposta
dos KPIs principais com o card de faturamento em aberto; UCs faturadas continuam disponíveis
na API, embora não apareçam no topo. Os gráficos existentes recebem a série Gold e mantêm
suas regras de barras/linhas, comparação e tooltips. O eixo Y adapta a faixa e a unidade aos
dados das séries visíveis, sempre partindo de zero, sem alterar os valores mensais.

### Evolução mensal

O gráfico é escolhido automaticamente, sem alternância manual de visualização:

| Seleção | Visualização |
|---|---|
| Um mês, sem referência | Uma barra com o valor mensal |
| Mês × mês | Duas barras, identificadas pelas competências reais |
| Vários meses, sem referência | Uma linha com as competências reais no eixo X |
| Período × período | Duas linhas alinhadas pela posição no intervalo |

Na comparação de períodos com os mesmos meses do calendário, o eixo X mostra os nomes dos
meses; nos demais casos, mostra “Mês 1”, “Mês 2” etc. Os tooltips identificam as competências
reais de cada série, e a legenda identifica os intervalos. Períodos longos reduzem apenas os
rótulos visíveis, preservando todos os pontos. Os gráficos mostram valores mensais, sem
acumulação progressiva; os totais ficam nos KPIs.

## Análise de Receita

A tela `/receita` (`src/features/receita/`) responde quanto da variação da receita foi preço e
quanto foi volume, e onde ela aconteceu. Consulta `api.receita.variacao(...)` e o catálogo
`api.filtros()`; os cálculos ficam no backend (`GET /api/receita/variacao`).

- **Períodos:** abre nos períodos do diagnóstico (jul/2022–jun/2023 × jul/2025–jun/2026). Períodos
  livres precisam ter a mesma duração (até 12 meses) e não podem se sobrepor.
- **Filtros:** município, bairro (só depois do município, porque a chave é município + bairro) e classe.
- **Conteúdo:** resumo, ponte da receita (waterfall), fatores associados (GD nas mesmas UCs,
  bandeira e troca de medidor), tabela de contribuição com detalhamento município → bairro →
  classe, ranking das maiores perdas por volume e evolução mensal.
- **Cores:** receita e volume em verde quando sobem e vermelho quando caem; o preço fica neutro.
- O waterfall não parte do zero, para os efeitos ficarem visíveis, e avisa isso abaixo do gráfico.

## Estrutura

```text
frontend/
├── src/
│   ├── components/
│   │   ├── layout/        # Layout compartilhado e navegação
│   │   └── ui/            # Componentes reutilizáveis
│   ├── features/         # Páginas por funcionalidade
│   │   ├── assistente/
│   │   ├── dashboard/
│   │   ├── inspecoes/
│   │   └── unidades/
│   ├── pages/            # Página de erro 404
│   ├── App.tsx           # Rotas da aplicação
│   ├── App.css           # Estilos do layout e componentes
│   ├── index.css         # Tokens e estilos globais
│   └── main.tsx          # Entrada do React
├── index.html
├── package.json          # Dependências e scripts
├── package-lock.json     # Versões das dependências
├── vite.config.ts        # Configuração do Vite
├── tsconfig*.json        # Configurações do TypeScript
└── V-Energy-Grid-360-Ideacao-UX.md  # Guia de layout e estilo
```
