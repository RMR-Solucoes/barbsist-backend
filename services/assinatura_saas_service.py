import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime
from calendar import monthrange
from urllib import error, request

from fastapi import HTTPException, status

import models
from auth.tenant import obter_barbearia_id

MP_API_BASE = "https://api.mercadopago.com"


def _add_months(dt: datetime, months: int) -> datetime:
    months = max(1, int(months or 1))
    y = dt.year + (dt.month - 1 + months) // 12
    m = (dt.month - 1 + months) % 12 + 1
    d = min(dt.day, monthrange(y, m)[1])
    return dt.replace(year=y, month=m, day=d)


def _mp_env():
    token = (os.getenv("BARBSIST_MP_ACCESS_TOKEN") or "").strip()
    public_key = (os.getenv("BARBSIST_MP_PUBLIC_KEY") or "").strip()
    webhook_secret = (os.getenv("BARBSIST_MP_WEBHOOK_SECRET") or "").strip()
    if not token:
        raise HTTPException(status_code=500, detail="BARBSIST_MP_ACCESS_TOKEN não configurado.")
    return token, public_key, webhook_secret


def obter_public_key_service():
    _, public_key, _ = _mp_env()
    if not public_key:
        raise HTTPException(status_code=503, detail="BARBSIST_MP_PUBLIC_KEY não configurada.")
    return {"public_key": public_key}


def _api(method, path, payload=None, extra_headers=None):
    token, _, _ = _mp_env()
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode()
    if extra_headers:
        headers.update(extra_headers)
    req = request.Request(MP_API_BASE + path, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=25) as resp:
            return json.loads(resp.read().decode())
    except error.HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        try:
            obj = json.loads(raw)
            detalhe = obj.get("message") or obj.get("cause") or obj.get("error") or raw
        except Exception:
            detalhe = raw
        raise HTTPException(status_code=502, detail=f"Mercado Pago recusou a operação: {detalhe}") from exc
    except error.URLError as exc:
        raise HTTPException(status_code=502, detail="Não foi possível conectar ao Mercado Pago.") from exc


def _webhook_url(base_url=None):
    raiz = (os.getenv("PUBLIC_BACKEND_URL") or os.getenv("BACKEND_PUBLIC_URL") or base_url or "").strip().rstrip("/")
    if not raiz:
        raise HTTPException(status_code=500, detail="PUBLIC_BACKEND_URL não configurada.")
    return f"{raiz}/barbsist-assinaturas/webhook"



def status_mercado_pago_barbsist_service(base_url: str | None = None):
    token = (os.getenv("BARBSIST_MP_ACCESS_TOKEN") or "").strip()
    public_key = (os.getenv("BARBSIST_MP_PUBLIC_KEY") or "").strip()
    webhook_secret = (os.getenv("BARBSIST_MP_WEBHOOK_SECRET") or "").strip()
    raiz = (os.getenv("PUBLIC_BACKEND_URL") or os.getenv("BACKEND_PUBLIC_URL") or base_url or "").strip().rstrip("/")
    return {
        "access_token_configurado": bool(token),
        "public_key_configurada": bool(public_key),
        "webhook_secret_configurado": bool(webhook_secret),
        "pronto_para_cobranca": bool(token and public_key and webhook_secret and raiz),
        "webhook_url": f"{raiz}/barbsist-assinaturas/webhook" if raiz else None,
    }

def listar_planos_saas_service(db, incluir_inativos=False):
    q = db.query(models.PlanoSaaS)
    if not incluir_inativos:
        q = q.filter(models.PlanoSaaS.ativo.is_(True))
    return q.order_by(models.PlanoSaaS.periodo_meses, models.PlanoSaaS.id).all()


