import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timedelta
from calendar import monthrange
from urllib import error, request

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

import models
from parceiros.service_parceiros import (
    aplicar_resgate_creditos_service,
    cancelar_reserva_creditos_service,
    processar_beneficio_pagamento_service,
)
from auth.tenant import obter_barbearia_id

from parceiros.models_parceiros import (
    Parceiro,
    ResgateCreditoBarbearia,
)

from parceiros.service_parceiros import (
    calcular_saldo_creditos_service,
)

MP_API_BASE = "https://api.mercadopago.com"



def _preparar_credito_mensalidade_saas(
    db,
    assinatura,
    plano,
    valor_original,
):
    """
    Prepara uma reserva automatica de credito para mensalidade SaaS.

    Regras:
    - somente plano mensal (periodo_meses == 1);
    - somente parceiro ativo do tipo BARBEARIA;
    - somente parceiro com beneficio CREDITO;
    - nao consome definitivamente o credito;
    - cria resgate APROVADO, que permanece reservado
      ate o pagamento ser confirmado;
    - semestral/anual continuam com credito na carteira.
    """

    valor_original = round(
        float(valor_original or 0),
        2,
    )

    resultado = {
        "parceiro": None,
        "resgate": None,
        "valor_original": valor_original,
        "valor_credito": 0.0,
        "valor_cobrar": valor_original,
    }

    if valor_original <= 0:
        return resultado

    if int(plano.periodo_meses or 1) != 1:
        return resultado

    parceiro = (
        db.query(Parceiro)
        .filter(
            Parceiro.barbearia_id == assinatura.barbearia_id,
            Parceiro.tipo == "BARBEARIA",
            Parceiro.tipo_beneficio == "CREDITO",
            Parceiro.ativo.is_(True),
        )
        .first()
    )

    if not parceiro:
        return resultado

    saldo = calcular_saldo_creditos_service(
        db,
        parceiro.id,
    )

    saldo_disponivel = round(
        float(saldo["saldo_disponivel"] or 0),
        2,
    )

    if saldo_disponivel <= 0:
        resultado["parceiro"] = parceiro
        return resultado

    valor_credito = round(
        min(
            saldo_disponivel,
            valor_original,
        ),
        2,
    )

    if valor_credito <= 0:
        resultado["parceiro"] = parceiro
        return resultado

    resgate = ResgateCreditoBarbearia(
        parceiro_id=parceiro.id,
        barbearia_id=assinatura.barbearia_id,
        assinatura_saas_id=assinatura.id,
        pagamento_saas_id=None,
        tipo_aplicacao="MENSALIDADE_AUTOMATICA",
        valor_solicitado=valor_credito,
        valor_aplicado=0,
        status="APROVADO",
        solicitado_em=datetime.now(),
        aprovado_em=datetime.now(),
        observacao=(
            "Credito reservado automaticamente "
            "para mensalidade BarbSist."
        ),
    )

    db.add(resgate)
    db.flush()

    resultado["parceiro"] = parceiro
    resultado["resgate"] = resgate
    resultado["valor_credito"] = valor_credito
    resultado["valor_cobrar"] = round(
        max(
            valor_original - valor_credito,
            0,
        ),
        2,
    )

    return resultado


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

# ============================================================
# PROGRAMA FUNDADORES BARBSIST
# ============================================================

FUNDADORES_CODIGO = "FUNDADORES_50"
FUNDADORES_LIMITE = 50
FUNDADORES_MESES = 6

FUNDADORES_PRECOS = {
    1: {
        "pix": 19.90,
        "cartao": 22.90,
    },
    5: {
        "pix": 29.90,
        "cartao": 34.90,
    },
    10: {
        "pix": 49.90,
        "cartao": 54.90,
    },
}


def _precos_fundador_para_plano(plano):
    """
    Retorna os preços promocionais do Programa Fundadores.

    A campanha Fundadores vale somente para planos mensais.
    Planos semestrais e anuais sempre utilizam seus preços normais.
    """
    if int(plano.periodo_meses or 1) != 1:
        return None

    precos = FUNDADORES_PRECOS.get(
        int(plano.limite_barbeiros or 0)
    )

    if not precos:
        return None

    # Uma promocao nunca pode ficar mais cara que o catalogo normal. Isso e
    # especialmente importante para o novo Solo de R$ 19,90.
    return {
        "pix": min(float(precos["pix"]), float(plano.valor_pix)),
        "cartao": min(
            float(precos["cartao"]),
            float(plano.valor_cartao),
        ),
    }


def _promocao_fundador_ativa(assinatura, agora=None):
    """
    Verifica se uma assinatura já conquistou a condição Fundador
    e ainda está dentro dos seis meses promocionais.
    """
    agora = agora or datetime.now()

    return (
        assinatura is not None
        and assinatura.promocao_codigo == FUNDADORES_CODIGO
        and assinatura.fundador_posicao is not None
        and assinatura.promocao_inicio is not None
        and assinatura.promocao_fim is not None
        and assinatura.promocao_inicio <= agora
        and agora < assinatura.promocao_fim
    )


def _proxima_posicao_fundador(db):
    """
    Retorna a primeira posição Fundador disponível entre 1 e 50.
    Se todas estiverem ocupadas, retorna None.
    """
    ocupadas = {
        int(posicao)
        for (posicao,) in (
            db.query(models.AssinaturaSaaS.fundador_posicao)
            .filter(
                models.AssinaturaSaaS.fundador_posicao.isnot(None)
            )
            .all()
        )
    }

    for posicao in range(1, FUNDADORES_LIMITE + 1):
        if posicao not in ocupadas:
            return posicao

    return None


def _tem_vaga_fundador(db):
    """
    Verifica se ainda existe alguma posição Fundador disponível.
    Não grava nem reserva vaga.
    """
    total = (
        db.query(models.AssinaturaSaaS)
        .filter(
            models.AssinaturaSaaS.fundador_posicao.isnot(None)
        )
        .count()
    )

    return total < FUNDADORES_LIMITE


def _elegivel_preco_fundador(db, assinatura, plano):
    """
    Determina se o checkout pode utilizar preço Fundador.

    Quem já possui promoção ativa mantém o benefício.
    Novos clientes recebem preço promocional enquanto houver
    vaga disponível, mas a posição somente será consolidada
    quando o pagamento for aprovado.
    """
    if _promocao_fundador_ativa(assinatura):
        return True

    if assinatura.fundador_posicao is not None:
        return False

    if not _precos_fundador_para_plano(plano):
        return False

    return _tem_vaga_fundador(db)


def _valor_checkout_saas_com_db(
    db,
    assinatura,
    plano,
    forma_pagamento,
):
    forma = (forma_pagamento or "").strip().lower()

    if _elegivel_preco_fundador(
        db,
        assinatura,
        plano,
    ):
        precos = _precos_fundador_para_plano(plano)

        if forma == "pix":
            return round(float(precos["pix"]), 2)

        if forma in {"cartao", "cartão"}:
            return round(float(precos["cartao"]), 2)

    if forma == "pix":
        return round(float(plano.valor_pix), 2)

    if forma in {"cartao", "cartão"}:
        return round(float(plano.valor_cartao), 2)

    raise HTTPException(
        status_code=400,
        detail="Forma de pagamento SaaS inválida."
    )


