from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db

from schemas import (
    CaixaCreate,
    CaixaResponse,
    CaixaResumoResponse,
)

from auth.permissions import (
    admin_gerente_ou_recepcao,
)

from services.caixa_service import (
    buscar_movimentacao_caixa_service,
    listar_caixa_service,
    registrar_movimentacao_caixa,
    resumo_caixa_service,
)


router = APIRouter(
    prefix="/caixa",
    tags=["Caixa"],
)


@router.get(
    "",
    response_model=list[CaixaResponse],
)
def listar_caixa(
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_ou_recepcao
    ),
):
    return listar_caixa_service(
        db=db,
        usuario_logado=usuario_logado,
    )


@router.get(
    "/resumo",
    response_model=CaixaResumoResponse,
)
def obter_resumo_caixa(
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_ou_recepcao
    ),
):
    return resumo_caixa_service(
        db=db,
        usuario_logado=usuario_logado,
    )


@router.get(
    "/{movimentacao_id}",
    response_model=CaixaResponse,
)
def buscar_movimentacao_caixa(
    movimentacao_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_ou_recepcao
    ),
):
    return buscar_movimentacao_caixa_service(
        db=db,
        movimentacao_id=movimentacao_id,
        usuario_logado=usuario_logado,
    )


@router.post(
    "",
    response_model=CaixaResponse,
    status_code=201,
)
def criar_movimentacao_caixa(
    dados: CaixaCreate,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_ou_recepcao
    ),
):
    return registrar_movimentacao_caixa(
        db=db,
        dados=dados,
        usuario_logado=usuario_logado,
    )