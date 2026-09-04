from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import schemas
from database import get_db
from auth.permissions import admin_ou_gerente
from services.conta_pagar_service import (
    buscar_conta_pagar_service,
    criar_conta_pagar_service,
    excluir_conta_pagar_service,
    listar_contas_pagar_service,
    pagar_conta_service,
    atualizar_conta_pagar_service,
)


router = APIRouter(
    prefix="/contas-pagar",
    tags=["Contas a Pagar"],
)


@router.post(
    "",
    response_model=schemas.ContaPagarResponse,
)
def criar_conta_pagar(
    dados: schemas.ContaPagarCreate,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_ou_gerente),
):
    return criar_conta_pagar_service(
        db=db,
        dados=dados,
        usuario_logado=usuario_logado,
    )


@router.get(
    "",
    response_model=list[
        schemas.ContaPagarResponse
    ],
)
def listar_contas_pagar(
    status: str | None = None,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_ou_gerente),
):
    return listar_contas_pagar_service(
        db=db,
        usuario_logado=usuario_logado,
        status_filtro=status,
    )


@router.get(
    "/{conta_id}",
    response_model=schemas.ContaPagarResponse,
)
def buscar_conta_pagar(
    conta_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_ou_gerente),
):
    return buscar_conta_pagar_service(
        db=db,
        conta_id=conta_id,
        usuario_logado=usuario_logado,
    )


@router.patch(
    "/{conta_id}",
    response_model=schemas.ContaPagarResponse,
)
def atualizar_conta_pagar(
    conta_id: int,
    dados: schemas.ContaPagarUpdate,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_ou_gerente),
):
    return atualizar_conta_pagar_service(
        db=db,
        conta_id=conta_id,
        dados=dados,
        usuario_logado=usuario_logado,
    )


@router.put(
    "/{conta_id}/pagar",
    response_model=schemas.ContaPagarResponse,
)
def pagar_conta(
    conta_id: int,
    forma_pagamento: str | None = None,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_ou_gerente),
):
    return pagar_conta_service(
        db=db,
        conta_id=conta_id,
        forma_pagamento=forma_pagamento,
        usuario_logado=usuario_logado,
    )


@router.delete("/{conta_id}")
def excluir_conta_pagar(
    conta_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_ou_gerente),
):
    return excluir_conta_pagar_service(
        db=db,
        conta_id=conta_id,
        usuario_logado=usuario_logado,
    )