def _garantir_promocao_fundador(db, assinatura, plano):
    """
    Registra a condição Fundador na assinatura, quando elegível.

    Regras:
    - preserva quem já possui posição Fundador;
    - somente planos oficiais 1 / 5 / 10 barbeiros participam;
    - somente as primeiras 50 posições são contempladas;
    - promoção dura 6 meses.
    """
    if assinatura.fundador_posicao is not None:
        return assinatura

    precos = _precos_fundador_para_plano(plano)

    if not precos:
        return assinatura

    posicao = _proxima_posicao_fundador(db)

    if posicao is None:
        return assinatura

    agora = datetime.now()

    assinatura.promocao_codigo = FUNDADORES_CODIGO
    assinatura.promocao_inicio = agora
    assinatura.promocao_fim = _add_months(
        agora,
        FUNDADORES_MESES,
    )
    assinatura.fundador_posicao = posicao

    db.flush()

    return assinatura


def _valor_checkout_saas(assinatura, plano, forma_pagamento):
    """
    Define o valor que deverá ser enviado ao Mercado Pago.

    Enquanto a condição Fundador estiver vigente, utiliza
    o preço promocional. Após o prazo, volta automaticamente
    ao preço normal cadastrado no PlanoSaaS.
    """
    forma = (forma_pagamento or "").strip().lower()

    if _promocao_fundador_ativa(assinatura):
        precos = _precos_fundador_para_plano(plano)

        if precos:
            if forma == "pix":
                return round(float(precos["pix"]), 2)

            if forma in {"cartao", "cartão"}:
                return round(float(precos["cartao"]), 2)

    if forma == "pix":
        return round(float(plano.valor_pix), 2)

    if forma in {"cartao", "cartão"}:
        return round(float(plano.valor_cartao), 2)

    raise HTTPException(
        status_code=400,
        detail="Forma de pagamento SaaS inválida."
    )


def listar_planos_saas_service(db, incluir_inativos=False):
    q = db.query(models.PlanoSaaS)
    if not incluir_inativos:
        q = q.filter(models.PlanoSaaS.ativo.is_(True))
    return q.order_by(models.PlanoSaaS.periodo_meses, models.PlanoSaaS.id).all()


def criar_plano_saas_service(db, dados):
    if dados.periodo_meses < 1:
        raise HTTPException(status_code=400, detail="periodo_meses deve ser >= 1.")

    if dados.limite_barbeiros < 1:
        raise HTTPException(
            status_code=400,
            detail="limite_barbeiros deve ser >= 1."
        )

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

    novo_limite = valores.get("limite_barbeiros")
    if (
        novo_limite is not None
        and int(novo_limite) < int(obj.limite_barbeiros or 1)
    ):
        assinaturas_ativas = (
            db.query(models.AssinaturaSaaS)
            .filter(
                models.AssinaturaSaaS.plano_id == obj.id,
                models.AssinaturaSaaS.status == "ATIVA",
            )
            .all()
        )

        excedentes = []
        for assinatura in assinaturas_ativas:
            total_ativos = (
                db.query(models.Barbeiro)
                .filter(
                    models.Barbeiro.barbearia_id
                    == assinatura.barbearia_id,
                    models.Barbeiro.ativo.is_(True),
                )
                .count()
            )
            if total_ativos > int(novo_limite):
                excedentes.append(
                    {
                        "barbearia_id": assinatura.barbearia_id,
                        "barbeiros_ativos": total_ativos,
                    }
                )

        if excedentes:
            raise HTTPException(
                status_code=409,
                detail={
                    "codigo": "REDUCAO_LIMITE_INCOMPATIVEL",
                    "mensagem": (
                        "O limite nao pode ser reduzido enquanto existirem "
                        "barbearias assinantes com mais profissionais ativos "
                        "que o novo limite."
                    ),
                    "novo_limite": int(novo_limite),
                    "barbearias_excedentes": excedentes,
                },
            )

    if (
        "limite_barbeiros" in valores
        and valores["limite_barbeiros"] is not None
        and valores["limite_barbeiros"] < 1
    ):
        raise HTTPException(
            status_code=400,
            detail="limite_barbeiros deve ser >= 1."
        )
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


def _obter_ou_criar_assinatura(
    db,
    barbearia_id,
    plano,
):
    """
    Obtém a assinatura SaaS sem trocar o plano vigente apenas por
    iniciar um checkout.

    A mudança de plano ocorre somente quando um pagamento aprovado
    é processado.
    """

    # Serializa a criação por barbearia.
    barbearia = (
        db.query(models.Barbearia)
        .filter(models.Barbearia.id == barbearia_id)
        .with_for_update()
        .first()
    )

    if barbearia is None:
        raise HTTPException(
            status_code=404,
            detail="Barbearia não encontrada.",
        )

    ass = (
        db.query(models.AssinaturaSaaS)
        .filter(
            models.AssinaturaSaaS.barbearia_id == barbearia_id
        )
        .with_for_update()
        .first()
    )

    if ass is None:
        ass = models.AssinaturaSaaS(
            barbearia_id=barbearia_id,
            plano_id=plano.id,
            status="PENDENTE",
            status_pagamento="PENDENTE",
        )
        db.add(ass)
        db.flush()

    # Assinatura existente permanece exatamente como está.
    # O plano pretendido fica registrado em PagamentoSaaS.plano_id.
    return ass

def minha_assinatura_saas_service(db, usuario):
    bid = obter_barbearia_id(usuario)
    return db.query(models.AssinaturaSaaS).filter(models.AssinaturaSaaS.barbearia_id == bid).first()


def _criar_pagamento_base(
    db,
    ass,
    plano,
    tipo,
    valor,
    payer_email,
    installments,
    method_id,
    resposta,
    idem,
    ext,
    valor_original=None,
    valor_credito=0.0,
    resgate=None,
    commit=True,
):
    valor = round(float(valor or 0), 2)

    valor_original = round(
        float(
            valor_original
            if valor_original is not None
            else valor
        ),
        2,
    )

    valor_credito = round(
        float(valor_credito or 0),
        2,
    )

    p = models.PagamentoSaaS(
        assinatura_id=ass.id,
        barbearia_id=ass.barbearia_id,
        plano_id=plano.id,

        payment_id=(
            str(resposta.get("id"))
            if resposta.get("id") is not None
            else None
        ),

        external_reference=ext,
        idempotency_key=idem,

        tipo_pagamento=tipo,

        payment_method_id=(
            resposta.get("payment_method_id")
            or method_id
        ),

        payment_type_id=resposta.get(
            "payment_type_id"
        ),

        installments=installments,

        valor=valor,
        valor_original=valor_original,
        valor_credito=valor_credito,

        valor_parcela=round(
            valor / installments,
            2,
        ) if installments else valor,

        payer_email=payer_email,

        status=(
            resposta.get("status")
            or "pending"
        ),

        status_detail=resposta.get(
            "status_detail"
        ),

        processado=False,
    )

    td = (
        (
            resposta.get("point_of_interaction")
            or {}
        ).get("transaction_data")
        or {}
    )

    p.qr_code = td.get("qr_code")
    p.qr_code_base64 = td.get("qr_code_base64")
    p.ticket_url = td.get("ticket_url")

    db.add(p)
    db.flush()

    if resgate is not None:
        resgate.pagamento_saas_id = p.id
        resgate.assinatura_saas_id = ass.id

    # V474_C54D_R1_CONTROLE_TRANSACAO
    # Fluxos historicos usam commit=True.
    # Adequacao usa commit=False e deixa a transacao
    # sob controle do chamador.
    if commit:
        db.commit()
        db.refresh(p)

    return p



def _validar_plano_compativel_com_barbeiros(
    db,
    barbearia_id,
    plano,
):
    """Bloqueia checkout de plano menor que a equipe ativa da barbearia."""
    (
        db.query(models.Barbearia)
        .filter(models.Barbearia.id == barbearia_id)
        .with_for_update()
        .first()
    )

    barbeiros_ativos = (
        db.query(models.Barbeiro)
        .filter(
            models.Barbeiro.barbearia_id == barbearia_id,
            models.Barbeiro.ativo.is_(True),
        )
        .count()
    )

    limite = max(1, int(plano.limite_barbeiros or 1))

    if barbeiros_ativos > limite:
        raise HTTPException(
            status_code=409,
            detail={
                "codigo": "PLANO_INCOMPATIVEL_COM_EQUIPE",
                "mensagem": (
                    f"Sua barbearia possui {barbeiros_ativos} barbeiro(s) ativo(s). "
                    f"O plano {plano.nome} permite ate {limite}. "
                    "Escolha um plano compativel com sua equipe."
                ),
                "plano_id": plano.id,
                "plano_nome": plano.nome,
                "limite_barbeiros": limite,
                "barbeiros_ativos": barbeiros_ativos,
            },
        )



# ============================================================
# V4.7.4-C5.2
# CHECKOUT FINANCEIRO DE ADEQUACAO DE PLANO
# ============================================================

# V474_C54A_REFERENCIA_TENTATIVA
def _external_reference_adequacao(
    adequacao_id: int,
    tentativa: int = 1,
) -> str:
    """
    Referencia auditavel da cobranca de adequacao.

    Tentativa 1 preserva o formato historico:
        BARBSIST-ADEQ-123

    Tentativas posteriores:
        BARBSIST-ADEQ-123-T2
        BARBSIST-ADEQ-123-T3
    """
    aid = int(adequacao_id)
    tentativa = int(tentativa)

    if tentativa <= 1:
        return f"BARBSIST-ADEQ-{aid}"

    return f"BARBSIST-ADEQ-{aid}-T{tentativa}"


def _parse_external_reference_adequacao(
    external_reference: str,
):
    """
    Aceita referencias historicas e versionadas.

    Retorna:
        (adequacao_id, tentativa)

    Exemplos:
        BARBSIST-ADEQ-2     -> (2, 1)
        BARBSIST-ADEQ-2-T2  -> (2, 2)
    """
    referencia = str(external_reference or "").strip()

    prefixo = "BARBSIST-ADEQ-"

    if not referencia.startswith(prefixo):
        raise ValueError("REFERENCIA_NAO_E_ADEQUACAO")

    restante = referencia[len(prefixo):]

    partes = restante.split("-T", 1)

    try:
        adequacao_id = int(partes[0])
    except (TypeError, ValueError):
        raise ValueError("ADEQUACAO_ID_INVALIDO")

    if adequacao_id <= 0:
        raise ValueError("ADEQUACAO_ID_INVALIDO")

    tentativa = 1

    if len(partes) == 2:
        try:
            tentativa = int(partes[1])
        except (TypeError, ValueError):
            raise ValueError("TENTATIVA_INVALIDA")

        if tentativa < 2:
            raise ValueError("TENTATIVA_INVALIDA")

    return adequacao_id, tentativa


# V474_C54A_P2_RETRY_SEGURO
def _resolver_tentativa_pagamento_adequacao(
    db,
    *,
    adequacao_id: int,
    barbearia_id: int,
):
    """
    Resolve a tentativa vigente de pagamento da adequacao.

    Regras:
    - nenhuma tentativa: cria tentativa 1;
    - pending/in_process/approved: reutiliza;
    - processado=True: reutiliza;
    - tentativa terminal rejeitada/cancelada: libera N+1.

    O historico nunca e apagado nem sobrescrito.
    """
    prefixo = _external_reference_adequacao(
        adequacao_id
    )

    pagamentos = (
        db.query(models.PagamentoSaaS)
        .filter(
            models.PagamentoSaaS.barbearia_id
            == barbearia_id,
            models.PagamentoSaaS.external_reference.like(
                f"{prefixo}%"
            ),
        )
        .order_by(
            models.PagamentoSaaS.id.asc()
        )
        .all()
    )

    tentativas = []

    for pagamento in pagamentos:
        try:
            aid, tentativa = (
                _parse_external_reference_adequacao(
                    pagamento.external_reference
                )
            )
        except (TypeError, ValueError):
            continue

        if int(aid) != int(adequacao_id):
            continue

        tentativas.append(
            (tentativa, pagamento)
        )

    if not tentativas:
        return {
            "existente": None,
            "tentativa": 1,
            "external_reference": (
                _external_reference_adequacao(
                    adequacao_id,
                    1,
                )
            ),
        }

    tentativas.sort(
        key=lambda item: (
            item[0],
            item[1].id or 0,
        )
    )

    tentativa_atual, pagamento_atual = (
        tentativas[-1]
    )

    status = str(
        pagamento_atual.status or ""
    ).strip().lower()

    # Pagamento ja processado nunca pode gerar
    # nova cobranca.
    if bool(pagamento_atual.processado):
        return {
            "existente": pagamento_atual,
            "tentativa": tentativa_atual,
            "external_reference": (
                pagamento_atual.external_reference
            ),
        }

    # Estados que representam cobranca ainda valida,
    # em andamento ou aprovada.
    estados_reutilizaveis = {
        "pending",
        "in_process",
        "approved",
        "authorized",
    }

    if status in estados_reutilizaveis:
        return {
            "existente": pagamento_atual,
            "tentativa": tentativa_atual,
            "external_reference": (
                pagamento_atual.external_reference
            ),
        }

    # Somente estados terminais conhecidos podem
    # liberar uma nova tentativa.
    estados_retry = {
        "rejected",
        "cancelled",
        "canceled",
        "cancelled_by_user",
    }

    if status in estados_retry:
        proxima = tentativa_atual + 1

        return {
            "existente": None,
            "tentativa": proxima,
            "external_reference": (
                _external_reference_adequacao(
                    adequacao_id,
                    proxima,
                )
            ),
        }

    # Fail-closed para status desconhecido.
    return {
        "existente": pagamento_atual,
        "tentativa": tentativa_atual,
        "external_reference": (
            pagamento_atual.external_reference
        ),
    }


