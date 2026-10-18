# V-Energy Grid 360 — contexto para assistentes de IA

> Arquivo lido automaticamente por Codex, Cursor, Copilot, Gemini CLI e outros. O `CLAUDE.md` apenas aponta para cá — edite sempre este arquivo.

Projeto do case final do Rocket Lab 2026.2 (Visagio). Plataforma que consolida dados de uma
distribuidora de energia (cadastro, medição, faturamento, rede e atendimento) e responde
à pergunta da diretoria: **por que a receita subiu só ~8% se a tarifa subiu 10,5% e o volume
faturado caiu ~4%?**

## Estrutura do repositório

| Pasta | Conteúdo | Frente |
|---|---|---|
| `data-engineering/` | Notebooks Databricks (Bronze → Silver → Gold) e YAML do Workflow | Dados |
| `backend/` | API FastAPI do portal | Dev |
| `frontend/` | React + TypeScript (Vite) | Dev |
| `ai-agent/` | Agente Text-to-SQL | IA |
| `docs/` | Dicionário de dados, log de qualidade, contrato da Gold, diagnóstico da receita | Todos |

Cada pasta pode ter o próprio `AGENTS.md` com regras específicas. Leia o da pasta em que for trabalhar.

## Regras gerais

- Idioma: português (código pode ter nomes em português, sem acentos).
- Nunca versionar dados brutos, o PDF do case ou credenciais (ver `.gitignore`).
- Uma branch por tarefa (`dados/...`, `dev/...`, `ia/...`), PR para `main` com 1 revisão.
- Não invente números: toda afirmação sobre os dados precisa vir de uma consulta.
