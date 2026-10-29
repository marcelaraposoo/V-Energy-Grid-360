"""Repositório sobre o SQLite exportado da camada Gold (`data/gold.db`).

ETAPA 1 (esta): só o que a Gold já entrega na `main`, a `dim_uc` (1 linha = 1 UC). Cobre catálogos,
busca de UC, medidor ativo e geração distribuída. O que depende de tabelas que ainda não estão na `main`
(fato_consumo_faturamento, fato_interrupcao, fila_inspecao...) levanta `NaoDisponivelNaGold` (HTTP 501),
em vez de devolver lista vazia: vazio pareceria "UC sem consumo", e não "dado que ainda não chegou".

Decisões:
- Conexão aberta a cada chamada e SOMENTE LEITURA (`mode=ro`): a exportação da Gold pode trocar o arquivo
  a qualquer momento e o portal nunca escreve na Gold. As ordens de inspeção vivem em `portal.db`
  (ver ordens_store.py) e os métodos de ordens delegam para lá.
- Leitura tolerante: coluna opcional ausente vira None, e booleanos aceitam 1/0, true/false e t/f.
  O formato exato do export (`04_export_banco_local`) ainda não existe.
- LGPD: a `dim_uc` só tem colunas mascaradas; nada aqui lê nome ou documento completos.
- `competencias()` vem do período coberto pelas leituras (primeiro e último mês da `dim_uc`),
  já que a fato de faturamento ainda não está disponível.
"""
from __future__ import annotations

import sqlite3
import unicodedata
from contextlib import closing
from pathlib import Path

from app.core.errors import NaoDisponivelNaGold
from app.repositories.base import OrdensStore
from app.repositories.ordens_store import MemoriaOrdensStore

TABELA_UC = "dim_uc"
TABELA_FILA = "fila_inspecao"
COLUNAS_OBRIGATORIAS = ("id_uc", "nome_titular_mascarado", "municipio", "bairro", "classe", "alimentador")

DESCRICAO_CLASSE = {
    "RESIDENCIAL": "Residencial",
    "RURAL": "Rural",
    "COMERCIAL": "Comercial",
    "PODER PUBLICO": "Poder público",
    "INDUSTRIAL": "Industrial",
}


def _normalizar(texto) -> str:
    """Minúsculas e sem acento, para a busca ('jose' encontra 'JOSÉ')."""
    if texto is None:
        return ""
    sem_acento = "".join(c for c in unicodedata.normalize("NFD", str(texto)) if unicodedata.category(c) != "Mn")
    return sem_acento.casefold().strip()


def _bool(valor) -> bool:
    if valor is None:
        return False
    if isinstance(valor, (int, float)):
        return bool(valor)
    return str(valor).strip().lower() in ("1", "true", "t", "sim", "s", "yes", "y")


def _num(valor) -> float | None:
    if valor is None or valor == "":
        return None
    try:
        return float(str(valor).replace(",", "."))
    except ValueError:
        return None


def _motivos(texto) -> list[str]:
    """A Gold guarda os motivos numa frase só, separados por ';' (ex.: 'consumo caiu 60% ...; medidor com 22 anos')."""
    if texto is None:
        return []
    return [parte.strip() for parte in str(texto).split(";") if parte.strip()]


def _meses(inicio: str, fim: str) -> list[str]:
    """Lista 'yyyy-MM' de `inicio` a `fim`, inclusive."""
    try:
        ano, mes = int(inicio[:4]), int(inicio[5:7])
    except (TypeError, ValueError):
        return []
    saida = []
    while f"{ano:04d}-{mes:02d}" <= fim:
        saida.append(f"{ano:04d}-{mes:02d}")
        mes += 1
        if mes == 13:
            ano, mes = ano + 1, 1
    return saida


def _sem_gold(recurso: str, tabela: str) -> NaoDisponivelNaGold:
    return NaoDisponivelNaGold(
        f"{recurso} ainda não está disponível na Gold (depende de {tabela}). Use DATA_SOURCE=mock para esta tela."
    )


