from datetime import date

from fastapi import HTTPException, status

import models

from auth.tenant import (
    buscar_da_barbearia,
    consultar_da_barbearia,
    obter_barbearia_id,
)

from services.caixa_service import _obter_usuario_id, registrar_entrada_caixa


STATUS_PENDENTE = "PENDENTE"
STATUS_RECEBIDA = "RECEBIDA"


def _validar_valor(valor: float) -> None:
    if valor is None or valor <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O valor deve ser maior que zero.",
        )


def criar_conta_receber_service(
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

    if dados.cliente_id is not None:
        cliente = buscar_da_barbearia(
            db=db,
            model=models.Cliente,
            registro_id=dados.cliente_id,
            usuario=usuario_logado,
            mensagem_nao_encontrado=(
                "Cliente não encontrado."
            ),
        )

        if not cliente.ativo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cliente inativo.",
            )

    try:
        conta = models.ContaReceber(
            descricao=descricao,
            cliente_id=dados.cliente_id,
            valor=dados.valor,
            vencimento=dados.vencimento,
            forma_pagamento=dados.forma_pagamento,
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
            detail=(
                f"Erro ao criar conta a receber: {erro}"
            ),
        )


def listar_contas_receber_service(
    db,
    usuario_logado,
    status_filtro: str | None = None,
):
    query = consultar_da_barbearia(
        db=db,
        model=models.ContaReceber,
        usuario=usuario_logado,
    )

    if status_filtro:
        query = query.filter(
            models.ContaReceber.status
            == status_filtro.strip().upper()
        )

    return (
        query
        .order_by(
            models.ContaReceber.vencimento.asc(),
            models.ContaReceber.id.asc(),
        )
        .all()
    )


def buscar_conta_receber_service(
    db,
    conta_id: int,
    usuario_logado,
):
    return buscar_da_barbearia(
        db=db,
        model=models.ContaReceber,
        registro_id=conta_id,
        usuario=usuario_logado,
        mensagem_nao_encontrado=(
            "Conta a receber não encontrada."
        ),
    )


def receber_conta_service(
    db,
    conta_id: int,
    forma_pagamento: str | None,
    usuario_logado,
):
    conta = buscar_conta_receber_service(
        db=db,
        conta_id=conta_id,
        usuario_logado=usuario_logado,
    )

    if conta.status == STATUS_RECEBIDA:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conta já recebida.",
        )

    try:
        if forma_pagamento and forma_pagamento.strip():
            conta.forma_pagamento = (
                forma_pagamento.strip()
            )

        conta.status = STATUS_RECEBIDA
        conta.data_pagamento = date.today()

        registrar_entrada_caixa(
            db=db,
            descricao=(
                f"Recebimento de conta: {conta.descricao}"
            ),
            valor=conta.valor,
            forma_pagamento=conta.forma_pagamento,
            barbearia_id=conta.barbearia_id,
            origem="CONTA_RECEBER",
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
            detail=(
                f"Erro ao receber conta: {erro}"
            ),
        )


def excluir_conta_receber_service(
    db,
    conta_id: int,
    usuario_logado,
):
    conta = buscar_conta_receber_service(
        db=db,
        conta_id=conta_id,
        usuario_logado=usuario_logado,
    )

    if conta.status == STATUS_RECEBIDA:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Uma conta recebida não pode ser excluída. "
                "Mantenha o registro para auditoria financeira."
            ),
        )

    try:
        db.delete(conta)
        db.commit()

        return {
            "mensagem": (
                "Conta a receber excluída com sucesso."
            )
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as erro:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                f"Erro ao excluir conta: {erro}"
            ),
        )