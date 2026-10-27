"""Armazém das ordens de inspeção.

As ordens pertencem ao PORTAL, não à camada Gold. Por isso ficam num banco próprio (`data/portal.db`),
separado do `gold.db`: quando a exportação da Gold sobrescrever o `gold.db`, as ordens continuam lá.

Duas implementações do mesmo contrato (`OrdensStore`, em base.py):
- `SqliteOrdensStore`: persistente, é a usada pela API.
- `MemoriaOrdensStore`: some quando o processo termina; serve a testes e experimentos.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from app.core.errors import ConflitoDeEstado, NaoEncontrado

ATIVAS = ("PENDENTE", "EM_CAMPO")
CAMPOS_ATUALIZAVEIS = frozenset({"status", "motivo", "observacoes", "resultado"})
MSG_ORDEM_ATIVA = "Já existe ordem de inspeção ativa para esta unidade"

_DDL = """
CREATE TABLE IF NOT EXISTS ordens_inspecao (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    uc_id         TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'PENDENTE'
                  CHECK (status IN ('PENDENTE', 'EM_CAMPO', 'CONCLUIDA', 'CANCELADA')),
    motivo        TEXT,
    observacoes   TEXT,
    criada_em     TEXT NOT NULL,
    atualizada_em TEXT NOT NULL,
    resultado     TEXT
);
CREATE INDEX IF NOT EXISTS ix_ordens_status ON ordens_inspecao (status);
-- no máximo uma ordem ativa por UC, mesmo com duas requisições simultâneas
CREATE UNIQUE INDEX IF NOT EXISTS ux_ordens_uc_ativa ON ordens_inspecao (uc_id)
    WHERE status IN ('PENDENTE', 'EM_CAMPO');
"""


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _erro_de_integridade(exc: sqlite3.IntegrityError) -> Exception:
    """UNIQUE = o índice de ordem ativa por UC; qualquer outra violação (ex.: status inexistente) é dado inválido."""
    if "UNIQUE" in str(exc):
        return ConflitoDeEstado(MSG_ORDEM_ATIVA)
    return ValueError(f"Dados inválidos para a ordem: {exc}")


class SqliteOrdensStore:
    """Ordens em SQLite. Uma conexão por processo, protegida por lock (o FastAPI roda rotas síncronas em threads)."""

    def __init__(self, path: str) -> None:
        if path != ":memory:":
            Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = threading.RLock()
        self._con = sqlite3.connect(path, check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        with self._lock, self._con:
            self._con.executescript(_DDL)

    def close(self) -> None:
        with self._lock:
            self._con.close()

    @staticmethod
    def _para_dict(linha: sqlite3.Row) -> dict:
        ordem = dict(linha)
        if ordem["resultado"] is not None:
            ordem["resultado"] = json.loads(ordem["resultado"])
        return ordem

    def criar(self, dados: dict) -> dict:
        agora = _agora()
        try:
            with self._lock, self._con:
                cur = self._con.execute(
                    "INSERT INTO ordens_inspecao (uc_id, status, motivo, observacoes, criada_em, atualizada_em) "
                    "VALUES (?, 'PENDENTE', ?, ?, ?, ?)",
                    (dados["uc_id"], dados.get("motivo"), dados.get("observacoes"), agora, agora),
                )
                novo_id = cur.lastrowid
        except sqlite3.IntegrityError as exc:
            raise _erro_de_integridade(exc) from exc
        return self.obter(novo_id)

    def listar(self, status: str | None = None) -> list[dict]:
        sql, params = "SELECT * FROM ordens_inspecao", ()
        if status is not None:
            sql, params = sql + " WHERE status = ?", (status,)
        with self._lock:
            linhas = self._con.execute(sql + " ORDER BY id", params).fetchall()
        return [self._para_dict(linha) for linha in linhas]

    def obter(self, ordem_id: int) -> dict | None:
        with self._lock:
            linha = self._con.execute("SELECT * FROM ordens_inspecao WHERE id = ?", (ordem_id,)).fetchone()
        return self._para_dict(linha) if linha else None

    def atualizar(self, ordem_id: int, campos: dict) -> dict:
        desconhecidos = set(campos) - CAMPOS_ATUALIZAVEIS
        if desconhecidos:
            raise ValueError(f"Campos não atualizáveis: {sorted(desconhecidos)}")
        valores = dict(campos)
        if valores.get("resultado") is not None:
            valores["resultado"] = json.dumps(valores["resultado"], ensure_ascii=False)
        colunas = [*valores, "atualizada_em"]
        sql = f"UPDATE ordens_inspecao SET {', '.join(f'{c} = ?' for c in colunas)} WHERE id = ?"
        try:
            with self._lock, self._con:
                cur = self._con.execute(sql, (*valores.values(), _agora(), ordem_id))
        except sqlite3.IntegrityError as exc:
            raise _erro_de_integridade(exc) from exc
        if cur.rowcount == 0:
            raise NaoEncontrado(f"Ordem {ordem_id} não encontrada")
        return self.obter(ordem_id)


class MemoriaOrdensStore:
    """Ordens só em memória (comportamento anterior do mock)."""

    def __init__(self) -> None:
        self._ordens: dict[int, dict] = {}
        self._seq = 0

    def criar(self, dados: dict) -> dict:
        self._seq += 1
        agora = _agora()
        ordem = {"id": self._seq, "status": "PENDENTE", "criada_em": agora, "atualizada_em": agora,
                 "resultado": None, **dados}
        self._ordens[self._seq] = ordem
        return ordem

    def listar(self, status: str | None = None) -> list[dict]:
        return [o for o in self._ordens.values() if status is None or o["status"] == status]

    def obter(self, ordem_id: int) -> dict | None:
        return self._ordens.get(ordem_id)

    def atualizar(self, ordem_id: int, campos: dict) -> dict:
        if ordem_id not in self._ordens:
            raise NaoEncontrado(f"Ordem {ordem_id} não encontrada")
        ordem = self._ordens[ordem_id]
        ordem.update(campos, atualizada_em=_agora())
        return ordem
