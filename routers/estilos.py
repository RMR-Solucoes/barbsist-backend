from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from schemas import EstiloCreate, EstiloResponse
from services.estilo_service import (
    criar_estilo_service,
    listar_estilos_service,
    buscar_estilo_service,
    atualizar_estilo_service,
    desativar_estilo_service
)

from auth.permissions import (
    admin_ou_gerente
)


router = APIRouter(
    prefix="/estilos",
    tags=["Estilos"],
    dependencies=[
        Depends(admin_ou_gerente)
    ]
)


@router.post("", response_model=EstiloResponse)
def criar_estilo(
    dados: EstiloCreate,
    db: Session = Depends(get_db)
):
    return criar_estilo_service(db, dados)


@router.get("", response_model=list[EstiloResponse])
def listar_estilos(db: Session = Depends(get_db)):
    return listar_estilos_service(db)


@router.get("/{estilo_id}", response_model=EstiloResponse)
def buscar_estilo(
    estilo_id: int,
    db: Session = Depends(get_db)
):
    return buscar_estilo_service(db, estilo_id)


@router.put("/{estilo_id}", response_model=EstiloResponse)
def atualizar_estilo(
    estilo_id: int,
    dados: EstiloCreate,
    db: Session = Depends(get_db)
):
    return atualizar_estilo_service(db, estilo_id, dados)


@router.delete("/{estilo_id}")
def desativar_estilo(
    estilo_id: int,
    db: Session = Depends(get_db)
):
    return desativar_estilo_service(db, estilo_id)