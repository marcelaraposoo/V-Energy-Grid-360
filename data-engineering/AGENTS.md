# Frente de Dados — regras para assistentes de IA

Seguimos o padrão de Arquitetura Medalhão ensinado pela Visagio no Rocket Lab
(aula prática com o dataset Olist), com os ajustes justificados abaixo.

## Ambiente

- **Databricks Free Edition** (serverless). Cada integrante tem a própria conta;
  o código é compartilhado pelo GitHub (Git folders).
- Linguagem: **PySpark**. pandas só para ler o Excel de inspeções e para exploração local.
- Em serverless **não use** `sparkContext`, RDDs, `input_file_name()` nem `.cache()`.
  Para saber o arquivo de origem, use `_metadata.file_path`.
- Notebooks em `.ipynb`.
- Não há integração direta IA ↔ Databricks: o código é escrito localmente,
  vai para o GitHub (push) e é executado no Databricks (pull no Git folder).

## Onde ficam as coisas

| Item | Local |
|---|---|
| Catalog | `v_energy` |
| Schemas | `v_energy.bronze`, `v_energy.silver`, `v_energy.gold` |
| Arquivos brutos (Landing) | Volume `/Volumes/v_energy/bronze/landing/` (leituras em `landing/leituras/`) |

Todo notebook começa com a **célula de parâmetros** (copiada do `00_organizacao_do_ambiente`):

```python
catalog = "v_energy"
bronze_schema = f"{catalog}.bronze"
silver_schema = f"{catalog}.silver"
gold_schema = f"{catalog}.gold"
landing_path = f"/Volumes/{catalog}/bronze/landing"
```

## Notebooks

| Notebook | Conteúdo | Responsável |
|---|---|---|
| `00_organizacao_do_ambiente` | Catalog, schemas, volume, validação da Landing | Aimê |
| `01_ingestao_bronze` | Leitura pura das 8 fontes → Delta | Aimê |
| `02_silver_<tabela>` | Um notebook por tabela (evita conflito entre as 3 pessoas) | dona da tabela |
| `03_gold_<tema>` | Tabelas de negócio | dona do tema |
| `04_export_banco_local` | Gold → CSV → banco do portal | bloco C |

## Regras por camada

### Bronze
- Leitura pura + gravação Delta com `mode("overwrite")`, **sem regra de negócio**.
- Colunas de auditoria: `ingestion_timestamp` (`current_timestamp()`) e `source_file`.
- **Tudo lido como string** (sem `inferSchema`). Diferente da aula: os dados da V-Energy são
  sujos (decimal com vírgula, datas em formatos mistos, códigos com zeros à esquerda) e a
  inferência alteraria o conteúdo original — o case exige preservá-lo exatamente.
- Nomes de colunas normalizados para snake_case sem acento (o Delta não aceita espaços).
- JSON aninhado: estrutura preservada (arrays/structs) com `primitivesAsString`; abertura em tabelas só na Silver.
- Excel (`inspecoes.xlsx`): lido com pandas (`dtype=str`); as 3 abas têm o mesmo layout e são
  unidas em `bronze.inspecoes`, com a coluna `aba_origem`.
- Toda execução registra contagens e checagem de integridade em `bronze.controle_ingestao`.

### Silver (padrão da aula `02_Bronze_to_Silver`)
- Uma **célula markdown antes de cada tratamento** listando as decisões
  (deduplicação, nulos, conversões, colunas derivadas) e o porquê.
- Pipeline encadeado: `dropDuplicates` → filtros → padronização (`upper`/`trim`) →
  `cast` (valores monetários em `decimal`, datas com `to_timestamp`/`to_date`) → colunas derivadas.
- Nulos: distinguir **nulo estrutural** (registro inutilizável → descartar) de
  **nulo de negócio** (tem significado → preservar). Nem todo nulo deve ser preenchido.
- **Checagens de qualidade** com as funções `dq_check` / `dq_check_unique` antes de gravar,
  e resultados persistidos na tabela `silver.dq_log` (append).
- **Melhoria em relação à aula:** todo filtro que descarta linhas deve imprimir a contagem
  antes e depois, e a decisão vai para `docs/data_quality_log.md`.
- Terminar com `display` da Bronze e da Silver lado a lado.

### Gold (padrão da aula `03_Silver_to_Gold`)
- Modelo dimensional: `dim_*` (com chave substituta `*_sk`) e `fato_*` com granularidade
  explícita na célula markdown. Tabelas agregadas adicionais para o portal quando necessário.
- Terminar com uma consulta de teste provando que fato e dimensões se conectam.
- Segue o contrato em `docs/gold_contract.md`. Mudanças no contrato avisam Dev e IA.

## Ao gerar código
- Consulte o schema real antes de referenciar colunas — não invente nomes.
- Confira fórmulas de negócio (DEC/FEC, efeito preço × volume) antes de implementar.
- Evite `monotonically_increasing_id` para chaves (não é determinístico); use `row_number`.
