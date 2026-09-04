from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models
from parceiros.models_parceiros import (
    Parceiro,
    Indicacao,
    ComissaoParceiro,
    CreditoBarbearia,
    ResgateCreditoBarbearia,
    ResgateCreditoItem,
)


STATUS_PAGAMENTO_SAAS_APROVADO = "approved"


def _normalizar_codigo_ref(codigo: str) -> str:
    codigo = (codigo or "").strip().upper()

    if not codigo:
        raise HTTPException(
            status_code=400,
            detail="Código de indicação obrigatório.",
        )

    return codigo


def _calcular_beneficio(parceiro: Parceiro, valor_base: float) -> float:
    valor_base = round(float(valor_base or 0), 2)

    if valor_base <= 0:
        raise HTTPException(
            status_code=400,
            detail="Valor base do pagamento deve ser maior que zero.",
        )

    if parceiro.regra_beneficio == "PERCENTUAL":
        percentual = float(parceiro.percentual_beneficio or 0)

        if percentual <= 0 or percentual > 100:
            raise HTTPException(
                status_code=400,
                detail="Percentual de benefício inválido.",
            )

        return round(valor_base * percentual / 100, 2)

    if parceiro.regra_beneficio == "VALOR_FIXO":
        valor = float(parceiro.valor_fixo_beneficio or 0)

        if valor <= 0:
            raise HTTPException(
                status_code=400,
                detail="Valor fixo do benefício inválido.",
            )

        return round(valor, 2)

    raise HTTPException(
        status_code=400,
        detail="Regra de benefício inválida.",
    )


def criar_parceiro_service(db: Session, dados):
    codigo_ref = _normalizar_codigo_ref(dados.codigo_ref)
    email = (dados.email or "").strip().lower()

    if db.query(Parceiro).filter(Parceiro.codigo_ref == codigo_ref).first():
        raise HTTPException(
            status_code=409,
            detail="Código de indicação já cadastrado.",
        )

    if db.query(Parceiro).filter(Parceiro.email == email).first():
        raise HTTPException(
            status_code=409,
            detail="E-mail já cadastrado para outro parceiro.",
        )

    if dados.tipo == "BARBEARIA":
        barbearia = (
            db.query(models.Barbearia)
            .filter(models.Barbearia.id == dados.barbearia_id)
            .first()
        )

        if not barbearia:
            raise HTTPException(
                status_code=404,
                detail="Barbearia parceira não encontrada.",
            )

    parceiro = Parceiro(
        tipo=dados.tipo,
        nome=dados.nome.strip(),
        email=email,
        telefone=(dados.telefone or "").strip() or None,
        barbearia_id=dados.barbearia_id,
        codigo_ref=codigo_ref,
        tipo_beneficio=dados.tipo_beneficio,
        regra_beneficio=dados.regra_beneficio,
        percentual_beneficio=dados.percentual_beneficio,
        valor_fixo_beneficio=dados.valor_fixo_beneficio,
        ativo=dados.ativo,
        observacao=dados.observacao,
    )

    db.add(parceiro)

    try:
        db.commit()
        db.refresh(parceiro)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Parceiro já cadastrado.",
        )

    return parceiro


def listar_parceiros_service(db: Session, incluir_inativos: bool = True):
    query = db.query(Parceiro)

    if not incluir_inativos:
        query = query.filter(Parceiro.ativo.is_(True))

    return query.order_by(Parceiro.id.desc()).all()


def obter_parceiro_service(db: Session, parceiro_id: int):
    parceiro = (
        db.query(Parceiro)
        .filter(Parceiro.id == parceiro_id)
        .first()
    )

    if not parceiro:
        raise HTTPException(
            status_code=404,
            detail="Parceiro não encontrado.",
        )

    return parceiro


