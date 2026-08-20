from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from auth.permissions import admin, superadmin
from database import get_db
from schemas import (
    AssinaturaSaaSResponse,
    CheckoutSaaSCartaoRequest,
    CheckoutSaaSPixRequest,
    PagamentoSaaSResponse,
    PlanoSaaSResponse,
)
from services.assinatura_saas_service import (
    checkout_cartao_saas_service,
    checkout_pix_saas_service,
    listar_planos_saas_service,
    minha_assinatura_saas_service,
    obter_public_key_service,
    processar_webhook_saas_service,
)

router = APIRouter(prefix="/barbsist-assinaturas", tags=["BarbSist Assinaturas"])


@router.get("/planos", response_model=list[PlanoSaaSResponse])
def listar_planos(db: Session = Depends(get_db), usuario_logado=Depends(admin)):
    return listar_planos_saas_service(db)


@router.get("/minha-assinatura", response_model=AssinaturaSaaSResponse | None)
def minha_assinatura(db: Session = Depends(get_db), usuario_logado=Depends(admin)):
    return minha_assinatura_saas_service(db, usuario_logado)


@router.get("/mercado-pago/public-key")
def public_key(usuario_logado=Depends(admin)):
    return obter_public_key_service()


@router.post("/checkout/pix", response_model=PagamentoSaaSResponse)
def checkout_pix(dados: CheckoutSaaSPixRequest, request: Request, db: Session = Depends(get_db), usuario_logado=Depends(admin)):
    return checkout_pix_saas_service(db, dados, usuario_logado, str(request.base_url).rstrip("/"))


@router.post("/checkout/cartao", response_model=PagamentoSaaSResponse)
def checkout_cartao(dados: CheckoutSaaSCartaoRequest, request: Request, db: Session = Depends(get_db), usuario_logado=Depends(admin)):
    return checkout_cartao_saas_service(db, dados, usuario_logado, str(request.base_url).rstrip("/"))


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db), x_signature: str | None = Header(default=None, alias="x-signature"), x_request_id: str | None = Header(default=None, alias="x-request-id")):
    try: payload = await request.json()
    except Exception: payload = {}
    data_id = request.query_params.get("data.id") or request.query_params.get("data_id")
    return processar_webhook_saas_service(db, data_id, payload, x_signature, x_request_id)
