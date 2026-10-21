# V-Energy Grid 360 — Guia de layout e estilo

Este documento orienta a aparência e a organização das telas do portal.
A interface utiliza exclusivamente **modo escuro**, com destaque amarelo,
superfícies discretas e foco na leitura dos dados. Não adicionar seletor de tema.

## 1. Referências e estado atual

Antes de alterar a interface, consultar estes arquivos:

| Arquivo | Referência |
| --- | --- |
| `src/index.css` | Tokens, fontes, tipografia e estilos globais |
| `src/App.css` | Dimensões do layout, componentes e regras responsivas |
| `src/components/layout/AppShell.tsx` | Sidebar, cabeçalho, conteúdo e menu mobile |
| `src/components/layout/navigation.ts` | Grupos, nomes e links da navegação |
| `src/App.tsx` | Rotas registradas |
| `src/components/ui/` | Componentes reutilizáveis |

Os valores descritos abaixo correspondem à base atual. Os componentes e tokens
existentes devem ser reutilizados ao criar novas telas, evitando estilos paralelos.

## 2. Cores

### Tokens existentes

| Token CSS | Valor | Uso |
| --- | --- | --- |
| `--background` | `#0F1115` | Fundo da aplicação |
| `--surface` | `#171A1F` | Cards e painéis |
| `--surface-elevated` | `#22262D` | Superfícies elevadas e hover |
| `--border` | `#2C3038` | Contornos de campos e controles |
| `--border-subtle` | `#24282F` | Separadores e bordas de painéis |
| `--text-primary` | `#F5F6F7` | Títulos e conteúdo principal |
| `--text-secondary` | `#A8AFB9` | Descrições e informações de apoio |
| `--text-muted` | `#8A929F` | Metadados e placeholders |
| `--accent` | `#FFD43B` | Ação principal, item ativo e destaques |
| `--accent-foreground` | `#0F1115` | Texto sobre o amarelo |
| `--success` | `#3DD68C` | Estados positivos |
| `--info` | `#60A5FA` | Informação |

Cores estruturais presentes no layout: sidebar `#12151A` e cabeçalho `#111418`.
Para novos estados de alerta e erro, as referências são `#F59E0B` e `#F16969`;
essas cores ainda não possuem tokens próprios em `src/index.css`.

### Aplicação

- Botão primário: fundo amarelo e texto escuro. Hover existente: `#FFE16C`.
- Amarelo marca ações e seleção; evitar grandes superfícies amarelas decorativas.
- Item ativo da sidebar: texto/ícone amarelos, fundo amarelo translúcido
  (`#FFD43B0D`) e marcador de 3px na borda esquerda.
- Cards usam bordas discretas. Reservar sombras suaves para overlays quando necessários.
- Status deve combinar ícone e rótulo; não depender apenas de cor.
- Variações precisam de sinal e contexto: queda de consumo ou de DEC não tem
  necessariamente o mesmo significado de uma queda de receita.

## 3. Tipografia e espaçamento

As fontes são servidas localmente pelo bundle: **Inter** (400/500/600) na interface
e **Manrope** (600/700) em títulos e futuros valores de indicadores.
Números usam `font-variant-numeric: tabular-nums`.

| Elemento | Padrão |
| --- | --- |
| Texto base | Inter, 14px, entrelinha 1.5 |
| H1 da página | Manrope 700, `clamp(23px, 2.2vw, 30px)`, entrelinha 1.3 |
| H2 de painel | Manrope 700, 15px, entrelinha 1.5; 14px no mobile |
| H3 | Manrope 600, 14px |
| Descrição da página | Inter 400, 13px |
| Navegação | Inter 500, 13px |
| Rótulo acima do título (`.eyebrow`) | Inter 600, 10px, maiúsculas, espaçamento entre letras de 1.5px |
| Legendas e metadados | Inter, 11–12px; usar com moderação |
| Valores de KPI, quando implementados | Manrope 700, referência de 28–32px |

Usar a escala de espaçamento 4, 8, 12, 16, 24, 32 e 48px como referência.
Preservar os ajustes existentes no layout, como o intervalo de 28px após o cabeçalho da página.

- Raio: 8px em painéis, 6px em inputs e botões; badges arredondadas em formato de cápsula.
- Botões: altura mínima de 36px; links da navegação têm altura mínima de 44px.
- Painéis: padding de referência de 20–24px, reduzido para 18px no cabeçalho mobile.
- Novas grades devem usar colunas flexíveis e `minmax(0, 1fr)` para evitar transbordamento.

## 4. Layout compartilhado e responsividade

### Estrutura

```text
┌ Sidebar ─────────┬ Cabeçalho: localização · busca UC · acesso à IA              ┐
│ Marca           ├ Cabeçalho da página: categoria · título · descrição · ações  │
│ Grupos de links │ Conteúdo: painéis, formulários, tabelas ou estado da página  │
│                 │                                                            │
│ Rodapé da marca ├ Rodapé da área de trabalho                                  │
└─────────────────┴────────────────────────────────────────────────────────────┘
```

- Sidebar fixa: **248px expandida / 76px recolhida**.
- Cabeçalho: **72px** no desktop e tablet; **60px** no mobile.
- Conteúdo: largura máxima de **1664px incluindo o padding**, centralizado.
- Padding lateral: **32px** a partir de 1280px, **24px** entre 768 e 1279px
  e **16px** abaixo de 768px.