def _pagamento_adequacao_existente(
    db,
    *,
    adequacao_id: int,
    barbearia_id: int,
):
    """
    Compatibilidade com chamadas existentes.

    Retorna somente uma cobranca que deva ser
    reutilizada. Tentativa terminal rejeitada/cancelada
    retorna None e permite retry.
    """
    resolucao = (
        _resolver_tentativa_pagamento_adequacao(
            db,
            adequacao_id=adequacao_id,
            barbearia_id=barbearia_id,
        )
    )

    return resolucao["existente"]


def _preparar_checkout_adequacao(
    db,
    *,
    barbearia_id: int,
    forma_pagamento: str,
):
    """
    Recalcula a adequacao exclusivamente no backend.

    Nenhum valor recebido do frontend participa do calculo.
    """
    from services.adequacao_financeira_saas_service import (
        previa_financeira_adequacao_saas,
    )

    forma = (forma_pagamento or "").strip().upper()

    if forma not in {"PIX", "CARTAO"}:
        raise HTTPException(
            status_code=400,
            detail="Forma de pagamento invalida para adequacao.",
        )

    previa = previa_financeira_adequacao_saas(
        db,
        barbearia_id=barbearia_id,
        forma_pagamento=forma,
    )

    if (
        previa.get("status") != "OK"
        or not previa.get("pode_pagar")
    ):
        codigo = previa.get("status") or "ADEQUACAO_INDISPONIVEL"

        raise HTTPException(
            status_code=409,
            detail={
                "codigo": codigo,
                "mensagem": (
                    "A adequacao ainda nao pode ser cobrada. "
                    "Revise os dados do ciclo atual da assinatura."
                ),
                "previa": previa,
            },
        )

    adequacao_id = previa.get("adequacao_id")
    assinatura_id = previa.get("assinatura_id")
    plano_destino_id = previa.get("plano_destino_id")

    if not adequacao_id or not assinatura_id or not plano_destino_id:
        raise HTTPException(
            status_code=409,
            detail={
                "codigo": "PREVIA_INCOMPLETA",
                "mensagem": (
                    "A previa financeira nao possui todos os "
                    "identificadores necessarios para cobranca."
                ),
            },
        )

    valor = round(
        float(previa.get("valor_adequacao") or 0),
        2,
    )

    if valor <= 0:
        raise HTTPException(
            status_code=409,
            detail={
                "codigo": "VALOR_ADEQUACAO_INVALIDO",
                "mensagem": (
                    "O valor calculado da adequacao deve ser positivo."
                ),
            },
        )

    ass = (
        db.query(models.AssinaturaSaaS)
        .filter(
            models.AssinaturaSaaS.id == assinatura_id,
            models.AssinaturaSaaS.barbearia_id == barbearia_id,
        )
        .with_for_update()
        .first()
    )

    if ass is None:
        raise HTTPException(
            status_code=404,
            detail="Assinatura SaaS nao encontrada.",
        )

    adequacao = (
        db.query(models.AdequacaoPlanoSaaS)
        .filter(
            models.AdequacaoPlanoSaaS.id == adequacao_id,
            models.AdequacaoPlanoSaaS.barbearia_id == barbearia_id,
            models.AdequacaoPlanoSaaS.status == "PENDENTE",
        )
        .with_for_update()
        .first()
    )

    if adequacao is None:
        raise HTTPException(
            status_code=409,
            detail="Adequacao pendente nao encontrada.",
        )

    if adequacao.assinatura_id != ass.id:
        raise HTTPException(
            status_code=409,
            detail="Adequacao nao pertence a assinatura atual.",
        )

    if adequacao.plano_destino_id != plano_destino_id:
        raise HTTPException(
            status_code=409,
            detail="Plano destino da adequacao foi alterado.",
        )

    plano = (
        db.query(models.PlanoSaaS)
        .filter(
            models.PlanoSaaS.id == plano_destino_id,
            models.PlanoSaaS.ativo.is_(True),
        )
        .first()
    )

    if plano is None:
        raise HTTPException(
            status_code=404,
            detail="Plano destino da adequacao nao encontrado.",
        )

    resolucao_tentativa = (
        _resolver_tentativa_pagamento_adequacao(
            db,
            adequacao_id=adequacao.id,
            barbearia_id=barbearia_id,
        )
    )

    return {
        "previa": previa,
        "assinatura": ass,
        "adequacao": adequacao,
        "plano": plano,
        "valor": valor,
        "existente": (
            resolucao_tentativa["existente"]
        ),
        "tentativa": (
            resolucao_tentativa["tentativa"]
        ),
        "external_reference": (
            resolucao_tentativa[
                "external_reference"
            ]
        ),
    }


def checkout_pix_adequacao_saas_service(
    db,
    *,
    usuario,
    payer_email: str,
    base_url=None,
):
    bid = obter_barbearia_id(usuario)

    email = (payer_email or "").strip()

    if "@" not in email:
        raise HTTPException(
            status_code=400,
            detail="Informe um e-mail valido.",
        )

    ctx = _preparar_checkout_adequacao(
        db,
        barbearia_id=bid,
        forma_pagamento="PIX",
    )

    existente = ctx["existente"]

    if existente is not None:
        return existente

    ass = ctx["assinatura"]
    plano = ctx["plano"]
    valor = ctx["valor"]
    ext = ctx["external_reference"]

    # Idempotencia deterministica por adequacao e tentativa.
    tentativa = int(ctx.get("tentativa") or 1)

    idem = (
        f"BARBSIST-ADEQ-PIX-"
        f"{ctx['adequacao'].id}"
        f"-T{tentativa}"
    )

    payload = {
        "transaction_amount": valor,
        "description": (
            f"BarbSist - Adequacao para {plano.nome}"
        ),
        "payment_method_id": "pix",
        "payer": {
            "email": email,
        },
        "external_reference": ext,
        "notification_url": _webhook_url(base_url),
    }

    resp = _api(
        "POST",
        "/v1/payments",
        payload,
        {
            "X-Idempotency-Key": idem,
        },
    )

    return _criar_pagamento_base(
        db=db,
        ass=ass,
        plano=plano,
        tipo="PIX",
        valor=valor,
        payer_email=email,
        installments=1,
        method_id="pix",
        resposta=resp,
        idem=idem,
        ext=ext,
        valor_original=valor,
        valor_credito=0.0,
        commit=False,
    )


