"""Visão geral: posição cadastral (A5 ou A3 com município), consumo por classe (A3) e operação (B1 e A8)."""
from collections import defaultdict
from decimal import Decimal

from app.repositories.base import Repository
from app.schemas import (
    CadastroGdMes, CadastroGdResponse, ConsumoClasse, ConsumoClassesResponse, ConsumoLocal, ConsumoLocaisResponse,
    IndicadoresOperacao, OperacaoResponse, Periodo,
)
from app.services.continuidade import resumo_periodo
from app.services.dashboard import (
    _arredondar, _comparar_valores, _competencias_periodo, _dividir, _somar_coluna, _somar_valores, _valor_monetario,
)

CLASSES = ("RESIDENCIAL", "COMERCIAL", "INDUSTRIAL", "PODER PUBLICO", "RURAL")


def _numero(valor: Decimal | None) -> float | None:
    return float(_arredondar(valor, 2)) if valor is not None else None


def _posicao_cadastral(repo: Repository, competencia: str, municipio: str | None = None) -> CadastroGdMes:
    if municipio is not None:
        # A A5 não tem município: soma os segmentos (bairro × classe) do município na competência.
        segmentos = [r for r in repo.segmentos_mensais(competencia, competencia, municipio) if r["mes_referencia"] == competencia]
        linha = {coluna: _somar_coluna(segmentos, coluna) for coluna in ("qtd_ucs_cadastradas", "qtd_ucs_com_gd")} if segmentos else {}
    else:
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


def cadastro_gd(repo: Repository, base: Periodo | None, atual: Periodo, municipio: str | None = None) -> CadastroGdResponse:
    a = _posicao_cadastral(repo, atual.fim, municipio)
    b = _posicao_cadastral(repo, base.fim, municipio) if base else None
    comparacao = _comparar_valores(b.qtd_ucs_cadastradas if b else None, a.qtd_ucs_cadastradas, casas=0)
    return CadastroGdResponse(atual=a, referencia=b, variacao_cadastradas_pct=comparacao.variacao_pct)


def _consumo_periodo(repo: Repository, periodo: Periodo, municipio: str | None = None):
    competencias = _competencias_periodo(periodo)
    por_classe = defaultdict(lambda: defaultdict(list))
    chaves = set()
    for linha in repo.segmentos_mensais(periodo.inicio, periodo.fim, municipio, None, None):
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


def consumo_classes(repo: Repository, base: Periodo | None, atual: Periodo, municipio: str | None = None) -> ConsumoClassesResponse:
    volumes, ausentes = _consumo_periodo(repo, atual, municipio)
    referencias, ausentes_base = _consumo_periodo(repo, base, municipio) if base else ({}, {})
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



def _consumo_locais_periodo(repo: Repository, periodo: Periodo, municipio: str | None):
    """Energia da A3 por município (ou por bairro do município), com as regras das classes:
    um mês sem o local invalida o acumulado dele, que não vira zero."""
    competencias = _competencias_periodo(periodo)
    por_local = defaultdict(lambda: defaultdict(list))
    chaves = set()
    for linha in repo.segmentos_mensais(periodo.inicio, periodo.fim, municipio, None, None):
        mes = linha["mes_referencia"]
        if mes not in competencias:
            continue
        chave = (mes, linha["municipio"], linha["bairro"], linha["classe"])
        if chave in chaves:
            raise ValueError(f"fato_segmento_mensal possui segmento duplicado: {chave}.")
        chaves.add(chave)
        local = (linha["municipio"], linha["bairro"] if municipio else None)
        por_local[local][mes].append(_valor_monetario(linha.get("consumo_kwh")))
    volumes, ausentes = {}, {}
    for local, meses in por_local.items():
        ausentes[local] = [mes for mes in competencias if mes not in meses]
        volumes[local] = _somar_valores([_somar_valores(meses[mes]) for mes in competencias]) if not ausentes[local] else None
    return volumes, ausentes


