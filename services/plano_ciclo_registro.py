"""Registro transacional de ciclos pagos do BarbSist.

P9.3T: modulo preparado, ainda nao conectado aos pagamentos.
Nao confirma transacoes, nao modifica saldo e nao lanca Caixa.
"""

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select

import models
from migrations.p9_3k_plano_ciclos_clientes import ciclos


def registrar_ciclo_pago(
    db,
    *,
    barbearia_id: int,
    assinatura_id: int,
    pagamento_plano_id: int,
    periodo_inicio: datetime,
    periodo_fim: datetime,
    creditos_concedidos: int,
    referencia_mes: str | None = None,
):
    """Insere o ciclo na transacao atual, sem commit.

    Chamador deve controlar commit/rollback.
    Requer que o pagamento e a assinatura ja existam.
    """
    if (
        not isinstance(periodo_inicio, datetime)
        or not isinstance(periodo_fim, datetime)
        or periodo_fim <= periodo_inicio
    ):
        raise HTTPException(
            status_code=400,
            detail="Periodo do ciclo invalido.",
        )

    if (
        not isinstance(creditos_concedidos, int)
        or isinstance(creditos_concedidos, bool)
        or creditos_concedidos < 0
    ):
        raise HTTPException(
            status_code=400,
            detail="Quantidade de creditos invalida.",
        )

    assinatura = (
        db.query(models.AssinaturaCliente)
        .filter(
            models.AssinaturaCliente.id == assinatura_id,
            models.AssinaturaCliente.barbearia_id == barbearia_id,
        )
        .with_for_update(of=models.AssinaturaCliente)
        .first()
    )

    if assinatura is None:
        raise HTTPException(
            status_code=404,
            detail="Assinatura nao encontrada na barbearia.",
        )

    pagamento = (
        db.query(models.PagamentoPlano)
        .filter(
            models.PagamentoPlano.id == pagamento_plano_id,
            models.PagamentoPlano.assinatura_id == assinatura.id,
            models.PagamentoPlano.cliente_id == assinatura.cliente_id,
            models.PagamentoPlano.status == "PAGO",
        )
        .first()
    )

    if pagamento is None:
        raise HTTPException(
            status_code=409,
            detail="Pagamento confirmado nao pertence a assinatura.",
        )

    plano = (
        db.query(models.Plano)
        .filter(
            models.Plano.id == pagamento.plano_id,
            models.Plano.barbearia_id == barbearia_id,
        )
        .first()
    )

    if plano is None:
        raise HTTPException(
            status_code=409,
            detail="Plano do pagamento nao pertence a barbearia.",
        )

    if (
        referencia_mes is not None
        and pagamento.referencia_mes != referencia_mes
    ):
        raise HTTPException(
            status_code=409,
            detail="Referencia do pagamento divergente.",
        )

    existente = db.execute(
        select(ciclos.c.id).where(
            ciclos.c.pagamento_plano_id == pagamento.id
        )
    ).first()

    if existente:
        raise HTTPException(
            status_code=409,
            detail="Ciclo ja registrado para este pagamento.",
        )

    sobreposicao = db.execute(
        select(ciclos.c.id).where(
            ciclos.c.barbearia_id == barbearia_id,
            ciclos.c.assinatura_id == assinatura.id,
            ciclos.c.periodo_inicio < periodo_fim,
            ciclos.c.periodo_fim > periodo_inicio,
        )
    ).first()

    if sobreposicao:
        raise HTTPException(
            status_code=409,
            detail="Periodo sobreposto a outro ciclo da assinatura.",
        )

    resultado = db.execute(
        ciclos.insert().values(
            barbearia_id=barbearia_id,
            assinatura_id=assinatura.id,
            plano_id=pagamento.plano_id,
            pagamento_plano_id=pagamento.id,
            periodo_inicio=periodo_inicio,
            periodo_fim=periodo_fim,
            creditos_concedidos=creditos_concedidos,
            referencia_mes=pagamento.referencia_mes,
            criado_em=datetime.now(),
        )
    )

    return resultado.inserted_primary_key[0]
