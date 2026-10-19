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

## Estrutura

- `src/main.tsx`: ponto de entrada do React, com StrictMode.
- `src/App.tsx`: componente principal da aplicação.
- `src/index.css`: estilos globais.
- `src/App.css`: estilos do componente principal.
- `vite.config.ts`: configuração do Vite e do plugin React.
- `tsconfig*.json`: configurações TypeScript com modo estrito.
- `.oxlintrc.json`: configuração do lint.

Este setup contém somente a base do frontend. Telas de negócio e integração
com a API serão implementadas nas respectivas tarefas.