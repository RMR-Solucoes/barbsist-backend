"""Consulta segura do ciclo pago aplicavel a um consumo.

Nao faz commit, nao altera assinatura, nao concede creditos.
A chamada deve ocorrer na mesma transacao do consumo.
"""

from datetime import datetime

import models
from services.plano_ciclo_regras import CicloPlano
from services.plano_ciclo_resolucao_uso import resolver_ciclo_consumo


def obter_ciclo_pago_para_consumo(
    db,
    *,
    barbearia_id: int,
    assinatura_id: int,
    data_atendimento: datetime,
    ciclo_reservado_id: int | None = None,
):
    for nome, valor in (
        ("barbearia_id", barbearia_id),
        ("assinatura_id", assinatura_id),
    ):
        if (
            not isinstance(valor, int)
            or isinstance(valor, bool)
            or valor <= 0
        ):
            raise ValueError(f"{nome} invalido.")

    if not isinstance(data_atendimento, datetime):
        raise ValueError("Data de atendimento invalida.")

    # Confirmar pertencimento da assinatura ao tenant.
    assinatura = (
        db.query(models.AssinaturaCliente.id)
        .filter(
            models.AssinaturaCliente.id == assinatura_id,
            models.AssinaturaCliente.barbearia_id == barbearia_id,
        )
        .first()
    )

    if assinatura is None:
        raise ValueError("Assinatura nao pertence a barbearia.")

    registros = (
        db.query(models.PlanoCicloCliente)
        .filter(
            models.PlanoCicloCliente.barbearia_id == barbearia_id,
            models.PlanoCicloCliente.assinatura_id == assinatura_id,
            models.PlanoCicloCliente.periodo_inicio <= data_atendimento,
            models.PlanoCicloCliente.periodo_fim > data_atendimento,
        )
        .all()
    )

    ciclos = [
        CicloPlano(
            id=r.id,
            assinatura_id=r.assinatura_id,
            inicio=r.periodo_inicio,
            fim=r.periodo_fim,
            creditos_concedidos=r.creditos_concedidos,
        )
        for r in registros
    ]

    escolhido = resolver_ciclo_consumo(
        ciclos=ciclos,
        assinatura_id=assinatura_id,
        data_atendimento=data_atendimento,
        ciclo_reservado_id=ciclo_reservado_id,
    )

    # Retornar o registro ORM selecionado, sem alterar o estado.
    return next(
        r for r in registros if r.id == escolhido.id
    )