def registrar_indicacao_service(
    db: Session,
    codigo_ref: str,
    barbearia_indicada_id: int,
):
    codigo_ref = _normalizar_codigo_ref(codigo_ref)

    parceiro = (
        db.query(Parceiro)
        .filter(
            Parceiro.codigo_ref == codigo_ref,
            Parceiro.ativo.is_(True),
        )
        .first()
    )

    if not parceiro:
        raise HTTPException(
            status_code=404,
            detail="Código de indicação inválido ou inativo.",
        )

    barbearia = (
        db.query(models.Barbearia)
        .filter(models.Barbearia.id == barbearia_indicada_id)
        .first()
    )

    if not barbearia:
        raise HTTPException(
            status_code=404,
            detail="Barbearia indicada não encontrada.",
        )

    existente = (
        db.query(Indicacao)
        .filter(Indicacao.barbearia_indicada_id == barbearia_indicada_id)
        .first()
    )

    if existente:
        raise HTTPException(
            status_code=409,
            detail="Esta barbearia já possui uma indicação registrada.",
        )

    if (
        parceiro.tipo == "BARBEARIA"
        and parceiro.barbearia_id == barbearia_indicada_id
    ):
        raise HTTPException(
            status_code=400,
            detail="A barbearia não pode indicar a si própria.",
        )

    indicacao = Indicacao(
        parceiro_id=parceiro.id,
        codigo_ref=parceiro.codigo_ref,
        barbearia_indicada_id=barbearia_indicada_id,
        status="CADASTRADA",
    )

    db.add(indicacao)

    try:
        db.commit()
        db.refresh(indicacao)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Indicação já registrada.",
        )

    return indicacao


def processar_beneficio_pagamento_service(
    db: Session,
    pagamento_saas_id: int,
):
    pagamento = (
        db.query(models.PagamentoSaaS)
        .filter(models.PagamentoSaaS.id == pagamento_saas_id)
        .first()
    )

    if not pagamento:
        raise HTTPException(
            status_code=404,
            detail="Pagamento SaaS não encontrado.",
        )

    if pagamento.status != STATUS_PAGAMENTO_SAAS_APROVADO:
        raise HTTPException(
            status_code=400,
            detail=(
                "Benefício somente pode ser gerado para "
                "PagamentoSaaS com status approved."
            ),
        )

    indicacao = (
        db.query(Indicacao)
        .filter(Indicacao.barbearia_indicada_id == pagamento.barbearia_id)
        .first()
    )

    if not indicacao:
        return {
            "gerado": False,
            "motivo": "Barbearia sem indicação registrada.",
        }

    parceiro = obter_parceiro_service(db, indicacao.parceiro_id)

    if not parceiro.ativo:
        return {
            "gerado": False,
            "motivo": "Parceiro inativo.",
        }

    # Registra qual assinatura efetivamente converteu a indicação.
    if indicacao.assinatura_saas_id is None:
        indicacao.assinatura_saas_id = pagamento.assinatura_id

    valor_base = round(float(pagamento.valor or 0), 2)
    valor_beneficio = _calcular_beneficio(parceiro, valor_base)

    if parceiro.tipo_beneficio == "COMISSAO":
        existente = (
            db.query(ComissaoParceiro)
            .filter(
                ComissaoParceiro.indicacao_id == indicacao.id,
                ComissaoParceiro.pagamento_saas_id == pagamento.id,
            )
            .first()
        )

        if existente:
            return {
                "gerado": False,
                "motivo": "Comissão já gerada para este pagamento.",
                "tipo": "COMISSAO",
                "id": existente.id,
            }

        beneficio = ComissaoParceiro(
            parceiro_id=parceiro.id,
            indicacao_id=indicacao.id,
            pagamento_saas_id=pagamento.id,
            valor_base=valor_base,
            percentual=(
                parceiro.percentual_beneficio
                if parceiro.regra_beneficio == "PERCENTUAL"
                else None
            ),
            valor_comissao=valor_beneficio,
            status="PENDENTE",
        )

        tipo = "COMISSAO"

    elif parceiro.tipo_beneficio == "CREDITO":
        if parceiro.tipo != "BARBEARIA" or not parceiro.barbearia_id:
            raise HTTPException(
                status_code=400,
                detail="Crédito exige parceiro vinculado a uma barbearia.",
            )

        existente = (
            db.query(CreditoBarbearia)
            .filter(
                CreditoBarbearia.indicacao_id == indicacao.id,
                CreditoBarbearia.pagamento_saas_id == pagamento.id,
            )
            .first()
        )

        if existente:
            return {
                "gerado": False,
                "motivo": "Crédito já gerado para este pagamento.",
                "tipo": "CREDITO",
                "id": existente.id,
            }

        beneficio = CreditoBarbearia(
            parceiro_id=parceiro.id,
            barbearia_parceira_id=parceiro.barbearia_id,
            indicacao_id=indicacao.id,
            pagamento_saas_id=pagamento.id,
            valor_base=valor_base,
            percentual=(
                parceiro.percentual_beneficio
                if parceiro.regra_beneficio == "PERCENTUAL"
                else None
            ),
            valor_credito=valor_beneficio,
            status="DISPONIVEL",
        )

        tipo = "CREDITO"

    else:
        raise HTTPException(
            status_code=400,
            detail="Tipo de benefício inválido.",
        )

    indicacao.status = "CONVERTIDA"

    if indicacao.data_conversao is None:
        indicacao.data_conversao = datetime.now()

    db.add(beneficio)

    try:
        db.commit()
        db.refresh(beneficio)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Benefício já processado para este pagamento.",
        )

    return {
        "gerado": True,
        "tipo": tipo,
        "id": beneficio.id,
        "valor": valor_beneficio,
        "parceiro_id": parceiro.id,
        "indicacao_id": indicacao.id,
        "pagamento_saas_id": pagamento.id,
    }



