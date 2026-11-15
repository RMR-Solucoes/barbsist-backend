"""Integracao preparada, ainda nao ativada no pagamento.

Nao confirma pagamentos, nao modifica saldos e nao realiza commit.
O chamador e responsavel pela transacao completa.
"""

from services.plano_ciclo_periodos_pagamento import (
    calcular_ciclo_apos_renovacao,
)
from services.plano_ciclo_registro import registrar_ciclo_pago


def registrar_ciclo_da_confirmacao(
    db,
    *,
    assinatura,
    plano,
    pagamento,
    estado_anterior,
    agora,
):
    if pagamento.id is None:
        raise ValueError("Pagamento precisa estar gravado por flush.")

    if pagamento.assinatura_id != assinatura.id:
        raise ValueError("Pagamento de outra assinatura.")

    if pagamento.cliente_id != assinatura.cliente_id:
        raise ValueError("Pagamento de outro cliente.")

    if pagamento.plano_id != plano.id:
        raise ValueError("Plano do pagamento divergente.")

    if pagamento.plano_id != assinatura.plano_id:
        raise ValueError("Plano da assinatura divergente.")

    if pagamento.status != "PAGO":
        raise ValueError("Pagamento ainda nao confirmado.")

    if plano.barbearia_id != assinatura.barbearia_id:
        raise ValueError("Plano de outra barbearia.")

    periodo = calcular_ciclo_apos_renovacao(
        estado_anterior,
        assinatura,
        plano,
        agora,
    )

    ciclo_id = registrar_ciclo_pago(
        db,
        barbearia_id=assinatura.barbearia_id,
        assinatura_id=assinatura.id,
        pagamento_plano_id=pagamento.id,
        periodo_inicio=periodo.inicio,
        periodo_fim=periodo.fim,
        creditos_concedidos=periodo.creditos,
        referencia_mes=pagamento.referencia_mes,
    )

    return ciclo_id
