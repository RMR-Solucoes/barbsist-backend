import hashlib, hmac, json, os, uuid
from datetime import datetime, timedelta
from urllib import error, request
from urllib.parse import urlencode
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, status
import models
from auth.tenant import obter_barbearia_id
from services.plano_service import confirmar_pagamento_assinatura_service
MP_API_BASE = "https://api.mercadopago.com"
MP_AUTH_BASE = "https://auth.mercadopago.com.br/authorization"

def _oauth_env():
    client_id = (os.getenv("MP_CLIENT_ID") or "").strip()
    client_secret = (os.getenv("MP_CLIENT_SECRET") or "").strip()
    redirect_uri = (os.getenv("MP_OAUTH_REDIRECT_URI") or "").strip()
    if not client_id or not client_secret or not redirect_uri:
        raise HTTPException(
            status_code=500,
            detail="OAuth do Mercado Pago não configurado. Defina MP_CLIENT_ID, MP_CLIENT_SECRET e MP_OAUTH_REDIRECT_URI.",
        )
    return client_id, client_secret, redirect_uri

def _state_hash(valor):
    return hashlib.sha256(valor.encode()).hexdigest()

def _pkce_ativo():
    return (os.getenv("MP_OAUTH_USE_PKCE") or "false").strip().lower() == "true"

def _oauth_post(payload):
    body = urlencode(payload).encode()
    req = request.Request(
        MP_API_BASE + "/oauth/token",
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode())
    except error.HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        try:
            obj = json.loads(raw)
            msg = obj.get("message") or obj.get("error_description") or obj.get("error") or raw
        except Exception:
            msg = raw
        raise HTTPException(status_code=502, detail=f"Mercado Pago recusou a autorização OAuth: {msg}") from exc
    except error.URLError as exc:
        raise HTTPException(status_code=502, detail="Não foi possível conectar ao OAuth do Mercado Pago.") from exc

def _salvar_tokens_oauth(db, cfg, token_data, renovacao=False):
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=502, detail="Mercado Pago não retornou access_token.")
    cfg.access_token_encrypted = criptografar(access_token)
    if token_data.get("refresh_token"):
        cfg.refresh_token_encrypted = criptografar(token_data.get("refresh_token"))
    if token_data.get("public_key"):
        cfg.public_key = token_data.get("public_key")
    if token_data.get("user_id") is not None:
        cfg.mercado_pago_user_id = str(token_data.get("user_id"))
    cfg.token_type = token_data.get("token_type") or cfg.token_type
    cfg.scope = token_data.get("scope") or cfg.scope
    expires_in = int(token_data.get("expires_in") or 0)
    cfg.token_expires_at = datetime.now() + timedelta(seconds=expires_in) if expires_in else None
    cfg.oauth_status = "CONECTADO"
    cfg.ativo = True
    if not cfg.conectado_em:
        cfg.conectado_em = datetime.now()
    if renovacao:
        cfg.ultima_renovacao_em = datetime.now()
    db.flush()

def obter_access_token_valido(db, cfg):
    if not cfg or not cfg.access_token_encrypted:
        raise HTTPException(
            status_code=400,
            detail="Mercado Pago não conectado para esta barbearia.",
        )

    margem = datetime.now() + timedelta(minutes=5)

    if cfg.token_expires_at and cfg.token_expires_at <= margem:
        # Serializa a renovação do token para evitar dois refreshes
        # simultâneos sobrescrevendo credenciais entre si.
        cfg = (
            db.query(models.MercadoPagoConfiguracao)
            .filter(models.MercadoPagoConfiguracao.id == cfg.id)
            .with_for_update()
            .first()
        )

        if not cfg or not cfg.access_token_encrypted:
            raise HTTPException(
                status_code=400,
                detail="Mercado Pago não conectado para esta barbearia.",
            )

        # Outra requisição pode ter renovado enquanto aguardávamos o lock.
        margem = datetime.now() + timedelta(minutes=5)
        if cfg.token_expires_at and cfg.token_expires_at <= margem:
            if not cfg.refresh_token_encrypted:
                cfg.oauth_status = "RECONECTAR"
                cfg.ativo = False
                db.commit()
                raise HTTPException(
                    status_code=401,
                    detail=(
                        "Conexão Mercado Pago expirada. "
                        "Reconecte a conta."
                    ),
                )

            client_id, client_secret, _ = _oauth_env()
            token_data = _oauth_post(
                {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": descriptografar(
                        cfg.refresh_token_encrypted
                    ),
                }
            )
            _salvar_tokens_oauth(
                db,
                cfg,
                token_data,
                renovacao=True,
            )
            db.commit()

    return descriptografar(cfg.access_token_encrypted)

