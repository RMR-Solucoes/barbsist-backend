
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db

import models

from schemas import (
    ProdutoCreate,
    ProdutoUpdate,
    ProdutoResponse,
    EntradaEstoqueRequest,
    AjusteEstoqueRequest,
    MovimentacaoEstoqueResponse,
)

from auth.permissions import (
    admin_gerente_ou_recepcao,
    todos_logados,
)

from services.produto_service import (
    criar_produto_service,
    listar_produtos_service,
    buscar_produto_service,
    atualizar_produto_service,
    inativar_produto_service,
    reativar_produto_service,
)

from services.estoque_service import (
    entrada_estoque_service,
    ajustar_estoque_service,
    listar_movimentacoes_estoque_service,
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
    apenas_ativos: bool = Query(default=True),
    db: Session = Depends(get_db),
    usuario_logado: models.Usuario = Depends(
        todos_logados
    ),
):
    return listar_produtos_service(
        db=db,
        usuario_logado=usuario_logado,
        apenas_ativos=apenas_ativos,
    )


@router.post(
    "/{produto_id}/estoque/entrada",
    response_model=ProdutoResponse,
)
def entrada_estoque(
    produto_id: int,
    dados: EntradaEstoqueRequest,
    db: Session = Depends(get_db),
    usuario_logado: models.Usuario = Depends(
        admin_gerente_ou_recepcao
    ),
):
    return entrada_estoque_service(
        db=db,
        produto_id=produto_id,
        quantidade=dados.quantidade,
        observacao=dados.observacao,
        usuario_logado=usuario_logado,
    )


@router.post(
    "/{produto_id}/estoque/ajuste",
    response_model=ProdutoResponse,
)
def ajustar_estoque(
    produto_id: int,
    dados: AjusteEstoqueRequest,
    db: Session = Depends(get_db),
    usuario_logado: models.Usuario = Depends(
        admin_gerente_ou_recepcao
    ),
):
    return ajustar_estoque_service(
        db=db,
        produto_id=produto_id,
        novo_estoque=dados.novo_estoque,
        observacao=dados.observacao,
        usuario_logado=usuario_logado,
    )


@router.get(
    "/{produto_id}/estoque/movimentacoes",
    response_model=list[MovimentacaoEstoqueResponse],
)
def listar_movimentacoes_estoque(
    produto_id: int,
    limite: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    usuario_logado: models.Usuario = Depends(
        admin_gerente_ou_recepcao
    ),
):
    return listar_movimentacoes_estoque_service(
        db=db,
        produto_id=produto_id,
        usuario_logado=usuario_logado,
        limite=limite,
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


@router.delete("/{produto_id}")
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
        "mensagem": "Produto desativado com sucesso.",
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