def criar_plano_saas_service(db, dados):
    if dados.periodo_meses < 1:
        raise HTTPException(status_code=400, detail="periodo_meses deve ser >= 1.")
    if dados.valor_pix <= 0 or dados.valor_cartao <= 0:
        raise HTTPException(status_code=400, detail="Os valores do plano devem ser positivos.")
    if dados.max_parcelas_cartao < 1 or dados.max_parcelas_cartao > 12:
        raise HTTPException(status_code=400, detail="max_parcelas_cartao deve ficar entre 1 e 12.")
    if db.query(models.PlanoSaaS).filter(models.PlanoSaaS.nome == dados.nome.strip()).first():
        raise HTTPException(status_code=409, detail="Já existe um plano SaaS com esse nome.")
    obj = models.PlanoSaaS(**dados.model_dump())
    obj.nome = obj.nome.strip()
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


def atualizar_plano_saas_service(db, plano_id, dados):
    obj = db.query(models.PlanoSaaS).filter(models.PlanoSaaS.id == plano_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Plano SaaS não encontrado.")
    valores = dados.model_dump(exclude_unset=True)
    if "periodo_meses" in valores and valores["periodo_meses"] < 1:
        raise HTTPException(status_code=400, detail="periodo_meses deve ser >= 1.")
    if "max_parcelas_cartao" in valores and not 1 <= valores["max_parcelas_cartao"] <= 12:
        raise HTTPException(status_code=400, detail="max_parcelas_cartao deve ficar entre 1 e 12.")
    for campo in ("valor_pix", "valor_cartao"):
        if campo in valores and valores[campo] <= 0:
            raise HTTPException(status_code=400, detail=f"{campo} deve ser positivo.")
    for k, v in valores.items(): setattr(obj, k, v.strip() if k == "nome" and isinstance(v, str) else v)
    db.commit(); db.refresh(obj); return obj


def _obter_plano(db, plano_id):
    plano = db.query(models.PlanoSaaS).filter(models.PlanoSaaS.id == plano_id, models.PlanoSaaS.ativo.is_(True)).first()
    if not plano:
        raise HTTPException(status_code=404, detail="Plano SaaS não encontrado ou inativo.")
    return plano


def _obter_ou_criar_assinatura(db, barbearia_id, plano):
    ass = db.query(models.AssinaturaSaaS).filter(models.AssinaturaSaaS.barbearia_id == barbearia_id).first()
    if not ass:
        ass = models.AssinaturaSaaS(barbearia_id=barbearia_id, plano_id=plano.id, status="PENDENTE", status_pagamento="PENDENTE")
        db.add(ass); db.flush()
    else:
        ass.plano_id = plano.id
        if ass.status not in ("ATIVA", "BLOQUEADA"):
            ass.status = "PENDENTE"
        ass.status_pagamento = "PENDENTE"
    return ass


def minha_assinatura_saas_service(db, usuario):
    bid = obter_barbearia_id(usuario)
    return db.query(models.AssinaturaSaaS).filter(models.AssinaturaSaaS.barbearia_id == bid).first()


def _criar_pagamento_base(db, ass, plano, tipo, valor, payer_email, installments, method_id, resposta, idem, ext):
    p = models.PagamentoSaaS(
        assinatura_id=ass.id, barbearia_id=ass.barbearia_id, plano_id=plano.id,
        payment_id=str(resposta.get("id")) if resposta.get("id") is not None else None,
        external_reference=ext, idempotency_key=idem,
        tipo_pagamento=tipo, payment_method_id=resposta.get("payment_method_id") or method_id,
        payment_type_id=resposta.get("payment_type_id"), installments=installments,
        valor=valor, valor_parcela=round(valor/installments, 2), payer_email=payer_email,
        status=resposta.get("status") or "pending", status_detail=resposta.get("status_detail"),
        processado=False,
    )
    td = ((resposta.get("point_of_interaction") or {}).get("transaction_data") or {})
    p.qr_code = td.get("qr_code"); p.qr_code_base64 = td.get("qr_code_base64"); p.ticket_url = td.get("ticket_url")
    db.add(p); db.commit(); db.refresh(p); return p


def checkout_pix_saas_service(db, dados, usuario, base_url=None):
    bid = obter_barbearia_id(usuario)
    plano = _obter_plano(db, dados.plano_id)
    email = (dados.payer_email or "").strip()
    if "@" not in email: raise HTTPException(status_code=400, detail="Informe um e-mail válido.")
    ass = _obter_ou_criar_assinatura(db, bid, plano)
    idem = str(uuid.uuid4()); ext = f"BARBSIST-SAAS-B{bid}-A{ass.id}-{uuid.uuid4().hex[:12]}"
    valor = round(float(plano.valor_pix), 2)
    payload = {"transaction_amount": valor, "description": f"BarbSist - {plano.nome}", "payment_method_id": "pix", "payer": {"email": email}, "external_reference": ext, "notification_url": _webhook_url(base_url)}
    resp = _api("POST", "/v1/payments", payload, {"X-Idempotency-Key": idem})
    return _criar_pagamento_base(db, ass, plano, "PIX", valor, email, 1, "pix", resp, idem, ext)


def checkout_cartao_saas_service(db, dados, usuario, base_url=None):
    bid = obter_barbearia_id(usuario)
    plano = _obter_plano(db, dados.plano_id)
    parcelas = int(dados.installments or 1)
    maxp = max(1, min(int(plano.max_parcelas_cartao or 1), 12))
    if parcelas < 1 or parcelas > maxp: raise HTTPException(status_code=400, detail=f"Este plano permite cartão em até {maxp}x.")
    email=(dados.payer_email or "").strip(); token=(dados.token or "").strip(); pmid=(dados.payment_method_id or "").strip()
    if "@" not in email: raise HTTPException(status_code=400, detail="Informe um e-mail válido.")
    if not token or not pmid: raise HTTPException(status_code=400, detail="Token e payment_method_id são obrigatórios.")
    ass = _obter_ou_criar_assinatura(db, bid, plano)
    idem=str(uuid.uuid4()); ext=f"BARBSIST-SAAS-B{bid}-A{ass.id}-{uuid.uuid4().hex[:12]}"; valor=round(float(plano.valor_cartao),2)
    payload={"transaction_amount":valor,"token":token,"description":f"BarbSist - {plano.nome}","installments":parcelas,"payment_method_id":pmid,"payer":{"email":email},"external_reference":ext,"notification_url":_webhook_url(base_url)}
    if dados.issuer_id is not None: payload["issuer_id"] = dados.issuer_id
    if dados.identification_type and dados.identification_number: payload["payer"]["identification"]={"type":dados.identification_type,"number":dados.identification_number}
    resp=_api("POST","/v1/payments",payload,{"X-Idempotency-Key":idem})
    return _criar_pagamento_base(db,ass,plano,"CARTAO",valor,email,parcelas,pmid,resp,idem,ext)


def _validar_assinatura_webhook(x_signature, x_request_id, data_id, secret):
    if not x_signature or not secret: return False
    parts={}
    for item in x_signature.split(","):
        if "=" in item:
            k,v=item.split("=",1); parts[k.strip()]=v.strip()
    ts=parts.get("ts"); v1=parts.get("v1")
    if not ts or not v1: return False
    template=(f"id:{str(data_id).lower()};" if data_id else "")+(f"request-id:{x_request_id};" if x_request_id else "")+f"ts:{ts};"
    digest=hmac.new(secret.encode(),template.encode(),hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest,v1)


def _ativar_assinatura_por_pagamento(db, pagamento, mp_payment):
    ass=db.query(models.AssinaturaSaaS).filter(models.AssinaturaSaaS.id==pagamento.assinatura_id).first()
    plano=db.query(models.PlanoSaaS).filter(models.PlanoSaaS.id==pagamento.plano_id).first()
    if not ass or not plano: raise HTTPException(status_code=404,detail="Assinatura SaaS/plano não encontrado.")
    agora=datetime.now()
    base=ass.data_fim if ass.data_fim and ass.data_fim > agora and ass.status == "ATIVA" else agora
    fim=_add_months(base, plano.periodo_meses)
    ass.status="ATIVA"; ass.status_pagamento="PAGO"; ass.forma_pagamento=pagamento.tipo_pagamento
    ass.data_inicio = ass.data_inicio or agora; ass.data_fim=fim; ass.data_proximo_vencimento=fim; ass.liberado_manual=False; ass.motivo_bloqueio=None
    pagamento.processado=True; pagamento.processado_em=agora


def processar_webhook_saas_service(db, data_id, payload, x_signature, x_request_id):
    _, _, secret = _mp_env()
    if not secret: raise HTTPException(status_code=503, detail="BARBSIST_MP_WEBHOOK_SECRET não configurado.")
    if not _validar_assinatura_webhook(x_signature,x_request_id,data_id,secret): raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Assinatura do Webhook inválida.")
    tipo=(payload.get("type") or "").lower(); pid=data_id or str((payload.get("data") or {}).get("id") or "")
    if tipo and tipo != "payment": return {"status":"ignorado","tipo":tipo}
    if not pid: return {"status":"ignorado","motivo":"sem payment id"}
    mp=_api("GET",f"/v1/payments/{pid}")
    ext=mp.get("external_reference")
    pag=db.query(models.PagamentoSaaS).filter((models.PagamentoSaaS.payment_id==str(pid)) | (models.PagamentoSaaS.external_reference==ext)).first()
    if not pag: return {"status":"ignorado","motivo":"pagamento não pertence à cobrança SaaS BarbSist"}
    pag.payment_id=str(pid); pag.status=mp.get("status") or pag.status; pag.status_detail=mp.get("status_detail") or pag.status_detail
    pag.payment_method_id=mp.get("payment_method_id") or pag.payment_method_id; pag.payment_type_id=mp.get("payment_type_id") or pag.payment_type_id; pag.installments=int(mp.get("installments") or pag.installments or 1)
    if pag.processado: db.commit(); return {"status":"ja_processado"}
    if pag.status != "approved": db.commit(); return {"status":pag.status}
    if round(float(mp.get("transaction_amount") or 0),2) != round(float(pag.valor),2): db.rollback(); raise HTTPException(status_code=409,detail="Valor aprovado diverge da cobrança SaaS.")
    _ativar_assinatura_por_pagamento(db,pag,mp); db.commit(); return {"status":"approved","processado":True}


def listar_assinaturas_admin_service(db):
    return db.query(models.AssinaturaSaaS).order_by(models.AssinaturaSaaS.id.desc()).all()


def listar_pagamentos_admin_service(db):
    return db.query(models.PagamentoSaaS).order_by(models.PagamentoSaaS.id.desc()).limit(500).all()


def liberar_assinatura_manual_service(db, assinatura_id, dados):
    ass=db.query(models.AssinaturaSaaS).filter(models.AssinaturaSaaS.id==assinatura_id).first()
    if not ass: raise HTTPException(status_code=404,detail="Assinatura SaaS não encontrada.")
    agora=datetime.now(); ass.status="ATIVA"; ass.status_pagamento="LIBERADO_MANUAL"; ass.forma_pagamento="MANUAL"; ass.data_inicio=ass.data_inicio or agora
    # Liberação manual em dias é suporte excepcional e não altera a definição do plano.
    from datetime import timedelta
    ass.data_fim=agora+timedelta(days=max(1,int(dados.dias or 30))); ass.data_proximo_vencimento=ass.data_fim; ass.liberado_manual=True; ass.motivo_bloqueio=None
    db.commit(); db.refresh(ass); return ass


def bloquear_assinatura_service(db, assinatura_id, dados):
    ass=db.query(models.AssinaturaSaaS).filter(models.AssinaturaSaaS.id==assinatura_id).first()
    if not ass: raise HTTPException(status_code=404,detail="Assinatura SaaS não encontrada.")
    ass.status="BLOQUEADA"; ass.status_pagamento="BLOQUEADA"; ass.motivo_bloqueio=(dados.motivo or "").strip() or "Bloqueio administrativo"
    db.commit(); db.refresh(ass); return ass
