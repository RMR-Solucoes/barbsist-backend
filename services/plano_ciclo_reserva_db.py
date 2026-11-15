"""Validacao de saldo para reservas de planos por ciclo.

Nao executa commit e nao grava agendamentos.
Deve ser chamado sob bloqueio FOR UPDATE da assinatura.
"""

from fastapi import HTTPException
from sqlalchemy import func, or_

import models
from services.plano_ciclo_compromissos import saldo_livre_ciclo
from services.plano_ciclo_resolucao_db import (
    obter_ciclo_pago_para_consumo,
)
from services.plano_ciclo_pendencias_reserva import (
    pendencias_da_reserva,
)



STATUS_RESERVA = (
    "agendado",
    "confirmado",
    "reagendado",
    "em_atendimento",
)


def validar_reserva_ciclo(
    db,
    *,
    assinatura,
    data_atendimento,
    quantidade_servicos,
):
    if (
        not isinstance(quantidade_servicos, int)
        or isinstance(quantidade_servicos, bool)
        or quantidade_servicos <= 0
    ):
        raise HTTPException(400, "Quantidade de servicos invalida.")

    def bloquear(mensagem):
        raise HTTPException(status_code=409, detail=mensagem)

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
        bloquear("Plano da assinatura diverge do ciclo.")

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
        bloquear("O ciclo nao possui pagamento confirmado.")

    # Impedir que reservas antigas sem vinculo sejam
    # ignoradas no calculo de compromissos.
    sem_ciclo = (
        db.query(models.Agendamento.id)
        .filter(
            models.Agendamento.barbearia_id == assinatura.barbearia_id,
            models.Agendamento.cliente_id == assinatura.cliente_id,
            models.Agendamento.tipo_atendimento == "plano",
            models.Agendamento.status.in_(STATUS_RESERVA),
            models.Agendamento.plano_ciclo_id.is_(None),
        )
        .first()
    )

    if sem_ciclo is not None:
        bloquear(
            "Existem reservas anteriores sem ciclo identificado."
        )

    # P10-PG04C: preservar usos historicos anteriores ao ciclo.
    # Bloquear consumos ambiguos sem data ou desde o inicio
    # do ciclo atual, sem alterar os registros legados.
    uso_sem_ciclo = (
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

    if uso_sem_ciclo is not None:
        bloquear(
            "Existem consumos anteriores sem ciclo identificado."
        )

    usados = int(
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
            models.Agendamento.barbearia_id == assinatura.barbearia_id,
            models.Agendamento.assinatura_cliente_id == assinatura.id,
            models.Agendamento.plano_ciclo_id == ciclo.id,
            models.Agendamento.tipo_atendimento == "plano",
            models.Agendamento.status.in_(STATUS_RESERVA),
        )
        .all()
    )

    # Reservas vinculadas a outro cliente ou assinatura
    # devem impedir conciliacao silenciosa.
    if any(
        reserva.cliente_id != assinatura.cliente_id
        for reserva in reservas
    ):
        bloquear("Reserva possui cliente divergente.")

    pendentes = 0

    for reserva in reservas:
        vinculos = (
            db.query(models.AgendamentoServico.servico_id)
            .filter(
                models.AgendamentoServico.agendamento_id == reserva.id
            )
            .all()
        )

        # Agendamentos legados podem ter apenas servico_id.
        reservados = (
            [int(v[0]) for v in vinculos]
            if vinculos
            else [int(reserva.servico_id)]
        )

        # BARBSIST_P9_8F4E2_PENDENCIAS_CONCILIADAS
        pendentes += pendencias_da_reserva(
            db,
            agendamento=reserva,
            assinatura_id=assinatura.id,
            ciclo_id=ciclo.id,
        )

    try:
        saldo = saldo_livre_ciclo(
            int(ciclo.creditos_concedidos),
            usados,
            pendentes,
        )
    except (TypeError, ValueError):
        bloquear("Contagem de creditos inconsistente.")

    # O saldo geral e uma segunda barreira, para
    # preservar o controle da assinatura existente.
    saldo_geral = int(assinatura.usos_disponiveis or 0)
    saldo_geral_livre = saldo_geral - pendentes

    if (
        saldo < quantidade_servicos
        or saldo_geral_livre < quantidade_servicos
    ):
        bloquear("Saldo livre insuficiente para reservar servi?os.")

    return ciclo
