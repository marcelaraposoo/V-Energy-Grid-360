# Backend — V-Energy Grid 360 (FastAPI)

API do portal. Roda com **dados mockados** (`DATA_SOURCE=mock`, o padrão) ou, em parte, com a Gold local
(`DATA_SOURCE=sqlite`): hoje só a `dim_uc` está pronta (ver "Usar a Gold local").

## Rodar
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```
Docs interativas: http://localhost:8000/docs · Testes: `pytest`

## Usar a Gold local (parcial)
1. Coloque o `gold.db` exportado em `backend/data/` (ou aponte `SQLITE_PATH` no `.env`) e use `DATA_SOURCE=sqlite`.
2. O arquivo precisa ter a tabela `dim_uc` (colunas do notebook `03_gold_dim_uc`). O banco é aberto só para leitura.
3. O que responde com a Gold hoje: `/filtros` (municípios, bairros, classes, alimentadores e competências vêm da
   `dim_uc`) e `/unidades?q=` (busca por UC ou pelo nome mascarado, sem diferenciar acento).
4. O que depende de tabela que ainda não chegou devolve **501** com a tabela que falta no `detail`
   (`fato_consumo_faturamento`, `fato_atendimento`, `fato_interrupcao`, `fila_inspecao`). Para essas telas, use `mock`.
5. As ordens de inspeção continuam em `data/portal.db`, nos dois modos.

## Estrutura
```
app/
  main.py            # app, CORS (front em :5173), handlers 404/409
  core/              # config (.env) e erros de domínio
  mock/              # gerador determinístico de dados fake
  repositories/      # acesso a dados: base (contrato), mock_repo, sqlite_repo (parcial: dim_uc)
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
| GET | `/perdas/fila?q=&pagina=&tamanho=` | fila priorizada, com busca e paginação (total no cabeçalho `X-Total-Count`) |
| GET | `/perdas/fila/exportar?q=&municipio=&classe=&prob_minima=&limite=` | fila filtrada em CSV (`;`, UTF-8 com BOM, abre no Excel); `limite` padrão 500, máximo 5000 |
| POST/GET | `/perdas/ordens`, `/{id}/iniciar`, `/{id}/resultado`, `/{id}/cancelar` | ordens de inspeção |
| GET | `/continuidade/alimentadores`, `/alimentadores/{id}/serie` | DEC/FEC |
| POST/GET | `/ia/perguntar` (stub), `/ia/insights?tela=` | módulo de IA |

Filtros comuns: `municipio`, `bairro`, `classe`; períodos: `base_inicio/base_fim/atual_inicio/atual_fim` (`YYYY-MM`).
Padrão: base = primeiros 12 meses, atual = últimos 12 (como na pergunta do diretor).

### Diagnóstico de conta alta

`GET /api/unidades/{uc}/visao-360?comparacao=mes_anterior` aceita três modos:
- `mes_anterior`: última competência da base × competência imediatamente anterior;
- `ano_anterior`: última competência da base × mesmo mês do ano anterior;
- `trimestre_ano_anterior` (padrão): últimos três meses consecutivos × mesmos meses do ano anterior.

A resposta identifica as competências e separa totais, percentuais e classificações de consumo (kWh)
e faturamento (`valor_total`, R$). Dados ausentes e referência zero têm mensagens próprias.
Os limites das faixas ficam nas constantes `LIMITE_VARIACAO_PEQUENA_PCT` e
`LIMITE_VARIACAO_MODERADA_PCT`, em `app/services/unidades.py`. O histórico geral não depende desse filtro.

## Premissas
- Mock: 400 UCs, 48 competências (2022-10 a 2026-09); ordens de inspeção ficam no SQLite do portal (`data/portal.db`, criado sozinho) e sobrevivem a reinícios. Para zerar, pare o servidor e apague o arquivo. O caminho muda com `PORTAL_DB_PATH` no `.env`.
- Efeito-preço inclui reajuste + bandeira + mix de classes.
- DEC/FEC simplificados conforme o enunciado.
- UC com ordem ativa sai da fila de suspeitas; score de prioridade = probabilidade × kWh/mês recuperável.
