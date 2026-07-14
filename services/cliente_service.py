from services.plano_service import (
    atualizar_status_assinatura
)

import models


def listar_clientes_com_assinaturas_service(db):
    clientes = (
        db.query(models.Cliente)
        .filter(
            models.Cliente.ativo == True
        )
        .order_by(
            models.Cliente.nome.asc()
        )
        .all()
    )

    resultado = []
    houve_alteracao = False

    for cliente in clientes:
        assinaturas = (
            db.query(models.AssinaturaCliente)
            .filter(
                models.AssinaturaCliente.cliente_id ==
                cliente.id
            )
            .order_by(
                models.AssinaturaCliente.id.desc()
            )
            .all()
        )

        for assinatura in assinaturas:
            status_anterior = assinatura.status
            pagamento_anterior = (
                assinatura.status_pagamento
            )

            atualizar_status_assinatura(
                assinatura
            )

            if (
                assinatura.status != status_anterior
                or assinatura.status_pagamento
                != pagamento_anterior
            ):
                houve_alteracao = True

        assinatura_atual = next(
            (
                assinatura
                for assinatura in assinaturas
                if assinatura.status in [
                    "ATIVO",
                    "VENCIDO",
                    "SUSPENSO"
                ]
            ),
            None
        )

        if assinatura_atual is None and assinaturas:
            assinatura_atual = assinaturas[0]

        plano = None

        if assinatura_atual:
            plano = (
                db.query(models.Plano)
                .filter(
                    models.Plano.id ==
                    assinatura_atual.plano_id
                )
                .first()
            )

        resultado.append(
            {
                "id": cliente.id,
                "nome": cliente.nome,
                "telefone": cliente.telefone,
                "email": cliente.email,
                "observacoes": cliente.observacoes,
                "ativo": cliente.ativo,

                "possui_assinatura": (
                    assinatura_atual is not None
                ),

                "assinatura_id": (
                    assinatura_atual.id
                    if assinatura_atual
                    else None
                ),

                "assinatura_status": (
                    assinatura_atual.status
                    if assinatura_atual
                    else None
                ),

                "status_pagamento": (
                    assinatura_atual.status_pagamento
                    if assinatura_atual
                    else None
                ),

                "plano_id": (
                    assinatura_atual.plano_id
                    if assinatura_atual
                    else None
                ),

                "plano_nome": (
                    plano.nome
                    if plano
                    else None
                ),

                "data_proximo_vencimento": (
                    assinatura_atual
                    .data_proximo_vencimento
                    if assinatura_atual
                    else None
                ),

                "usos_disponiveis": (
                    assinatura_atual.usos_disponiveis
                    if assinatura_atual
                    else None
                ),

                "quantidade_servicos_plano": (
                    plano.quantidade_servicos
                    if plano
                    else None
                )
            }
        )

    if houve_alteracao:
        db.commit()

    return resultado