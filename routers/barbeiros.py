from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

import models

from database import get_db
from schemas import (
    BarbeiroCreate,
    BarbeiroResponse,
)

from auth.permissions import admin_ou_gerente

from services.barbeiro_service import (
    criar_barbeiro_service,
    listar_barbeiros_service,
    buscar_barbeiro_service,
    atualizar_barbeiro_service,
    inativar_barbeiro_service,
    reativar_barbeiro_service,
)


router = APIRouter(
    prefix="/barbeiros",
    tags=["Barbeiros"],
)


@router.post(
    "",
    response_model=BarbeiroResponse,
    status_code=201
)
def criar_barbeiro(
    dados: BarbeiroCreate,
    db: Session = Depends(get_db),
    usuario_logado: models.Usuario = Depends(
        admin_ou_gerente
    )
):
    return criar_barbeiro_service(
        dados=dados,
        db=db,
        usuario_logado=usuario_logado
    )


@router.get(
    "",
    response_model=list[BarbeiroResponse]
)
def listar_barbeiros(
    apenas_ativos: bool = Query(
        True,
        description=(
            "Quando verdadeiro, retorna somente "
            "os barbeiros ativos."
        )
    ),
    db: Session = Depends(get_db),
    usuario_logado: models.Usuario = Depends(
        admin_ou_gerente
    )
):
    return listar_barbeiros_service(
        db=db,
        usuario_logado=usuario_logado,
        apenas_ativos=apenas_ativos
    )


@router.get(
    "/{barbeiro_id}",
    response_model=BarbeiroResponse
)
def buscar_barbeiro(
    barbeiro_id: int,
    db: Session = Depends(get_db),
    usuario_logado: models.Usuario = Depends(
        admin_ou_gerente
    )
):
    return buscar_barbeiro_service(
        barbeiro_id=barbeiro_id,
        db=db,
        usuario_logado=usuario_logado,
        exigir_ativo=False
    )


@router.put(
    "/{barbeiro_id}",
    response_model=BarbeiroResponse
)
def atualizar_barbeiro(
    barbeiro_id: int,
    dados: BarbeiroCreate,
    db: Session = Depends(get_db),
    usuario_logado: models.Usuario = Depends(
        admin_ou_gerente
    )
):
    return atualizar_barbeiro_service(
        barbeiro_id=barbeiro_id,
        dados=dados,
        db=db,
        usuario_logado=usuario_logado
    )


@router.delete(
    "/{barbeiro_id}"
)
def inativar_barbeiro(
    barbeiro_id: int,
    db: Session = Depends(get_db),
    usuario_logado: models.Usuario = Depends(
        admin_ou_gerente
    )
):
    barbeiro = inativar_barbeiro_service(
        barbeiro_id=barbeiro_id,
        db=db,
        usuario_logado=usuario_logado
    )

    return {
        "mensagem": "Barbeiro inativado com sucesso.",
        "barbeiro_id": barbeiro.id
    }


@router.put(
    "/{barbeiro_id}/reativar",
    response_model=BarbeiroResponse
)
def reativar_barbeiro(
    barbeiro_id: int,
    db: Session = Depends(get_db),
    usuario_logado: models.Usuario = Depends(
        admin_ou_gerente
    )
):
    return reativar_barbeiro_service(
        barbeiro_id=barbeiro_id,
        db=db,
        usuario_logado=usuario_logado
    )