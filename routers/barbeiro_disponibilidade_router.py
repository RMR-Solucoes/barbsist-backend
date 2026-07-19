from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth.permissions import (
    admin_ou_gerente,
    admin_gerente_recepcao_ou_barbeiro,
)
from database import get_db
from schemas import (
    BarbeiroDisponibilidadeResponse,
    BarbeiroDisponibilidadeUpdate,
)
from services.barbeiro_disponibilidade_service import (
    atualizar_disponibilidade,
    listar_disponibilidade_por_barbeiro,
)


router = APIRouter(
    prefix="/barbeiro-disponibilidade",
    tags=["Disponibilidade dos Barbeiros"],
)


@router.get(
    "/{barbeiro_id}",
    response_model=list[BarbeiroDisponibilidadeResponse],
)
def listar_por_barbeiro(
    barbeiro_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_gerente_recepcao_ou_barbeiro),
):
    dados = listar_disponibilidade_por_barbeiro(
        db=db,
        barbeiro_id=barbeiro_id,
        usuario_logado=usuario_logado,
    )

    if dados is None:
        raise HTTPException(
            status_code=404,
            detail="Barbeiro não encontrado.",
        )

    return dados


@router.put(
    "/{disponibilidade_id}",
    response_model=BarbeiroDisponibilidadeResponse,
)
def atualizar(
    disponibilidade_id: int,
    dados: BarbeiroDisponibilidadeUpdate,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_ou_gerente),
):
    return atualizar_disponibilidade(
        db=db,
        disponibilidade_id=disponibilidade_id,
        dados=dados,
        usuario_logado=usuario_logado,
    )
