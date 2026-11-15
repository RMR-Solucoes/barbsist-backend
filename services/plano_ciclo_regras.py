"""Regras puras para ciclos de planos dos clientes.

Nao acessa banco, nao concede credito e nao altera saldo.
Periodos sao semiabertos: inicio <= atendimento < fim.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CicloPlano:
    id: int
    assinatura_id: int
    inicio: datetime
    fim: datetime
    creditos_concedidos: int

    def __post_init__(self):
        if self.fim <= self.inicio:
            raise ValueError("Periodo de ciclo invalido.")
        if self.creditos_concedidos < 0:
            raise ValueError("Creditos negativos nao permitidos.")


def calcular_periodo(
    primeiro_pagamento: bool,
    agora: datetime,
    vencimento_anterior: datetime | None,
    novo_vencimento: datetime,
) -> tuple[datetime, datetime]:
    if primeiro_pagamento:
        inicio = agora
    elif vencimento_anterior and vencimento_anterior > agora:
        inicio = vencimento_anterior
    else:
        inicio = agora

    if novo_vencimento <= inicio:
        raise ValueError("Vencimento invalido para o ciclo.")

    return inicio, novo_vencimento


def selecionar_ciclo(
    ciclos: list[CicloPlano],
    assinatura_id: int,
    data_atendimento: datetime,
) -> CicloPlano | None:
    encontrados = [
        ciclo for ciclo in ciclos
        if ciclo.assinatura_id == assinatura_id
        and ciclo.inicio <= data_atendimento < ciclo.fim
    ]

    if len(encontrados) > 1:
        raise ValueError(
            "Ciclos sobrepostos para a mesma assinatura."
        )

    return encontrados[0] if encontrados else None


def saldo_livre(
    creditos_concedidos: int,
    usos_consumidos: int,
    usos_reservados_nao_consumidos: int,
) -> int:
    valores = (
        creditos_concedidos,
        usos_consumidos,
        usos_reservados_nao_consumidos,
    )
    if any(valor < 0 for valor in valores):
        raise ValueError("Contagens negativas nao permitidas.")

    return (
        creditos_concedidos
        - usos_consumidos
        - usos_reservados_nao_consumidos
    )
