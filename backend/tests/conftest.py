"""Configuração global dos testes.

O banco do portal (ordens de inspeção) roda em memória nos testes: assim eles nunca escrevem em
`data/portal.db` (o banco de desenvolvimento) nem herdam ordens de execuções anteriores.
Os testes também usam sempre os dados mockados, mesmo com `DATA_SOURCE=sqlite` no `.env`: eles
conferem regras sobre dados conhecidos. Os testes do SQLite montam bancos próprios ou abrem o
`gold.db` pelo caminho, e o `load_dotenv` não sobrescreve variáveis já definidas aqui.
Este arquivo precisa vir antes de qualquer import de `app`, porque `settings` é lido na importação.
"""
import os

os.environ["PORTAL_DB_PATH"] = ":memory:"
os.environ["DATA_SOURCE"] = "mock"
