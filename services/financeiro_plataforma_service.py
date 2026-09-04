from datetime import date, datetime, time, timedelta

from fastapi import HTTPException, status
from sqlalchemy import case, func

import models


CATEGORIA_ASSINATURA_SAAS = "ASSINATURA_SAAS"

CATEGORIAS_SAIDA_DESTAQUE = {
    "TAXA_PAGAMENTO",
    "COMISSAO_PARCEIRO",
    "IMPOSTO",
}


def _resolver_periodo(
    data_inicio: date | None,
    data_fim: date | None,
):
    hoje = date.today()

    if data_inicio is None:
        data_inicio = hoje.replace(day=1)

    if data_fim is None:
        data_fim = hoje

    if data_inicio > data_fim:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="data_inicio nao pode ser maior que data_fim.",
        )

    return data_inicio, data_fim


def _limites_datetime(
    data_inicio: date,
    data_fim: date,
):
    inicio = datetime.combine(
        data_inicio,
        time.min,
    )

    fim_exclusivo = datetime.combine(
        data_fim + timedelta(days=1),
        time.min,
    )

    return inicio, fim_exclusivo


def _normalizar_texto(valor: str | None):
    if valor is None:
        return None

    return valor.strip().upper()


def _validar_movimentacao_manual(
    tipo: str,
    categoria: str,
    status_movimentacao: str,
    data_realizacao: datetime | None,
):
    if tipo not in {"ENTRADA", "SAIDA"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="tipo deve ser ENTRADA ou SAIDA.",
        )

    if status_movimentacao not in {
        "PENDENTE",
        "REALIZADO",
        "CANCELADO",
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "status deve ser PENDENTE, "
                "REALIZADO ou CANCELADO."
            ),
        )

    if (
        tipo == "ENTRADA"
        and categoria == CATEGORIA_ASSINATURA_SAAS
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Receitas de ASSINATURA_SAAS sao geradas "
                "automaticamente a partir de PagamentoSaaS."
            ),
        )

    if (
        status_movimentacao == "REALIZADO"
        and data_realizacao is None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "data_realizacao e obrigatoria "
                "quando status=REALIZADO."
            ),
        )

    if (
        status_movimentacao != "REALIZADO"
        and data_realizacao is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "data_realizacao deve ser nula "
                "quando status nao for REALIZADO."
            ),
        )


def criar_movimentacao_plataforma_service(
    db,
    dados,
    usuario_logado,
):
    tipo = _normalizar_texto(dados.tipo)
    categoria = _normalizar_texto(
        dados.categoria
    )
    status_movimentacao = _normalizar_texto(
        dados.status
    )

    _validar_movimentacao_manual(
        tipo=tipo,
        categoria=categoria,
        status_movimentacao=status_movimentacao,
        data_realizacao=dados.data_realizacao,
    )

    movimentacao = (
        models.FinanceiroPlataformaMovimentacao(
            tipo=tipo,
            categoria=categoria,
            descricao=dados.descricao.strip(),
            valor=float(dados.valor),
            data_competencia=dados.data_competencia,
            data_realizacao=dados.data_realizacao,
            forma_pagamento=(
                dados.forma_pagamento.strip()
                if dados.forma_pagamento
                else None
            ),
            observacao=(
                dados.observacao.strip()
                if dados.observacao
                else None
            ),
            status=status_movimentacao,
            usuario_id=usuario_logado.id,
        )
    )

    db.add(movimentacao)
    db.commit()
    db.refresh(movimentacao)

    return movimentacao