def checkout_cartao_adequacao_saas_service(
    db,
    *,
    usuario,
    token: str,
    installments: int,
    payment_method_id: str,
    payer_email: str,
    issuer_id=None,
    identification_type=None,
    identification_number=None,
    base_url=None,
):
    bid = obter_barbearia_id(usuario)

    email = (payer_email or "").strip()
    token = (token or "").strip()
    pmid = (payment_method_id or "").strip()

    if "@" not in email:
        raise HTTPException(
            status_code=400,
            detail="Informe um e-mail valido.",
        )

    if not token or not pmid:
        raise HTTPException(
            status_code=400,
            detail="Token e payment_method_id sao obrigatorios.",
        )

    ctx = _preparar_checkout_adequacao(
        db,
        barbearia_id=bid,
        forma_pagamento="CARTAO",
    )

    existente = ctx["existente"]

    if existente is not None:
        return existente

    ass = ctx["assinatura"]
    plano = ctx["plano"]
    valor = ctx["valor"]
    ext = ctx["external_reference"]

    parcelas = int(installments or 1)

    maxp = max(
        1,
        min(
            int(plano.max_parcelas_cartao or 1),
            12,
        ),
    )

    if parcelas < 1 or parcelas > maxp:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Este plano permite cartao em ate {maxp}x."
            ),
        )

    tentativa = int(ctx.get("tentativa") or 1)

    idem = (
        f"BARBSIST-ADEQ-CARTAO-"
        f"{ctx['adequacao'].id}"
        f"-T{tentativa}"
    )

    payload = {
        "transaction_amount": valor,
        "token": token,
        "description": (
            f"BarbSist - Adequacao para {plano.nome}"
        ),
        "installments": parcelas,
        "payment_method_id": pmid,
        "payer": {
            "email": email,
        },
        "external_reference": ext,
        "notification_url": _webhook_url(base_url),
    }

    if issuer_id is not None:
        payload["issuer_id"] = issuer_id

    if identification_type and identification_number:
        payload["payer"]["identification"] = {
            "type": identification_type,
            "number": identification_number,
        }

    resp = _api(
        "POST",
        "/v1/payments",
        payload,
        {
            "X-Idempotency-Key": idem,
        },
    )

    return _criar_pagamento_base(
        db=db,
        ass=ass,
        plano=plano,
        tipo="CARTAO",
        valor=valor,
        payer_email=email,
        installments=parcelas,
        method_id=pmid,
        resposta=resp,
        idem=idem,
        ext=ext,
        valor_original=valor,
        valor_credito=0.0,
        commit=False,
    )


def checkout_pix_saas_service(
    db,
    dados,
    usuario,
    base_url=None,
):
    bid = obter_barbearia_id(usuario)

    plano = _obter_plano(
        db,
        dados.plano_id,
    )

    _validar_plano_compativel_com_barbeiros(
        db=db,
        barbearia_id=bid,
        plano=plano,
    )

    email = (
        dados.payer_email
        or ""
    ).strip()

    if "@" not in email:
        raise HTTPException(
            status_code=400,
            detail="Informe um e-mail valido.",
        )

    ass = _obter_ou_criar_assinatura(
        db,
        bid,
        plano,
    )

    valor_original = _valor_checkout_saas_com_db(
        db,
        ass,
        plano,
        "pix",
    )

    credito = _preparar_credito_mensalidade_saas(
        db=db,
        assinatura=ass,
        plano=plano,
        valor_original=valor_original,
    )

    valor_credito = round(
        float(
            credito["valor_credito"]
            or 0
        ),
        2,
    )

    valor = round(
        float(
            credito["valor_cobrar"]
            or 0
        ),
        2,
    )

    resgate = credito["resgate"]

    idem = str(uuid.uuid4())

    ext = (
        f"BARBSIST-SAAS-B{bid}-A{ass.id}-"
        f"{uuid.uuid4().hex[:12]}"
    )

    # Quitacao integral por credito.
    # Nao envia cobranca de valor zero ao Mercado Pago.
    if valor <= 0:
        resposta = {
            "id": None,
            "status": "approved",
            "status_detail": "paid_by_credit",
            "payment_method_id": "credito_barbsist",
            "payment_type_id": "account_money",
        }

        pagamento = _criar_pagamento_base(
            db=db,
            ass=ass,
            plano=plano,
            # A forma comercial continua sendo PIX.
            # valor_credito registra que a carteira quitou
            # integralmente o valor, sem chamada ao Mercado Pago.
            tipo="PIX",
            valor=0.0,
            payer_email=email,
            installments=1,
            method_id="credito_barbsist",
            resposta=resposta,
            idem=idem,
            ext=ext,
            valor_original=valor_original,
            valor_credito=valor_credito,
            resgate=resgate,
        )

        # Nao existe webhook do Mercado Pago neste fluxo.
        # Portanto a quitacao precisa ser concluida localmente.
        if resgate is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Quitacao integral por credito sem "
                    "reserva de credito associada."
                ),
            )

        aplicar_resgate_creditos_service(
            db=db,
            resgate_id=resgate.id,
            assinatura_saas_id=ass.id,
            pagamento_saas_id=pagamento.id,
        )

        # Recarrega os objetos porque o service de resgate
        # executa commit proprio.
        db.refresh(pagamento)
        db.refresh(ass)

        _ativar_assinatura_por_pagamento(
            db=db,
            pagamento=pagamento,
            mp_payment=resposta,
        )

        db.commit()
        db.refresh(pagamento)

        return pagamento

    payload = {
        "transaction_amount": valor,
        "description": f"BarbSist - {plano.nome}",
        "payment_method_id": "pix",
        "payer": {
            "email": email,
        },
        "external_reference": ext,
        "notification_url": _webhook_url(
            base_url
        ),
    }

    try:
        resp = _api(
            "POST",
            "/v1/payments",
            payload,
            {
                "X-Idempotency-Key": idem,
            },
        )

    except Exception:
        # Libera a reserva automatica se a criacao
        # da cobranca falhar antes do PagamentoSaaS existir.
        if (
            resgate is not None
            and resgate.status == "APROVADO"
        ):
            resgate.status = "CANCELADO"
            resgate.observacao = (
                "Reserva cancelada por falha "
                "na criacao da cobranca PIX."
            )

        db.commit()
        raise

    return _criar_pagamento_base(
        db=db,
        ass=ass,
        plano=plano,
        tipo="PIX",
        valor=valor,
        payer_email=email,
        installments=1,
        method_id="pix",
        resposta=resp,
        idem=idem,
        ext=ext,
        valor_original=valor_original,
        valor_credito=valor_credito,
        resgate=resgate,
    )


def checkout_cartao_saas_service(db, dados, usuario, base_url=None):
    bid = obter_barbearia_id(usuario)
    plano = _obter_plano(db, dados.plano_id)
    _validar_plano_compativel_com_barbeiros(
        db=db,
        barbearia_id=bid,
        plano=plano,
    )
    parcelas = int(dados.installments or 1)
    maxp = max(1, min(int(plano.max_parcelas_cartao or 1), 12))
    if parcelas < 1 or parcelas > maxp: raise HTTPException(status_code=400, detail=f"Este plano permite cartão em até {maxp}x.")
    email=(dados.payer_email or "").strip(); token=(dados.token or "").strip(); pmid=(dados.payment_method_id or "").strip()
    if "@" not in email: raise HTTPException(status_code=400, detail="Informe um e-mail válido.")
    if not token or not pmid: raise HTTPException(status_code=400, detail="Token e payment_method_id são obrigatórios.")
    ass = _obter_ou_criar_assinatura(db, bid, plano)
    valor = _valor_checkout_saas_com_db(
        db,
        ass,
        plano,
        "cartao",
    )
    idem=str(uuid.uuid4()); ext=f"BARBSIST-SAAS-B{bid}-A{ass.id}-{uuid.uuid4().hex[:12]}"
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


