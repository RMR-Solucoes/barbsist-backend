from fastapi import (
    APIRouter,
    Depends,
)

from sqlalchemy.orm import Session

from database import get_db

from schemas import (
    VendaCreate,
    VendaResponse,
    AdicionarProdutoVenda,
    ItemVendaResponse,
    FecharVenda,
)

from services.venda_service import (
    criar_venda_service,
    listar_vendas_service,
    buscar_venda_service,
    adicionar_produto_venda_service,
    remover_item_venda_service,
    fechar_venda_service,
    cancelar_venda_service,
)

from auth.permissions import (
    admin_gerente_ou_recepcao,
)


router = APIRouter(
    prefix="/vendas",
    tags=["Vendas"],
)


@router.post(
    "",
    response_model=VendaResponse,
)
def criar_venda(
    dados: VendaCreate,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_ou_recepcao
    ),
):
    return criar_venda_service(
        db=db,
        dados=dados,
        usuario_logado=usuario_logado,
    )


@router.get(
    "",
    response_model=list[VendaResponse],
)
def listar_vendas(
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_ou_recepcao
    ),
):
    return listar_vendas_service(
        db=db,
        usuario_logado=usuario_logado,
    )


@router.get(
    "/{venda_id}",
    response_model=VendaResponse,
)
def buscar_venda(
    venda_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_ou_recepcao
    ),
):
    return buscar_venda_service(
        db=db,
        venda_id=venda_id,
        usuario_logado=usuario_logado,
    )


@router.post(
    "/{venda_id}/produtos",
    response_model=ItemVendaResponse,
)
def adicionar_produto_venda(
    venda_id: int,
    dados: AdicionarProdutoVenda,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_ou_recepcao
    ),
):
    return adicionar_produto_venda_service(
        db=db,
        venda_id=venda_id,
        produto_id=dados.produto_id,
        quantidade=dados.quantidade,
        usuario_logado=usuario_logado,
    )


@router.delete(
    "/{venda_id}/itens/{item_id}",
)
def remover_item_venda(
    venda_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_ou_recepcao
    ),
):
    return remover_item_venda_service(
        db=db,
        venda_id=venda_id,
        item_id=item_id,
        usuario_logado=usuario_logado,
    )


@router.put(
    "/{venda_id}/fechar",
)
def fechar_venda(
    venda_id: int,
    dados: FecharVenda,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_ou_recepcao
    ),
):
    return fechar_venda_service(
        db=db,
        venda_id=venda_id,
        forma_pagamento=dados.forma_pagamento,
        usuario_logado=usuario_logado,
    )


@router.put(
    "/{venda_id}/cancelar",
)
def cancelar_venda(
    venda_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_ou_recepcao
    ),
):
    return cancelar_venda_service(
        db=db,
        venda_id=venda_id,
        usuario_logado=usuario_logado,
    )