def listar_movimentacoes_plataforma_service(
    db,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    tipo: str | None = None,
    categoria: str | None = None,
    status_movimentacao: str | None = None,
):
    query = db.query(
        models.FinanceiroPlataformaMovimentacao
    )

    if data_inicio is not None:
        inicio = datetime.combine(
            data_inicio,
            time.min,
        )

        query = query.filter(
            models.FinanceiroPlataformaMovimentacao
            .data_competencia >= inicio
        )

    if data_fim is not None:
        fim_exclusivo = datetime.combine(
            data_fim + timedelta(days=1),
            time.min,
        )

        query = query.filter(
            models.FinanceiroPlataformaMovimentacao
            .data_competencia < fim_exclusivo
        )

    if tipo:
        query = query.filter(
            models.FinanceiroPlataformaMovimentacao.tipo
            == _normalizar_texto(tipo)
        )

    if categoria:
        query = query.filter(
            models.FinanceiroPlataformaMovimentacao.categoria
            == _normalizar_texto(categoria)
        )

    if status_movimentacao:
        query = query.filter(
            models.FinanceiroPlataformaMovimentacao.status
            == _normalizar_texto(
                status_movimentacao
            )
        )

    return (
        query
        .order_by(
            models.FinanceiroPlataformaMovimentacao
            .data_competencia.desc(),
            models.FinanceiroPlataformaMovimentacao
            .id.desc(),
        )
        .all()
    )


def atualizar_movimentacao_plataforma_service(
    db,
    movimentacao_id: int,
    dados,
):
    movimentacao = (
        db.query(
            models.FinanceiroPlataformaMovimentacao
        )
        .filter(
            models.FinanceiroPlataformaMovimentacao.id
            == movimentacao_id
        )
        .first()
    )

    if not movimentacao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movimentacao financeira nao encontrada.",
        )

    atualizacoes = dados.model_dump(
        exclude_unset=True
    )

    categoria = _normalizar_texto(
        atualizacoes.get(
            "categoria",
            movimentacao.categoria,
        )
    )

    status_final = _normalizar_texto(
        atualizacoes.get(
            "status",
            movimentacao.status,
        )
    )

    data_realizacao_final = (
        atualizacoes["data_realizacao"]
        if "data_realizacao" in atualizacoes
        else movimentacao.data_realizacao
    )

    _validar_movimentacao_manual(
        tipo=movimentacao.tipo,
        categoria=categoria,
        status_movimentacao=status_final,
        data_realizacao=data_realizacao_final,
    )

    for campo, valor in atualizacoes.items():
        if campo in {
            "categoria",
            "status",
        } and valor is not None:
            valor = _normalizar_texto(valor)

        if campo in {
            "descricao",
            "forma_pagamento",
            "observacao",
        } and isinstance(valor, str):
            valor = valor.strip()

        setattr(
            movimentacao,
            campo,
            valor,
        )

    db.commit()
    db.refresh(movimentacao)

    return movimentacao


