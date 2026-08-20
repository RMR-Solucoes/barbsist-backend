from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from auth.permissions import superadmin
from database import get_db
from schemas import (
    AssinaturaSaaSResponse,
    BloquearAssinaturaSaaSRequest,
    LiberarAssinaturaSaaSRequest,
    PagamentoSaaSResponse,
    PlanoSaaSCreate,
    PlanoSaaSResponse,
    PlanoSaaSUpdate,
)
from services.assinatura_saas_service import (
    atualizar_plano_saas_service,
    bloquear_assinatura_service,
    criar_plano_saas_service,
    liberar_assinatura_manual_service,
    listar_assinaturas_admin_service,
    listar_pagamentos_admin_service,
    listar_planos_saas_service,
    status_mercado_pago_barbsist_service,
)

router = APIRouter(prefix="/admin/barbsist-assinaturas", tags=["Admin - BarbSist Assinaturas"])

@router.get("/planos", response_model=list[PlanoSaaSResponse])
def planos(db: Session = Depends(get_db), usuario_logado=Depends(superadmin)):
    return listar_planos_saas_service(db, incluir_inativos=True)

@router.post("/planos", response_model=PlanoSaaSResponse)
def criar_plano(dados: PlanoSaaSCreate, db: Session = Depends(get_db), usuario_logado=Depends(superadmin)):
    return criar_plano_saas_service(db, dados)

@router.put("/planos/{plano_id}", response_model=PlanoSaaSResponse)
def atualizar_plano(plano_id: int, dados: PlanoSaaSUpdate, db: Session = Depends(get_db), usuario_logado=Depends(superadmin)):
    return atualizar_plano_saas_service(db, plano_id, dados)

@router.get("/assinaturas", response_model=list[AssinaturaSaaSResponse])
def assinaturas(db: Session = Depends(get_db), usuario_logado=Depends(superadmin)):
    return listar_assinaturas_admin_service(db)

@router.get("/pagamentos", response_model=list[PagamentoSaaSResponse])
def pagamentos(db: Session = Depends(get_db), usuario_logado=Depends(superadmin)):
    return listar_pagamentos_admin_service(db)

@router.put("/assinaturas/{assinatura_id}/liberar", response_model=AssinaturaSaaSResponse)
def liberar(assinatura_id: int, dados: LiberarAssinaturaSaaSRequest, db: Session = Depends(get_db), usuario_logado=Depends(superadmin)):
    return liberar_assinatura_manual_service(db, assinatura_id, dados)

@router.put("/assinaturas/{assinatura_id}/bloquear", response_model=AssinaturaSaaSResponse)
def bloquear(assinatura_id: int, dados: BloquearAssinaturaSaaSRequest, db: Session = Depends(get_db), usuario_logado=Depends(superadmin)):
    return bloquear_assinatura_service(db, assinatura_id, dados)


@router.get("/mercado-pago/status")
def mercado_pago_status(request: Request, usuario_logado=Depends(superadmin)):
    return status_mercado_pago_barbsist_service(str(request.base_url).rstrip("/"))