def _ativar_assinatura_por_pagamento(
    db,
    pagamento,
    mp_payment,
):
    ass = (
        db.query(models.AssinaturaSaaS)
        .filter(
            models.AssinaturaSaaS.id == pagamento.assinatura_id,
            models.AssinaturaSaaS.barbearia_id
            == pagamento.barbearia_id,
        )
        .with_for_update()
        .first()
    )

    plano = (
        db.query(models.PlanoSaaS)
        .filter(
            models.PlanoSaaS.id == pagamento.plano_id,
            models.PlanoSaaS.ativo.is_(True),
        )
        .first()
    )

    if not ass or not plano:
        raise HTTPException(
            status_code=404,
            detail="Assinatura SaaS/plano não encontrado.",
        )

    agora = datetime.now()

    # Consolida a condição Fundador somente após pagamento aprovado.
    # Gerar checkout promocional não consome vaga.
    if ass.fundador_posicao is None:
        precos_fundador = _precos_fundador_para_plano(plano)

        if precos_fundador:
            tipo_pagamento = (
                pagamento.tipo_pagamento or ""
            ).strip().lower()

            valor_promocional = None

            if tipo_pagamento == "pix":
                valor_promocional = round(
                    float(precos_fundador["pix"]),
                    2,
                )

            elif tipo_pagamento in {"cartao", "cartão"}:
                valor_promocional = round(
                    float(precos_fundador["cartao"]),
                    2,
                )

            # O preco comercial precisa ser considerado antes
            # do abatimento de creditos BarbSist.
            # Ex.: mensalidade Fundador R$ 19,90 integralmente
            # quitada por credito possui pagamento.valor == 0,
            # mas valor_original == 19,90.
            valor_pago = round(
                float(
                    pagamento.valor_original
                    if (
                        float(pagamento.valor_credito or 0) > 0
                        and pagamento.valor_original is not None
                    )
                    else pagamento.valor
                    or 0
                ),
                2,
            )

            if (
                valor_promocional is not None
                and valor_pago == valor_promocional
                and _tem_vaga_fundador(db)
            ):
                _garantir_promocao_fundador(
                    db=db,
                    assinatura=ass,
                    plano=plano,
                )

    # Se a assinatura está vigente, a renovação/upgrade entra após
    # o período já pago; caso contrário começa imediatamente.
    base = (
        ass.data_fim
        if (
            ass.data_fim
            and ass.data_fim > agora
            and ass.status == "ATIVA"
        )
        else agora
    )

    fim = _add_months(base, plano.periodo_meses)

    # O plano é efetivamente trocado somente neste ponto.
    ass.plano_id = plano.id
    ass.status = "ATIVA"
    ass.status_pagamento = "PAGO"
    ass.forma_pagamento = pagamento.tipo_pagamento
    ass.data_inicio = ass.data_inicio or agora
    ass.data_fim = fim
    ass.data_proximo_vencimento = fim
    ass.liberado_manual = False
    ass.motivo_bloqueio = None

    # V474_C42B_GRAVAR_CICLO_PAGAMENTO
    #
    # O pagamento normal financia exatamente o intervalo
    # calculado nesta ativacao/renovacao.
    #
    # Primeira contratacao:
    #   base = agora
    #
    # Renovacao:
    #   base = vencimento anterior
    #
    # Adequacao de plano nao passa por esta funcao e,
    # portanto, nao cria nem estende ciclo financeiro.
    pagamento.ciclo_inicio = base
    pagamento.ciclo_fim = fim

    pagamento.processado = True
    pagamento.processado_em = agora