class SqliteRepository:
    def __init__(self, path: str, ordens: OrdensStore | None = None) -> None:
        arquivo = Path(path)
        if not arquivo.is_file():
            raise FileNotFoundError(
                f"Banco da Gold não encontrado: {arquivo}. Coloque o gold.db nesse caminho "
                "(SQLITE_PATH no .env) ou use DATA_SOURCE=mock."
            )
        # as_uri() codifica espaços e barras do Windows, e `mode=ro` abre só para leitura
        self._uri = f"{arquivo.resolve().as_uri()}?mode=ro"
        self._ordens = ordens if ordens is not None else MemoriaOrdensStore()
        self._validar_esquema(arquivo)

    # ---------- infraestrutura ----------
    def _conectar(self) -> sqlite3.Connection:
        con = sqlite3.connect(self._uri, uri=True)
        con.row_factory = sqlite3.Row
        con.create_function("norm", 1, _normalizar, deterministic=True)
        return con

    def _validar_esquema(self, arquivo: Path) -> None:
        with closing(self._conectar()) as con:
            colunas = {r["name"] for r in con.execute(f"PRAGMA table_info({TABELA_UC})")}
        if not colunas:
            raise RuntimeError(f"A tabela {TABELA_UC} não existe em {arquivo}.")
        faltam = [c for c in COLUNAS_OBRIGATORIAS if c not in colunas]
        if faltam:
            raise RuntimeError(f"A tabela {TABELA_UC} em {arquivo} não tem as colunas: {', '.join(faltam)}.")

    def _linha_uc(self, uc_id: str) -> dict | None:
        with closing(self._conectar()) as con:
            r = con.execute(
                f"SELECT * FROM {TABELA_UC} WHERE id_uc = ? COLLATE NOCASE LIMIT 1", (uc_id.strip(),)
            ).fetchone()
        return dict(r) if r else None

    @staticmethod
    def _uc_publica(d: dict) -> dict:
        """Nomes lógicos do portal (mesmos do mock) a partir das colunas da dim_uc."""
        classe = d["classe"]
        return {
            "uc_id": d["id_uc"],
            "titular": d["nome_titular_mascarado"],
            "documento_mascarado": d.get("documento_mascarado"),
            "tipo_pessoa": d.get("tipo_pessoa"),
            "classe": classe,
            "classe_descricao": DESCRICAO_CLASSE.get(classe, classe.title() if classe else None),
            "subgrupo_tarifario": d.get("subgrupo_tarifario"),
            "municipio": d["municipio"],
            "bairro": d["bairro"],
            "logradouro": d.get("logradouro"),
            "numero": d.get("numero"),
            "cep": d.get("cep"),
            "alimentador_id": d["alimentador"],
            "status": d.get("status"),
            "data_ligacao": d.get("data_ligacao"),
            "consumo_medio_12m_kwh": _num(d.get("consumo_medio_12m_kwh")),
            "variacao_consumo_12m_pct": _num(d.get("variacao_consumo_12m_pct")),
        }

    # ---------- catálogos ----------
    def competencias(self) -> list[str]:
        with closing(self._conectar()) as con:
            r = con.execute(f"SELECT MIN(primeiro_mes_leitura) AS i, MAX(ultimo_mes_leitura) AS f FROM {TABELA_UC}").fetchone()
        return _meses(r["i"], r["f"]) if r and r["i"] and r["f"] else []

    def municipios_bairros(self) -> dict[str, list[str]]:
        # a chave é o PAR município + bairro: o mesmo bairro existe em municípios diferentes
        with closing(self._conectar()) as con:
            linhas = con.execute(
                f"SELECT DISTINCT municipio, bairro FROM {TABELA_UC} "
                "WHERE municipio IS NOT NULL AND bairro IS NOT NULL ORDER BY municipio, bairro"
            ).fetchall()
        saida: dict[str, list[str]] = {}
        for r in linhas:
            saida.setdefault(r["municipio"], []).append(r["bairro"])
        return saida

    def classes(self) -> dict[str, str]:
        with closing(self._conectar()) as con:
            linhas = con.execute(
                f"SELECT DISTINCT classe FROM {TABELA_UC} WHERE classe IS NOT NULL ORDER BY classe"
            ).fetchall()
        return {r["classe"]: DESCRICAO_CLASSE.get(r["classe"], r["classe"].title()) for r in linhas}

    def alimentadores(self, municipio: str | None = None) -> list[dict]:
        """[{id, municipio, ucs_total}]. Se um alimentador atender mais de um município, `municipio`
        é o de mais UCs e `ucs_total` conta todas as UCs dele (é o denominador do DEC/FEC)."""
        with closing(self._conectar()) as con:
            linhas = con.execute(
                f"SELECT alimentador, municipio, COUNT(*) AS n FROM {TABELA_UC} "
                "WHERE alimentador IS NOT NULL GROUP BY alimentador, municipio"
            ).fetchall()
        por_alim: dict[str, list[tuple[int, str]]] = {}
        for r in linhas:
            por_alim.setdefault(r["alimentador"], []).append((r["n"], r["municipio"]))
        saida = []
        for alim in sorted(por_alim):
            partes = por_alim[alim]
            principal = max(partes, key=lambda p: (p[0], p[1] or ""))[1]
            if municipio is None or principal == municipio:
                saida.append({"id": alim, "municipio": principal, "ucs_total": sum(p[0] for p in partes)})
        return saida

    # ---------- unidades consumidoras (dim_uc) ----------
    def buscar_ucs(self, q: str | None, municipio: str | None, classe: str | None, limite: int) -> list[dict]:
        cond: list[str] = []
        args: list = []
        termo = _normalizar(q)
        if termo:
            padrao = "%" + termo.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            cond.append("(norm(id_uc) LIKE ? ESCAPE '\\' OR norm(nome_titular_mascarado) LIKE ? ESCAPE '\\')")
            args += [padrao, padrao]
        if municipio is not None:
            cond.append("municipio = ?")
            args.append(municipio)
        if classe is not None:
            cond.append("classe = ?")
            args.append(classe)
        where = f" WHERE {' AND '.join(cond)}" if cond else ""
        with closing(self._conectar()) as con:
            linhas = con.execute(f"SELECT * FROM {TABELA_UC}{where} ORDER BY id_uc LIMIT ?", (*args, limite)).fetchall()
        return [self._uc_publica(dict(r)) for r in linhas]

    def uc(self, uc_id: str) -> dict | None:
        d = self._linha_uc(uc_id)
        return self._uc_publica(d) if d else None

    def medidor_uc(self, uc_id: str) -> dict | None:
        d = self._linha_uc(uc_id)
        if not d or d.get("id_medidor_ativo") in (None, ""):
            return None  # a origem tem UCs sem medidor ativo
        return {
            "medidor_id": d["id_medidor_ativo"],
            "tipo": d.get("tipo_medidor_ativo"),
            "modelo": d.get("modelo_medidor_ativo"),
            "data_instalacao": d.get("data_instalacao_medidor"),
            "status": "ativo",
            "idade_anos": _num(d.get("idade_medidor_anos")),
            "trocado_recentemente": _bool(d.get("medidor_trocado_recentemente")),
        }

    def gd_uc(self, uc_id: str) -> dict | None:
        d = self._linha_uc(uc_id)
        if not d or not _bool(d.get("possui_gd")):
            return None
        return {
            "potencia_kwp": _num(d.get("potencia_gd_kwp")),
            "data_conexao": d.get("data_conexao_gd"),
            "modalidade": d.get("modalidade_gd"),
            # a Gold manda o valor com a flag: quando `atipica` é true, não é medida real (log G5)
            "energia_injetada_media_kwh": _num(d.get("energia_injetada_media_kwh")),
            "energia_injetada_atipica": _bool(d.get("energia_injetada_atipica")),
        }

    # ---------- ainda sem tabela na Gold ----------
    def faturas(self, inicio, fim, municipio=None, bairro=None, classe=None):
        raise _sem_gold("Faturamento", "fato_consumo_faturamento")

    def consumo_uc(self, uc_id):
        raise _sem_gold("Consumo da UC", "fato_consumo_faturamento")

    def faturas_uc(self, uc_id):
        raise _sem_gold("Faturas da UC", "fato_consumo_faturamento")

    def atendimentos_uc(self, uc_id):
        raise _sem_gold("Atendimentos da UC", "fato_atendimento")

    def ocorrencias(self, inicio, fim, alimentador_id=None, municipio=None, uc_id=None):
        raise _sem_gold("Ocorrências de rede", "fato_interrupcao")

    def indicadores_continuidade(self, inicio, fim, alimentador_id=None, municipio=None):
        raise _sem_gold("Indicadores de continuidade (DEC/FEC)", "dec_fec_alimentador_mensal")

    def suspeitas(self):
        """Fila de suspeitas da Gold (`fila_inspecao`, 1 linha = 1 UC), no formato que o serviço de perdas usa.

        - `prioridade` e `score` vêm prontos da Gold (regra versionada pelo time de Dados): o serviço respeita
          essa ordem em vez de recalcular.
        - SUPOSIÇÃO: o contrato da API tem `probabilidade` (0 a 1) e a Gold entrega `score` (0 a 100, "pontuação
          de suspeita"). Usamos score / 100 como probabilidade relativa até o time de Dados confirmar se o score
          é calibrado como probabilidade de irregularidade.
        - Linhas sem UC, score ou energia estimada são descartadas (não dá para ordenar nem priorizar).
        """
        with closing(self._conectar()) as con:
            existe = con.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (TABELA_FILA,)
            ).fetchone()
            if not existe:
                raise _sem_gold("Fila de suspeitas de perdas", TABELA_FILA)
            linhas = [dict(r) for r in con.execute(f"SELECT * FROM {TABELA_FILA}")]
        saida = []
        for d in linhas:
            score, kwh = _num(d.get("score")), _num(d.get("kwh_estimado_recuperar_mes"))
            if d.get("id_uc") in (None, "") or score is None or kwh is None:
                continue
            prioridade = _num(d.get("prioridade"))
            saida.append({
                "uc_id": str(d["id_uc"]).strip(),
                "motivos": _motivos(d.get("motivo")),
                "probabilidade": min(1.0, max(0.0, score / 100)),
                "energia_recuperavel_kwh_mes": max(0.0, kwh),
                "score": score,
                "prioridade": int(prioridade) if prioridade is not None else None,
            })
        return saida

    # ---------- ordens de inspeção: tabela do PORTAL (portal.db), não da Gold ----------
    def criar_ordem(self, dados):
        return self._ordens.criar(dados)

    def listar_ordens(self, status=None):
        return self._ordens.listar(status)

    def obter_ordem(self, ordem_id):
        return self._ordens.obter(ordem_id)

    def atualizar_ordem(self, ordem_id, campos):
        return self._ordens.atualizar(ordem_id, campos)