- Padding superior do conteúdo: 34px no desktop/tablet, 40px a partir de 1600px
  e 26px no mobile.
- Marca na sidebar: “V-Energy” na primeira linha e “Grid 360” abaixo.
- Rodapé discreto, com separador e nome da plataforma.

### Breakpoints

| Largura | Comportamento |
| --- | --- |
| ≥1280px | Sidebar expandida por padrão, com opção de recolher; cabeçalho completo |
| 1024–1279px | Sidebar ainda recolhível; busca e ações do cabeçalho mais compactas |
| 768–1023px | Sidebar automaticamente recolhida para 76px, com ícones |
| <768px | Sidebar substituída por menu modal lateral; ações compactas e conteúdo empilhado |

No mobile, o menu usa um `dialog` nativo com largura `min(290px, 88vw)`.
Deve fechar ao navegar, pressionar Escape, clicar no fundo ou voltar à largura de desktop/tablet.
A busca global em campo é substituída por um link para a página da UC.

Novas telas devem funcionar a partir de 320px sem rolagem horizontal da página.
Quando uma tabela exigir mais largura, restringir a rolagem ao seu contêiner.
Filtros e ações devem quebrar linha ou empilhar antes de comprimir o texto.

### Cabeçalho e navegação

- Breadcrumb com grupo e página atual; no mobile, priorizar o nome da página.
- Busca global de UC e atalho `Ctrl/Cmd + K` já existentes.
- Acesso “Perguntar à IA” direciona para `/assistente`.
- A sidebar deve mostrar apenas rotas disponíveis e destacar o item correspondente à rota atual.

## 5. Componentes e estados

### Reutilizar a base existente

| Componente | Uso |
| --- | --- |
| `AppShell` | Estrutura comum; as páginas entram pelo `Outlet` |
| `PageHeader` | Categoria, título, descrição e ações opcionais |
| `Panel` | Superfície com título, descrição e ações opcionais |
| `EmptyState` | Ícone, título, explicação e ação opcional; variante compacta |
| `UnitSearch` | Busca por identificador de UC; variante compacta para o cabeçalho |
| `UnderDevelopmentPage` | Aviso temporário das quatro telas atuais |

Há estilos compartilhados para botões primários/secundários, badges e links.
KPI, gráficos, tabelas, filtros, drawer, chat e insights completos ainda precisam
ser implementados; os padrões abaixo orientam sua aparência.

- **KPI:** rótulo, unidade, valor e comparação explícita entre períodos.
- **Gráfico:** título, período, legenda e estados de carregamento, vazio e erro.
- **Tabela:** cabeçalhos claros, ordenação identificável, filtros e paginação
  quando necessários; alinhar números para facilitar comparação.
- **Filtros:** rótulos acessíveis, seleção visível e ação para limpar quando houver filtros ativos.
- **Ordens:** usar os rótulos Pendente, Em campo, Concluída e Cancelada,
  correspondentes a `PENDENTE`, `EM_CAMPO`, `CONCLUIDA` e `CANCELADA` no backend.
- **Insight IA:** ícone, identificação “Gerado por IA”, texto fundamentado,
  horário e acesso às fontes ou dados usados, quando a funcionalidade estiver disponível.

### Comportamento e acessibilidade

- Foco global: contorno de 2px em amarelo, offset de 4px. Campos agrupados usam
  borda amarela e contorno de 2px com offset de 2px em `:focus-within`.
- Desabilitado: opacidade de 40% e ação indisponível de fato.
- Manter labels acessíveis e nomes em botões com apenas ícones.
- Navegação por teclado, link “Pular para o conteúdo” e foco no conteúdo após troca de rota.
- Respeitar `prefers-reduced-motion`; não usar animações indispensáveis à compreensão.
- Carregamento, ausência de registros, falha e indisponibilidade são estados distintos.
- Não representar ausência de dados como zero nem criar resultados ou alertas fictícios.
- Confirmar ações destrutivas e irreversíveis; mensagens de sucesso só após a operação ser concluída.

### Ícones e gráficos

Usar **Lucide**, em geral com traço de 1.5–1.6px e tamanho de 16–20px.
Ícones decorativos devem ser ocultados das tecnologias assistivas.

Para gráficos futuros, **Recharts** é uma sugestão da ideação e ainda não está instalado.
Usar a série principal em amarelo, a comparativa em cinza e cores semânticas somente
quando acrescentarem significado. Grade discreta, sem 3D ou gradientes.
Waterfall para preço × volume; barras horizontais para rankings.

## 6. Organização das páginas

### Rotas atuais

| Grupo | Página | Rota |
| --- | --- | --- |
| Visão geral | Dashboard Executivo | `/` |
| Análises | Visão 360 da UC | `/uc` e `/uc/:id` |
| Operações | Ordens de Inspeção | `/inspecoes/ordens` |
| Inteligência | Assistente IA | `/assistente` |

As quatro páginas permanecem com o aviso “Em desenvolvimento”.
A busca global navega para a rota da UC, mas ainda não consulta o backend.

### Organização proposta para expansão

Análise de Receita (`/receita`) e Qualidade da Rede (`/rede`) pertencem ao grupo
Análises; Fila de Suspeitos (`/inspecoes/suspeitos`), ao grupo Operações.
Essas rotas ainda não estão registradas. Novas páginas devem reutilizar o layout
compartilhado e ser adicionadas à configuração de navegação quando implementadas.