def obter_portal_parceiro_service(
    db: Session,
    parceiro_id: int,
):
    parceiro = obter_parceiro_service(db, parceiro_id)

    indicacoes = (
        db.query(Indicacao)
        .filter(Indicacao.parceiro_id == parceiro_id)
        .order_by(Indicacao.id.desc())
        .all()
    )

    comissoes = (
        db.query(ComissaoParceiro)
        .filter(ComissaoParceiro.parceiro_id == parceiro_id)
        .order_by(ComissaoParceiro.id.desc())
        .all()
    )

    creditos = (
        db.query(CreditoBarbearia)
        .filter(CreditoBarbearia.parceiro_id == parceiro_id)
        .order_by(CreditoBarbearia.id.desc())
        .all()
    )

    indicacoes_detalhadas = []

    for indicacao in indicacoes:
        barbearia = (
            db.query(models.Barbearia)
            .filter(
                models.Barbearia.id
                == indicacao.barbearia_indicada_id
            )
            .first()
        )

        assinatura = None
        plano = None

        if indicacao.assinatura_saas_id:
            assinatura = (
                db.query(models.AssinaturaSaaS)
                .filter(
                    models.AssinaturaSaaS.id
                    == indicacao.assinatura_saas_id
                )
                .first()
            )

        if assinatura:
            plano = (
                db.query(models.PlanoSaaS)
                .filter(
                    models.PlanoSaaS.id
                    == assinatura.plano_id
                )
                .first()
            )

        indicacoes_detalhadas.append({
            "indicacao_id": indicacao.id,
            "barbearia_id": indicacao.barbearia_indicada_id,
            "barbearia_nome": (
                barbearia.nome if barbearia else None
            ),
            "codigo_ref": indicacao.codigo_ref,
            "status": indicacao.status,
            "data_cadastro": indicacao.data_cadastro,
            "data_conversao": indicacao.data_conversao,
            "assinatura_saas_id": indicacao.assinatura_saas_id,
            "plano_id": plano.id if plano else None,
            "plano_nome": plano.nome if plano else None,
        })

    comissoes_detalhadas = []

    for comissao in comissoes:
        indicacao = (
            db.query(Indicacao)
            .filter(
                Indicacao.id == comissao.indicacao_id
            )
            .first()
        )

        barbearia = None
        pagamento = None

        if indicacao:
            barbearia = (
                db.query(models.Barbearia)
                .filter(
                    models.Barbearia.id
                    == indicacao.barbearia_indicada_id
                )
                .first()
            )

        if comissao.pagamento_saas_id:
            pagamento = (
                db.query(models.PagamentoSaaS)
                .filter(
                    models.PagamentoSaaS.id
                    == comissao.pagamento_saas_id
                )
                .first()
            )

        comissoes_detalhadas.append({
            "comissao_id": comissao.id,
            "indicacao_id": comissao.indicacao_id,
            "barbearia_nome": (
                barbearia.nome if barbearia else None
            ),
            "pagamento_saas_id": comissao.pagamento_saas_id,
            "valor_pagamento": (
                float(pagamento.valor)
                if pagamento
                else comissao.valor_base
            ),
            "valor_comissao": comissao.valor_comissao,
            "status": comissao.status,
            "data_geracao": comissao.data_geracao,
            "data_liberacao": comissao.data_liberacao,
            "data_pagamento": comissao.data_pagamento,
        })

    creditos_detalhados = []

    for credito in creditos:
        indicacao = (
            db.query(Indicacao)
            .filter(
                Indicacao.id == credito.indicacao_id
            )
            .first()
        )

        barbearia_indicada = None

        if indicacao:
            barbearia_indicada = (
                db.query(models.Barbearia)
                .filter(
                    models.Barbearia.id
                    == indicacao.barbearia_indicada_id
                )
                .first()
            )

        creditos_detalhados.append({
            "credito_id": credito.id,
            "indicacao_id": credito.indicacao_id,
            "barbearia_indicada_nome": (
                barbearia_indicada.nome
                if barbearia_indicada
                else None
            ),
            "valor_credito": credito.valor_credito,
            "status": credito.status,
            "referencia_mensalidade":
                credito.referencia_mensalidade,
            "data_geracao": credito.data_geracao,
            "data_aplicacao": credito.data_aplicacao,
        })

    total_convertidas = sum(
        1
        for item in indicacoes
        if item.status == "CONVERTIDA"
    )

    valor_pendente = sum(
        float(item.valor_comissao or 0)
        for item in comissoes
        if item.status == "PENDENTE"
    )

    valor_liberado = sum(
        float(item.valor_comissao or 0)
        for item in comissoes
        if item.status == "LIBERADA"
    )

    valor_pago = sum(
        float(item.valor_comissao or 0)
        for item in comissoes
        if item.status == "PAGA"
    )

    credito_disponivel = sum(
        float(item.valor_credito or 0)
        for item in creditos
        if item.status == "DISPONIVEL"
    )

    credito_aplicado = sum(
        float(item.valor_credito or 0)
        for item in creditos
        if item.status == "APLICADO"
    )

    return {
        "parceiro": {
            "id": parceiro.id,
            "tipo": parceiro.tipo,
            "nome": parceiro.nome,
            "email": parceiro.email,
            "codigo_ref": parceiro.codigo_ref,
            "tipo_beneficio": parceiro.tipo_beneficio,
            "ativo": parceiro.ativo,
        },
        "resumo": {
            "indicacoes_total": len(indicacoes),
            "indicacoes_convertidas": total_convertidas,
            "comissao_pendente": round(valor_pendente, 2),
            "comissao_liberada": round(valor_liberado, 2),
            "comissao_paga": round(valor_pago, 2),
            "credito_disponivel": round(
                credito_disponivel,
                2,
            ),
            "credito_aplicado": round(
                credito_aplicado,
                2,
            ),
        },
        "indicacoes": indicacoes_detalhadas,
        "comissoes": comissoes_detalhadas,
        "creditos": creditos_detalhados,
    }


