from datetime import date

from fastapi import HTTPException, status

import models

from auth.tenant import (
    buscar_da_barbearia,
    consultar_da_barbearia,
    obter_barbearia_id,
)

from services.caixa_service import registrar_saida_caixa
from services.financeiro_common import (
    normalizar_forma_pagamento,
    validar_status_filtro,
)


STATUS_PENDENTE = "PENDENTE"
STATUS_PAGA = "PAGA"

def _obter_usuario_id(usuario_logado) -> int | None:
    if isinstance(usuario_logado, dict):
        return usuario_logado.get("id")

    return getattr(
        usuario_logado,
        "id",
        None,
    )


def _validar_valor(valor: float) -> None:
    if valor is None or valor <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O valor deve ser maior que zero.",
        )


def criar_conta_pagar_service(
    db,
    dados,
    usuario_logado,
):
    _validar_valor(dados.valor)

    descricao = (dados.descricao or "").strip()

    if not descricao:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A descrição é obrigatória.",
        )

    try:
        conta = models.ContaPagar(
            descricao=descricao,
            fornecedor=(
                dados.fornecedor.strip()
                if dados.fornecedor
                else None
            ),
            valor=dados.valor,
            vencimento=dados.vencimento,
            forma_pagamento=normalizar_forma_pagamento(
                dados.forma_pagamento
            ),
            observacoes=dados.observacoes,
            status=STATUS_PENDENTE,
            barbearia_id=obter_barbearia_id(
                usuario_logado
            ),
        )

        db.add(conta)
        db.commit()
        db.refresh(conta)

        return conta

    except HTTPException:
        db.rollback()
        raise

    except Exception as erro:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar conta a pagar: {erro}",
        )


def listar_contas_pagar_service(
    db,
    usuario_logado,
    status_filtro: str | None = None,
):
    query = consultar_da_barbearia(
        db=db,
        model=models.ContaPagar,
        usuario=usuario_logado,
    )

    status_normalizado = validar_status_filtro(
        status_filtro,
        {STATUS_PENDENTE, STATUS_PAGA},
    )

    if status_normalizado:
        query = query.filter(
            models.ContaPagar.status == status_normalizado
        )

    return (
        query
        .order_by(
            models.ContaPagar.vencimento.asc(),
            models.ContaPagar.id.asc(),
        )
        .all()
    )


def buscar_conta_pagar_service(
    db,
    conta_id: int,
    usuario_logado,
):
    return buscar_da_barbearia(
        db=db,
        model=models.ContaPagar,
        registro_id=conta_id,
        usuario=usuario_logado,
        mensagem_nao_encontrado=(
            "Conta a pagar não encontrada."
        ),
    )


def pagar_conta_service(
    db,
    conta_id: int,
    forma_pagamento: str | None,
    usuario_logado,
):
    barbearia_id = obter_barbearia_id(usuario_logado)

    try:
        conta = (
            db.query(models.ContaPagar)
            .filter(
                models.ContaPagar.id == conta_id,
                models.ContaPagar.barbearia_id == barbearia_id,
            )
            .with_for_update()
            .first()
        )

        if conta is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conta a pagar não encontrada.",
            )

        if conta.status == STATUS_PAGA:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conta já paga.",
            )

        if forma_pagamento is not None:
            conta.forma_pagamento = normalizar_forma_pagamento(
                forma_pagamento,
                permitir_none=False,
            )
        elif conta.forma_pagamento:
            conta.forma_pagamento = normalizar_forma_pagamento(
                conta.forma_pagamento
            )

        conta.status = STATUS_PAGA
        conta.data_pagamento = date.today()

        registrar_saida_caixa(
            db=db,
            descricao=f"Pagamento de conta: {conta.descricao}",
            valor=conta.valor,
            forma_pagamento=conta.forma_pagamento,
            barbearia_id=conta.barbearia_id,
            origem="CONTA_PAGAR",
            referencia_id=conta.id,
            observacoes=conta.observacoes,
            usuario_id=_obter_usuario_id(usuario_logado),
        )

        db.commit()
        db.refresh(conta)
        return conta

    except HTTPException:
        db.rollback()
        raise

    except Exception as erro:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao pagar conta: {erro}",
        )


def atualizar_conta_pagar_service(
    db,
    conta_id: int,
    dados,
    usuario_logado,
):
    conta = buscar_conta_pagar_service(
        db=db,
        conta_id=conta_id,
        usuario_logado=usuario_logado,
    )

    if conta.status != STATUS_PENDENTE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Somente contas pendentes podem ser editadas.",
        )

    if dados.descricao is not None:
        descricao = dados.descricao.strip()
        if not descricao:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A descrição é obrigatória.",
            )
        conta.descricao = descricao

    if dados.valor is not None:
        _validar_valor(dados.valor)
        conta.valor = dados.valor

    if dados.vencimento is not None:
        conta.vencimento = dados.vencimento

    if dados.fornecedor is not None:
        conta.fornecedor = dados.fornecedor.strip() or None

    if dados.forma_pagamento is not None:
        conta.forma_pagamento = normalizar_forma_pagamento(
            dados.forma_pagamento
        )

    if dados.observacoes is not None:
        conta.observacoes = dados.observacoes.strip() or None

    try:
        db.commit()
        db.refresh(conta)
        return conta
    except Exception as erro:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar conta a pagar: {erro}",
        )


def excluir_conta_pagar_service(
    db,
    conta_id: int,
    usuario_logado,
):
    conta = buscar_conta_pagar_service(
        db=db,
        conta_id=conta_id,
        usuario_logado=usuario_logado,
    )

    if conta.status == STATUS_PAGA:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Uma conta paga não pode ser excluída. "
                "Mantenha o registro para auditoria financeira."
            ),
        )

    try:
        db.delete(conta)
        db.commit()

        return {
            "mensagem": (
                "Conta a pagar excluída com sucesso."
            )
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as erro:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao excluir conta: {erro}",
        )