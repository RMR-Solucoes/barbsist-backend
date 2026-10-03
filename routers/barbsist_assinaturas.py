from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from auth.permissions import admin, superadmin
from database import get_db
from auth.tenant import obter_barbearia_id
from schemas import (
    AdequacaoPlanoSaaSResponse,
    AssinaturaSaaSResponse,
    CheckoutSaaSCartaoRequest,
    CheckoutSaaSMercadoPagoRequest,
    CheckoutSaaSPixRequest,
    PagamentoSaaSResponse,
    PlanoSaaSResponse,
)
from services.adequacao_plano_saas_service import obter_adequacao_pendente_saas
from services.adequacao_financeira_saas_service import previa_financeira_adequacao_saas
from services.assinatura_saas_service import (
    checkout_cartao_saas_service,
    checkout_mercado_pago_saas_service,
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


@router.get("/adequacao-pendente", response_model=AdequacaoPlanoSaaSResponse | None)
def adequacao_pendente(db: Session = Depends(get_db), usuario_logado=Depends(admin)):
    barbearia_id = obter_barbearia_id(usuario_logado)
    return obter_adequacao_pendente_saas(db, barbearia_id)



# V474_C4_ROUTE_PREVIA_FINANCEIRA
@router.get("/adequacao-pendente/previa-financeira")
def previa_financeira_adequacao(
    forma_pagamento: str = "PIX",
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin),
):
    barbearia_id = obter_barbearia_id(
        usuario_logado
    )

    return previa_financeira_adequacao_saas(
        db,
        barbearia_id=barbearia_id,
        forma_pagamento=forma_pagamento,
    )


@router.get("/mercado-pago/public-key")
def public_key(usuario_logado=Depends(admin)):
    return obter_public_key_service()


@router.post("/checkout/pix", response_model=PagamentoSaaSResponse)
def checkout_pix(dados: CheckoutSaaSPixRequest, request: Request, db: Session = Depends(get_db), usuario_logado=Depends(admin)):
    return checkout_pix_saas_service(db, dados, usuario_logado, str(request.base_url).rstrip("/"))


@router.post("/checkout/cartao", response_model=PagamentoSaaSResponse)
def checkout_cartao(dados: CheckoutSaaSCartaoRequest, request: Request, db: Session = Depends(get_db), usuario_logado=Depends(admin)):
    return checkout_cartao_saas_service(db, dados, usuario_logado, str(request.base_url).rstrip("/"))


@router.post("/checkout/mercado-pago", response_model=PagamentoSaaSResponse)
def checkout_mercado_pago(dados: CheckoutSaaSMercadoPagoRequest, request: Request, db: Session = Depends(get_db), usuario_logado=Depends(admin)):
    return checkout_mercado_pago_saas_service(db, dados, usuario_logado, str(request.base_url).rstrip("/"))


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db), x_signature: str | None = Header(default=None, alias="x-signature"), x_request_id: str | None = Header(default=None, alias="x-request-id")):
    try: payload = await request.json()
    except Exception: payload = {}
    data_id = request.query_params.get("data.id") or request.query_params.get("data_id")
    return processar_webhook_saas_service(db, data_id, payload, x_signature, x_request_id)