def listar_indicacoes_parceiro_service(db: Session, parceiro_id: int):
    obter_parceiro_service(db, parceiro_id)

    return (
        db.query(Indicacao)
        .filter(Indicacao.parceiro_id == parceiro_id)
        .order_by(Indicacao.id.desc())
        .all()
    )


def listar_comissoes_parceiro_service(db: Session, parceiro_id: int):
    obter_parceiro_service(db, parceiro_id)

    return (
        db.query(ComissaoParceiro)
        .filter(ComissaoParceiro.parceiro_id == parceiro_id)
        .order_by(ComissaoParceiro.id.desc())
        .all()
    )


def listar_creditos_parceiro_service(db: Session, parceiro_id: int):
    obter_parceiro_service(db, parceiro_id)

    return (
        db.query(CreditoBarbearia)
        .filter(CreditoBarbearia.parceiro_id == parceiro_id)
        .order_by(CreditoBarbearia.id.desc())
        .all()
    )


def calcular_saldo_creditos_service(
    db: Session,
    parceiro_id: int,
):
    parceiro = obter_parceiro_service(db, parceiro_id)

    if parceiro.tipo_beneficio != "CREDITO":
        raise HTTPException(
            status_code=400,
            detail="Este parceiro n?o utiliza carteira de cr?ditos.",
        )

    creditos = (
        db.query(CreditoBarbearia)
        .filter(CreditoBarbearia.parceiro_id == parceiro_id)
        .order_by(CreditoBarbearia.id.asc())
        .all()
    )

    total_gerado = round(
        sum(float(c.valor_credito or 0) for c in creditos),
        2,
    )

    itens_aplicados = (
        db.query(ResgateCreditoItem)
        .join(
            ResgateCreditoBarbearia,
            ResgateCreditoBarbearia.id
            == ResgateCreditoItem.resgate_id,
        )
        .filter(
            ResgateCreditoBarbearia.parceiro_id == parceiro_id,
            ResgateCreditoBarbearia.status == "APLICADO",
        )
        .all()
    )

    total_aplicado = round(
        sum(float(i.valor_utilizado or 0) for i in itens_aplicados),
        2,
    )

    resgates_reservados = (
        db.query(ResgateCreditoBarbearia)
        .filter(
            ResgateCreditoBarbearia.parceiro_id == parceiro_id,
            ResgateCreditoBarbearia.status.in_(
                ["SOLICITADO", "APROVADO"]
            ),
        )
        .all()
    )

    total_reservado = round(
        sum(float(r.valor_solicitado or 0) for r in resgates_reservados),
        2,
    )

    saldo_bruto = round(
        max(total_gerado - total_aplicado, 0),
        2,
    )

    saldo_disponivel = round(
        max(saldo_bruto - total_reservado, 0),
        2,
    )

    return {
        "parceiro_id": parceiro.id,
        "barbearia_id": parceiro.barbearia_id,
        "total_gerado": total_gerado,
        "total_aplicado": total_aplicado,
        "total_reservado": total_reservado,
        "saldo_bruto": saldo_bruto,
        "saldo_disponivel": saldo_disponivel,
    }


