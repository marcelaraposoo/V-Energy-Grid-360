# Backend — V-Energy Grid 360 (FastAPI)

API do portal. Por enquanto roda com **dados mockados** (`DATA_SOURCE=mock`); quando a camada Gold estiver
pronta, basta implementar `app/repositories/sqlite_repo.py` e trocar para `DATA_SOURCE=sqlite`.

## Rodar
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```
Docs interativas: http://localhost:8000/docs · Testes: `pytest`

## Estrutura
```
app/
  main.py            # app, CORS (front em :5173), handlers 404/409
  core/              # config (.env) e erros de domínio
  mock/              # gerador determinístico de dados fake
  repositories/      # acesso a dados: base (contrato), mock_repo, sqlite_repo (TODO)
  services/          # regras de negócio (receita, dashboard, unidades, perdas, continuidade, ia)
  routers/           # endpoints finos que só chamam services
  schemas.py         # modelos Pydantic (contrato com o frontend)
tests/               # pytest
docs/contrato-gold.md
```

## Endpoints (`/api`)
| Método | Rota | Tela / user story |
|---|---|---|
| GET | `/filtros` | selects de filtros |
| GET | `/dashboard/kpis`, `/dashboard/serie` | visão do diretor |
| GET | `/receita/variacao?agrupar_por=municipio\|bairro\|classe` | efeito preço × volume (drill-down) |
| GET | `/unidades?q=`, `/unidades/{uc}/visao-360` | atendente |
| GET | `/perdas/fila` | fila priorizada |
| POST/GET | `/perdas/ordens`, `/{id}/iniciar`, `/{id}/resultado`, `/{id}/cancelar` | ordens de inspeção |
| GET | `/continuidade/alimentadores`, `/alimentadores/{id}/serie` | DEC/FEC |
| POST/GET | `/ia/perguntar` (stub), `/ia/insights?tela=` | módulo de IA |

Filtros comuns: `municipio`, `bairro`, `classe`; períodos: `base_inicio/base_fim/atual_inicio/atual_fim` (`YYYY-MM`).
Padrão: base = primeiros 12 meses, atual = últimos 12 (como na pergunta do diretor).

## Premissas
- Mock: 400 UCs, 48 competências (2022-10 a 2026-09); ordens de inspeção ficam em memória (reiniciam com o servidor).
- Efeito-preço inclui reajuste + bandeira + mix de classes.
- DEC/FEC simplificados conforme o enunciado.
- UC com ordem ativa sai da fila de suspeitas; score de prioridade = probabilidade × kWh/mês recuperável.
