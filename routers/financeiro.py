from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import schemas
from auth.permissions import admin_ou_gerente
from database import get_db
from services.financeiro_service import (
    dashboard_financeiro_service,
    dre_simplificada_service,
    fluxo_caixa_service,
)


router = APIRouter(
    prefix="/financeiro",
    tags=["Financeiro"],
)


@router.get(
    "/dashboard",
    response_model=schemas.FinanceiroDashboardResponse,
)
def dashboard_financeiro(
    data_inicio: date | None = None,
    data_fim: date | None = None,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_ou_gerente),
):
    return dashboard_financeiro_service(
        db=db,
        usuario_logado=usuario_logado,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )


@router.get(
    "/fluxo-caixa",
    response_model=schemas.FluxoCaixaResponse,
)
def fluxo_caixa(
    data_inicio: date | None = None,
    data_fim: date | None = None,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_ou_gerente),
):
    return fluxo_caixa_service(
        db=db,
        usuario_logado=usuario_logado,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )


@router.get(
    "/dre",
    response_model=schemas.DRESimplificadaResponse,
)
def dre_simplificada(
    data_inicio: date | None = None,
    data_fim: date | None = None,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_ou_gerente),
):
    return dre_simplificada_service(
        db=db,
        usuario_logado=usuario_logado,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )
