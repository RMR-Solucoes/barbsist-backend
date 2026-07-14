from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
import models

from schemas import ComissaoResponse

from auth.permissions import (
    admin_ou_gerente
)

from auth.dependencies import (
    get_barbeiro_logado
)

router = APIRouter(
    prefix="/comissoes",
    tags=["Comissões"]
)


@router.get("", response_model=list[ComissaoResponse])
def listar_comissoes(
    db: Session = Depends(get_db),
    
):
    comissoes = db.query(models.Comissao).all()
    return comissoes


@router.get(
    "/barbeiro/{barbeiro_id}",
    response_model=list[ComissaoResponse]
)
def listar_comissoes_barbeiro(
    barbeiro_id: int,
    db: Session = Depends(get_db)
):
    return db.query(models.Comissao).filter(
        models.Comissao.barbeiro_id == barbeiro_id
    ).all()

@router.get(
    "/minhas",
    response_model=list[ComissaoResponse]
)
def minhas_comissoes(
    barbeiro_id: int = Depends(get_barbeiro_logado),
    db: Session = Depends(get_db)
):
    return db.query(models.Comissao).filter(
        models.Comissao.barbeiro_id == barbeiro_id
    ).all()