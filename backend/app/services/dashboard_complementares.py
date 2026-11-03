"""Visão geral: posição cadastral da A5 e consumo por classe da A3."""
from collections import defaultdict
from decimal import Decimal

from app.repositories.base import Repository
from app.schemas import CadastroGdMes, CadastroGdResponse, ConsumoClasse, ConsumoClassesResponse, Periodo
from app.services.dashboard import _arredondar, _comparar_valores, _competencias_periodo, _dividir, _somar_valores, _valor_monetario

CLASSES = ("RESIDENCIAL", "COMERCIAL", "INDUSTRIAL", "PODER PUBLICO", "RURAL")


def _numero(valor: Decimal | None) -> float | None:
    return float(_arredondar(valor, 2)) if valor is not None else None


def _posicao_cadastral(repo: Repository, competencia: str) -> CadastroGdMes:
    linhas = [r for r in repo.kpis_mensais(competencia, competencia) if r["mes_referencia"] == competencia]
    if len(linhas) > 1:
        raise ValueError(f"kpis_mensal possui mais de uma linha para {competencia}; o grão da A5 é um mês.")
    linha = linhas[0] if linhas else {}

    def quantidade(coluna):
        valor = _valor_monetario(linha.get(coluna))
        return int(valor) if valor is not None and valor == valor.to_integral_value() else None

    cadastradas = quantidade("qtd_ucs_cadastradas")
    gd = quantidade("qtd_ucs_com_gd")
    percentual = _dividir(Decimal(gd) * 100 if gd is not None else None,
                         Decimal(cadastradas) if cadastradas is not None else None)
    return CadastroGdMes(competencia=competencia, qtd_ucs_cadastradas=cadastradas,
                         qtd_ucs_com_gd=gd, percentual_gd=_numero(percentual))


def cadastro_gd(repo: Repository, base: Periodo | None, atual: Periodo) -> CadastroGdResponse:
    a = _posicao_cadastral(repo, atual.fim)
    b = _posicao_cadastral(repo, base.fim) if base else None
    comparacao = _comparar_valores(b.qtd_ucs_cadastradas if b else None, a.qtd_ucs_cadastradas, casas=0)
    return CadastroGdResponse(atual=a, referencia=b, variacao_cadastradas_pct=comparacao.variacao_pct)


def _consumo_periodo(repo: Repository, periodo: Periodo):
    competencias = _competencias_periodo(periodo)
    por_classe = defaultdict(lambda: defaultdict(list))
    chaves = set()
    for linha in repo.segmentos_mensais(periodo.inicio, periodo.fim, None, None, None):
        mes, classe = linha["mes_referencia"], linha["classe"]
        if mes not in competencias:
            continue
        if classe not in CLASSES:
            raise ValueError(f"Classe desconhecida na A3: {classe}.")
        chave = (mes, linha["municipio"], linha["bairro"], classe)
        if chave in chaves:
            raise ValueError(f"fato_segmento_mensal possui segmento duplicado: {chave}.")
        chaves.add(chave)
        por_classe[classe][mes].append(_valor_monetario(linha.get("consumo_kwh")))
    volumes, ausentes = {}, {}
    for classe in CLASSES:
        meses = por_classe[classe]
        ausentes[classe] = [mes for mes in competencias if mes not in meses]
        volumes[classe] = _somar_valores([_somar_valores(meses[mes]) for mes in competencias]) if not ausentes[classe] else None
    return volumes, ausentes


def consumo_classes(repo: Repository, base: Periodo | None, atual: Periodo) -> ConsumoClassesResponse:
    volumes, ausentes = _consumo_periodo(repo, atual)
    referencias, ausentes_base = _consumo_periodo(repo, base) if base else ({}, {})
    total = _somar_valores(list(volumes.values()))
    ordem = sorted(CLASSES, key=lambda classe: (volumes[classe] is None, -(volumes[classe] or Decimal(0))))
    linhas = []
    for classe in ordem:
        volume, referencia = volumes[classe], referencias.get(classe)
        participacao = _dividir(volume * 100 if volume is not None else None, total)
        comparacao = _comparar_valores(referencia, volume)
        linhas.append(ConsumoClasse(
            classe=classe, consumo_kwh=_numero(volume), participacao_pct=_numero(participacao),
            consumo_referencia_kwh=_numero(referencia), variacao_pct=comparacao.variacao_pct,
            competencias_ausentes=ausentes[classe], competencias_ausentes_referencia=ausentes_base.get(classe),
        ))
    return ConsumoClassesResponse(periodo_atual=atual, periodo_base=base, consumo_total_kwh=_numero(total), classes=linhas)
