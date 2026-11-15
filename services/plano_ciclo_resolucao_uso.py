"""Resolucao defensiva de ciclo para consumo de plano de cliente.

Modulo puro: nao acessa banco, nao altera saldos e nao executa commit.
"""

from datetime import datetime
from services.plano_ciclo_regras import CicloPlano, selecionar_ciclo


def resolver_ciclo_consumo(
    *,
    ciclos: list[CicloPlano],
    assinatura_id: int,
    data_atendimento: datetime,
    ciclo_reservado_id: int | None = None,
) -> CicloPlano:
    if (
        not isinstance(assinatura_id, int)
        or isinstance(assinatura_id, bool)
        or assinatura_id <= 0
    ):
        raise ValueError("Assinatura invalida.")

    if not isinstance(data_atendimento, datetime):
        raise ValueError("Data de atendimento invalida.")

    if ciclo_reservado_id is not None and (
        not isinstance(ciclo_reservado_id, int)
        or isinstance(ciclo_reservado_id, bool)
        or ciclo_reservado_id <= 0
    ):
        raise ValueError("Ciclo reservado invalido.")

    ciclo = selecionar_ciclo(
        ciclos,
        assinatura_id,
        data_atendimento,
    )

    if ciclo is None:
        raise ValueError(
            "Nao existe ciclo pago para a data de atendimento."
        )

    if (
        ciclo_reservado_id is not None
        and ciclo.id != ciclo_reservado_id
    ):
        raise ValueError(
            "Ciclo de consumo diverge do ciclo reservado."
        )

    return ciclo
