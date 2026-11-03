"""Repositório sobre o SQLite exportado da camada Gold (`data/gold.db`).

Cobre cadastro, catálogos, medidor e GD pela dim_uc; consumo e faturas da UC pela
fato_consumo_faturamento; trocas de medidor pela A6; rede pelas A7/A8; atendimentos pela B1;
fila de suspeitas pela fila_inspecao.
Dashboard: leitura mensal das agregadas kpis_mensal (A5) e fato_segmento_mensal (A3);
a integração dessas leituras aos endpoints ainda está pendente.
A consulta paginada de faturas
faz contagens em SQL e usa LIMIT/OFFSET. Métodos ainda não integrados ou tabelas ausentes
levantam `NaoDisponivelNaGold` (HTTP 501), sem apresentar indisponibilidade como histórico vazio.

Decisões:
- Conexão aberta a cada chamada e SOMENTE LEITURA (`mode=ro`): a exportação da Gold pode trocar o arquivo
  a qualquer momento e o portal nunca escreve na Gold. As ordens de inspeção vivem em `portal.db`
  (ver ordens_store.py) e os métodos de ordens delegam para lá.
- Leitura tolerante: coluna opcional ausente vira None, e booleanos aceitam 1/0, true/false e t/f.
  O formato exato do export (`04_export_banco_local`) ainda não existe.
- LGPD: a `dim_uc` só tem colunas mascaradas; nada aqui lê nome ou documento completos.
- `competencias()` vem do período coberto pelas leituras (primeiro e último mês da `dim_uc`).
"""
from __future__ import annotations

import sqlite3
import unicodedata
from contextlib import closing
from pathlib import Path

from app.core.errors import NaoDisponivelNaGold
from app.repositories.atendimento import atendimento_publico
from app.repositories.base import OrdensStore
from app.repositories.dashboard import COLUNAS_KPIS, COLUNAS_SEGMENTOS, COLUNAS_TEXTO, validar_filtro_bairro
from app.repositories.faturamento import FAIXA_ANTIGA, FAIXAS_RECENTES, TAMANHO_PAGINA, consumo_publico, fatura_publica
from app.repositories.ordens_store import MemoriaOrdensStore
from app.repositories.rede import ocorrencia_publica

TABELA_UC = "dim_uc"
TABELA_FILA = "fila_inspecao"
TABELA_FATURAMENTO = "fato_consumo_faturamento"
COLUNAS_OBRIGATORIAS = ("id_uc", "nome_titular_mascarado", "municipio", "bairro", "classe", "alimentador")
COLUNAS_GD_MESMAS_UCS = ("id_uc", "mes_referencia", "possui_gd_no_mes", "consumo_kwh", "municipio", "bairro", "classe")
# Mesma tolerância de `_bool`: o booleano pode chegar como 0/1, 1.0 ou texto, conforme a exportação.
VERDADEIROS = ("1", "1.0", "true", "t", "sim", "s", "yes", "y")

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