def processar_webhook_saas_service(
    db,
    data_id,
    payload,
    x_signature,
    x_request_id,
):
    _, _, secret = _mp_env()

    if not secret:
        raise HTTPException(
            status_code=503,
            detail="BARBSIST_MP_WEBHOOK_SECRET não configurado.",
        )

    if not _validar_assinatura_webhook(
        x_signature,
        x_request_id,
        data_id,
        secret,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Assinatura do Webhook inválida.",
        )

    tipo = (payload.get("type") or "").lower()
    pid = data_id or str(
        (payload.get("data") or {}).get("id") or ""
    )

    if tipo and tipo != "payment":
        return {"status": "ignorado", "tipo": tipo}

    if not pid:
        return {"status": "ignorado", "motivo": "sem payment id"}

    # Consulta o Mercado Pago antes de confiar no estado recebido.
    mp = _api(
        "GET",
        f"/v1/payments/{pid}",
    )

    ext = mp.get("external_reference")

    pag = (
        db.query(models.PagamentoSaaS)
        .filter(
            (
                models.PagamentoSaaS.payment_id == str(pid)
            )
            | (
                models.PagamentoSaaS.external_reference == ext
            )
        )
        .with_for_update()
        .first()
    )

    if not pag:
        return {
            "status": "ignorado",
            "motivo": (
                "pagamento não pertence à cobrança SaaS BarbSist"
            ),
        }

    if ext and pag.external_reference != ext:
        raise HTTPException(
            status_code=409,
            detail="external_reference divergente do pagamento SaaS.",
        )

    pag.payment_id = str(pid)
    pag.status = mp.get("status") or pag.status
    pag.status_detail = (
        mp.get("status_detail") or pag.status_detail
    )
    pag.payment_method_id = (
        mp.get("payment_method_id")
        or pag.payment_method_id
    )
    pag.payment_type_id = (
        mp.get("payment_type_id")
        or pag.payment_type_id
    )
    pag.installments = int(
        mp.get("installments")
        or pag.installments
        or 1
    )

    if pag.processado:
        db.commit()
        return {"status": "ja_processado"}

    if pag.status != "approved":
        # Status ainda aguardando pagamento mantem o
        # credito reservado.
        status_terminal_credito = {
            "rejected",
            "cancelled",
            "refunded",
            "charged_back",
        }

        valor_credito = round(
            float(
                getattr(
                    pag,
                    "valor_credito",
                    0,
                )
                or 0
            ),
            2,
        )

        if (
            valor_credito > 0
            and pag.status in status_terminal_credito
        ):
            resgate = (
                db.query(ResgateCreditoBarbearia)
                .filter(
                    ResgateCreditoBarbearia.pagamento_saas_id
                    == pag.id,
                    ResgateCreditoBarbearia.assinatura_saas_id
                    == pag.assinatura_id,
                    ResgateCreditoBarbearia.tipo_aplicacao
                    == "MENSALIDADE_AUTOMATICA",
                )
                .order_by(
                    ResgateCreditoBarbearia.id.desc()
                )
                .first()
            )

            if resgate:
                if resgate.status in {
                    "SOLICITADO",
                    "APROVADO",
                }:
                    cancelar_reserva_creditos_service(
                        db=db,
                        resgate_id=resgate.id,
                        motivo=(
                            "Pagamento Mercado Pago "
                            f"finalizado como {pag.status}."
                        ),
                    )

                    # O service executa commit.
                    db.refresh(pag)

                elif resgate.status not in {
                    "CANCELADO",
                    "APLICADO",
                }:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "Reserva de credito em estado "
                            f"inesperado: {resgate.status}."
                        ),
                    )

        db.commit()
        return {"status": pag.status}

    valor_mp = round(
        float(mp.get("transaction_amount") or 0),
        2,
    )

    if valor_mp != round(float(pag.valor), 2):
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Valor aprovado diverge da cobrança SaaS.",
        )

    # Se esta cobranca utilizou credito BarbSist,
    # o credito ficou apenas RESERVADO durante o checkout.
    # Somente apos a confirmacao do Mercado Pago ele pode
    # ser definitivamente consumido.
    valor_credito = round(
        float(getattr(pag, "valor_credito", 0) or 0),
        2,
    )

    if valor_credito > 0:
        resgate = (
            db.query(ResgateCreditoBarbearia)
            .filter(
                ResgateCreditoBarbearia.pagamento_saas_id
                == pag.id,
                ResgateCreditoBarbearia.assinatura_saas_id
                == pag.assinatura_id,
                ResgateCreditoBarbearia.tipo_aplicacao
                == "MENSALIDADE_AUTOMATICA",
            )
            .order_by(
                ResgateCreditoBarbearia.id.desc()
            )
            .first()
        )

        if resgate is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Pagamento aprovado possui credito "
                    "BarbSist sem reserva associada."
                ),
            )

        if resgate.status == "APROVADO":
            aplicar_resgate_creditos_service(
                db=db,
                resgate_id=resgate.id,
                assinatura_saas_id=pag.assinatura_id,
                pagamento_saas_id=pag.id,
            )

            # O service de resgate executa commit proprio.
            # Recarrega o pagamento antes de prosseguir.
            db.refresh(pag)

        elif resgate.status != "APLICADO":
            raise HTTPException(
                status_code=409,
                detail=(
                    "Reserva de credito da mensalidade "
                    f"esta em estado invalido: {resgate.status}."
                ),
            )

    # V474_C53_WEBHOOK_ADEQUACAO
    #
    # Pagamentos de adequacao nao podem entrar na ativacao/renovacao
    # normal, pois devem preservar integralmente o ciclo vigente.
    referencia_pagamento = str(
        pag.external_reference or ""
    ).strip()

    if referencia_pagamento.startswith("BARBSIST-ADEQ-"):
        try:
            (
                adequacao_id,
                _tentativa_adequacao,
            ) = _parse_external_reference_adequacao(
                referencia_pagamento
            )
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Referencia de pagamento de adequacao invalida."
                ),
            )

        from services.adequacao_plano_saas_service import (
            finalizar_adequacao_paga_saas,
        )

        finalizar_adequacao_paga_saas(
            db,
            adequacao_id=adequacao_id,
            pagamento_id=pag.id,
        )

    else:
        _ativar_assinatura_por_pagamento(
            db,
            pag,
            mp,
        )

    db.commit()

    # O beneficio do parceiro somente nasce depois que:
    # 1. o Mercado Pago confirmou approved;
    # 2. o valor recebido foi validado;
    # 3. eventual credito BarbSist foi aplicado;
    # 4. a assinatura foi ativada/renovada.
    #
    # A base do beneficio permanece pagamento.valor,
    # isto e, somente dinheiro efetivamente recebido.
    #
    # V474_C54B_R1_CLASSIFICADOR_SEGURO
    def _eh_pagamento_adequacao(
        external_reference,
    ):
        try:
            return (
                _parse_external_reference_adequacao(
                    external_reference
                )
                is not None
            )
        except (TypeError, ValueError):
            return False

    # V474_C54B_ADEQUACAO_SEM_BENEFICIO_PARCEIRO
    #
    # Pagamento proporcional de adequacao de capacidade
    # nao representa nova mensalidade/renovacao e, portanto,
    # nao gera um segundo beneficio de parceiro.
    eh_pagamento_adequacao = (
        _eh_pagamento_adequacao(
            pag.external_reference
        )
    )

    if (
        not eh_pagamento_adequacao
        and round(float(pag.valor or 0), 2) > 0
    ):
        processar_beneficio_pagamento_service(
            db=db,
            pagamento_saas_id=pag.id,
        )

    return {
        "status": "approved",
        "processado": True,
    }

def listar_assinaturas_admin_service(db):
    return db.query(models.AssinaturaSaaS).order_by(models.AssinaturaSaaS.id.desc()).all()


