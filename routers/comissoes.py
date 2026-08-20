from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from schemas import ComissaoResponse

from auth.dependencies import (
    get_barbeiro_logado,
    get_usuario_logado,
)
from auth.permissions import admin_ou_gerente
from services.comissao_service import (
    listar_comissoes_service,
    listar_comissoes_barbeiro_service,
    listar_minhas_comissoes_service,
)


router = APIRouter(
    prefix="/comissoes",
    tags=["Comissões"],
)


@router.get(
    "",
    response_model=list[ComissaoResponse],
)
def listar_comissoes(
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_ou_gerente),
):
    return listar_comissoes_service(
        db=db,
        usuario_logado=usuario_logado,
    )


@router.get(
    "/minhas",
    response_model=list[ComissaoResponse],
)
def minhas_comissoes(
    barbeiro_id: int = Depends(
        get_barbeiro_logado
    ),
    usuario_logado=Depends(
        get_usuario_logado
    ),
    db: Session = Depends(get_db),
):
    return listar_minhas_comissoes_service(
        db=db,
        barbeiro_id=barbeiro_id,
        usuario_logado=usuario_logado,
    )


@router.get(
    "/barbeiro/{barbeiro_id}",
    response_model=list[ComissaoResponse],
)
def listar_comissoes_barbeiro(
    barbeiro_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_ou_gerente),
):
    return listar_comissoes_barbeiro_service(
        db=db,
        barbeiro_id=barbeiro_id,
        usuario_logado=usuario_logado,
    )