def _codigo(valor: str) -> str:
    """UC e alimentador vêm em maiúsculas na Gold. Normalizar a entrada, em vez de comparar com
   , deixa o SQLite usar os índices (sem isso, a A2 inteira era lida a cada UC)."""
    return valor.strip().upper()


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
                f"SELECT * FROM {TABELA_UC} WHERE id_uc = ? LIMIT 1", (_codigo(uc_id),)
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
            "possui_gd": None if d.get("possui_gd") is None else _bool(d["possui_gd"]),
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

    # ---------- dashboard (A5/A3) ----------
    def _dashboard_mensal(self, tabela, colunas, inicio, fim, municipio=None, bairro=None, classe=None):
        # Tabela, colunas e ordenação vêm somente das constantes internas A5/A3.
        # Todos os valores recebidos do chamador usam parâmetros SQL.
        cond = ["mes_referencia BETWEEN ? AND ?"]
        args = [inicio, fim]
        for coluna, valor in (("municipio", municipio), ("bairro", bairro), ("classe", classe)):
            if valor is not None:
                cond.append(f"{coluna} = ?")
                args.append(valor)
        ordem = [c for c in ("mes_referencia", "municipio", "bairro", "classe") if c in colunas]
        with closing(self._conectar()) as con:
            disponiveis = {r["name"] for r in con.execute(f"PRAGMA table_info({tabela})")}
            if not disponiveis:
                raise _sem_gold("Dados mensais do Dashboard", tabela)
            faltantes = [c for c in colunas if c not in disponiveis]
            if faltantes:
                raise NaoDisponivelNaGold(
                    f"A tabela {tabela} está incompleta para o Dashboard. Colunas ausentes: {', '.join(faltantes)}."
                )
            registros = con.execute(
                f"SELECT {', '.join(colunas)} FROM {tabela} WHERE {' AND '.join(cond)} ORDER BY {', '.join(ordem)}",
                args,
            ).fetchall()
        linhas = []
        for registro in registros:
            linha = {}
            for coluna in colunas:
                valor = registro[coluna]
                if coluna not in COLUNAS_TEXTO:
                    valor = _num(valor)
                    if valor is not None and coluna.startswith("qtd_"):
                        valor = int(valor)
                linha[coluna] = valor
            linhas.append(linha)
        return linhas

    def kpis_mensais(self, inicio, fim):
        return self._dashboard_mensal("kpis_mensal", COLUNAS_KPIS, inicio, fim)

    def segmentos_mensais(self, inicio, fim, municipio=None, bairro=None, classe=None):
        validar_filtro_bairro(municipio, bairro)
        return self._dashboard_mensal("fato_segmento_mensal", COLUNAS_SEGMENTOS, inicio, fim, municipio, bairro, classe)

    # ---------- receita: GD nas mesmas UCs (A2) ----------
    def gd_mesmas_ucs(self, base_inicio, base_fim, atual_inicio, atual_fim, municipio=None, bairro=None, classe=None):
        """UCs com GD na última competência do período atual e o volume delas nos dois períodos.
        None se a A2 não foi exportada: o fator só complementa a A3, então a tela segue sem ele."""
        validar_filtro_bairro(municipio, bairro)
        cond = ["mes_referencia = ?", f"lower(trim(CAST(possui_gd_no_mes AS TEXT))) IN ({', '.join('?' * len(VERDADEIROS))})"]
        args = [atual_fim, *VERDADEIROS]
        for coluna, valor in (("municipio", municipio), ("bairro", bairro), ("classe", classe)):
            if valor is not None:
                cond.append(f"{coluna} = ?")
                args.append(valor)
        with closing(self._conectar()) as con:
            disponiveis = {r["name"] for r in con.execute(f"PRAGMA table_info({TABELA_FATURAMENTO})")}
            if not disponiveis:
                return None
            faltantes = [c for c in COLUNAS_GD_MESMAS_UCS if c not in disponiveis]
            if faltantes:
                raise NaoDisponivelNaGold(f"A tabela {TABELA_FATURAMENTO} está incompleta. Colunas ausentes: {', '.join(faltantes)}.")
            r = con.execute(f"""
                WITH gd AS (SELECT DISTINCT id_uc FROM {TABELA_FATURAMENTO} WHERE {' AND '.join(cond)})
                SELECT (SELECT COUNT(*) FROM gd) AS qtd_ucs,
                       COALESCE(SUM(CASE WHEN f.mes_referencia BETWEEN ? AND ? THEN f.consumo_kwh END), 0) AS energia_base_kwh,
                       COALESCE(SUM(CASE WHEN f.mes_referencia BETWEEN ? AND ? THEN f.consumo_kwh END), 0) AS energia_atual_kwh
                FROM {TABELA_FATURAMENTO} f JOIN gd ON gd.id_uc = f.id_uc
                WHERE f.mes_referencia BETWEEN ? AND ? OR f.mes_referencia BETWEEN ? AND ?
            """, (*args, base_inicio, base_fim, atual_inicio, atual_fim, base_inicio, base_fim, atual_inicio, atual_fim)).fetchone()
        return {"qtd_ucs": int(r["qtd_ucs"]), "energia_base_kwh": _num(r["energia_base_kwh"]) or 0.0,
                "energia_atual_kwh": _num(r["energia_atual_kwh"]) or 0.0}

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

    def trocas_medidor_uc(self, uc_id: str) -> list[dict]:
        tabela = "fato_troca_medidor"
        with closing(self._conectar()) as con:
            if not con.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (tabela,)).fetchone():
                raise _sem_gold("Trocas de medidor da UC", tabela)
            return [dict(r) for r in con.execute(f"""
                SELECT * FROM {tabela} WHERE id_uc = ?
                ORDER BY mes_troca DESC, id_medidor_novo DESC
            """, (_codigo(uc_id),))]

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

    # ---------- consumo e faturas da UC (A2) ----------
    def _faturamento_uc(self, uc_id):
        with closing(self._conectar()) as con:
            if not con.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (TABELA_FATURAMENTO,)).fetchone():
                raise _sem_gold("Consumo e faturas da UC", TABELA_FATURAMENTO)
            return [dict(r) for r in con.execute(f"""
                SELECT * FROM {TABELA_FATURAMENTO} WHERE id_uc = ?
                ORDER BY mes_referencia, id_fatura
            """, (_codigo(uc_id),))]

    def consumo_uc(self, uc_id):
        return consumo_publico([
            {**f, "troca_medidor": None if f["troca_medidor"] is None else _bool(f["troca_medidor"])}
            for f in self._faturamento_uc(uc_id)
        ])

    def faturas_uc(self, uc_id):
        linhas = self._faturamento_uc(uc_id)
        if not linhas:
            return []
        uc = self._linha_uc(uc_id)
        return [fatura_publica(f, uc) for f in linhas]

    def pagina_faturas_uc(self, uc_id, aba, ano, situacao, pagina):
        tabela = TABELA_FATURAMENTO
        uc_id = _codigo(uc_id)
        uc = self._linha_uc(uc_id)
        with closing(self._conectar()) as con:
            con.execute("BEGIN")
            if not con.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (tabela,)).fetchone():
                raise _sem_gold("Faturas da UC", tabela)
            resumo = dict(con.execute(f"""
                SELECT COALESCE(SUM(status_fatura = 'EM ABERTO' AND faixa_atraso IN (?, ?, ?)), 0)
                           AS pendencias_recentes,
                       COALESCE(SUM(status_fatura = 'EM ABERTO' AND faixa_atraso = ?), 0)
                           AS pendencias_antigas
                FROM {tabela} WHERE id_uc = ?
            """, (*FAIXAS_RECENTES, FAIXA_ANTIGA, uc_id)).fetchone())
            anos = [r[0] for r in con.execute(f"""
                SELECT DISTINCT CAST(substr(mes_referencia, 1, 4) AS INTEGER)
                FROM {tabela} WHERE id_uc = ? ORDER BY 1 DESC
            """, (uc_id,))]
            where = "id_uc = ?"
            params = [uc_id]
            if aba == "recentes":
                where += f""" AND mes_referencia IN (
                    SELECT DISTINCT mes_referencia FROM {tabela}
                    WHERE id_uc = ? ORDER BY mes_referencia DESC LIMIT 12
                ) AND (status_fatura = 'PAGA' OR (
                    status_fatura = 'EM ABERTO' AND faixa_atraso IN (?, ?, ?)
                ))"""
                params.extend((uc_id, *FAIXAS_RECENTES))
            else:
                if ano is not None:
                    where += " AND mes_referencia >= ? AND mes_referencia <= ?"
                    params.extend((f"{ano:04d}-01", f"{ano:04d}-12"))
                if situacao != "todas":
                    where += " AND status_fatura = ?"
                    params.append("PAGA" if situacao == "paga" else "EM ABERTO")
            total = con.execute(f"SELECT COUNT(*) FROM {tabela} WHERE {where}", params).fetchone()[0]
            linhas = con.execute(f"""
                SELECT * FROM {tabela} WHERE {where}
                ORDER BY mes_referencia DESC, id_fatura DESC LIMIT ? OFFSET ?
            """, (*params, TAMANHO_PAGINA, (pagina - 1) * TAMANHO_PAGINA)).fetchall()
        return {
            "itens": [fatura_publica(dict(f), uc) for f in linhas],
            "total": total, "pagina": pagina, "tamanho": TAMANHO_PAGINA,
            "resumo": resumo, "anos_disponiveis": anos,
        }

    # ---------- rede (A7 e A8) ----------
    def ocorrencias(self, inicio, fim, alimentador_id=None, municipio=None, uc_id=None):
        tabela = "fato_interrupcao"
        where = "mes_referencia BETWEEN ? AND ?"
        params = [inicio, fim]
        if alimentador_id is not None:
            where += " AND alimentador = ?"
            params.append(_codigo(alimentador_id))
        if municipio is not None:
            where += " AND municipio = ?"
            params.append(municipio)
        if uc_id is not None:
            where += " AND id_uc = ?"
            params.append(_codigo(uc_id))
        with closing(self._conectar()) as con:
            if not con.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (tabela,)).fetchone():
                raise _sem_gold("Ocorrências de rede", tabela)
            linhas = [dict(r) for r in con.execute(f"""
                SELECT * FROM {tabela} WHERE {where} ORDER BY data_hora_inicio, id_ocorrencia
            """, params)]
        return [ocorrencia_publica({**r, "causa_evitavel": _bool(r["causa_evitavel"])}) for r in linhas]

    def indicadores_continuidade(self, inicio, fim, alimentador_id=None, municipio=None):
        tabela = "dec_fec_alimentador_mensal"
        where = "mes_referencia BETWEEN ? AND ?"
        params = [inicio, fim]
        if alimentador_id is not None:
            where += " AND alimentador = ?"
            params.append(_codigo(alimentador_id))
        if municipio is not None:
            where += " AND municipio = ?"
            params.append(municipio)
        with closing(self._conectar()) as con:
            if not con.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (tabela,)).fetchone():
                raise _sem_gold("Indicadores de continuidade (DEC/FEC)", tabela)
            return [dict(r) for r in con.execute(f"""
                SELECT * FROM {tabela} WHERE {where} ORDER BY mes_referencia, alimentador
            """, params)]

    def ucs_afetadas_por_alimentador(self, inicio, fim, municipio=None):
        tabela = "fato_interrupcao"
        where = "mes_referencia BETWEEN ? AND ?"
        params = [inicio, fim]
        if municipio is not None:
            where += " AND municipio = ?"
            params.append(municipio)
        with closing(self._conectar()) as con:
            if not con.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (tabela,)).fetchone():
                raise _sem_gold("UCs afetadas por interrupções", tabela)
            return {r[0]: r[1] for r in con.execute(
                f"SELECT alimentador, COUNT(DISTINCT id_uc) FROM {tabela} WHERE {where} GROUP BY alimentador", params)}

    def causas_interrupcao(self, inicio, fim, alimentador_id=None, municipio=None):
        tabela = "fato_interrupcao"
        where = "mes_referencia BETWEEN ? AND ?"
        params = [inicio, fim]
        if alimentador_id is not None:
            where += " AND alimentador = ?"
            params.append(_codigo(alimentador_id))
        if municipio is not None:
            where += " AND municipio = ?"
            params.append(municipio)
        with closing(self._conectar()) as con:
            if not con.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (tabela,)).fetchone():
                raise _sem_gold("Causas das interrupções", tabela)
            linhas = [dict(r) for r in con.execute(f"""
                SELECT causa, causa_evitavel, COUNT(*) AS qtd, COALESCE(SUM(duracao_min), 0) AS minutos
                FROM {tabela} WHERE {where} GROUP BY causa, causa_evitavel
            """, params)]
        return [{**r, "causa_evitavel": _bool(r["causa_evitavel"])} for r in linhas]

    # ---------- atendimentos da UC (B1) ----------
    def atendimentos_uc(self, uc_id):
        tabela = "fato_atendimento"
        with closing(self._conectar()) as con:
            if not con.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (tabela,)).fetchone():
                raise _sem_gold("Atendimentos da UC", tabela)
            linhas = [dict(r) for r in con.execute(f"""
                SELECT * FROM {tabela} WHERE id_uc = ?
                ORDER BY data_hora_abertura DESC, protocolo DESC
            """, (_codigo(uc_id),))]
        return [atendimento_publico({**a, "aberto": _bool(a["aberto"])}) for a in linhas]

    # ---------- métodos ainda não integrados ----------
    def faturas(self, inicio, fim, municipio=None, bairro=None, classe=None):
        raise _sem_gold("Faturamento", TABELA_FATURAMENTO)

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
