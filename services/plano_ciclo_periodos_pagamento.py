"""Calculo puro de periodos e creditos de ciclos pagos."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class EstadoAnteriorCiclo:
    primeiro_pagamento: bool
    vencimento_anterior: datetime | None
    creditos_primeiro_ciclo: int | None


@dataclass(frozen=True)
class PeriodoCicloPago:
    inicio: datetime
    fim: datetime
    creditos: int


def capturar_estado_anterior(assinatura):
    return EstadoAnteriorCiclo(
        primeiro_pagamento=(
            assinatura.data_ultimo_pagamento is None
        ),
        vencimento_anterior=(
            assinatura.data_proximo_vencimento
            or assinatura.data_fim
        ),
        creditos_primeiro_ciclo=(
            assinatura.usos_proximo_ciclo
        ),
    )


def calcular_ciclo_apos_renovacao(
    estado_anterior, assinatura, plano, agora
):
    if not isinstance(agora, datetime):
        raise ValueError("Data de confirmacao invalida.")

    if estado_anterior.primeiro_pagamento:
        inicio = agora
        creditos = (
            estado_anterior.creditos_primeiro_ciclo
            if estado_anterior.creditos_primeiro_ciclo is not None
            else plano.quantidade_servicos
        )
    else:
        vencimento = estado_anterior.vencimento_anterior

        if (
            vencimento is not None
            and not isinstance(vencimento, datetime)
        ):
            raise ValueError("Vencimento anterior invalido.")

        inicio = (
            vencimento
            if vencimento is not None and vencimento > agora
            else agora
        )
        creditos = plano.quantidade_servicos

    fim = assinatura.data_fim

    if not isinstance(fim, datetime) or fim <= inicio:
        raise ValueError("Periodo do ciclo invalido.")

    if (
        not isinstance(creditos, int)
        or isinstance(creditos, bool)
        or creditos < 0
    ):
        raise ValueError("Quantidade de creditos invalida.")

    return PeriodoCicloPago(
        inicio=inicio,
        fim=fim,
        creditos=creditos,
    )