def conceder_teste_saas_service(
    db,
    barbearia_id,
    dados,
    usuario_logado,
):
    """Cria ou atualiza o teste individual de uma barbearia."""
    barbearia = (
        db.query(models.Barbearia)
        .filter(models.Barbearia.id == barbearia_id)
        .with_for_update()
        .first()
    )
    if not barbearia:
        raise HTTPException(status_code=404, detail="Barbearia não encontrada.")

    plano = (
        db.query(models.PlanoSaaS)
        .filter(
            models.PlanoSaaS.id == dados.plano_id,
            models.PlanoSaaS.ativo.is_(True),
        )
        .first()
    )
    if not plano:
        raise HTTPException(status_code=404, detail="Plano SaaS ativo não encontrado.")

    observacao = (dados.observacao or "").strip()
    if len(observacao) < 3:
        raise HTTPException(status_code=400, detail="Informe a justificativa da concessão.")

    ass = (
        db.query(models.AssinaturaSaaS)
        .filter(models.AssinaturaSaaS.barbearia_id == barbearia_id)
        .with_for_update()
        .first()
    )
    agora = datetime.now()
    status_anterior = ass.status if ass else None

    assinatura_paga_ativa = bool(
        ass
        and (ass.status or "").upper() == "ATIVA"
        and (ass.status_pagamento or "").upper() == "PAGO"
    )

    teste_anterior = (
        db.query(models.AssinaturaSaaSAuditoria.id)
        .filter(
            models.AssinaturaSaaSAuditoria.barbearia_id
            == barbearia_id,
            models.AssinaturaSaaSAuditoria.acao
            == "CONCESSAO_TESTE",
        )
        .first()
        is not None
    )

    if ass and (
        (ass.status_pagamento or "").upper() == "TESTE_GRATUITO"
        or (ass.forma_pagamento or "").upper() == "TESTE"
    ):
        teste_anterior = True

    frase_exigida = None
    codigo_bloqueio = None
    mensagem_bloqueio = None

    if assinatura_paga_ativa:
        codigo_bloqueio = "ASSINATURA_PAGA_ATIVA"
        frase_exigida = "SUBSTITUIR ASSINATURA PAGA"
        mensagem_bloqueio = (
            "Esta barbearia possui uma assinatura paga ativa. "
            "A concessão do teste substituirá a vigência e a "
            "situação financeira atuais."
        )
    elif teste_anterior:
        codigo_bloqueio = "TESTE_JA_CONCEDIDO"
        frase_exigida = "CONCEDER NOVO TESTE"
        mensagem_bloqueio = (
            "Esta barbearia já recebeu um período de teste. "
            "Uma nova concessão é uma exceção administrativa."
        )

    confirmacao = (getattr(dados, "confirmacao", None) or "").strip()
    excecao_autorizada = bool(
        getattr(dados, "autorizar_excecao", False)
    )

    if frase_exigida and (
        not excecao_autorizada
        or confirmacao != frase_exigida
    ):
        detalhe_assinatura = None
        if ass:
            detalhe_assinatura = {
                "id": ass.id,
                "plano_id": ass.plano_id,
                "status": ass.status,
                "status_pagamento": ass.status_pagamento,
                "forma_pagamento": ass.forma_pagamento,
                "data_inicio": (
                    ass.data_inicio.isoformat()
                    if ass.data_inicio
                    else None
                ),
                "data_fim": (
                    ass.data_fim.isoformat()
                    if ass.data_fim
                    else None
                ),
                "data_proximo_vencimento": (
                    ass.data_proximo_vencimento.isoformat()
                    if ass.data_proximo_vencimento
                    else None
                ),
            }

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "codigo": codigo_bloqueio,
                "mensagem": mensagem_bloqueio,
                "confirmacao_exigida": frase_exigida,
                "assinatura_atual": detalhe_assinatura,
            },
        )

    estado_anterior = None
    if ass:
        estado_anterior = {
            "plano_id": ass.plano_id,
            "status": ass.status,
            "status_pagamento": ass.status_pagamento,
            "forma_pagamento": ass.forma_pagamento,
            "data_inicio": (
                ass.data_inicio.isoformat()
                if ass.data_inicio
                else None
            ),
            "data_fim": (
                ass.data_fim.isoformat()
                if ass.data_fim
                else None
            ),
            "data_proximo_vencimento": (
                ass.data_proximo_vencimento.isoformat()
                if ass.data_proximo_vencimento
                else None
            ),
        }
    if ass is None:
        ass = models.AssinaturaSaaS(
            barbearia_id=barbearia_id,
            plano_id=plano.id,
            status="PENDENTE",
            status_pagamento="PENDENTE",
        )
        db.add(ass)
        db.flush()

    ass.plano_id = plano.id
    ass.status = "ATIVA"
    ass.status_pagamento = "TESTE_GRATUITO"
    ass.forma_pagamento = "TESTE"
    ass.data_inicio = agora
    ass.data_fim = agora + timedelta(days=int(dados.dias))
    ass.data_proximo_vencimento = ass.data_fim
    ass.liberado_manual = True
    ass.motivo_bloqueio = None

    tipo_concessao = (
        "EXCECAO_" + codigo_bloqueio
        if codigo_bloqueio
        else "PRIMEIRO_TESTE"
    )
    _registrar_auditoria_assinatura_saas(
        db,
        ass,
        usuario_logado,
        "CONCESSAO_TESTE",
        (
            f"{observacao} | tipo={tipo_concessao} "
            f"| estado_anterior={estado_anterior} "
            f"| plano_novo_id={plano.id} "
            f"| dias={int(dados.dias)} "
            f"| inicio={ass.data_inicio.isoformat()} "
            f"| fim={ass.data_fim.isoformat()}"
        ),
        status_anterior,
    )
    db.commit()
    db.refresh(ass)
    return ass


def listar_pagamentos_admin_service(db):
    return db.query(models.PagamentoSaaS).order_by(models.PagamentoSaaS.id.desc()).limit(500).all()


def _registrar_auditoria_assinatura_saas(
    db,
    assinatura,
    usuario_logado,
    acao,
    observacao,
    status_anterior,
):
    if usuario_logado is None or getattr(
        usuario_logado,
        "id",
        None,
    ) is None:
        raise HTTPException(
            status_code=403,
            detail="Superadministrador não identificado.",
        )

    registro = models.AssinaturaSaaSAuditoria(
        assinatura_id=assinatura.id,
        barbearia_id=assinatura.barbearia_id,
        usuario_id=usuario_logado.id,
        acao=acao,
        observacao=(observacao or "").strip() or None,
        status_anterior=status_anterior,
        status_novo=assinatura.status,
    )
    db.add(registro)


def liberar_assinatura_manual_service(
    db,
    assinatura_id,
    dados,
    usuario_logado,
):
    ass = (
        db.query(models.AssinaturaSaaS)
        .filter(models.AssinaturaSaaS.id == assinatura_id)
        .with_for_update()
        .first()
    )

    if not ass:
        raise HTTPException(
            status_code=404,
            detail="Assinatura SaaS não encontrada.",
        )

    status_anterior = ass.status
    agora = datetime.now()

    ass.status = "ATIVA"
    ass.status_pagamento = "LIBERADO_MANUAL"
    ass.forma_pagamento = "MANUAL"
    ass.data_inicio = ass.data_inicio or agora

    from datetime import timedelta

    ass.data_fim = agora + timedelta(days=int(dados.dias))
    ass.data_proximo_vencimento = ass.data_fim
    ass.liberado_manual = True
    ass.motivo_bloqueio = None

    _registrar_auditoria_assinatura_saas(
        db,
        ass,
        usuario_logado,
        "LIBERACAO_MANUAL",
        getattr(dados, "observacao", None),
        status_anterior,
    )

    db.commit()
    db.refresh(ass)
    return ass


def bloquear_assinatura_service(
    db,
    assinatura_id,
    dados,
    usuario_logado,
):
    ass = (
        db.query(models.AssinaturaSaaS)
        .filter(models.AssinaturaSaaS.id == assinatura_id)
        .with_for_update()
        .first()
    )

    if not ass:
        raise HTTPException(
            status_code=404,
            detail="Assinatura SaaS não encontrada.",
        )

    status_anterior = ass.status
    motivo = (
        (dados.motivo or "").strip()
        or "Bloqueio administrativo"
    )

    ass.status = "BLOQUEADA"
    ass.status_pagamento = "BLOQUEADA"
    ass.motivo_bloqueio = motivo

    _registrar_auditoria_assinatura_saas(
        db,
        ass,
        usuario_logado,
        "BLOQUEIO",
        motivo,
        status_anterior,
    )

    db.commit()
    db.refresh(ass)
    return ass


def listar_auditoria_assinaturas_saas_service(
    db,
    assinatura_id=None,
):
    query = db.query(models.AssinaturaSaaSAuditoria)

    if assinatura_id is not None:
        query = query.filter(
            models.AssinaturaSaaSAuditoria.assinatura_id
            == assinatura_id
        )

    return (
        query.order_by(
            models.AssinaturaSaaSAuditoria.id.desc()
        )
        .limit(500)
        .all()
    )