def solicitar_resgate_creditos_service(
    db: Session,
    parceiro_id: int,
    valor: float,
    tipo_aplicacao: str = "RESGATE_SOLICITADO",
    observacao: str | None = None,
):
    parceiro = obter_parceiro_service(db, parceiro_id)

    if parceiro.tipo_beneficio != "CREDITO":
        raise HTTPException(
            status_code=400,
            detail="Este parceiro n?o utiliza cr?ditos.",
        )

    if not parceiro.barbearia_id:
        raise HTTPException(
            status_code=400,
            detail="Parceiro sem barbearia vinculada.",
        )

    valor = round(float(valor or 0), 2)

    if valor <= 0:
        raise HTTPException(
            status_code=400,
            detail="O valor do resgate deve ser maior que zero.",
        )

    saldo = calcular_saldo_creditos_service(
        db,
        parceiro_id,
    )

    if valor > saldo["saldo_disponivel"]:
        raise HTTPException(
            status_code=400,
            detail=(
                "Saldo insuficiente. "
                f"Dispon?vel: R$ {saldo['saldo_disponivel']:.2f}"
            ),
        )

    resgate = ResgateCreditoBarbearia(
        parceiro_id=parceiro.id,
        barbearia_id=parceiro.barbearia_id,
        tipo_aplicacao=tipo_aplicacao,
        valor_solicitado=valor,
        valor_aplicado=0,
        status="SOLICITADO",
        observacao=observacao,
    )

    db.add(resgate)
    db.commit()
    db.refresh(resgate)

    return resgate


def aprovar_resgate_creditos_service(
    db: Session,
    resgate_id: int,
):
    resgate = (
        db.query(ResgateCreditoBarbearia)
        .filter(ResgateCreditoBarbearia.id == resgate_id)
        .first()
    )

    if not resgate:
        raise HTTPException(
            status_code=404,
            detail="Resgate n?o encontrado.",
        )

    if resgate.status == "APROVADO":
        return resgate

    if resgate.status != "SOLICITADO":
        raise HTTPException(
            status_code=409,
            detail=(
                "Somente resgates SOLICITADOS "
                "podem ser aprovados."
            ),
        )

    resgate.status = "APROVADO"
    resgate.aprovado_em = datetime.now()

    db.commit()
    db.refresh(resgate)

    return resgate


