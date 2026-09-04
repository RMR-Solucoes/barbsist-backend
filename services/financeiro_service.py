from datetime import date, datetime, time, timedelta

from sqlalchemy import case, func

import models
from auth.tenant import obter_barbearia_id


def _resolver_periodo(
    data_inicio: date | None,
    data_fim: date | None,
) -> tuple[date, date]:
    hoje = date.today()

    if data_inicio is None:
        data_inicio = hoje.replace(day=1)

    if data_fim is None:
        data_fim = hoje

    if data_inicio > data_fim:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail="data_inicio não pode ser posterior a data_fim.",
        )

    return data_inicio, data_fim


def _limites_datetime(
    data_inicio: date,
    data_fim: date,
):
    inicio = datetime.combine(data_inicio, time.min)
    fim_exclusivo = datetime.combine(
        data_fim + timedelta(days=1),
        time.min,
    )
    return inicio, fim_exclusivo


def dashboard_financeiro_service(
    db,
    usuario_logado,
    data_inicio: date | None = None,
    data_fim: date | None = None,
):
    barbearia_id = obter_barbearia_id(usuario_logado)
    data_inicio, data_fim = _resolver_periodo(
        data_inicio,
        data_fim,
    )
    inicio_dt, fim_dt = _limites_datetime(
        data_inicio,
        data_fim,
    )

    base_caixa = (
        db.query(models.Caixa)
        .filter(
            models.Caixa.barbearia_id == barbearia_id,
            models.Caixa.status == "ATIVO",
            models.Caixa.data >= inicio_dt,
            models.Caixa.data < fim_dt,
        )
    )

    totais = (
        db.query(
            func.coalesce(
                func.sum(
                    case(
                        (models.Caixa.tipo == "entrada", models.Caixa.valor),
                        else_=0,
                    )
                ),
                0,
            ).label("entradas"),
            func.coalesce(
                func.sum(
                    case(
                        (models.Caixa.tipo == "saida", models.Caixa.valor),
                        else_=0,
                    )
                ),
                0,
            ).label("saidas"),
            func.count(models.Caixa.id).label("quantidade"),
        )
        .filter(
            models.Caixa.barbearia_id == barbearia_id,
            models.Caixa.status == "ATIVO",
            models.Caixa.data >= inicio_dt,
            models.Caixa.data < fim_dt,
        )
        .one()
    )

    receber_pendente = (
        db.query(func.coalesce(func.sum(models.ContaReceber.valor), 0))
        .filter(
            models.ContaReceber.barbearia_id == barbearia_id,
            models.ContaReceber.status == "PENDENTE",
        )
        .scalar()
    )

    pagar_pendente = (
        db.query(func.coalesce(func.sum(models.ContaPagar.valor), 0))
        .filter(
            models.ContaPagar.barbearia_id == barbearia_id,
            models.ContaPagar.status == "PENDENTE",
        )
        .scalar()
    )

    hoje = date.today()
    receber_vencidas = (
        db.query(func.count(models.ContaReceber.id))
        .filter(
            models.ContaReceber.barbearia_id == barbearia_id,
            models.ContaReceber.status == "PENDENTE",
            models.ContaReceber.vencimento < hoje,
        )
        .scalar()
        or 0
    )

    pagar_vencidas = (
        db.query(func.count(models.ContaPagar.id))
        .filter(
            models.ContaPagar.barbearia_id == barbearia_id,
            models.ContaPagar.status == "PENDENTE",
            models.ContaPagar.vencimento < hoje,
        )
        .scalar()
        or 0
    )

    por_origem = (
        db.query(
            models.Caixa.tipo,
            models.Caixa.origem,
            func.coalesce(func.sum(models.Caixa.valor), 0).label("valor"),
        )
        .filter(
            models.Caixa.barbearia_id == barbearia_id,
            models.Caixa.status == "ATIVO",
            models.Caixa.data >= inicio_dt,
            models.Caixa.data < fim_dt,
        )
        .group_by(
            models.Caixa.tipo,
            models.Caixa.origem,
        )
        .all()
    )

    recentes = (
        base_caixa
        .order_by(
            models.Caixa.data.desc(),
            models.Caixa.id.desc(),
        )
        .limit(10)
        .all()
    )

    entradas = float(totais.entradas or 0)
    saidas = float(totais.saidas or 0)

    return {
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "entradas": entradas,
        "saidas": saidas,
        "saldo": entradas - saidas,
        "contas_receber_pendentes": float(receber_pendente or 0),
        "contas_pagar_pendentes": float(pagar_pendente or 0),
        "contas_receber_vencidas": int(receber_vencidas),
        "contas_pagar_vencidas": int(pagar_vencidas),
        "quantidade_movimentacoes": int(totais.quantidade or 0),
        "receitas_por_origem": [
            {"origem": r.origem, "valor": float(r.valor or 0)}
            for r in por_origem
            if r.tipo == "entrada"
        ],
        "despesas_por_origem": [
            {"origem": r.origem, "valor": float(r.valor or 0)}
            for r in por_origem
            if r.tipo == "saida"
        ],
        "movimentacoes_recentes": [
            {
                "id": m.id,
                "tipo": m.tipo,
                "descricao": m.descricao,
                "valor": float(m.valor),
                "origem": m.origem,
                "forma_pagamento": m.forma_pagamento,
                "data": m.data,
            }
            for m in recentes
        ],
    }


