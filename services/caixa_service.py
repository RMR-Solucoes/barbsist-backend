import models


def registrar_entrada_caixa(
    db,
    descricao: str,
    valor: float,
    forma_pagamento: str
):
    movimentacao = models.Caixa(
        tipo="entrada",
        descricao=descricao,
        valor=valor,
        forma_pagamento=forma_pagamento
    )

    db.add(movimentacao)
    return movimentacao


def registrar_saida_caixa(
    db,
    descricao: str,
    valor: float,
    forma_pagamento: str | None = None
):
    movimentacao = models.Caixa(
        tipo="saida",
        descricao=descricao,
        valor=valor,
        forma_pagamento=forma_pagamento
    )

    db.add(movimentacao)
    db.commit()
    db.refresh(movimentacao)

    return movimentacao


def registrar_movimentacao_caixa(db, dados):
    movimentacao = models.Caixa(
        tipo=dados.tipo,
        descricao=dados.descricao,
        valor=dados.valor,
        forma_pagamento=dados.forma_pagamento
    )

    db.add(movimentacao)
    db.commit()
    db.refresh(movimentacao)

    return movimentacao