def aplicar_resgate_creditos_service(
    db: Session,
    resgate_id: int,
    assinatura_saas_id: int | None = None,
    pagamento_saas_id: int | None = None,
):
    resgate = (
        db.query(ResgateCreditoBarbearia)
        .filter(ResgateCreditoBarbearia.id == resgate_id)
        .first()
    )

    if not resgate:
        raise HTTPException(
            status_code=404,
            detail="Resgate n?o encontrado.",
        )

    if resgate.status == "APLICADO":
        return resgate

    if resgate.status != "APROVADO":
        raise HTTPException(
            status_code=409,
            detail=(
                "O resgate precisa estar APROVADO "
                "antes da aplica??o."
            ),
        )

    valor_necessario = round(
        float(resgate.valor_solicitado),
        2,
    )

    creditos = (
        db.query(CreditoBarbearia)
        .filter(
            CreditoBarbearia.parceiro_id
            == resgate.parceiro_id
        )
        .order_by(CreditoBarbearia.id.asc())
        .all()
    )

    restante = valor_necessario
    itens_novos = []

    try:
        for credito in creditos:
            if restante <= 0:
                break

            utilizados = (
                db.query(ResgateCreditoItem)
                .join(
                    ResgateCreditoBarbearia,
                    ResgateCreditoBarbearia.id
                    == ResgateCreditoItem.resgate_id,
                )
                .filter(
                    ResgateCreditoItem.credito_id
                    == credito.id,
                    ResgateCreditoBarbearia.status
                    == "APLICADO",
                )
                .all()
            )

            ja_utilizado = round(
                sum(
                    float(i.valor_utilizado or 0)
                    for i in utilizados
                ),
                2,
            )

            disponivel_credito = round(
                max(
                    float(credito.valor_credito or 0)
                    - ja_utilizado,
                    0,
                ),
                2,
            )

            if disponivel_credito <= 0:
                continue

            usar = round(
                min(disponivel_credito, restante),
                2,
            )

            item = ResgateCreditoItem(
                resgate_id=resgate.id,
                credito_id=credito.id,
                valor_utilizado=usar,
            )

            db.add(item)
            itens_novos.append((credito, usar))

            restante = round(restante - usar, 2)

        if restante > 0:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Cr?ditos dispon?veis insuficientes "
                    "para concluir a aplica??o."
                ),
            )

        resgate.assinatura_saas_id = assinatura_saas_id
        resgate.pagamento_saas_id = pagamento_saas_id
        resgate.valor_aplicado = valor_necessario
        resgate.status = "APLICADO"
        resgate.aplicado_em = datetime.now()

        # Mant?m o status legado dos cr?ditos coerente
        # quando um cr?dito foi totalmente consumido.
        for credito, _ in itens_novos:
            total_usado = (
                db.query(ResgateCreditoItem)
                .join(
                    ResgateCreditoBarbearia,
                    ResgateCreditoBarbearia.id
                    == ResgateCreditoItem.resgate_id,
                )
                .filter(
                    ResgateCreditoItem.credito_id
                    == credito.id,
                    ResgateCreditoBarbearia.status
                    == "APLICADO",
                )
                .all()
            )

            soma = round(
                sum(
                    float(i.valor_utilizado or 0)
                    for i in total_usado
                ),
                2,
            )

            if soma >= round(
                float(credito.valor_credito or 0),
                2,
            ):
                credito.status = "APLICADO"
                credito.data_aplicacao = datetime.now()

        db.commit()
        db.refresh(resgate)

        return resgate

    except Exception:
        db.rollback()
        raise


def cancelar_reserva_creditos_service(
    db: Session,
    resgate_id: int,
    motivo: str | None = None,
):
    resgate = (
        db.query(ResgateCreditoBarbearia)
        .filter(
            ResgateCreditoBarbearia.id == resgate_id
        )
        .with_for_update()
        .first()
    )

    if not resgate:
        raise HTTPException(
            status_code=404,
            detail="Reserva de credito nao encontrada.",
        )

    # Idempotencia: uma reserva ja cancelada nao deve
    # provocar qualquer nova movimentacao.
    if resgate.status == "CANCELADO":
        return resgate

    # Credito efetivamente aplicado nao pode ser
    # simplesmente devolvido por esta rotina.
    if resgate.status == "APLICADO":
        raise HTTPException(
            status_code=409,
            detail=(
                "Credito ja aplicado nao pode ser "
                "cancelado como simples reserva."
            ),
        )

    if resgate.status not in {
        "SOLICITADO",
        "APROVADO",
    }:
        raise HTTPException(
            status_code=409,
            detail=(
                "Reserva em estado invalido para "
                f"cancelamento: {resgate.status}."
            ),
        )

    resgate.status = "CANCELADO"

    if motivo:
        anterior = (resgate.observacao or "").strip()

        complemento = (
            f"Reserva cancelada: {motivo}"
        )

        resgate.observacao = (
            f"{anterior}\n{complemento}"
            if anterior
            else complemento
        )

    db.commit()
    db.refresh(resgate)

    return resgate

