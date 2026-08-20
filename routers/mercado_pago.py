import os
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from auth.permissions import admin_ou_gerente, admin_gerente_ou_recepcao
from database import get_db
from schemas import (
    MercadoPagoConfiguracaoResponse,
    MercadoPagoConfiguracaoUpdate,
    MercadoPagoCobrancaResponse,
    MercadoPagoCobrancaPixRequest,
    MercadoPagoCobrancaCartaoRequest,
    MercadoPagoPixRequest,
    MercadoPagoPixResponse,
    MercadoPagoCartaoRequest,
    MercadoPagoOAuthConectarResponse,
    MercadoPagoOAuthDesconectarResponse,
)
from services.mercado_pago_service import (
    concluir_oauth_service,
    desconectar_oauth_service,
    gerar_pix_assinatura_service,
    gerar_cartao_assinatura_service,
    gerar_pix_cobranca_service,
    gerar_cartao_cobranca_service,
    iniciar_oauth_service,
    listar_cobrancas_service,
    obter_minha_configuracao_service,
    processar_webhook_global_service,
    processar_webhook_service,
    salvar_minha_configuracao_service,
)

router = APIRouter(prefix="/mercado-pago", tags=["Mercado Pago"])


def _frontend_retorno(status: str, mensagem: str | None = None):
    base = (os.getenv("FRONTEND_PUBLIC_URL") or "").strip().rstrip("/")
    if not base:
        return None
    params = {"mercado_pago": status}
    if mensagem:
        params["mensagem"] = mensagem[:180]
    return f"{base}/configuracoes?{urlencode(params)}"


@router.get("/status", response_model=MercadoPagoConfiguracaoResponse)
def status_mercado_pago(
    request: Request,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_ou_gerente),
):
    return obter_minha_configuracao_service(
        db, usuario_logado, str(request.base_url).rstrip("/")
    )


@router.get("/oauth/conectar", response_model=MercadoPagoOAuthConectarResponse)
def conectar_mercado_pago(
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_ou_gerente),
):
    return iniciar_oauth_service(db, usuario_logado)


@router.get("/oauth/callback")
def callback_mercado_pago(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    db: Session = Depends(get_db),
):
    if error:
        destino = _frontend_retorno("erro", error_description or error)
        if destino:
            return RedirectResponse(destino, status_code=302)
        return {"conectado": False, "erro": error_description or error}

    try:
        concluir_oauth_service(db, code, state)
    except Exception as exc:
        detalhe = getattr(exc, "detail", str(exc))
        destino = _frontend_retorno("erro", str(detalhe))
        if destino:
            return RedirectResponse(destino, status_code=302)
        raise

    destino = _frontend_retorno("conectado")
    if destino:
        return RedirectResponse(destino, status_code=302)
    return {"conectado": True, "mensagem": "Mercado Pago conectado com sucesso."}


@router.post("/oauth/desconectar", response_model=MercadoPagoOAuthDesconectarResponse)
def desconectar_mercado_pago(
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_ou_gerente),
):
    return desconectar_oauth_service(db, usuario_logado)


# Rotas manuais mantidas para compatibilidade/suporte. O fluxo normal da
# barbearia deve utilizar /oauth/conectar e nunca exigir que o usuário copie tokens.
@router.get("/configuracao", response_model=MercadoPagoConfiguracaoResponse)
def obter_configuracao(
    request: Request,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_ou_gerente),
):
    return obter_minha_configuracao_service(
        db, usuario_logado, str(request.base_url).rstrip("/")
    )


@router.put("/configuracao", response_model=MercadoPagoConfiguracaoResponse)
def salvar_configuracao(
    dados: MercadoPagoConfiguracaoUpdate,
    request: Request,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_ou_gerente),
):
    return salvar_minha_configuracao_service(
        db, dados, usuario_logado, str(request.base_url).rstrip("/")
    )


@router.post("/assinaturas/{assinatura_id}/pix", response_model=MercadoPagoPixResponse)
def gerar_pix(
    assinatura_id: int,
    dados: MercadoPagoPixRequest,
    request: Request,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_gerente_ou_recepcao),
):
    return gerar_pix_assinatura_service(
        db,
        assinatura_id,
        dados.payer_email,
        usuario_logado,
        str(request.base_url).rstrip("/"),
    )


@router.post("/assinaturas/{assinatura_id}/cartao", response_model=MercadoPagoCobrancaResponse)
def pagar_cartao(
    assinatura_id: int,
    dados: MercadoPagoCartaoRequest,
    request: Request,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_gerente_ou_recepcao),
):
    return gerar_cartao_assinatura_service(
        db,
        assinatura_id,
        dados,
        usuario_logado,
        str(request.base_url).rstrip("/"),
    )


@router.post("/cobrancas/pix", response_model=MercadoPagoCobrancaResponse)
def gerar_cobranca_pix(
    dados: MercadoPagoCobrancaPixRequest,
    request: Request,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_gerente_ou_recepcao),
):
    return gerar_pix_cobranca_service(
        db, dados, usuario_logado, str(request.base_url).rstrip("/")
    )


@router.post("/cobrancas/cartao", response_model=MercadoPagoCobrancaResponse)
def gerar_cobranca_cartao(
    dados: MercadoPagoCobrancaCartaoRequest,
    request: Request,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_gerente_ou_recepcao),
):
    return gerar_cartao_cobranca_service(
        db, dados, usuario_logado, str(request.base_url).rstrip("/")
    )


@router.get("/cobrancas", response_model=list[MercadoPagoCobrancaResponse])
def listar_cobrancas(
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_gerente_ou_recepcao),
):
    return listar_cobrancas_service(db, usuario_logado)


@router.post("/webhook")
async def webhook_global(
    request: Request,
    db: Session = Depends(get_db),
    x_signature: str | None = Header(default=None, alias="x-signature"),
    x_request_id: str | None = Header(default=None, alias="x-request-id"),
):
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    data_id = request.query_params.get("data.id") or request.query_params.get("data_id")
    return processar_webhook_global_service(
        db, data_id, payload, x_signature, x_request_id
    )


@router.post("/webhook/{barbearia_id}")
async def webhook(
    barbearia_id: int,
    request: Request,
    db: Session = Depends(get_db),
    x_signature: str | None = Header(default=None, alias="x-signature"),
    x_request_id: str | None = Header(default=None, alias="x-request-id"),
):
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    data_id = request.query_params.get("data.id") or request.query_params.get("data_id")
    return processar_webhook_service(
        db, barbearia_id, data_id, payload, x_signature, x_request_id
    )