def iniciar_oauth_service(db, usuario):
    bid = obter_barbearia_id(usuario)
    client_id, _, redirect_uri = _oauth_env()
    # Invalida tentativas antigas ainda não usadas para o mesmo usuário/barbearia.
    agora = datetime.now()
    db.query(models.MercadoPagoOAuthState).filter(
        models.MercadoPagoOAuthState.barbearia_id == bid,
        models.MercadoPagoOAuthState.usuario_id == usuario.id,
        models.MercadoPagoOAuthState.utilizado_em.is_(None),
    ).update({models.MercadoPagoOAuthState.expira_em: agora})
    state = uuid.uuid4().hex + uuid.uuid4().hex
    verifier = None
    params = {
        "client_id": client_id,
        "response_type": "code",
        "platform_id": "mp",
        "state": state,
        "redirect_uri": redirect_uri,
    }
    if _pkce_ativo():
        import base64
        verifier = uuid.uuid4().hex + uuid.uuid4().hex
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        params["code_challenge"] = challenge
        params["code_challenge_method"] = "S256"
    registro = models.MercadoPagoOAuthState(
        state_hash=_state_hash(state),
        barbearia_id=bid,
        usuario_id=usuario.id,
        code_verifier_encrypted=criptografar(verifier) if verifier else None,
        expira_em=agora + timedelta(minutes=10),
    )
    db.add(registro)
    db.commit()
    return {
        "authorization_url": MP_AUTH_BASE + "?" + urlencode(params),
        "expires_in_seconds": 600,
    }

def concluir_oauth_service(db, code, state):
    if not code or not state:
        raise HTTPException(status_code=400, detail="Retorno OAuth sem code/state.")
    reg = db.query(models.MercadoPagoOAuthState).filter(
        models.MercadoPagoOAuthState.state_hash == _state_hash(state)
    ).first()
    if not reg or reg.utilizado_em is not None or reg.expira_em < datetime.now():
        raise HTTPException(status_code=400, detail="state OAuth inválido, expirado ou já utilizado.")
    client_id, client_secret, redirect_uri = _oauth_env()
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "state": state,
    }
    if reg.code_verifier_encrypted:
        payload["code_verifier"] = descriptografar(reg.code_verifier_encrypted)
    token_data = _oauth_post(payload)
    cfg = obter_configuracao(db, reg.barbearia_id)
    if not cfg:
        cfg = models.MercadoPagoConfiguracao(barbearia_id=reg.barbearia_id)
        db.add(cfg)
    _salvar_tokens_oauth(db, cfg, token_data)
    # Webhook secret é da aplicação e pode ser fornecido globalmente no ambiente.
    app_webhook_secret = (os.getenv("MP_WEBHOOK_SECRET") or "").strip()
    if app_webhook_secret and not cfg.webhook_secret_encrypted:
        cfg.webhook_secret_encrypted = criptografar(app_webhook_secret)
    reg.utilizado_em = datetime.now()
    db.commit()
    return cfg

