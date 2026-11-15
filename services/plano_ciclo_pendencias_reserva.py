"""Calcula compromissos de uma reserva convertida ou nao.

Somente leitura. O chamador deve garantir bloqueio
transacional da assinatura ao contabilizar saldos.
"""

from fastapi import HTTPException

import models
from services.plano_ciclo_compromissos import (
    compromissos_pendentes,
)


def pendencias_da_reserva(
    db,
    *,
    agendamento,
    assinatura_id: int,
    ciclo_id: int,
) -> int:
    def bloquear(mensagem):
        raise HTTPException(status_code=409, detail=mensagem)

    if (
        not isinstance(assinatura_id, int)
        or isinstance(assinatura_id, bool)
        or assinatura_id <= 0
        or not isinstance(ciclo_id, int)
        or isinstance(ciclo_id, bool)
        or ciclo_id <= 0
    ):
        bloquear("Identificadores da reserva invalidos.")

    if (
        agendamento.assinatura_cliente_id != assinatura_id
        or agendamento.plano_ciclo_id != ciclo_id
        or agendamento.tipo_atendimento != "plano"
    ):
        bloquear("Reserva vinculada a outro ciclo ou assinatura.")

    vinculos = (
        db.query(models.AgendamentoServico.servico_id)
        .filter(
            models.AgendamentoServico.agendamento_id
            == agendamento.id
        )
        .order_by(models.AgendamentoServico.ordem)
        .all()
    )

    reservados = (
        [int(v[0]) for v in vinculos]
        if vinculos
        else [int(agendamento.servico_id)]
    )

    comandas = (
        db.query(models.Comanda)
        .filter(
            models.Comanda.agendamento_id == agendamento.id
        )
        .all()
    )

    if len(comandas) > 1:
        bloquear("Mais de uma comanda vinculada ao agendamento.")

    consumidos = []

    if comandas:
        comanda = comandas[0]

        if (
            comanda.barbearia_id != agendamento.barbearia_id
            or comanda.cliente_id != agendamento.cliente_id
        ):
            bloquear("Comanda possui cliente ou barbearia divergente.")

        usos = (
            db.query(models.UsoPlano)
            .filter(models.UsoPlano.comanda_id == comanda.id)
            .all()
        )

        for uso in usos:
            if (
                uso.assinatura_id != assinatura_id
                or uso.plano_ciclo_id != ciclo_id
                or uso.servico_id is None
            ):
                bloquear("Consumo nao corresponde ao ciclo reservado.")

            consumidos.append(int(uso.servico_id))

    try:
        return compromissos_pendentes(
            reservados,
            consumidos,
        )
    except (ValueError, TypeError) as erro:
        bloquear(str(erro))
