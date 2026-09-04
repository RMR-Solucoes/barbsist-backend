from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import joinedload

import models

from auth.tenant import (
    buscar_da_barbearia,
    consultar_da_barbearia,
    obter_barbearia_id,
)

from services.estoque_service import (
    obter_produto_para_movimentacao,
    baixar_estoque,
    devolver_estoque,
)

from services.caixa_service import (
    registrar_entrada_caixa,
)


def criar_venda_service(
    db,
    dados,
    usuario_logado,
):
    barbearia_id = obter_barbearia_id(
        usuario_logado
    )

    cliente = None

    if dados.cliente_id is not None:
        cliente = buscar_da_barbearia(
            db=db,
            model=models.Cliente,
            registro_id=dados.cliente_id,
            usuario=usuario_logado,
            mensagem_nao_encontrado=(
                "Cliente nao encontrado ou inativo."
            ),
        )

        if not cliente.ativo:
            raise HTTPException(
                status_code=404,
                detail="Cliente nao encontrado ou inativo.",
            )

    barbeiro = None

    if dados.barbeiro_id is not None:
        barbeiro = buscar_da_barbearia(
            db=db,
            model=models.Barbeiro,
            registro_id=dados.barbeiro_id,
            usuario=usuario_logado,
            mensagem_nao_encontrado=(
                "Barbeiro nao encontrado ou inativo."
            ),
        )

        if not barbeiro.ativo:
            raise HTTPException(
                status_code=404,
                detail="Barbeiro nao encontrado ou inativo.",
            )

    venda = models.Venda(
        cliente_id=(
            cliente.id if cliente else None
        ),
        barbeiro_id=(
            barbeiro.id if barbeiro else None
        ),
        status="aberta",
        total=0,
        forma_pagamento=None,
        usuario_id=usuario_logado.id,
        barbearia_id=barbearia_id,
    )

    db.add(venda)
    db.commit()
    db.refresh(venda)

    return venda


def listar_vendas_service(
    db,
    usuario_logado,
):
    return (
        consultar_da_barbearia(
            db=db,
            model=models.Venda,
            usuario=usuario_logado,
        )
        .options(
            joinedload(models.Venda.cliente),
            joinedload(models.Venda.barbeiro),
            joinedload(models.Venda.itens),
        )
        .order_by(models.Venda.id.desc())
        .all()
    )


def buscar_venda_service(
    db,
    venda_id: int,
    usuario_logado,
):
    venda = (
        consultar_da_barbearia(
            db=db,
            model=models.Venda,
            usuario=usuario_logado,
        )
        .options(
            joinedload(models.Venda.cliente),
            joinedload(models.Venda.barbeiro),
            joinedload(models.Venda.itens),
        )
        .filter(models.Venda.id == venda_id)
        .first()
    )

    if venda is None:
        raise HTTPException(
            status_code=404,
            detail="Venda nao encontrada.",
        )

    return venda


def adicionar_produto_venda_service(
    db,
    venda_id: int,
    produto_id: int,
    quantidade: int,
    usuario_logado,
):
    if quantidade is None or quantidade <= 0:
        raise HTTPException(
            status_code=400,
            detail="A quantidade deve ser maior que zero.",
        )

    venda = buscar_da_barbearia(
        db=db,
        model=models.Venda,
        registro_id=venda_id,
        usuario=usuario_logado,
        mensagem_nao_encontrado=(
            "Venda nao encontrada ou ja encerrada."
        ),
    )

    if venda.status != "aberta":
        raise HTTPException(
            status_code=404,
            detail="Venda nao encontrada ou ja encerrada.",
        )

    produto = obter_produto_para_movimentacao(
        db,
        produto_id=produto_id,
        barbearia_id=venda.barbearia_id,
    )

    subtotal = (
        produto.preco_venda * quantidade
    )

    baixar_estoque(
        produto,
        quantidade,
    )

    item = models.ItemVenda(
        venda_id=venda.id,
        produto_id=produto.id,
        descricao=produto.nome,
        quantidade=quantidade,
        valor_unitario=produto.preco_venda,
        subtotal=subtotal,
    )

    venda.total = (
        (venda.total or 0) + subtotal
    )

    try:
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    except Exception:
        db.rollback()
        raise


