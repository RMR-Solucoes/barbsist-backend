from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session

from database import get_db
from auth.permissions import superadmin

from parceiros.service_parceiros import (
    obter_portal_parceiro_service,
    listar_indicacoes_parceiro_service,
    listar_comissoes_parceiro_service,
    listar_creditos_parceiro_service,
    calcular_saldo_creditos_service,
    solicitar_resgate_creditos_service,
)


router = APIRouter(
    prefix="/portal-parceiro",
    tags=["Portal do Parceiro BarbSist"],
)


# TEMPORARIAMENTE protegido pelo superadmin.
# A autenticação própria do parceiro será adicionada
# posteriormente em arquivo separado.
@router.get("/{parceiro_id}")
def portal_parceiro(
    parceiro_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(superadmin),
):
    return obter_portal_parceiro_service(
        db,
        parceiro_id,
    )


@router.get("/{parceiro_id}/indicacoes")
def minhas_indicacoes(
    parceiro_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(superadmin),
):
    return listar_indicacoes_parceiro_service(
        db,
        parceiro_id,
    )


@router.get("/{parceiro_id}/comissoes")
def minhas_comissoes(
    parceiro_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(superadmin),
):
    return listar_comissoes_parceiro_service(
        db,
        parceiro_id,
    )


@router.get("/{parceiro_id}/creditos")
def meus_creditos(
    parceiro_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(superadmin),
):
    return listar_creditos_parceiro_service(
        db,
        parceiro_id,
    )


@router.get("/{parceiro_id}/carteira")
def minha_carteira(
    parceiro_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(superadmin),
):
    return calcular_saldo_creditos_service(
        db,
        parceiro_id,
    )


@router.post(
    "/{parceiro_id}/resgates",
    status_code=201,
)
def solicitar_resgate(
    parceiro_id: int,
    valor: float = Body(..., embed=True),
    observacao: str | None = Body(default=None, embed=True),
    db: Session = Depends(get_db),
    usuario_logado=Depends(superadmin),
):
    return solicitar_resgate_creditos_service(
        db=db,
        parceiro_id=parceiro_id,
        valor=valor,
        tipo_aplicacao="RESGATE_SOLICITADO",
        observacao=observacao,
    )

