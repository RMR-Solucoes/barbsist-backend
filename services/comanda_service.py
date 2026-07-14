
from datetime import datetime
from types import SimpleNamespace

from fastapi import HTTPException

import models

from services.caixa_service import registrar_entrada_caixa
from services.comissao_service import calcular_e_registrar_comissao
from services.plano_service import (
    atualizar_status_assinatura,
    usar_plano_service
)


def calcular_total_devido_comanda(itens):
    """
    Calcula somente o valor que deve ser pago no fechamento.

    Serviços utilizados pelo plano não entram no total devido.
    Produtos e serviços avulsos entram normalmente.
    """
    return sum(
        item.subtotal or 0
        for item in itens
        if not (
            item.tipo == "servico"
            and item.pago_com_plano is True
        )
    )


def obter_assinatura_disponivel_comanda_service(
    db,
    comanda_id: int
):
    comanda = (
        db.query(models.Comanda)
        .filter(
            models.Comanda.id == comanda_id
        )
        .first()
    )

    if not comanda:
        raise HTTPException(
            status_code=404,
            detail="Comanda não encontrada"
        )

    if comanda.cliente_id is None:
        return {
            "possui_assinatura": False,
            "pode_usar_plano": False,
            "motivo": (
                "A comanda não está vinculada a um cliente"
            ),
            "assinatura": None
        }

    assinaturas = (
        db.query(models.AssinaturaCliente)
        .filter(
            models.AssinaturaCliente.cliente_id ==
            comanda.cliente_id
        )
        .order_by(
            models.AssinaturaCliente.id.desc()
        )
        .all()
    )

    if not assinaturas:
        return {
            "possui_assinatura": False,
            "pode_usar_plano": False,
            "motivo": (
                "O cliente não possui assinatura cadastrada"
            ),
            "assinatura": None
        }

    houve_alteracao = False

    for assinatura in assinaturas:
        status_anterior = assinatura.status
        pagamento_anterior = (
            assinatura.status_pagamento
        )

        atualizar_status_assinatura(assinatura)

        if (
            assinatura.status != status_anterior
            or assinatura.status_pagamento
            != pagamento_anterior
        ):
            houve_alteracao = True

    if houve_alteracao:
        db.commit()

    assinatura_disponivel = next(
        (
            assinatura
            for assinatura in assinaturas
            if assinatura.status == "ATIVO"
            and assinatura.status_pagamento == "PAGO"
        ),
        None
    )

    if assinatura_disponivel:
        plano = (
            db.query(models.Plano)
            .filter(
                models.Plano.id ==
                assinatura_disponivel.plano_id
            )
            .first()
        )

        servicos_permitidos_ids = [
            vinculo.servico_id
            for vinculo in (
                db.query(models.PlanoServico)
                .filter(
                    models.PlanoServico.plano_id ==
                    assinatura_disponivel.plano_id
                )
                .all()
            )
        ]

        pode_usar = (
            assinatura_disponivel.usos_disponiveis
            is not None
            and assinatura_disponivel.usos_disponiveis > 0
        )

        return {
            "possui_assinatura": True,
            "pode_usar_plano": pode_usar,
            "motivo": (
                None
                if pode_usar
                else "O plano não possui usos disponíveis"
            ),
            "assinatura": {
                "id": assinatura_disponivel.id,
                "cliente_id": (
                    assinatura_disponivel.cliente_id
                ),
                "plano_id": (
                    assinatura_disponivel.plano_id
                ),
                "plano_nome": (
                    plano.nome if plano else None
                ),
                "status": assinatura_disponivel.status,
                "status_pagamento": (
                    assinatura_disponivel
                    .status_pagamento
                ),
                "usos_disponiveis": (
                    assinatura_disponivel
                    .usos_disponiveis
                ),
                "data_proximo_vencimento": (
                    assinatura_disponivel
                    .data_proximo_vencimento
                ),
                "servicos_permitidos_ids": (
                    servicos_permitidos_ids
                )
            }
        }

    assinatura_recente = assinaturas[0]

    plano = (
        db.query(models.Plano)
        .filter(
            models.Plano.id ==
            assinatura_recente.plano_id
        )
        .first()
    )

    servicos_permitidos_ids = [
        vinculo.servico_id
        for vinculo in (
            db.query(models.PlanoServico)
            .filter(
                models.PlanoServico.plano_id ==
                assinatura_recente.plano_id
            )
            .all()
        )
    ]

    return {
        "possui_assinatura": True,
        "pode_usar_plano": False,
        "motivo": (
            "Assinatura indisponível para uso. "
            f"Status: {assinatura_recente.status}. "
            "Pagamento: "
            f"{assinatura_recente.status_pagamento}."
        ),
        "assinatura": {
            "id": assinatura_recente.id,
            "cliente_id": (
                assinatura_recente.cliente_id
            ),
            "plano_id": (
                assinatura_recente.plano_id
            ),
            "plano_nome": (
                plano.nome if plano else None
            ),
            "status": assinatura_recente.status,
            "status_pagamento": (
                assinatura_recente.status_pagamento
            ),
            "usos_disponiveis": (
                assinatura_recente.usos_disponiveis
            ),
            "data_proximo_vencimento": (
                assinatura_recente
                .data_proximo_vencimento
            ),
            "servicos_permitidos_ids": (
                servicos_permitidos_ids
            )
        }
    }