def remover_item_venda_service(
    db,
    venda_id: int,
    item_id: int,
    usuario_logado,
):
    venda = buscar_da_barbearia(
        db=db,
        model=models.Venda,
        registro_id=venda_id,
        usuario=usuario_logado,
        mensagem_nao_encontrado=(
            "Venda nao encontrada ou ja encerrada."
        ),
    )

    if venda.status != "aberta":
        raise HTTPException(
            status_code=404,
            detail="Venda nao encontrada ou ja encerrada.",
        )

    item = (
        db.query(models.ItemVenda)
        .filter(
            models.ItemVenda.id == item_id,
            models.ItemVenda.venda_id == venda.id,
        )
        .first()
    )

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Item da venda nao encontrado.",
        )

    produto = obter_produto_para_movimentacao(
        db,
        produto_id=item.produto_id,
        barbearia_id=venda.barbearia_id,
    )

    devolver_estoque(
        produto,
        item.quantidade or 0,
    )

    venda.total = max(
        0,
        (venda.total or 0)
        - (item.subtotal or 0),
    )

    db.delete(item)
    db.commit()
    db.refresh(venda)

    return {
        "mensagem": "Item removido com sucesso.",
        "venda_id": venda.id,
        "total": venda.total,
    }


def fechar_venda_service(
    db,
    venda_id: int,
    forma_pagamento: str,
    usuario_logado,
):
    venda = buscar_da_barbearia(
        db=db,
        model=models.Venda,
        registro_id=venda_id,
        usuario=usuario_logado,
        mensagem_nao_encontrado=(
            "Venda nao encontrada ou ja encerrada."
        ),
    )

    if venda.status != "aberta":
        raise HTTPException(
            status_code=404,
            detail="Venda nao encontrada ou ja encerrada.",
        )

    itens = (
        db.query(models.ItemVenda)
        .filter(
            models.ItemVenda.venda_id == venda.id
        )
        .all()
    )

    if not itens:
        raise HTTPException(
            status_code=400,
            detail=(
                "Nao e possivel fechar uma venda sem itens."
            ),
        )

    if not forma_pagamento:
        raise HTTPException(
            status_code=400,
            detail="Informe a forma de pagamento.",
        )

    total = sum(
        (item.subtotal or 0)
        for item in itens
    )

    venda.total = total
    venda.forma_pagamento = forma_pagamento
    venda.status = "fechada"
    venda.data_fechamento = datetime.now()

    try:
        registrar_entrada_caixa(
            db=db,
            descricao=f"Venda #{venda.id}",
            valor=total,
            forma_pagamento=forma_pagamento,
            barbearia_id=venda.barbearia_id,
            origem="VENDA",
            referencia_id=venda.id,
            usuario_id=usuario_logado.id,
        )

        db.commit()
        db.refresh(venda)

        return {
            "mensagem": "Venda fechada com sucesso.",
            "venda_id": venda.id,
            "total": venda.total,
            "forma_pagamento": venda.forma_pagamento,
        }

    except Exception:
        db.rollback()
        raise


def cancelar_venda_service(
    db,
    venda_id: int,
    usuario_logado,
):
    venda = buscar_da_barbearia(
        db=db,
        model=models.Venda,
        registro_id=venda_id,
        usuario=usuario_logado,
        mensagem_nao_encontrado=(
            "Venda nao encontrada ou ja encerrada."
        ),
    )

    if venda.status != "aberta":
        raise HTTPException(
            status_code=404,
            detail="Venda nao encontrada ou ja encerrada.",
        )

    itens = (
        db.query(models.ItemVenda)
        .filter(
            models.ItemVenda.venda_id == venda.id
        )
        .all()
    )

    try:
        for item in itens:
            produto = obter_produto_para_movimentacao(
                db,
                produto_id=item.produto_id,
                barbearia_id=venda.barbearia_id,
            )

            devolver_estoque(
                produto,
                item.quantidade or 0,
            )

        venda.status = "cancelada"
        venda.total = 0
        venda.forma_pagamento = None
        venda.data_fechamento = None

        db.commit()
        db.refresh(venda)

        return {
            "mensagem": "Venda cancelada com sucesso.",
            "venda_id": venda.id,
            "status": venda.status,
        }

    except Exception:
        db.rollback()
        raise