def fluxo_caixa_service(
    db,
    usuario_logado,
    data_inicio: date | None = None,
    data_fim: date | None = None,
):
    barbearia_id = obter_barbearia_id(usuario_logado)
    data_inicio, data_fim = _resolver_periodo(
        data_inicio,
        data_fim,
    )
    inicio_dt, fim_dt = _limites_datetime(
        data_inicio,
        data_fim,
    )

    saldo_anterior = (
        db.query(
            func.coalesce(
                func.sum(
                    case(
                        (models.Caixa.tipo == "entrada", models.Caixa.valor),
                        else_=-models.Caixa.valor,
                    )
                ),
                0,
            )
        )
        .filter(
            models.Caixa.barbearia_id == barbearia_id,
            models.Caixa.status == "ATIVO",
            models.Caixa.data < inicio_dt,
        )
        .scalar()
        or 0
    )

    rows = (
        db.query(
            func.date(models.Caixa.data).label("dia"),
            func.coalesce(
                func.sum(
                    case(
                        (models.Caixa.tipo == "entrada", models.Caixa.valor),
                        else_=0,
                    )
                ),
                0,
            ).label("entradas"),
            func.coalesce(
                func.sum(
                    case(
                        (models.Caixa.tipo == "saida", models.Caixa.valor),
                        else_=0,
                    )
                ),
                0,
            ).label("saidas"),
        )
        .filter(
            models.Caixa.barbearia_id == barbearia_id,
            models.Caixa.status == "ATIVO",
            models.Caixa.data >= inicio_dt,
            models.Caixa.data < fim_dt,
        )
        .group_by(func.date(models.Caixa.data))
        .order_by(func.date(models.Caixa.data))
        .all()
    )

    saldo = float(saldo_anterior)
    dias = []

    for row in rows:
        entradas = float(row.entradas or 0)
        saidas = float(row.saidas or 0)
        saldo_dia = entradas - saidas
        saldo += saldo_dia

        dia = row.dia
        if isinstance(dia, str):
            dia = date.fromisoformat(dia)

        dias.append(
            {
                "data": dia,
                "entradas": entradas,
                "saidas": saidas,
                "saldo_dia": saldo_dia,
                "saldo_acumulado": saldo,
            }
        )

    return {
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "saldo_inicial": float(saldo_anterior),
        "saldo_final": saldo,
        "dias": dias,
    }


def dre_simplificada_service(
    db,
    usuario_logado,
    data_inicio: date | None = None,
    data_fim: date | None = None,
):
    barbearia_id = obter_barbearia_id(usuario_logado)
    data_inicio, data_fim = _resolver_periodo(
        data_inicio,
        data_fim,
    )
    inicio_dt, fim_dt = _limites_datetime(
        data_inicio,
        data_fim,
    )

    rows = (
        db.query(
            models.Caixa.tipo,
            models.Caixa.origem,
            func.coalesce(func.sum(models.Caixa.valor), 0).label("valor"),
        )
        .filter(
            models.Caixa.barbearia_id == barbearia_id,
            models.Caixa.status == "ATIVO",
            models.Caixa.data >= inicio_dt,
            models.Caixa.data < fim_dt,
        )
        .group_by(
            models.Caixa.tipo,
            models.Caixa.origem,
        )
        .all()
    )

    receita_operacional = 0.0
    outras_entradas = 0.0
    despesas_operacionais = 0.0
    outras_saidas = 0.0

    origens_receita_operacional = {
        "COMANDA",
        "PLANO",
        "CONTA_RECEBER",
    }
    origens_despesa_operacional = {
        "CONTA_PAGAR",
    }

    for row in rows:
        valor = float(row.valor or 0)

        if row.tipo == "entrada":
            if row.origem in origens_receita_operacional:
                receita_operacional += valor
            else:
                outras_entradas += valor
        elif row.tipo == "saida":
            if row.origem in origens_despesa_operacional:
                despesas_operacionais += valor
            else:
                outras_saidas += valor

    receitas_totais = receita_operacional + outras_entradas
    despesas_totais = despesas_operacionais + outras_saidas

    return {
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "receita_operacional": receita_operacional,
        "outras_entradas": outras_entradas,
        "receitas_totais": receitas_totais,
        "despesas_operacionais": despesas_operacionais,
        "outras_saidas": outras_saidas,
        "despesas_totais": despesas_totais,
        "resultado": receitas_totais - despesas_totais,
    }
