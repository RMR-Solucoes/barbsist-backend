"""Validacao conservadora do consumo direto por ciclo.

Executar dentro da transacao que ja bloqueou a assinatura.
Nao realiza commit e nao modifica o saldo.
"""

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, or_

import models
from services.plano_ciclo_resolucao_db import (
    obter_ciclo_pago_para_consumo,
)


def validar_consumo_direto_ciclo(
    db,
    *,
    assinatura,
    comanda,
):
    def bloquear(mensagem):
        raise HTTPException(
            status_code=409,
            detail=mensagem,
        )

    if comanda.agendamento_id is not None:
        bloquear(
            "Consumo de reserva ainda nao habilitado "
            "no controle por ciclos."
        )

    # Uma reserva ativa pode comprometer creditos
    # que ainda aparecem em usos_disponiveis.
    reservas = (
        db.query(models.Agendamento.id)
        .filter(
            models.Agendamento.barbearia_id
                == assinatura.barbearia_id,
            models.Agendamento.cliente_id
                == assinatura.cliente_id,
            models.Agendamento.tipo_atendimento == "plano",
            models.Agendamento.status.in_(
                ("agendado", "confirmado", "reagendado", "em_atendimento")
            ),
        )
        .first()
    )

    if reservas is not None:
        bloquear(
            "Existem reservas de plano pendentes. "
            "A conciliacao por ciclo ainda nao esta habilitada."
        )

    agora = datetime.now()

    try:
        ciclo = obter_ciclo_pago_para_consumo(
            db,
            barbearia_id=assinatura.barbearia_id,
            assinatura_id=assinatura.id,
            data_atendimento=agora,
        )
    except ValueError as erro:
        bloquear(str(erro))

    # P10-PG04E-C3B: comparar os consumos legados
    # com o inicio do ciclo efetivamente selecionado.
    # Sem data ou desde o inicio do ciclo: bloquear.
    uso_sem_ciclo_ambiguo = (
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

    if uso_sem_ciclo_ambiguo is not None:
        bloquear(
            "Assinatura possui consumos sem ciclo "
            "identificado no periodo vigente."
        )

    if ciclo.plano_id != assinatura.plano_id:
        bloquear(
            "O plano do ciclo diverge do plano da assinatura."
        )

    pagamento = (
        db.query(models.PagamentoPlano)
        .filter(
            models.PagamentoPlano.id
                == ciclo.pagamento_plano_id,
            models.PagamentoPlano.assinatura_id
                == assinatura.id,
            models.PagamentoPlano.plano_id
                == ciclo.plano_id,
        )
        .first()
    )

    if (
        pagamento is None
        or (pagamento.status or "").strip().upper()
            != "PAGO"
    ):
        bloquear(
            "O ciclo nao possui pagamento confirmado."
        )

    utilizados = (
        db.query(func.count(models.UsoPlano.id))
        .filter(
            models.UsoPlano.assinatura_id == assinatura.id,
            models.UsoPlano.plano_ciclo_id == ciclo.id,
        )
        .scalar()
    )

    utilizados = int(utilizados or 0)
    concedidos = int(ciclo.creditos_concedidos)

    if concedidos <= 0 or utilizados >= concedidos:
        bloquear("Sem creditos livres no ciclo pago.")

    if int(assinatura.usos_disponiveis or 0) <= 0:
        bloquear("Sem usos disponiveis na assinatura.")

    return ciclo.id
