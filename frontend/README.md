# Frontend — V-Energy Grid 360

React + TypeScript + Vite.

Requisitos: Node.js 24+ e npm. Com nvm, use `nvm use` neste diretório.

```bash
npm ci
npm run dev
```

Acesse http://localhost:5173 ou o endereço indicado no terminal.

- `npm run lint`: analisar o código com Oxlint.
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
a homologação da exportação oficial. O dashboard continua mockado no frontend para validação do design.
Ele inicia em jul/2025–jun/2026, sem referência; “Limpar” restaura essa seleção sem comparação.

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
