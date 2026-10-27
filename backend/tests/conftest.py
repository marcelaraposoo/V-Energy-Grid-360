"""Configuração global dos testes.

O banco do portal (ordens de inspeção) roda em memória nos testes: assim eles nunca escrevem em
`data/portal.db` (o banco de desenvolvimento) nem herdam ordens de execuções anteriores.
Este arquivo precisa vir antes de qualquer import de `app`, porque `settings` é lido na importação.
"""
import os

os.environ["PORTAL_DB_PATH"] = ":memory:"