def desconectar_oauth_service(db, usuario):
    bid = obter_barbearia_id(usuario)
    cfg = obter_configuracao(db, bid)
    if not cfg:
        return {"desconectado": True, "mensagem": "Mercado Pago já estava desconectado."}
    cfg.access_token_encrypted = None
    cfg.refresh_token_encrypted = None
    cfg.public_key = None
    cfg.mercado_pago_user_id = None
    cfg.token_type = None
    cfg.scope = None
    cfg.token_expires_at = None
    cfg.oauth_status = "NAO_CONECTADO"
    cfg.ativo = False
    db.commit()
    return {
        "desconectado": True,
        "mensagem": "Conta Mercado Pago desconectada do BarbSist. A revogação na conta Mercado Pago, quando desejada, deve ser feita também pelo vendedor no Mercado Pago.",
    }

def _fernet():
    chave=os.getenv("MP_CREDENTIALS_KEY")
    if not chave: raise HTTPException(status_code=500, detail="MP_CREDENTIALS_KEY não configurada. Execute gerar_chave_mp.py e configure a variável no Railway.")
    try: return Fernet(chave.encode())
    except Exception as exc: raise HTTPException(status_code=500, detail="MP_CREDENTIALS_KEY inválida.") from exc

def criptografar(v): return _fernet().encrypt(v.strip().encode()).decode() if v else None
def descriptografar(v):
    if not v: return None
    try: return _fernet().decrypt(v.encode()).decode()
    except InvalidToken as exc: raise HTTPException(status_code=500, detail="Credencial Mercado Pago inválida ou chave de criptografia alterada.") from exc

def obter_configuracao(db, bid):
    return db.query(models.MercadoPagoConfiguracao).filter(
        models.MercadoPagoConfiguracao.barbearia_id == bid
    ).first()


def _webhook_url(_bid=None, base=None):
    """URL global de Webhook da aplicação Mercado Pago (Orders API)."""
    raiz = os.getenv("PUBLIC_BACKEND_URL") or os.getenv("BACKEND_PUBLIC_URL") or base
    return f"{raiz.rstrip('/')}/mercado-pago/webhook" if raiz else None


def configuracao_response(c, bid, base=None):
    conectado = bool(c and c.access_token_encrypted and c.oauth_status == "CONECTADO")
    return {
        "configurado": bool(c and c.access_token_encrypted),
        "conectado": conectado,
        "access_token_configurado": bool(c and c.access_token_encrypted),
        "webhook_secret_configurado": bool(
            (c and c.webhook_secret_encrypted)
            or (os.getenv("MP_WEBHOOK_SECRET") or "").strip()
        ),
        "public_key": c.public_key if c else None,
        "mercado_pago_user_id": c.mercado_pago_user_id if c else None,
        "oauth_status": c.oauth_status if c else "NAO_CONECTADO",
        "token_expires_at": c.token_expires_at if c else None,
        "conectado_em": c.conectado_em if c else None,
        "ambiente": c.ambiente if c else "producao",
        "ativo": bool(c and c.ativo),
        "webhook_url": _webhook_url(bid, base),
    }


def obter_minha_configuracao_service(db, u, base=None):
    bid = obter_barbearia_id(u)
    return configuracao_response(obter_configuracao(db, bid), bid, base)


def salvar_minha_configuracao_service(db, d, u, base=None):
    bid = obter_barbearia_id(u)
    c = obter_configuracao(db, bid)
    if not c:
        c = models.MercadoPagoConfiguracao(barbearia_id=bid)
        db.add(c)
    if d.access_token and d.access_token.strip():
        c.access_token_encrypted = criptografar(d.access_token)
        c.oauth_status = "MANUAL"
    if d.webhook_secret and d.webhook_secret.strip():
        c.webhook_secret_encrypted = criptografar(d.webhook_secret)
    if d.public_key is not None:
        c.public_key = d.public_key.strip() or None
    ambiente = (d.ambiente or "producao").lower().strip()
    if ambiente not in {"teste", "producao"}:
        raise HTTPException(status_code=400, detail="Ambiente deve ser 'teste' ou 'producao'.")
    c.ambiente = ambiente
    c.ativo = bool(d.ativo)
    if c.ativo and not c.access_token_encrypted:
        raise HTTPException(status_code=400, detail="Informe o Access Token antes de ativar o Mercado Pago.")
    if c.ativo and not c.webhook_secret_encrypted and not (os.getenv("MP_WEBHOOK_SECRET") or "").strip():
        raise HTTPException(
            status_code=400,
            detail="Configure MP_WEBHOOK_SECRET no backend ou informe a assinatura secreta do Webhook.",
        )
    db.commit()
    db.refresh(c)
    return configuracao_response(c, bid, base)


