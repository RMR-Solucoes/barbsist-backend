from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from schemas import (
    BarbeiroDisponibilidadeResponse,
    BarbeiroDisponibilidadeUpdate,
)
from services.barbeiro_disponibilidade_service import (
    listar_disponibilidade_por_barbeiro,
    atualizar_disponibilidade,
)

router = APIRouter(
    prefix="/barbeiro-disponibilidade",
    tags=["Disponibilidade dos Barbeiros"],
)


@router.get(
    "/{barbeiro_id}",
    response_model=list[BarbeiroDisponibilidadeResponse]
)
def listar_por_barbeiro(
    barbeiro_id: int,
    db: Session = Depends(get_db)
):
    dados = listar_disponibilidade_por_barbeiro(db, barbeiro_id)

    if dados is None:
        raise HTTPException(status_code=404, detail="Barbeiro não encontrado.")

    return dados


@router.put(
    "/{disponibilidade_id}",
    response_model=BarbeiroDisponibilidadeResponse
)
def atualizar(
    disponibilidade_id: int,
    dados: BarbeiroDisponibilidadeUpdate,
    db: Session = Depends(get_db)
):
    disponibilidade = atualizar_disponibilidade(
        db=db,
        disponibilidade_id=disponibilidade_id,
        dados=dados,
    )

    if not disponibilidade:
        raise HTTPException(
            status_code=404,
            detail="Disponibilidade não encontrada."
        )

    return disponibilidade