def obter_resumo_financeiro_plataforma_service(
    db,
    data_inicio: date | None = None,
    data_fim: date | None = None,
):
    data_inicio, data_fim = _resolver_periodo(
        data_inicio,
        data_fim,
    )

    inicio_dt, fim_dt = _limites_datetime(
        data_inicio,
        data_fim,
    )

    data_pagamento = func.coalesce(
        models.PagamentoSaaS.processado_em,
        models.PagamentoSaaS.data_criacao,
    )

    receita_saas = (
        db.query(
            func.coalesce(
                func.sum(
                    models.PagamentoSaaS.valor
                ),
                0,
            )
        )
        .filter(
            func.lower(
                models.PagamentoSaaS.status
            ) == "approved",
            models.PagamentoSaaS.processado.is_(
                True
            ),
            data_pagamento >= inicio_dt,
            data_pagamento < fim_dt,
        )
        .scalar()
    )

    realizadas = (
        db.query(
            models.FinanceiroPlataformaMovimentacao.tipo,
            models.FinanceiroPlataformaMovimentacao.categoria,
            func.coalesce(
                func.sum(
                    models.FinanceiroPlataformaMovimentacao.valor
                ),
                0,
            ).label("valor"),
        )
        .filter(
            models.FinanceiroPlataformaMovimentacao.status
            == "REALIZADO",
            models.FinanceiroPlataformaMovimentacao
            .data_realizacao.isnot(None),
            models.FinanceiroPlataformaMovimentacao
            .data_realizacao >= inicio_dt,
            models.FinanceiroPlataformaMovimentacao
            .data_realizacao < fim_dt,
        )
        .group_by(
            models.FinanceiroPlataformaMovimentacao.tipo,
            models.FinanceiroPlataformaMovimentacao.categoria,
        )
        .all()
    )

    entradas_por_categoria = []
    saidas_por_categoria = []

    outras_entradas = 0.0
    despesas_totais = 0.0

    taxas_pagamento = 0.0
    comissoes_parceiros = 0.0
    impostos = 0.0

    for tipo, categoria, valor in realizadas:
        valor = float(valor or 0)

        item = {
            "categoria": categoria,
            "valor": valor,
        }

        if tipo == "ENTRADA":
            outras_entradas += valor
            entradas_por_categoria.append(
                item
            )

        elif tipo == "SAIDA":
            despesas_totais += valor
            saidas_por_categoria.append(
                item
            )

            if categoria == "TAXA_PAGAMENTO":
                taxas_pagamento += valor

            elif categoria == "COMISSAO_PARCEIRO":
                comissoes_parceiros += valor

            elif categoria == "IMPOSTO":
                impostos += valor

    outras_despesas = (
        despesas_totais
        - taxas_pagamento
        - comissoes_parceiros
        - impostos
    )

    entradas_totais = (
        float(receita_saas or 0)
        + outras_entradas
    )

    resultado_liquido = (
        entradas_totais
        - despesas_totais
    )

    pendencias = (
        db.query(
            models.FinanceiroPlataformaMovimentacao.tipo,
            func.coalesce(
                func.sum(
                    models.FinanceiroPlataformaMovimentacao.valor
                ),
                0,
            ).label("valor"),
        )
        .filter(
            models.FinanceiroPlataformaMovimentacao.status
            == "PENDENTE",
            models.FinanceiroPlataformaMovimentacao
            .data_competencia >= inicio_dt,
            models.FinanceiroPlataformaMovimentacao
            .data_competencia < fim_dt,
        )
        .group_by(
            models.FinanceiroPlataformaMovimentacao.tipo
        )
        .all()
    )

    pendentes_entrada = 0.0
    pendentes_saida = 0.0

    for tipo, valor in pendencias:
        if tipo == "ENTRADA":
            pendentes_entrada = float(
                valor or 0
            )

        elif tipo == "SAIDA":
            pendentes_saida = float(
                valor or 0
            )

    quantidade_movimentacoes = (
        db.query(
            func.count(
                models.FinanceiroPlataformaMovimentacao.id
            )
        )
        .filter(
            models.FinanceiroPlataformaMovimentacao
            .data_competencia >= inicio_dt,
            models.FinanceiroPlataformaMovimentacao
            .data_competencia < fim_dt,
            models.FinanceiroPlataformaMovimentacao.status
            != "CANCELADO",
        )
        .scalar()
    )

    return {
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "receita_saas": float(
            receita_saas or 0
        ),
        "outras_entradas": outras_entradas,
        "entradas_totais": entradas_totais,
        "despesas_totais": despesas_totais,
        "taxas_pagamento": taxas_pagamento,
        "comissoes_parceiros": (
            comissoes_parceiros
        ),
        "impostos": impostos,
        "outras_despesas": outras_despesas,
        "resultado_liquido": resultado_liquido,
        "pendentes_entrada": pendentes_entrada,
        "pendentes_saida": pendentes_saida,
        "quantidade_movimentacoes": int(
            quantidade_movimentacoes or 0
        ),
        "entradas_por_categoria": (
            entradas_por_categoria
        ),
        "saidas_por_categoria": (
            saidas_por_categoria
        ),
    }


