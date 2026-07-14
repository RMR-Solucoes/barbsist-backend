import models


def calcular_e_registrar_comissao(
    db,
    barbeiro_id: int,
    comanda_id: int,
    itens: list
):
    barbeiro = db.query(models.Barbeiro).filter(
        models.Barbeiro.id == barbeiro_id
    ).first()

    if not barbeiro:
        return 0

    percentual = barbeiro.percentual_comissao or 0

    valor_servicos = sum(
        item.subtotal
        for item in itens
        if item.tipo == "servico"
    )

    valor_comissao = (valor_servicos * percentual) / 100

    comissao = models.Comissao(
        barbeiro_id=barbeiro.id,
        comanda_id=comanda_id,
        valor_servico=valor_servicos,
        percentual=percentual,
        valor_comissao=valor_comissao
    )

    db.add(comissao)

    return valor_comissao