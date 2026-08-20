from fastapi import HTTPException, status

import models

from auth.tenant import (
    buscar_da_barbearia,
    consultar_da_barbearia,
    obter_barbearia_id,
)


def calcular_e_registrar_comissao(
    db,
    barbeiro_id: int,
    comanda_id: int,
    itens: list,
    usuario_logado,
):
    """
    Calcula e registra a comissão sem executar commit.

    A transação é finalizada pelo fechamento da comanda.
    """
    barbeiro = buscar_da_barbearia(
        db=db,
        model=models.Barbeiro,
        registro_id=barbeiro_id,
        usuario=usuario_logado,
        mensagem_nao_encontrado="Barbeiro não encontrado.",
    )

    comanda = buscar_da_barbearia(
        db=db,
        model=models.Comanda,
        registro_id=comanda_id,
        usuario=usuario_logado,
        mensagem_nao_encontrado="Comanda não encontrada.",
    )

    if comanda.barbeiro_id != barbeiro.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O barbeiro informado não pertence à comanda.",
        )

    comissao_existente = (
        consultar_da_barbearia(
            db=db,
            model=models.Comissao,
            usuario=usuario_logado,
        )
        .filter(
            models.Comissao.comanda_id == comanda.id
        )
        .first()
    )

    if comissao_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A comissão desta comanda já foi registrada.",
        )

    percentual = barbeiro.percentual_comissao or 0

    if percentual < 0 or percentual > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O percentual de comissão deve estar entre 0 e 100.",
        )

    valor_servicos = sum(
        (item.subtotal or 0)
        for item in itens
        if item.tipo == "servico"
    )

    valor_comissao = (
        valor_servicos * percentual
    ) / 100

    comissao = models.Comissao(
        barbeiro_id=barbeiro.id,
        comanda_id=comanda.id,
        valor_servico=valor_servicos,
        percentual=percentual,
        valor_comissao=valor_comissao,
        barbearia_id=obter_barbearia_id(
            usuario_logado
        ),
    )

    db.add(comissao)
    return valor_comissao


def listar_comissoes_service(
    db,
    usuario_logado,
):
    return (
        consultar_da_barbearia(
            db=db,
            model=models.Comissao,
            usuario=usuario_logado,
        )
        .order_by(
            models.Comissao.data.desc(),
            models.Comissao.id.desc(),
        )
        .all()
    )


def listar_comissoes_barbeiro_service(
    db,
    barbeiro_id: int,
    usuario_logado,
):
    buscar_da_barbearia(
        db=db,
        model=models.Barbeiro,
        registro_id=barbeiro_id,
        usuario=usuario_logado,
        mensagem_nao_encontrado="Barbeiro não encontrado.",
    )

    return (
        consultar_da_barbearia(
            db=db,
            model=models.Comissao,
            usuario=usuario_logado,
        )
        .filter(
            models.Comissao.barbeiro_id
            == barbeiro_id
        )
        .order_by(
            models.Comissao.data.desc(),
            models.Comissao.id.desc(),
        )
        .all()
    )


def listar_minhas_comissoes_service(
    db,
    barbeiro_id: int,
    usuario_logado,
):
    barbeiro = buscar_da_barbearia(
        db=db,
        model=models.Barbeiro,
        registro_id=barbeiro_id,
        usuario=usuario_logado,
        mensagem_nao_encontrado="Barbeiro não encontrado.",
    )

    return listar_comissoes_barbeiro_service(
        db=db,
        barbeiro_id=barbeiro.id,
        usuario_logado=usuario_logado,
    )