def fluxo_caixa_plataforma_service(
    db,
    data_inicio: date | None = None,
    data_fim: date | None = None,
):
    data_inicio, data_fim = _resolver_periodo(
        data_inicio,
        data_fim,
    )

    inicio_dt, fim_dt = _limites_datetime(
        data_inicio,
        data_fim,
    )

    data_pagamento = func.coalesce(
        models.PagamentoSaaS.processado_em,
        models.PagamentoSaaS.data_criacao,
    )

    receita_anterior = (
        db.query(
            func.coalesce(
                func.sum(
                    models.PagamentoSaaS.valor
                ),
                0,
            )
        )
        .filter(
            func.lower(
                models.PagamentoSaaS.status
            ) == "approved",
            models.PagamentoSaaS.processado.is_(
                True
            ),
            data_pagamento < inicio_dt,
        )
        .scalar()
    )

    movimentos_anteriores = (
        db.query(
            func.coalesce(
                func.sum(
                    case(
                        (
                            models.FinanceiroPlataformaMovimentacao.tipo
                            == "ENTRADA",
                            models.FinanceiroPlataformaMovimentacao.valor,
                        ),
                        else_=-
                        models.FinanceiroPlataformaMovimentacao.valor,
                    )
                ),
                0,
            )
        )
        .filter(
            models.FinanceiroPlataformaMovimentacao.status
            == "REALIZADO",
            models.FinanceiroPlataformaMovimentacao
            .data_realizacao.isnot(None),
            models.FinanceiroPlataformaMovimentacao
            .data_realizacao < inicio_dt,
        )
        .scalar()
    )

    saldo_inicial = (
        float(receita_anterior or 0)
        + float(
            movimentos_anteriores or 0
        )
    )

    pagamentos_periodo = (
        db.query(
            data_pagamento.label("data"),
            models.PagamentoSaaS.valor.label(
                "valor"
            ),
        )
        .filter(
            func.lower(
                models.PagamentoSaaS.status
            ) == "approved",
            models.PagamentoSaaS.processado.is_(
                True
            ),
            data_pagamento >= inicio_dt,
            data_pagamento < fim_dt,
        )
        .all()
    )

    movimentos_periodo = (
        db.query(
            models.FinanceiroPlataformaMovimentacao
        )
        .filter(
            models.FinanceiroPlataformaMovimentacao.status
            == "REALIZADO",
            models.FinanceiroPlataformaMovimentacao
            .data_realizacao.isnot(None),
            models.FinanceiroPlataformaMovimentacao
            .data_realizacao >= inicio_dt,
            models.FinanceiroPlataformaMovimentacao
            .data_realizacao < fim_dt,
        )
        .all()
    )

    por_dia = {}

    for data_mov, valor in pagamentos_periodo:
        dia = data_mov.date()

        item = por_dia.setdefault(
            dia,
            {
                "entradas": 0.0,
                "saidas": 0.0,
            },
        )

        item["entradas"] += float(
            valor or 0
        )

    for movimento in movimentos_periodo:
        dia = movimento.data_realizacao.date()

        item = por_dia.setdefault(
            dia,
            {
                "entradas": 0.0,
                "saidas": 0.0,
            },
        )

        if movimento.tipo == "ENTRADA":
            item["entradas"] += float(
                movimento.valor
            )
        else:
            item["saidas"] += float(
                movimento.valor
            )

    dias = []
    saldo = saldo_inicial

    data_atual = data_inicio

    while data_atual <= data_fim:
        valores = por_dia.get(
            data_atual,
            {
                "entradas": 0.0,
                "saidas": 0.0,
            },
        )

        entradas = valores["entradas"]
        saidas = valores["saidas"]

        resultado_dia = entradas - saidas
        saldo += resultado_dia

        dias.append(
            {
                "data": data_atual,
                "entradas": entradas,
                "saidas": saidas,
                "resultado_dia": resultado_dia,
                "saldo_acumulado": saldo,
            }
        )

        data_atual += timedelta(days=1)

    return {
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "saldo_inicial": saldo_inicial,
        "saldo_final": saldo,
        "dias": dias,
    }
