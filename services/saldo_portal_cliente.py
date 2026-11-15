"""BARBSIST F3C5-A9B2 — candidato isolado.

Consulta somente leitura. Nao altera creditos ou agendamentos.
Ainda nao integrado a API oficial.
"""

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, or_

import models
from services.plano_ciclo_resolucao_db import (
    obter_ciclo_pago_para_consumo,
)
from services.plano_ciclo_reserva_db import STATUS_RESERVA
from services.plano_ciclo_pendencias_reserva import (
    pendencias_da_reserva,
)
from services.plano_ciclo_compromissos import (
    saldo_livre_ciclo,
)


def calcular_saldo_portal_candidato(
    db,
    *,
    assinatura,
    data_atendimento: datetime,
):
    """Calcula saldo aplicavel a data solicitada.

    A transacao e o isolamento de tenant devem ser
    fornecidos pelo endpoint autenticado chamador.
    """

    def bloquear(mensagem):
        raise HTTPException(status_code=409, detail=mensagem)

    if not isinstance(data_atendimento, datetime):
        raise ValueError("Data de atendimento invalida.")

    if (
        (assinatura.status or "").upper() != "ATIVO"
        or (assinatura.status_pagamento or "").upper() != "PAGO"
    ):
        bloquear("Assinatura sem direito ativo para agendar.")

    try:
        ciclo = obter_ciclo_pago_para_consumo(
            db,
            barbearia_id=assinatura.barbearia_id,
            assinatura_id=assinatura.id,
            data_atendimento=data_atendimento,
        )
    except ValueError as erro:
        bloquear(str(erro))

    if ciclo.plano_id != assinatura.plano_id:
        bloquear("Plano divergente do ciclo pago.")

    pagamento = (
        db.query(models.PagamentoPlano)
        .filter(
            models.PagamentoPlano.id == ciclo.pagamento_plano_id,
            models.PagamentoPlano.assinatura_id == assinatura.id,
            models.PagamentoPlano.plano_id == ciclo.plano_id,
        )
        .first()
    )

    if (
        pagamento is None
        or (pagamento.status or "").strip().upper() != "PAGO"
    ):
        bloquear("Ciclo sem pagamento confirmado.")

    reservas_sem_ciclo = (
        db.query(models.Agendamento.id)
        .filter(
            models.Agendamento.barbearia_id
            == assinatura.barbearia_id,
            models.Agendamento.cliente_id
            == assinatura.cliente_id,
            models.Agendamento.tipo_atendimento == "plano",
            models.Agendamento.status.in_(STATUS_RESERVA),
            models.Agendamento.plano_ciclo_id.is_(None),
        )
        .first()
    )

    if reservas_sem_ciclo is not None:
        bloquear("Reservas anteriores sem ciclo identificado.")

    usos_ambiguos = (
        db.query(models.UsoPlano.id)
        .filter(
            models.UsoPlano.assinatura_id == assinatura.id,
            models.UsoPlano.plano_ciclo_id.is_(None),
            or_(
                models.UsoPlano.data_uso.is_(None),
                models.UsoPlano.data_uso >= ciclo.periodo_inicio,
            ),
        )
        .first()
    )

    if usos_ambiguos is not None:
        bloquear("Consumos anteriores sem ciclo identificado.")

    consumidos = int(
        db.query(func.count(models.UsoPlano.id))
        .filter(
            models.UsoPlano.assinatura_id == assinatura.id,
            models.UsoPlano.plano_ciclo_id == ciclo.id,
        )
        .scalar() or 0
    )

    reservas = (
        db.query(models.Agendamento)
        .filter(
            models.Agendamento.barbearia_id
            == assinatura.barbearia_id,
            models.Agendamento.assinatura_cliente_id
            == assinatura.id,
            models.Agendamento.plano_ciclo_id == ciclo.id,
            models.Agendamento.tipo_atendimento == "plano",
            models.Agendamento.status.in_(STATUS_RESERVA),
        )
        .all()
    )

    if any(
        reserva.cliente_id != assinatura.cliente_id
        for reserva in reservas
    ):
        bloquear("Reserva vinculada a cliente divergente.")

    pendentes = sum(
        pendencias_da_reserva(
            db,
            agendamento=reserva,
            assinatura_id=assinatura.id,
            ciclo_id=ciclo.id,
        )
        for reserva in reservas
    )

    concedidos = int(ciclo.creditos_concedidos)
    saldo_bruto = int(assinatura.usos_disponiveis or 0)

    try:
        livre_ciclo = saldo_livre_ciclo(
            concedidos,
            consumidos,
            pendentes,
        )
    except (TypeError, ValueError):
        bloquear("Contagem de creditos inconsistente.")

    livre_geral = saldo_bruto - pendentes

    if min(livre_ciclo, livre_geral) < 0:
        bloquear("Saldo de creditos inconsistente.")

    return {
        "ciclo_id": ciclo.id,
        "periodo_inicio": ciclo.periodo_inicio.isoformat(),
        "periodo_fim": ciclo.periodo_fim.isoformat(),
        "data_atendimento": data_atendimento.isoformat(),
        "creditos_concedidos_ciclo": concedidos,
        "creditos_consumidos_ciclo": consumidos,
        "creditos_reservados": pendentes,
        "usos_disponiveis": saldo_bruto,
        "creditos_livres": min(livre_ciclo, livre_geral),
    }
