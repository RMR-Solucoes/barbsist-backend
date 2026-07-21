from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db

import models

from schemas import (
    ProdutoCreate,
    ProdutoUpdate,
    ProdutoResponse,
)

from auth.permissions import (
    admin_gerente_ou_recepcao,
)

from services.produto_service import (
    criar_produto_service,
    listar_produtos_service,
    buscar_produto_service,
    atualizar_produto_service,
    inativar_produto_service,
    reativar_produto_service,
)


router = APIRouter(
    prefix="/produtos",
    tags=["Produtos"],
)


@router.post(
    "",
    response_model=ProdutoResponse,
)
def criar_produto(
    produto: ProdutoCreate,
    db: Session = Depends(get_db),
    usuario_logado: models.Usuario = Depends(
        admin_gerente_ou_recepcao
    ),
):
    return criar_produto_service(
        dados=produto,
        db=db,
        usuario_logado=usuario_logado,
    )


@router.get(
    "",
    response_model=list[ProdutoResponse],
)
def listar_produtos(
    apenas_ativos: bool = Query(
        default=True
    ),
    db: Session = Depends(get_db),
    usuario_logado: models.Usuario = Depends(
        admin_gerente_ou_recepcao
    ),
):
    return listar_produtos_service(
        db=db,
        usuario_logado=usuario_logado,
        apenas_ativos=apenas_ativos,
    )


@router.get(
    "/{produto_id}",
    response_model=ProdutoResponse,
)
def buscar_produto(
    produto_id: int,
    db: Session = Depends(get_db),
    usuario_logado: models.Usuario = Depends(
        admin_gerente_ou_recepcao
    ),
):
    return buscar_produto_service(
        produto_id=produto_id,
        db=db,
        usuario_logado=usuario_logado,
        exigir_ativo=True,
    )


@router.put(
    "/{produto_id}",
    response_model=ProdutoResponse,
)
def atualizar_produto(
    produto_id: int,
    dados: ProdutoUpdate,
    db: Session = Depends(get_db),
    usuario_logado: models.Usuario = Depends(
        admin_gerente_ou_recepcao
    ),
):
    return atualizar_produto_service(
        produto_id=produto_id,
        dados=dados,
        db=db,
        usuario_logado=usuario_logado,
    )


@router.delete(
    "/{produto_id}",
)
def deletar_produto(
    produto_id: int,
    db: Session = Depends(get_db),
    usuario_logado: models.Usuario = Depends(
        admin_gerente_ou_recepcao
    ),
):
    produto = inativar_produto_service(
        produto_id=produto_id,
        db=db,
        usuario_logado=usuario_logado,
    )

    return {
        "mensagem": (
            "Produto desativado com sucesso."
        ),
        "produto": {
            "id": produto.id,
            "codigo": produto.codigo,
            "nome": produto.nome,
            "ativo": produto.ativo,
        },
    }


@router.put(
    "/{produto_id}/reativar",
    response_model=ProdutoResponse,
)
def reativar_produto(
    produto_id: int,
    db: Session = Depends(get_db),
    usuario_logado: models.Usuario = Depends(
        admin_gerente_ou_recepcao
    ),
):
    return reativar_produto_service(
        produto_id=produto_id,
        db=db,
        usuario_logado=usuario_logado,
    )