def _api(method, path, token, payload=None, headers=None):
    body = None if payload is None else json.dumps(payload).encode()
    h = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    h.update(headers or {})
    req = request.Request(MP_API_BASE + path, data=body, headers=h, method=method)
    try:
        with request.urlopen(req, timeout=20) as r:
            raw = r.read().decode()
            return json.loads(raw) if raw else {}
    except error.HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        try:
            obj = json.loads(raw)
            msg = obj.get("message") or obj.get("error") or obj.get("errors") or raw
        except Exception:
            msg = raw
        raise HTTPException(
            status_code=502,
            detail=f"Mercado Pago recusou a operação: {msg}",
        ) from exc
    except error.URLError as exc:
        raise HTTPException(
            status_code=502,
            detail="Não foi possível conectar ao Mercado Pago.",
        ) from exc


def _amount(valor):
    return f"{round(float(valor), 2):.2f}"


def _order_payment(order):
    payments = ((order.get("transactions") or {}).get("payments") or [])
    return payments[0] if payments else {}


def _order_fields(order):
    pay = _order_payment(order)
    pm = pay.get("payment_method") or {}
    order_id = str(order.get("id")) if order.get("id") is not None else None
    payment_id = str(pay.get("id")) if pay.get("id") is not None else None
    status_value = pay.get("status") or order.get("status") or "pending"
    status_detail = pay.get("status_detail") or order.get("status_detail")
    installments = int(pm.get("installments") or 1)
    return {
        "order_id": order_id,
        "payment_id": payment_id,
        "status": status_value,
        "status_detail": status_detail,
        "installments": installments,
        "payment_method_id": pm.get("id"),
        "payment_type_id": pm.get("type"),
        "qr_code": pm.get("qr_code"),
        "qr_code_base64": pm.get("qr_code_base64"),
        "ticket_url": pm.get("ticket_url"),
        "amount": pay.get("amount") or order.get("total_amount"),
    }


def _dict(c):
    return {
        "cobranca_id": c.id,
        "assinatura_id": c.assinatura_id,
        "origem_negocio": c.origem_negocio or "PLANO_CLIENTE",
        "origem_id": c.origem_id,
        "order_id": c.order_id,
        "payment_id": c.payment_id,
        "status": c.status,
        "status_detail": c.status_detail,
        "external_reference": c.external_reference,
        "valor": c.valor,
        "tipo_pagamento": c.tipo_pagamento,
        "installments": c.installments,
        "valor_parcela": c.valor_parcela,
        "payment_method_id": c.payment_method_id,
        "payment_type_id": c.payment_type_id,
        "payer_email": c.payer_email,
        "qr_code": c.qr_code,
        "qr_code_base64": c.qr_code_base64,
        "ticket_url": c.ticket_url,
        "processado": c.processado,
        "data_criacao": c.data_criacao,
    }


def _validar_assinatura_para_cobranca(db, aid, bid):
    ass = db.query(models.AssinaturaCliente).filter(
        models.AssinaturaCliente.id == aid,
        models.AssinaturaCliente.barbearia_id == bid,
    ).first()
    if not ass:
        raise HTTPException(status_code=404, detail="Assinatura não encontrada.")
    plano = db.query(models.Plano).filter(
        models.Plano.id == ass.plano_id,
        models.Plano.barbearia_id == bid,
    ).first()
    if not plano or not plano.ativo:
        raise HTTPException(status_code=400, detail="Plano da assinatura não está disponível.")
    ref = datetime.now().strftime("%Y-%m")
    if db.query(models.PagamentoPlano).filter(
        models.PagamentoPlano.assinatura_id == aid,
        models.PagamentoPlano.referencia_mes == ref,
        models.PagamentoPlano.status == "PAGO",
    ).first():
        raise HTTPException(status_code=409, detail=f"A referência {ref} já está paga.")
    return ass, plano, ref


