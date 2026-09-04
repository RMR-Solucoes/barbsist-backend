from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import schemas
from database import get_db
from auth.permissions import admin_ou_gerente
from services.conta_receber_service import (
    buscar_conta_receber_service,
    criar_conta_receber_service,
    excluir_conta_receber_service,
    listar_contas_receber_service,
    receber_conta_service,
    atualizar_conta_receber_service,
)


router = APIRouter(
    prefix="/contas-receber",
    tags=["Contas a Receber"],
)


@router.post(
    "",
    response_model=schemas.ContaReceberResponse,
)
def criar_conta_receber(
    dados: schemas.ContaReceberCreate,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_ou_gerente),
):
    return criar_conta_receber_service(
        db=db,
        dados=dados,
        usuario_logado=usuario_logado,
    )


@router.get(
    "",
    response_model=list[
        schemas.ContaReceberResponse
    ],
)
def listar_contas_receber(
    status: str | None = None,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_ou_gerente),
):
    return listar_contas_receber_service(
        db=db,
        usuario_logado=usuario_logado,
        status_filtro=status,
    )


@router.get(
    "/{conta_id}",
    response_model=schemas.ContaReceberResponse,
)
def buscar_conta_receber(
    conta_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_ou_gerente),
):
    return buscar_conta_receber_service(
        db=db,
        conta_id=conta_id,
        usuario_logado=usuario_logado,
    )


@router.patch(
    "/{conta_id}",
    response_model=schemas.ContaReceberResponse,
)
def atualizar_conta_receber(
    conta_id: int,
    dados: schemas.ContaReceberUpdate,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_ou_gerente),
):
    return atualizar_conta_receber_service(
        db=db,
        conta_id=conta_id,
        dados=dados,
        usuario_logado=usuario_logado,
    )


@router.put(
    "/{conta_id}/receber",
    response_model=schemas.ContaReceberResponse,
)
def receber_conta(
    conta_id: int,
    forma_pagamento: str | None = None,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_ou_gerente),
):
    return receber_conta_service(
        db=db,
        conta_id=conta_id,
        forma_pagamento=forma_pagamento,
        usuario_logado=usuario_logado,
    )


@router.delete("/{conta_id}")
def excluir_conta_receber(
    conta_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_ou_gerente),
):
    return excluir_conta_receber_service(
        db=db,
        conta_id=conta_id,
        usuario_logado=usuario_logado,
    )
