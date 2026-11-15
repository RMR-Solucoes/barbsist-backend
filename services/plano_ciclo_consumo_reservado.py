"""Consumo de creditos vinculados a uma reserva por ciclo.

Nao executa commit ou altera saldos diretamente.
Exige bloqueio transacional da assinatura pelo chamador.
"""

from fastapi import HTTPException
from sqlalchemy import func
import models

from services.plano_ciclo_consumo_direto import (
    validar_consumo_direto_ciclo,
)
from services.plano_ciclo_conciliacao_uso import (
    conciliar_consumo_reservado,
)
from services.plano_ciclo_resolucao_db import (
    obter_ciclo_pago_para_consumo,
)


def validar_consumo_ciclo(
    db, *, assinatura, comanda, servico_id
):
    if comanda.agendamento_id is None:
        return validar_consumo_direto_ciclo(
            db, assinatura=assinatura, comanda=comanda
        )

    def bloquear(mensagem):
        raise HTTPException(status_code=409, detail=mensagem)

    agenda = (
        db.query(models.Agendamento)
        .filter(
            models.Agendamento.id == comanda.agendamento_id,
            models.Agendamento.barbearia_id == assinatura.barbearia_id,
        )
        .first()
    )
    if agenda is None:
        bloquear("Agendamento nao encontrado.")

    if (
        agenda.cliente_id != assinatura.cliente_id
        or comanda.cliente_id != assinatura.cliente_id
        or comanda.barbearia_id != assinatura.barbearia_id
        or agenda.assinatura_cliente_id != assinatura.id
        or agenda.tipo_atendimento != "plano"
        or (agenda.origem or "").strip().upper() not in ("ONLINE", "INTERNO")
        or (agenda.status or "").strip().lower() != "em_atendimento"
        or agenda.plano_ciclo_id is None
    ):
        bloquear("Comanda nao corresponde a reserva.")

    try:
        ciclo = obter_ciclo_pago_para_consumo(
            db,
            barbearia_id=assinatura.barbearia_id,
            assinatura_id=assinatura.id,
            data_atendimento=agenda.data_hora_inicio,
            ciclo_reservado_id=agenda.plano_ciclo_id,
        )
    except ValueError as erro:
        bloquear(str(erro))

    if ciclo.plano_id != assinatura.plano_id:
        bloquear("Plano do ciclo divergente.")

    if (
        agenda.plano_ciclo_inicio != ciclo.periodo_inicio
        or agenda.plano_ciclo_fim != ciclo.periodo_fim
    ):
        bloquear("Periodo reservado divergente.")

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
        bloquear("Pagamento do ciclo nao confirmado.")

    # P10-PG04E-C1: usos anteriores ao ciclo atual
    # sao historicos. Usos ambiguos no periodo atual
    # ou sem data continuam bloqueados.
    from sqlalchemy import or_

    sem_ciclo = (
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
    if sem_ciclo is not None:
        bloquear("Consumos historicos sem ciclo identificado.")

    vinculos = (
        db.query(models.AgendamentoServico.servico_id)
        .filter(
            models.AgendamentoServico.agendamento_id == agenda.id
        )
        .order_by(models.AgendamentoServico.ordem)
        .all()
    )

    reservados = (
        [int(v[0]) for v in vinculos]
        if vinculos else [int(agenda.servico_id)]
    )

    usos = (
        db.query(models.UsoPlano)
        .filter(models.UsoPlano.comanda_id == comanda.id)
        .all()
    )

    if any(
        uso.assinatura_id != assinatura.id
        or uso.plano_ciclo_id != ciclo.id
        or uso.servico_id is None
        for uso in usos
    ):
        bloquear("Consumo anterior divergente.")

    try:
        conciliar_consumo_reservado(
            servicos_reservados=reservados,
            servicos_consumidos=[int(u.servico_id) for u in usos],
            novo_servico_id=servico_id,
        )
    except (ValueError, TypeError) as erro:
        bloquear(str(erro))

    usados = int(
        db.query(func.count(models.UsoPlano.id))
        .filter(
            models.UsoPlano.assinatura_id == assinatura.id,
            models.UsoPlano.plano_ciclo_id == ciclo.id,
        )
        .scalar() or 0
    )

    if (
        usados >= int(ciclo.creditos_concedidos)
        or int(assinatura.usos_disponiveis or 0) <= 0
    ):
        bloquear("Saldo de creditos insuficiente.")

    return ciclo.id