def usar_plano_em_item_comanda_service(
    db,
    comanda_id: int,
    item_id: int,
    assinatura_id: int
):
    try:
        comanda = db.query(models.Comanda).filter(
            models.Comanda.id == comanda_id,
            models.Comanda.status == "aberta"
        ).first()

        if not comanda:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Comanda não encontrada ou já fechada"
                )
            )

        if comanda.cliente_id is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "A comanda precisa estar vinculada "
                    "a um cliente para utilizar o plano"
                )
            )

        item = db.query(models.ItemComanda).filter(
            models.ItemComanda.id == item_id,
            models.ItemComanda.comanda_id == comanda_id
        ).first()

        if not item:
            raise HTTPException(
                status_code=404,
                detail="Item não encontrado nesta comanda"
            )

        if item.tipo != "servico":
            raise HTTPException(
                status_code=400,
                detail=(
                    "Somente serviços podem ser "
                    "utilizados pelo plano"
                )
            )

        if item.servico_id is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "O item não possui um serviço vinculado"
                )
            )

        if item.quantidade != 1:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Para utilizar o plano, o serviço "
                    "deve ser lançado com quantidade 1"
                )
            )

        if item.pago_com_plano is True:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Este serviço já foi utilizado "
                    "pelo plano"
                )
            )

        if item.uso_plano_id is not None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Este item já possui um uso de "
                    "plano registrado"
                )
            )

        assinatura = db.query(
            models.AssinaturaCliente
        ).filter(
            models.AssinaturaCliente.id ==
            assinatura_id
        ).first()

        if not assinatura:
            raise HTTPException(
                status_code=404,
                detail="Assinatura não encontrada"
            )

        if assinatura.cliente_id != comanda.cliente_id:
            raise HTTPException(
                status_code=400,
                detail=(
                    "A assinatura não pertence ao "
                    "cliente desta comanda"
                )
            )

        dados_uso = SimpleNamespace(
            assinatura_id=assinatura.id,
            comanda_id=comanda.id,
            servico_id=item.servico_id
        )

        uso = usar_plano_service(
            db=db,
            dados=dados_uso,
            realizar_commit=False
        )

        item.pago_com_plano = True
        item.uso_plano_id = uso.id

        db.flush()

        itens = db.query(models.ItemComanda).filter(
            models.ItemComanda.comanda_id ==
            comanda.id
        ).all()

        comanda.total = calcular_total_devido_comanda(
            itens
        )

        db.commit()

        db.refresh(item)
        db.refresh(comanda)
        db.refresh(assinatura)
        db.refresh(uso)

        return {
            "mensagem": (
                "Serviço utilizado pelo plano com sucesso"
            ),
            "comanda_id": comanda.id,
            "item_id": item.id,
            "uso_plano_id": uso.id,
            "assinatura_id": assinatura.id,
            "plano_id": assinatura.plano_id,
            "usos_disponiveis": (
                assinatura.usos_disponiveis
            ),
            "total_comanda": comanda.total
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as erro:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Erro ao utilizar plano na comanda: "
                f"{str(erro)}"
            )
        )


def fechar_comanda_service(
    db,
    comanda_id: int,
    forma_pagamento: str
):
    try:
        comanda = db.query(models.Comanda).filter(
            models.Comanda.id == comanda_id,
            models.Comanda.status == "aberta"
        ).first()

        if not comanda:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Comanda não encontrada ou já fechada"
                )
            )

        itens = db.query(models.ItemComanda).filter(
            models.ItemComanda.comanda_id ==
            comanda_id
        ).all()

        if not itens:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Não é possível fechar uma "
                    "comanda sem itens"
                )
            )

        total_devido = calcular_total_devido_comanda(
            itens
        )

        possui_item_plano = any(
            item.tipo == "servico"
            and item.pago_com_plano is True
            for item in itens
        )

        comanda.total = total_devido

        if total_devido == 0 and possui_item_plano:
            comanda.forma_pagamento = "plano"

        elif possui_item_plano:
            comanda.forma_pagamento = (
                f"plano + {forma_pagamento}"
            )

        else:
            comanda.forma_pagamento = forma_pagamento

        comanda.status = "fechada"
        comanda.data_fechamento = datetime.now()

        if total_devido > 0:
            registrar_entrada_caixa(
                db=db,
                descricao=f"Comanda #{comanda.id}",
                valor=total_devido,
                forma_pagamento=forma_pagamento
            )

        valor_comissao = calcular_e_registrar_comissao(
            db=db,
            barbeiro_id=comanda.barbeiro_id,
            comanda_id=comanda.id,
            itens=itens
        )

        db.commit()
        db.refresh(comanda)

        return {
            "mensagem": "Comanda fechada com sucesso",
            "comanda_id": comanda.id,
            "total": total_devido,
            "forma_pagamento": (
                comanda.forma_pagamento
            ),
            "possui_item_plano": possui_item_plano,
            "comissao": valor_comissao
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as erro:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Erro ao fechar comanda: "
                f"{str(erro)}"
            )
        )

