# Auditoria do Assistente de IA

## Objetivo

A auditoria registra, por requisição, o resultado e o caminho percorrido pelo pipeline do assistente. A interface do chat exibe o resumo da própria resposta; esta entrega não cria uma consulta administrativa ao histórico global.

## Etapas registradas

| Código | Etapa | Evidência exibida |
|---|---|---|
| C1 | Validação de entrada | Aprovação, bloqueio ou erro e duração |
| C2 | Cache e memória | Cache hit, cache desabilitado/não consultado ou consulta sem resultado reutilizável |
| C3 | Seleção e fallback | Tentativas agregadas dos provedores |
| C4.1 | Geração SQL | Resultado da geração |
| C4.2 | Validação SQL | Aprovação ou motivo de bloqueio |
| C4.3 | Execução SQL | Linhas, truncamento, duração, erro ou cache pós-SQL |
| C4.4 | Síntese | Resultado da síntese ou falha do provedor |
| C5 | Guardrail de saída | Resposta aprovada ou bloqueada |
| C6 | Pós-processamento | Preparação da resposta e visualização |
| C7 | Finalização | Situação da persistência da auditoria |

A duração total (`duracao_ms`) é medida do início do pipeline até imediatamente antes da finalização C7. As durações por etapa são preenchidas quando a etapa dispõe de uma medição direta; ausência de duração não significa duração zero.

## Persistência

A auditoria é gravada na tabela `agent_audit`, no banco operacional `portal.db`. Os campos existentes permanecem preservados. Na primeira gravação após a atualização, `SQLiteAuditStore` verifica o esquema e adiciona, quando necessário, as colunas `stage`, `duration_ms`, `provider_attempts` e `steps` por `ALTER TABLE`.

`provider_attempts` e `steps` são armazenados como JSON. A gravação é executada fora do event loop. Falhas de auditoria não devem impedir a entrega de uma resposta já aprovada pelo pipeline.

Se o `audit_store` não estiver configurado, a resposta informa persistência indisponível; a finalização ainda deve processar memória e cache quando esses stores estiverem configurados.

## Contrato HTTP

`POST /api/ia/perguntar` mantém os campos anteriores (`status`, `resposta`, `sql_executado`, `fontes` e `visualizacao`) e acrescenta `auditoria`:

- `request_id`: identificador da requisição;
- `resultado`: outcome final;
- `etapa_final`: etapa na qual o fluxo terminou;
- `duracao_ms`: duração do pipeline antes da C7;
- `cache_hit` e `regeneracoes`;
- `linhas_retornadas` e `resultado_truncado`;
- `persistencia`: `salva`, `falha` ou `indisponivel`;
- `etapas`: lista cronológica de códigos, status, detalhe e duração quando disponível;
- `tentativas_provedor`: fase, provedor, modelo, número da tentativa, horário, sucesso, latência e tipo de erro.

Para respostas aprovadas, `sql_executado` contém a consulta gerada e validada que fundamenta a resposta; `fontes` contém apenas nomes presentes na lista de tabelas autorizadas. Quando o resultado foi recuperado do cache pós-SQL, a consulta é exibida como proveniência do resultado, embora não tenha sido reexecutada fisicamente naquela requisição.

Para respostas sem aprovação, a API não devolve SQL nem fontes, mesmo que exista uma tentativa de consulta interna. O objeto de auditoria, entretanto, informa as etapas concluídas/bloqueadas e as tentativas disponíveis.

## Interface

O componente `AuditoriaResposta` é exibido dentro da mensagem correspondente do assistente, por meio de um painel expansível chamado **Auditoria desta resposta**. Ele mostra:

- resultado e etapa final;
- duração total e linhas retornadas;
- uso de cache, regenerações e estado da persistência;
- rastro C1–C7;
- tentativas dos provedores;
- SQL e tabelas de origem quando a resposta foi aprovada.

A interface exibe apenas a auditoria da resposta recebida naquela conversa. Não há endpoint de listagem global do `agent_audit` nesta entrega.

## Segurança e privacidade

- Não se expõe SQL de consultas bloqueadas ou respostas não aprovadas.
- As fontes são extraídas do SQL validado e filtradas pela allowlist do agente.
- Detalhes de erro enviados à interface são tipos/categorias, não mensagens brutas do banco ou stack traces.
- A auditoria persistida contém pergunta, SQL, resposta final e identificadores de sessão/requisição; o acesso direto ao banco deve permanecer restrito ao ambiente operacional.
- Uma tela administrativa com histórico global exige autenticação, autorização por perfil e política de retenção antes de ser implementada.

## Validação

Testes adicionados/atualizados cobrem serialização dos metadados da auditoria, migração aditiva do esquema existente, preservação de registros antigos, rastro do pipeline, metadados de execução no fluxo de esclarecimento, contrato HTTP e renderização do componente do frontend.

Antes de integrar, executar no ambiente do projeto:

```bash
cd backend
pytest -q tests/agent/test_sqlite_audit.py tests/agent/test_pipeline.py tests/agent/test_sql_execution_orchestrator.py tests/test_api.py

cd ../frontend
npm test
npm run build
npm run lint
```

A suíte completa depende das dependências declaradas em `backend/requirements.txt` e `frontend/package-lock.json`.
