from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from schemas import EstiloCreate, EstiloResponse

from auth.permissions import admin_ou_gerente
from services.estilo_service import (
    atualizar_estilo_service,
    buscar_estilo_service,
    criar_estilo_service,
    desativar_estilo_service,
    listar_estilos_service,
)


router = APIRouter(
    prefix="/estilos",
    tags=["Estilos"],
)


@router.post(
    "",
    response_model=EstiloResponse,
)
def criar_estilo(
    dados: EstiloCreate,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_ou_gerente),
):
    return criar_estilo_service(
        db=db,
        dados=dados,
        usuario_logado=usuario_logado,
    )


@router.get(
    "",
    response_model=list[EstiloResponse],
)
def listar_estilos(
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_ou_gerente),
):
    return listar_estilos_service(
        db=db,
        usuario_logado=usuario_logado,
    )


@router.get(
    "/{estilo_id}",
    response_model=EstiloResponse,
)
def buscar_estilo(
    estilo_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_ou_gerente),
):
    return buscar_estilo_service(
        db=db,
        estilo_id=estilo_id,
        usuario_logado=usuario_logado,
    )


@router.put(
    "/{estilo_id}",
    response_model=EstiloResponse,
)
def atualizar_estilo(
    estilo_id: int,
    dados: EstiloCreate,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_ou_gerente),
):
    return atualizar_estilo_service(
        db=db,
        estilo_id=estilo_id,
        dados=dados,
        usuario_logado=usuario_logado,
    )


@router.delete("/{estilo_id}")
def desativar_estilo(
    estilo_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_ou_gerente),
):
    return desativar_estilo_service(
        db=db,
        estilo_id=estilo_id,
        usuario_logado=usuario_logado,
    )
