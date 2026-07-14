from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

import models

from database import get_db

from schemas import (
    ComandaCreate,
    ComandaResponse,
    AdicionarServicoComanda,
    AdicionarProdutoComanda,
    ItemComandaResponse,
    FecharComanda,
    UsarPlanoItemComandaRequest
)

from services.comanda_service import (
    fechar_comanda_service,
    obter_assinatura_disponivel_comanda_service,
    usar_plano_em_item_comanda_service
)

from services.estoque_service import (
    validar_estoque,
    baixar_estoque
)

from auth.permissions import (
    admin_gerente_recepcao_ou_barbeiro
)

from auth.dependencies import (
    get_barbeiro_logado
)


router = APIRouter(
    prefix="/comandas",
    tags=["Comandas"],
    dependencies=[
        Depends(
            admin_gerente_recepcao_ou_barbeiro
        )
    ]
)


@router.post(
    "",
    response_model=ComandaResponse
)
def abrir_comanda(
    comanda: ComandaCreate,
    db: Session = Depends(get_db)
):
    barbeiro = db.query(models.Barbeiro).filter(
        models.Barbeiro.id ==
        comanda.barbeiro_id,
        models.Barbeiro.ativo == True
    ).first()

    if not barbeiro:
        raise HTTPException(
            status_code=404,
            detail="Barbeiro não encontrado ou inativo"
        )

    if comanda.cliente_id is not None:
        cliente = db.query(models.Cliente).filter(
            models.Cliente.id ==
            comanda.cliente_id,
            models.Cliente.ativo == True
        ).first()

        if not cliente:
            raise HTTPException(
                status_code=404,
                detail="Cliente não encontrado ou inativo"
            )

    nova_comanda = models.Comanda(
        cliente_id=comanda.cliente_id,
        barbeiro_id=comanda.barbeiro_id,
        status="aberta",
        total=0
    )

    db.add(nova_comanda)
    db.commit()
    db.refresh(nova_comanda)

    return nova_comanda


@router.get(
    "",
    response_model=list[ComandaResponse]
)
def listar_comandas(
    db: Session = Depends(get_db)
):
    return (
        db.query(models.Comanda)
        .options(
            joinedload(models.Comanda.cliente),
            joinedload(models.Comanda.barbeiro),
            joinedload(models.Comanda.itens)
        )
        .order_by(models.Comanda.id.desc())
        .all()
    )


@router.get(
    "/minhas",
    response_model=list[ComandaResponse]
)
def minhas_comandas(
    barbeiro_id: int = Depends(
        get_barbeiro_logado
    ),
    db: Session = Depends(get_db)
):
    return (
        db.query(models.Comanda)
        .options(
            joinedload(models.Comanda.cliente),
            joinedload(models.Comanda.barbeiro),
            joinedload(models.Comanda.itens)
        )
        .filter(
            models.Comanda.barbeiro_id ==
            barbeiro_id
        )
        .order_by(models.Comanda.id.desc())
        .all()
    )


@router.get(
    "/{comanda_id}",
    response_model=ComandaResponse
)
def buscar_comanda(
    comanda_id: int,
    db: Session = Depends(get_db)
):
    comanda = (
        db.query(models.Comanda)
        .options(
            joinedload(models.Comanda.cliente),
            joinedload(models.Comanda.barbeiro),
            joinedload(models.Comanda.itens)
        )
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

    return comanda


@router.get(
    "/{comanda_id}/assinatura"
)
def consultar_assinatura_da_comanda(
    comanda_id: int,
    db: Session = Depends(get_db)
):
    return obter_assinatura_disponivel_comanda_service(
        db=db,
        comanda_id=comanda_id
    )


@router.post(
    "/{comanda_id}/servicos",
    response_model=ItemComandaResponse
)
def adicionar_servico_na_comanda(
    comanda_id: int,
    item: AdicionarServicoComanda,
    db: Session = Depends(get_db)
):
    if item.quantidade <= 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "A quantidade do serviço deve ser "
                "maior que zero"
            )
        )

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

    servico = db.query(models.Servico).filter(
        models.Servico.id == item.servico_id,
        models.Servico.ativo == True
    ).first()

    if not servico:
        raise HTTPException(
            status_code=404,
            detail="Serviço não encontrado ou inativo"
        )

    subtotal = servico.preco * item.quantidade

    novo_item = models.ItemComanda(
        comanda_id=comanda_id,
        tipo="servico",
        descricao=servico.nome,
        quantidade=item.quantidade,
        valor_unitario=servico.preco,
        subtotal=subtotal,
        servico_id=servico.id,
        pago_com_plano=False,
        uso_plano_id=None
    )

    comanda.total = (
        (comanda.total or 0) + subtotal
    )

    db.add(novo_item)
    db.commit()
    db.refresh(novo_item)

    return novo_item


@router.post(
    "/{comanda_id}/produtos",
    response_model=ItemComandaResponse
)
def adicionar_produto_na_comanda(
    comanda_id: int,
    item: AdicionarProdutoComanda,
    db: Session = Depends(get_db)
):
    if item.quantidade <= 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "A quantidade do produto deve ser "
                "maior que zero"
            )
        )

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

    produto = db.query(models.Produto).filter(
        models.Produto.id == item.produto_id,
        models.Produto.ativo == True
    ).first()

    if not produto:
        raise HTTPException(
            status_code=404,
            detail="Produto não encontrado ou inativo"
        )

    validar_estoque(
        produto=produto,
        quantidade=item.quantidade
    )

    subtotal = (
        produto.preco_venda * item.quantidade
    )

    novo_item = models.ItemComanda(
        comanda_id=comanda_id,
        tipo="produto",
        descricao=produto.nome,
        quantidade=item.quantidade,
        valor_unitario=produto.preco_venda,
        subtotal=subtotal,
        produto_id=produto.id,
        pago_com_plano=False,
        uso_plano_id=None
    )

    baixar_estoque(
        produto=produto,
        quantidade=item.quantidade
    )

    comanda.total = (
        (comanda.total or 0) + subtotal
    )

    db.add(novo_item)
    db.commit()
    db.refresh(novo_item)

    return novo_item


@router.get(
    "/{comanda_id}/itens",
    response_model=list[ItemComandaResponse]
)
def listar_itens_da_comanda(
    comanda_id: int,
    db: Session = Depends(get_db)
):
    comanda = db.query(models.Comanda).filter(
        models.Comanda.id == comanda_id
    ).first()

    if not comanda:
        raise HTTPException(
            status_code=404,
            detail="Comanda não encontrada"
        )

    return (
        db.query(models.ItemComanda)
        .filter(
            models.ItemComanda.comanda_id ==
            comanda_id
        )
        .order_by(models.ItemComanda.id.asc())
        .all()
    )


@router.post(
    "/{comanda_id}/itens/{item_id}/usar-plano"
)
def usar_plano_no_item(
    comanda_id: int,
    item_id: int,
    dados: UsarPlanoItemComandaRequest,
    db: Session = Depends(get_db)
):
    return usar_plano_em_item_comanda_service(
        db=db,
        comanda_id=comanda_id,
        item_id=item_id,
        assinatura_id=dados.assinatura_id
    )


@router.put(
    "/{comanda_id}/fechar"
)
def fechar_comanda(
    comanda_id: int,
    dados: FecharComanda,
    db: Session = Depends(get_db)
):
    return fechar_comanda_service(
        db=db,
        comanda_id=comanda_id,
        forma_pagamento=dados.forma_pagamento
    )

