from fastapi import HTTPException

import models


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
    Busca e bloqueia a linha do produto durante a transação.

    PostgreSQL aplica SELECT ... FOR UPDATE. No SQLite de desenvolvimento,
    o dialect não oferece lock de linha equivalente, mas a mesma função
    continua compatível para testes locais.
    """
    produto = (
        db.query(models.Produto)
        .filter(
            models.Produto.id == produto_id,
            models.Produto.barbearia_id == barbearia_id,
            models.Produto.ativo.is_(True),
        )
        .with_for_update()
        .first()
    )

    if produto is None:
        raise HTTPException(
            status_code=404,
            detail="Produto não encontrado ou inativo.",
        )

    return produto


def baixar_estoque(produto, quantidade):
    """
    Baixa estoque sobre uma instância que deve ter sido obtida por
    obter_produto_para_movimentacao() dentro da mesma transação.
    """
    validar_estoque(produto, quantidade)
    produto.estoque = (produto.estoque or 0) - quantidade


def devolver_estoque(produto, quantidade):
    if quantidade is None or quantidade <= 0:
        return

    produto.estoque = (produto.estoque or 0) + quantidade
