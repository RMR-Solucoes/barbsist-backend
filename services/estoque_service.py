from fastapi import HTTPException

import models


def validar_estoque(produto, quantidade):
    if produto.estoque < quantidade:
        raise HTTPException(
            status_code=400,
            detail="Estoque insuficiente"
        )


def baixar_estoque(produto, quantidade):
    produto.estoque -= quantidade