def gerar_pix_assinatura_service(db, aid, email, u, base):
    bid = obter_barbearia_id(u)
    cfg = obter_configuracao(db, bid)
    if not cfg or not cfg.ativo or not cfg.access_token_encrypted:
        raise HTTPException(
            status_code=400,
            detail="Mercado Pago não está configurado/ativo para esta barbearia.",
        )
    ass, plano, ref = _validar_assinatura_para_cobranca(db, aid, bid)
    cli = db.query(models.Cliente).filter(models.Cliente.id == ass.cliente_id).first()
    payer = (email or (cli.email if cli else None) or "").strip()
    if "@" not in payer:
        raise HTTPException(
            status_code=400,
            detail="Informe um e-mail válido do pagador para gerar o PIX.",
        )

    valor = round(float(plano.valor_pix if plano.valor_pix is not None else plano.valor), 2)
    idem = str(uuid.uuid4())
    ext = f"BARBSIST-{bid}-ASS-{aid}-{ref}-{uuid.uuid4().hex[:8]}"
    payload = {
        "type": "online",
        "total_amount": _amount(valor),
        "external_reference": ext,
        "processing_mode": "automatic",
        "transactions": {
            "payments": [
                {
                    "amount": _amount(valor),
                    "payment_method": {"id": "pix", "type": "bank_transfer"},
                }
            ]
        },
        "payer": {"email": payer},
    }
    order = _api(
        "POST",
        "/v1/orders",
        obter_access_token_valido(db, cfg),
        payload,
        {"X-Idempotency-Key": idem},
    )
    f = _order_fields(order)
    c = models.MercadoPagoCobranca(
        barbearia_id=bid,
        assinatura_id=aid,
        origem_negocio="PLANO_CLIENTE",
        origem_id=aid,
        order_id=f["order_id"],
        payment_id=f["payment_id"],
        idempotency_key=idem,
        external_reference=ext,
        valor=valor,
        tipo_pagamento="PIX",
        installments=1,
        valor_parcela=valor,
        payment_method_id=f["payment_method_id"] or "pix",
        payment_type_id=f["payment_type_id"] or "bank_transfer",
        status=f["status"],
        status_detail=f["status_detail"],
        payer_email=payer,
        qr_code=f["qr_code"],
        qr_code_base64=f["qr_code_base64"],
        ticket_url=f["ticket_url"],
        processado=False,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return _dict(c)


def gerar_cartao_assinatura_service(db, aid, dados, u, base):
    bid = obter_barbearia_id(u)
    cfg = obter_configuracao(db, bid)
    if not cfg or not cfg.ativo or not cfg.access_token_encrypted:
        raise HTTPException(
            status_code=400,
            detail="Mercado Pago não está configurado/ativo para esta barbearia.",
        )
    _, plano, ref = _validar_assinatura_para_cobranca(db, aid, bid)
    parcelas = int(dados.installments or 1)
    max_parcelas = max(1, min(int(plano.max_parcelas_cartao or 1), 12))
    if parcelas < 1 or parcelas > max_parcelas:
        raise HTTPException(
            status_code=400,
            detail=f"Este plano permite cartão em até {max_parcelas}x.",
        )
    payer = (dados.payer_email or "").strip()
    if "@" not in payer:
        raise HTTPException(status_code=400, detail="Informe um e-mail válido do pagador.")
    token = (dados.token or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Token do cartão não informado.")
    pmid = (dados.payment_method_id or "").strip()
    if not pmid:
        raise HTTPException(status_code=400, detail="payment_method_id não informado.")

    valor = round(float(plano.valor_cartao if plano.valor_cartao is not None else plano.valor), 2)
    idem = str(uuid.uuid4())
    ext = f"BARBSIST-{bid}-ASS-{aid}-{ref}-{uuid.uuid4().hex[:8]}"
    payer_obj = {"email": payer}
    if dados.identification_type and dados.identification_number:
        payer_obj["identification"] = {
            "type": dados.identification_type,
            "number": dados.identification_number,
        }
    payload = {
        "type": "online",
        "processing_mode": "automatic",
        "total_amount": _amount(valor),
        "external_reference": ext,
        "payer": payer_obj,
        "transactions": {
            "payments": [
                {
                    "amount": _amount(valor),
                    "payment_method": {
                        "id": pmid,
                        "type": "credit_card",
                        "token": token,
                        "installments": parcelas,
                    },
                }
            ]
        },
    }
    order = _api(
        "POST",
        "/v1/orders",
        obter_access_token_valido(db, cfg),
        payload,
        {"X-Idempotency-Key": idem},
    )
    f = _order_fields(order)
    c = models.MercadoPagoCobranca(
        barbearia_id=bid,
        assinatura_id=aid,
        origem_negocio="PLANO_CLIENTE",
        origem_id=aid,
        order_id=f["order_id"],
        payment_id=f["payment_id"],
        idempotency_key=idem,
        external_reference=ext,
        valor=valor,
        tipo_pagamento="CARTAO",
        installments=f["installments"] or parcelas,
        valor_parcela=round(valor / parcelas, 2),
        payment_method_id=f["payment_method_id"] or pmid,
        payment_type_id=f["payment_type_id"] or "credit_card",
        status=f["status"],
        status_detail=f["status_detail"],
        payer_email=payer,
        processado=False,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return _dict(c)


def _normalizar_origem_negocio(valor):
    origem = (valor or "").strip().upper()
    aliases = {
        "PLANO": "PLANO_CLIENTE",
        "ASSINATURA": "PLANO_CLIENTE",
        "ASSINATURA_CLIENTE": "PLANO_CLIENTE",
    }
    origem = aliases.get(origem, origem)
    permitidas = {"PLANO_CLIENTE", "COMANDA", "VENDA"}
    if origem not in permitidas:
        raise HTTPException(
            status_code=400,
            detail=f"Origem de cobrança inválida. Permitidas: {', '.join(sorted(permitidas))}.",
        )
    return origem


def gerar_pix_cobranca_service(db, dados, u, base):
    origem = _normalizar_origem_negocio(dados.origem_negocio)
    if origem == "PLANO_CLIENTE":
        return gerar_pix_assinatura_service(
            db, int(dados.origem_id), dados.payer_email, u, base
        )
    raise HTTPException(
        status_code=501,
        detail=f"A origem {origem} já está reservada na arquitetura, mas será ativada na etapa específica de integração.",
    )


def gerar_cartao_cobranca_service(db, dados, u, base):
    origem = _normalizar_origem_negocio(dados.origem_negocio)
    if origem == "PLANO_CLIENTE":
        return gerar_cartao_assinatura_service(
            db, int(dados.origem_id), dados, u, base
        )
    raise HTTPException(
        status_code=501,
        detail=f"A origem {origem} já está reservada na arquitetura, mas será ativada na etapa específica de integração.",
    )


def listar_cobrancas_service(db, u):
    bid = obter_barbearia_id(u)
    return [
        _dict(c)
        for c in db.query(models.MercadoPagoCobranca)
        .filter(models.MercadoPagoCobranca.barbearia_id == bid)
        .order_by(models.MercadoPagoCobranca.id.desc())
        .limit(200)
        .all()
    ]


def validar_assinatura_webhook(xs, xr, data_id, secret):
    if not xs:
        return False
    parts = {
        k.strip(): v.strip()
        for item in xs.split(",")
        if "=" in item
        for k, v in [item.split("=", 1)]
    }
    ts = parts.get("ts")
    v1 = parts.get("v1")
    if not ts or not v1:
        return False
    manifest = (
        (f"id:{str(data_id).lower()};" if data_id else "")
        + (f"request-id:{xr};" if xr else "")
        + f"ts:{ts};"
    )
    assinatura = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(assinatura, v1)


def _webhook_secret(cfg=None):
    global_secret = (os.getenv("MP_WEBHOOK_SECRET") or "").strip()
    if global_secret:
        return global_secret
    if cfg and cfg.webhook_secret_encrypted:
        return descriptografar(cfg.webhook_secret_encrypted)
    return ""


def _configuracao_por_webhook(db, payload, order_id, bid_forcado=None):
    if bid_forcado is not None:
        return obter_configuracao(db, bid_forcado)

    seller_user_id = payload.get("user_id")
    if seller_user_id is not None:
        cfg = db.query(models.MercadoPagoConfiguracao).filter(
            models.MercadoPagoConfiguracao.mercado_pago_user_id == str(seller_user_id),
            models.MercadoPagoConfiguracao.ativo.is_(True),
        ).first()
        if cfg:
            return cfg

    cobranca = db.query(models.MercadoPagoCobranca).filter(
        models.MercadoPagoCobranca.order_id == str(order_id)
    ).first()
    return obter_configuracao(db, cobranca.barbearia_id) if cobranca else None


def _processar_order_webhook(
    db,
    order_id,
    payload,
    xs,
    xr,
    bid_forcado=None,
):
    tipo = (payload.get("type") or "").lower()

    if tipo and tipo != "order":
        return {"status": "ignorado", "tipo": tipo}

    if not order_id:
        return {"status": "ignorado", "motivo": "sem order id"}

    cfg_pre = _configuracao_por_webhook(
        db,
        payload,
        order_id,
        bid_forcado,
    )

    secret = _webhook_secret(cfg_pre)

    if not secret:
        raise HTTPException(
            status_code=503,
            detail=(
                "Webhook Mercado Pago sem assinatura secreta "
                "configurada."
            ),
        )

    if not validar_assinatura_webhook(
        xs,
        xr,
        order_id,
        secret,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Assinatura do Webhook inválida.",
        )

    if (
        not cfg_pre
        or not cfg_pre.ativo
        or not cfg_pre.access_token_encrypted
    ):
        raise HTTPException(
            status_code=404,
            detail=(
                "Configuração Mercado Pago da barbearia "
                "não encontrada."
            ),
        )

    seller_user_id = payload.get("user_id")
    if (
        seller_user_id is not None
        and cfg_pre.mercado_pago_user_id
        and str(seller_user_id) != str(cfg_pre.mercado_pago_user_id)
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Webhook recebido para vendedor Mercado Pago "
                "divergente da configuração da barbearia."
            ),
        )

    order = _api(
        "GET",
        f"/v1/orders/{order_id}",
        obter_access_token_valido(db, cfg_pre),
    )

    ext = order.get("external_reference")
    f = _order_fields(order)
    bid = cfg_pre.barbearia_id

    # O lock garante que dois webhooks simultâneos não processem
    # a mesma cobrança em paralelo.
    c = (
        db.query(models.MercadoPagoCobranca)
        .filter(
            models.MercadoPagoCobranca.barbearia_id == bid,
            (
                (models.MercadoPagoCobranca.order_id == str(order_id))
                | (
                    models.MercadoPagoCobranca.external_reference
                    == ext
                )
            ),
        )
        .with_for_update()
        .first()
    )

    if not c:
        return {
            "status": "ignorado",
            "motivo": "cobrança não pertence ao BarbSist",
        }

    # Defesa em profundidade: configuração, cobrança e tenant precisam
    # apontar para a mesma barbearia.
    if c.barbearia_id != cfg_pre.barbearia_id:
        raise HTTPException(
            status_code=409,
            detail="Cobrança e configuração Mercado Pago divergentes.",
        )

    if (
        ext
        and c.external_reference
        and ext != c.external_reference
    ):
        raise HTTPException(
            status_code=409,
            detail="external_reference divergente da cobrança registrada.",
        )

    c.order_id = str(order_id)
    c.payment_id = f["payment_id"] or c.payment_id
    c.status = f["status"] or c.status
    c.status_detail = f["status_detail"] or c.status_detail
    c.payment_method_id = (
        f["payment_method_id"] or c.payment_method_id
    )
    c.payment_type_id = (
        f["payment_type_id"] or c.payment_type_id
    )
    c.installments = int(
        f["installments"] or c.installments or 1
    )
    c.qr_code = f["qr_code"] or c.qr_code
    c.qr_code_base64 = (
        f["qr_code_base64"] or c.qr_code_base64
    )
    c.ticket_url = f["ticket_url"] or c.ticket_url

    if c.installments:
        c.valor_parcela = round(
            float(c.valor) / c.installments,
            2,
        )

    if c.processado:
        db.commit()
        return {"status": "ja_processado"}

    if c.status != "processed":
        db.commit()
        return {
            "status": c.status,
            "status_detail": c.status_detail,
        }

    valor_order = round(
        float(f["amount"] or 0),
        2,
    )

    if valor_order != round(float(c.valor), 2):
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Valor processado diverge da cobrança.",
        )

    origem = _normalizar_origem_negocio(
        c.origem_negocio or "PLANO_CLIENTE"
    )

    # COMANDA/VENDA permanecem reservadas e deliberadamente não
    # são ativadas neste pacote de hardening.
    if origem != "PLANO_CLIENTE":
        db.commit()
        raise HTTPException(
            status_code=501,
            detail=(
                f"Processamento da origem {origem} ainda "
                "não foi ativado nesta etapa."
            ),
        )

    aid = c.origem_id or c.assinatura_id

    ass = (
        db.query(models.AssinaturaCliente)
        .filter(
            models.AssinaturaCliente.id == aid,
            models.AssinaturaCliente.barbearia_id == bid,
        )
        .first()
    )

    plano = (
        db.query(models.Plano)
        .filter(
            models.Plano.id == ass.plano_id,
            models.Plano.barbearia_id == bid,
        )
        .first()
        if ass
        else None
    )

    if not ass or not plano:
        raise HTTPException(
            status_code=404,
            detail="Assinatura/plano da cobrança não encontrado.",
        )

    forma = (
        "MERCADO_PAGO_CARTAO"
        if (c.tipo_pagamento or "").upper() == "CARTAO"
        else "MERCADO_PAGO_PIX"
    )

    obs = (
        f"Mercado Pago order_id={c.order_id}; "
        f"payment_id={c.payment_id or ''}; "
        f"{c.installments or 1}x; "
        f"método={c.payment_method_id or ''}"
    )

    pagamento_duplicado = False

    try:
        confirmar_pagamento_assinatura_service(
            db,
            ass,
            plano,
            forma,
            obs,
            None,
            c.data_criacao.strftime("%Y-%m"),
            False,
            valor_pagamento=c.valor,
        )
    except HTTPException as exc:
        if exc.status_code != 409:
            db.rollback()
            raise

        pagamento_duplicado = True
        c.status_detail = "pagamento_duplicado_referencia"

    c.processado = True
    c.processado_em = datetime.now()
    db.commit()

    return {
        "status": "processed",
        "processado": True,
        "origem_negocio": origem,
        "origem_id": aid,
        "order_id": c.order_id,
        "payment_id": c.payment_id,
        "pagamento_duplicado": pagamento_duplicado,
    }

def processar_webhook_global_service(db, data_id, payload, xs, xr):
    order_id = data_id or str((payload.get("data") or {}).get("id") or "")
    return _processar_order_webhook(db, order_id, payload, xs, xr)


def processar_webhook_service(db, bid, data_id, payload, xs, xr):
    """Compatibilidade temporária com a antiga rota /webhook/{barbearia_id}."""
    order_id = data_id or str((payload.get("data") or {}).get("id") or "")
    return _processar_order_webhook(
        db, order_id, payload, xs, xr, bid_forcado=bid
    )