def consumo_locais(repo: Repository, base: Periodo | None, atual: Periodo, municipio: str | None = None) -> ConsumoLocaisResponse:
    volumes, ausentes = _consumo_locais_periodo(repo, atual, municipio)
    referencias, _ = _consumo_locais_periodo(repo, base, municipio) if base else ({}, {})
    total = _somar_valores(list(volumes.values()))
    ordem = sorted(volumes, key=lambda local: (volumes[local] is None, -(volumes[local] or Decimal(0)), local))
    locais = []
    for local in ordem:
        volume, referencia = volumes[local], referencias.get(local)
        participacao = _dividir(volume * 100 if volume is not None else None, total)
        locais.append(ConsumoLocal(
            municipio=local[0], bairro=local[1], consumo_kwh=_numero(volume), participacao_pct=_numero(participacao),
            consumo_referencia_kwh=_numero(referencia), variacao_pct=_comparar_valores(referencia, volume).variacao_pct,
            competencias_ausentes=ausentes[local],
        ))
    return ConsumoLocaisResponse(
        periodo_atual=atual, periodo_base=base, municipio=municipio, nivel="bairro" if municipio else "municipio",
        consumo_total_kwh=_numero(total), locais=locais,
    )


def _operacao_periodo(repo: Repository, periodo: Periodo, municipio: str | None) -> dict:
    """Chamados e notas da B1; DEC/FEC da A8 com a mesma regra da Qualidade do Serviço, sem arredondar.

    Mês sem chamado conta como zero (é uma contagem). Com município, o DEC/FEC é o dos alimentadores
    cujo município principal é o escolhido, como na A8.
    """
    competencias = set(_competencias_periodo(periodo))
    meses = [m for m in repo.atendimentos_mensais(periodo.inicio, periodo.fim, municipio) if m["mes_referencia"] in competencias]
    avaliacoes = sum(int(m["qtd_avaliacoes"]) for m in meses)
    continuidade = repo.indicadores_continuidade(periodo.inicio, periodo.fim, municipio=municipio)
    r = resumo_periodo(continuidade) if continuidade else None
    return {
        "qtd_atendimentos": sum(int(m["qtd_atendimentos"]) for m in meses), "qtd_avaliacoes": avaliacoes,
        "nota_satisfacao_media": _dividir(_somar_coluna(meses, "soma_notas"), Decimal(avaliacoes)) if meses else None,
        "dec_horas": Decimal(str(r["dec_horas"])) if r else None, "fec_vezes": Decimal(str(r["fec_vezes"])) if r else None,
        "qtd_interrupcoes": int(r["n_ocorrencias"]) if r else None,
    }


def _indicadores_operacao(valores: dict) -> IndicadoresOperacao:
    return IndicadoresOperacao(**{
        campo: float(_arredondar(valor, 2)) if isinstance(valor, Decimal) else valor for campo, valor in valores.items()
    })


def operacao(repo: Repository, base: Periodo | None, atual: Periodo, municipio: str | None = None) -> OperacaoResponse:
    """As variações saem dos valores exatos (como na Qualidade do Serviço); só a exibição é arredondada."""
    a = _operacao_periodo(repo, atual, municipio)
    b = _operacao_periodo(repo, base, municipio) if base else None

    def variacao(campo):
        return _comparar_valores(b[campo] if b else None, a[campo]).variacao_pct

    satisfacao = _comparar_valores(b["nota_satisfacao_media"] if b else None, a["nota_satisfacao_media"], pontos_percentuais=True)
    return OperacaoResponse(
        periodo_atual=atual, periodo_base=base, municipio=municipio,
        atual=_indicadores_operacao(a), base=_indicadores_operacao(b) if b else None,
        variacao_atendimentos_pct=variacao("qtd_atendimentos"),
        variacao_satisfacao=float(satisfacao.variacao_pp) if satisfacao.variacao_pp is not None else None,
        variacao_dec_pct=variacao("dec_horas"), variacao_fec_pct=variacao("fec_vezes"),
    )
