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
