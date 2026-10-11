from fastapi import HTTPException

import models

from auth.tenant import obter_barbearia_id


def validar_estoque(produto, quantidade):
    if quantidade is None or quantidade <= 0:
        raise HTTPException(
            status_code=400,
            detail="A quantidade deve ser maior que zero.",
        )

    if (produto.estoque or 0) < quantidade:
        raise HTTPException(
            status_code=400,
            detail="Estoque insuficiente",
        )


def obter_produto_para_movimentacao(
    db,
    *,
    produto_id: int,
    barbearia_id: int,
):
    """
    Busca e bloqueia o produto da barbearia durante a transação.
    """
    produto = (
        db.query(models.Produto)
        .filter(
            models.Produto.id == produto_id,
            models.Produto.barbearia_id == barbearia_id,
            models.Produto.ativo.is_(True),
        )
        .with_for_update(of=models.Produto)
        .first()
    )

    if produto is None:
        raise HTTPException(
            status_code=404,
            detail="Produto não encontrado ou inativo.",
        )

    return produto


def registrar_movimentacao_estoque(
    db,
    *,
    produto,
    tipo: str,
    origem: str,
    quantidade: int,
    saldo_anterior: int,
    saldo_posterior: int,
    referencia_id: int | None = None,
    usuario_id: int | None = None,
    observacao: str | None = None,
):
    movimento = models.MovimentacaoEstoque(
        barbearia_id=produto.barbearia_id,
        produto_id=produto.id,
        tipo=tipo,
        origem=origem,
        quantidade=max(0, int(quantidade or 0)),
        saldo_anterior=int(saldo_anterior or 0),
        saldo_posterior=int(saldo_posterior or 0),
        referencia_id=referencia_id,
        usuario_id=usuario_id,
        observacao=(observacao or "").strip() or None,
    )

    db.add(movimento)
    return movimento


def baixar_estoque(
    produto,
    quantidade,
    *,
    db=None,
    origem: str | None = None,
    referencia_id: int | None = None,
    usuario_id: int | None = None,
    observacao: str | None = None,
):
    validar_estoque(produto, quantidade)

    saldo_anterior = int(produto.estoque or 0)
    produto.estoque = saldo_anterior - quantidade

    if db is not None and origem:
        registrar_movimentacao_estoque(
            db,
            produto=produto,
            tipo="SAIDA",
            origem=origem,
            quantidade=quantidade,
            saldo_anterior=saldo_anterior,
            saldo_posterior=produto.estoque,
            referencia_id=referencia_id,
            usuario_id=usuario_id,
            observacao=observacao,
        )


def devolver_estoque(
    produto,
    quantidade,
    *,
    db=None,
    origem: str | None = None,
    referencia_id: int | None = None,
    usuario_id: int | None = None,
    observacao: str | None = None,
):
    if quantidade is None or quantidade <= 0:
        return

    saldo_anterior = int(produto.estoque or 0)
    produto.estoque = saldo_anterior + quantidade

    if db is not None and origem:
        registrar_movimentacao_estoque(
            db,
            produto=produto,
            tipo="ENTRADA",
            origem=origem,
            quantidade=quantidade,
            saldo_anterior=saldo_anterior,
            saldo_posterior=produto.estoque,
            referencia_id=referencia_id,
            usuario_id=usuario_id,
            observacao=observacao,
        )


def entrada_estoque_service(
    db,
    produto_id: int,
    quantidade: int,
    observacao,
    usuario_logado,
):
    barbearia_id = obter_barbearia_id(usuario_logado)

    produto = obter_produto_para_movimentacao(
        db,
        produto_id=produto_id,
        barbearia_id=barbearia_id,
    )

    saldo_anterior = int(produto.estoque or 0)
    produto.estoque = saldo_anterior + quantidade

    registrar_movimentacao_estoque(
        db,
        produto=produto,
        tipo="ENTRADA",
        origem="ENTRADA_MANUAL",
        quantidade=quantidade,
        saldo_anterior=saldo_anterior,
        saldo_posterior=produto.estoque,
        usuario_id=getattr(usuario_logado, "id", None),
        observacao=observacao,
    )

    db.commit()
    db.refresh(produto)
    return produto


def ajustar_estoque_service(
    db,
    produto_id: int,
    novo_estoque: int,
    observacao: str,
    usuario_logado,
):
    barbearia_id = obter_barbearia_id(usuario_logado)

    produto = obter_produto_para_movimentacao(
        db,
        produto_id=produto_id,
        barbearia_id=barbearia_id,
    )

    saldo_anterior = int(produto.estoque or 0)
    novo_estoque = int(novo_estoque)
    observacao_normalizada = (observacao or "").strip()

    if len(observacao_normalizada) < 3:
        raise HTTPException(
            status_code=400,
            detail="Informe o motivo do ajuste com pelo menos 3 caracteres.",
        )

    if novo_estoque == saldo_anterior:
        raise HTTPException(
            status_code=400,
            detail="O novo estoque é igual ao saldo atual.",
        )

    quantidade = abs(novo_estoque - saldo_anterior)
    tipo = "ENTRADA" if novo_estoque > saldo_anterior else "SAIDA"
    produto.estoque = novo_estoque

    registrar_movimentacao_estoque(
        db,
        produto=produto,
        tipo=tipo,
        origem="AJUSTE_MANUAL",
        quantidade=quantidade,
        saldo_anterior=saldo_anterior,
        saldo_posterior=novo_estoque,
        usuario_id=getattr(usuario_logado, "id", None),
        observacao=observacao_normalizada,
    )

    db.commit()
    db.refresh(produto)
    return produto


def listar_movimentacoes_estoque_service(
    db,
    produto_id: int,
    usuario_logado,
    limite: int = 50,
):
    barbearia_id = obter_barbearia_id(usuario_logado)

    produto = (
        db.query(models.Produto)
        .filter(
            models.Produto.id == produto_id,
            models.Produto.barbearia_id == barbearia_id,
        )
        .first()
    )

    if produto is None:
        raise HTTPException(
            status_code=404,
            detail="Produto não encontrado.",
        )

    return (
        db.query(models.MovimentacaoEstoque)
        .filter(
            models.MovimentacaoEstoque.barbearia_id == barbearia_id,
            models.MovimentacaoEstoque.produto_id == produto_id,
        )
        .order_by(models.MovimentacaoEstoque.id.desc())
        .limit(limite)
        .all()
    )
