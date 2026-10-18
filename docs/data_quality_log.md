# Log de qualidade de dados

Registro de todos os problemas de qualidade encontrados e da decisão tomada para cada um.
Este arquivo alimenta o dicionário de dados e a seção de suposições do README.

**Regra:** todo problema tratado na Silver precisa de uma linha aqui.

## Problemas confirmados

| # | Tabela | Coluna | Problema | Nº de linhas afetadas | Decisão | Justificativa | Responsável |
|---|---|---|---|---|---|---|---|
| 1 | medidores | data_ultima_manutencao | Coluna 100% vazia | 51.812 (100%) | Manter a coluna, sem uso em métricas | Não há informação na origem; para avaliar o medidor, usar a idade calculada a partir de `data_instalacao` | Aimê |
| 2 | medidores | data_retirada | Valor coringa `9999-12-31` em medidor ATIVO | 13.649 (26,3%) | Converter para `null` | Significa "não retirado": 100% dos casos têm status ATIVO; os 6.367 RETIRADOS têm data real e nenhum ATIVO tem data real | Aimê |

## Achados a investigar na Silver

Observados na inspeção dos arquivos (notebook `00`), ainda sem contagem. Quem for fazer a silver da tabela confirma, quantifica e move para a tabela acima.

| Tabela | Coluna | Observação |
|---|---|---|
| leituras | data_leitura | Formatos de data misturados (`2022-07-25`, `10/09/2022`) |
| leituras | consumo_kwh | Consumo diferente de `leitura_atual − leitura_anterior` em alguns casos (ex.: 431 vs 432) |
| inspecoes | data | Formatos misturados (`2025-08-01`, `14.08.2025`, `09-01-2025`) |
| inspecoes | resultado | Mesmo valor escrito de formas diferentes (`CONFIRMADA`, `IRREGULARIDADE CONFIRMADA`, `irregularidade confirmada`) |
| inspecoes | kwh_recuperado | Decimal com vírgula e com ponto na mesma coluna (`1313,70` e `838.10`) |
| inspecoes | tipo_irregularidade | `"-"` usado no lugar de nulo |
| inspecoes | inspetor | Espaços sobrando (`" INSP-006"`) |
| medidores | tipo | Variação de grafia (`ELETROMECANICO` e `Eletromecanico`) |
| medidores | modelo | Espaços sobrando (`"  EL-3000 "`) |
| unidades_consumidoras | uf | `PE` e `Pernambuco` |
| unidades_consumidoras | logradouro | Espaços no fim do texto |
| unidades_consumidoras / medidores | — | 45.445 medidores ativos para 46.461 UCs: verificar UCs sem medidor ativo e UCs com mais de um |
| unidades_consumidoras | cpf_cnpj, nome_titular | Dados pessoais: mascarar na Gold e no portal (LGPD) |
