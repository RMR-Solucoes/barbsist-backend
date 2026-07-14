from datetime import datetime, timedelta

from fastapi import HTTPException

import models


# =========================
# CONSTANTES DE STATUS
# =========================

STATUS_ATIVO = "ATIVO"
STATUS_INATIVO = "INATIVO"
STATUS_VENCIDO = "VENCIDO"
STATUS_SUSPENSO = "SUSPENSO"
STATUS_CANCELADO = "CANCELADO"
STATUS_ENCERRADO = "ENCERRADO"

PAGAMENTO_PAGO = "PAGO"
PAGAMENTO_VENCIDO = "VENCIDO"
PAGAMENTO_INADIMPLENTE = "INADIMPLENTE"
PAGAMENTO_PENDENTE = "PENDENTE_PAGAMENTO"


# =========================
# PLANOS
# =========================

def validar_servicos_plano(db, servicos_ids):
    servicos_ids = list(set(servicos_ids or []))

    if not servicos_ids:
        raise HTTPException(
            status_code=400,
            detail=(
                "Selecione pelo menos um serviço "
                "para o plano"
            )
        )

    servicos = (
        db.query(models.Servico)
        .filter(
            models.Servico.id.in_(servicos_ids),
            models.Servico.ativo == True
        )
        .all()
    )

    ids_encontrados = {
        servico.id
        for servico in servicos
    }

    ids_invalidos = [
        servico_id
        for servico_id in servicos_ids
        if servico_id not in ids_encontrados
    ]

    if ids_invalidos:
        raise HTTPException(
            status_code=400,
            detail=(
                "Serviços não encontrados ou inativos: "
                f"{ids_invalidos}"
            )
        )

    return servicos_ids


def criar_vinculos_servicos_plano(
    db,
    plano_id: int,
    servicos_ids
):
    for servico_id in servicos_ids:
        vinculo = models.PlanoServico(
            plano_id=plano_id,
            servico_id=servico_id
        )

        db.add(vinculo)


def criar_plano_service(db, dados):
    try:
        servicos_ids = validar_servicos_plano(
            db=db,
            servicos_ids=dados.servicos_ids
        )

        plano = models.Plano(
            nome=dados.nome,
            descricao=dados.descricao,
            valor=dados.valor,
            quantidade_servicos=(
                dados.quantidade_servicos
            ),
            validade_dias=dados.validade_dias,
            ativo=True
        )

        db.add(plano)
        db.flush()

        criar_vinculos_servicos_plano(
            db=db,
            plano_id=plano.id,
            servicos_ids=servicos_ids
        )

        db.commit()
        db.refresh(plano)

        return plano

    except HTTPException:
        db.rollback()
        raise

    except Exception as erro:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Erro ao criar plano: "
                f"{str(erro)}"
            )
        )


def listar_planos_service(db):
    return (
        db.query(models.Plano)
        .filter(models.Plano.ativo == True)
        .order_by(models.Plano.nome.asc())
        .all()
    )


def buscar_plano_service(db, plano_id: int):
    plano = (
        db.query(models.Plano)
        .filter(
            models.Plano.id == plano_id,
            models.Plano.ativo == True
        )
        .first()
    )

    if not plano:
        raise HTTPException(
            status_code=404,
            detail="Plano não encontrado ou inativo"
        )

    return plano


def atualizar_plano_service(
    db,
    plano_id: int,
    dados
):
    try:
        plano = (
            db.query(models.Plano)
            .filter(
                models.Plano.id == plano_id
            )
            .first()
        )

        if not plano:
            raise HTTPException(
                status_code=404,
                detail="Plano não encontrado"
            )

        servicos_ids = validar_servicos_plano(
            db=db,
            servicos_ids=dados.servicos_ids
        )

        plano.nome = dados.nome
        plano.descricao = dados.descricao
        plano.valor = dados.valor
        plano.quantidade_servicos = (
            dados.quantidade_servicos
        )
        plano.validade_dias = (
            dados.validade_dias
        )
        plano.ativo = dados.ativo

        (
            db.query(models.PlanoServico)
            .filter(
                models.PlanoServico.plano_id ==
                plano.id
            )
            .delete(
                synchronize_session=False
            )
        )

        criar_vinculos_servicos_plano(
            db=db,
            plano_id=plano.id,
            servicos_ids=servicos_ids
        )

        db.commit()
        db.refresh(plano)

        return plano

    except HTTPException:
        db.rollback()
        raise

    except Exception as erro:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Erro ao atualizar plano: "
                f"{str(erro)}"
            )
        )

# =========================
# ASSINATURAS
# =========================

def criar_assinatura_service(db, dados):
    cliente = (
        db.query(models.Cliente)
        .filter(
            models.Cliente.id == dados.cliente_id,
            models.Cliente.ativo == True
        )
        .first()
    )

    if not cliente:
        raise HTTPException(
            status_code=404,
            detail="Cliente não encontrado ou inativo"
        )

    plano = buscar_plano_service(
        db=db,
        plano_id=dados.plano_id
    )

    assinatura_existente = (
        db.query(models.AssinaturaCliente)
        .filter(
            models.AssinaturaCliente.cliente_id ==
            dados.cliente_id,
            models.AssinaturaCliente.status.in_([
                STATUS_ATIVO,
                STATUS_VENCIDO,
                STATUS_SUSPENSO
            ])
        )
        .first()
    )

    if assinatura_existente:
        raise HTTPException(
            status_code=400,
            detail=(
                "O cliente já possui uma assinatura "
                "ativa, vencida ou suspensa"
            )
        )

    agora = datetime.now()
    data_fim = agora + timedelta(
        days=plano.validade_dias
    )

    assinatura = models.AssinaturaCliente(
        cliente_id=dados.cliente_id,
        plano_id=dados.plano_id,
        data_inicio=agora,
        data_fim=data_fim,
        data_ultimo_pagamento=agora,
        data_proximo_vencimento=data_fim,
        dias_tolerancia=5,
        valor_mensal=plano.valor,
        usos_disponiveis=plano.quantidade_servicos,
        status=STATUS_ATIVO,
        status_pagamento=PAGAMENTO_PAGO
    )

    db.add(assinatura)
    db.commit()
    db.refresh(assinatura)

    return assinatura


def listar_assinaturas_service(db):
    assinaturas = (
        db.query(models.AssinaturaCliente)
        .order_by(
            models.AssinaturaCliente.id.desc()
        )
        .all()
    )

    houve_alteracao = False

    for assinatura in assinaturas:
        status_anterior = assinatura.status
        pagamento_anterior = (
            assinatura.status_pagamento
        )

        atualizar_status_assinatura(assinatura)

        if (
            assinatura.status != status_anterior
            or assinatura.status_pagamento
            != pagamento_anterior
        ):
            houve_alteracao = True

    if houve_alteracao:
        db.commit()

    return assinaturas


def buscar_assinaturas_cliente_service(
    db,
    cliente_id: int
):
    assinaturas = (
        db.query(models.AssinaturaCliente)
        .filter(
            models.AssinaturaCliente.cliente_id ==
            cliente_id
        )
        .order_by(
            models.AssinaturaCliente.id.desc()
        )
        .all()
    )

    houve_alteracao = False

    for assinatura in assinaturas:
        status_anterior = assinatura.status
        pagamento_anterior = (
            assinatura.status_pagamento
        )

        atualizar_status_assinatura(assinatura)

        if (
            assinatura.status != status_anterior
            or assinatura.status_pagamento
            != pagamento_anterior
        ):
            houve_alteracao = True

    if houve_alteracao:
        db.commit()

    return assinaturas


def atualizar_assinatura_service(
    db,
    assinatura_id: int,
    dados
):
    assinatura = (
        db.query(models.AssinaturaCliente)
        .filter(
            models.AssinaturaCliente.id ==
            assinatura_id
        )
        .first()
    )

    if not assinatura:
        raise HTTPException(
            status_code=404,
            detail="Assinatura não encontrada"
        )

    if hasattr(dados, "model_dump"):
        campos = dados.model_dump(
            exclude_unset=True
        )
    else:
        campos = dados.dict(
            exclude_unset=True
        )

    for campo, valor in campos.items():
        setattr(assinatura, campo, valor)

    if assinatura.status:
        assinatura.status = (
            assinatura.status.upper()
        )

    if assinatura.status_pagamento:
        assinatura.status_pagamento = (
            assinatura.status_pagamento.upper()
        )

    db.commit()
    db.refresh(assinatura)

    return assinatura


# =========================
# STATUS DA ASSINATURA
# =========================

def atualizar_status_assinatura(assinatura):
    agora = datetime.now()

    status_atual = (
        assinatura.status or ""
    ).upper()

    pagamento_atual = (
        assinatura.status_pagamento or ""
    ).upper()

    assinatura.status = status_atual
    assinatura.status_pagamento = pagamento_atual

    if status_atual in [
        STATUS_CANCELADO,
        STATUS_INATIVO,
        STATUS_SUSPENSO,
        STATUS_ENCERRADO
    ]:
        return assinatura

    if assinatura.data_proximo_vencimento is None:
        assinatura.status_pagamento = (
            PAGAMENTO_PENDENTE
        )

        return assinatura

    dias_tolerancia = (
        assinatura.dias_tolerancia or 0
    )

    limite_tolerancia = (
        assinatura.data_proximo_vencimento
        + timedelta(days=dias_tolerancia)
    )

    if agora <= assinatura.data_proximo_vencimento:
        assinatura.status = STATUS_ATIVO
        assinatura.status_pagamento = (
            PAGAMENTO_PAGO
        )

    elif agora <= limite_tolerancia:
        assinatura.status = STATUS_VENCIDO
        assinatura.status_pagamento = (
            PAGAMENTO_VENCIDO
        )

    else:
        assinatura.status = STATUS_INATIVO
        assinatura.status_pagamento = (
            PAGAMENTO_INADIMPLENTE
        )

    return assinatura


# =========================
# USO DE PLANO
# =========================

def usar_plano_service(
    db,
    dados,
    realizar_commit: bool = True
):
    try:
        assinatura = (
            db.query(models.AssinaturaCliente)
            .filter(
                models.AssinaturaCliente.id ==
                dados.assinatura_id
            )
            .first()
        )

        if not assinatura:
            raise HTTPException(
                status_code=404,
                detail="Assinatura não encontrada"
            )

        comanda = (
            db.query(models.Comanda)
            .filter(
                models.Comanda.id ==
                dados.comanda_id
            )
            .first()
        )

        if not comanda:
            raise HTTPException(
                status_code=404,
                detail="Comanda não encontrada"
            )

        if (
            comanda.cliente_id
            != assinatura.cliente_id
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "A assinatura informada não pertence "
                    "ao cliente desta comanda"
                )
            )

        status_comanda = (
            comanda.status or ""
        ).upper()

        if status_comanda != "ABERTA":
            raise HTTPException(
                status_code=400,
                detail=(
                    "Não é possível utilizar o plano "
                    "em uma comanda que não esteja aberta. "
                    f"Status atual: {status_comanda}"
                )
            )

        atualizar_status_assinatura(assinatura)

        if assinatura.status != STATUS_ATIVO:
            if realizar_commit:
                db.commit()
            else:
                db.flush()

            raise HTTPException(
                status_code=400,
                detail=(
                    "Assinatura indisponível para uso. "
                    f"Status atual: {assinatura.status}"
                )
            )

        if (
            assinatura.status_pagamento
            != PAGAMENTO_PAGO
        ):
            if realizar_commit:
                db.commit()
            else:
                db.flush()

            raise HTTPException(
                status_code=400,
                detail=(
                    "Pagamento do plano não está regular. "
                    "Status atual: "
                    f"{assinatura.status_pagamento}"
                )
            )

        servico = (
            db.query(models.Servico)
            .filter(
                models.Servico.id ==
                dados.servico_id,
                models.Servico.ativo == True
            )
            .first()
        )

        if not servico:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Serviço não encontrado ou inativo"
                )
            )

        uso_existente = (
            db.query(models.UsoPlano)
            .filter(
                models.UsoPlano.comanda_id ==
                dados.comanda_id,
                models.UsoPlano.servico_id ==
                dados.servico_id
            )
            .first()
        )

        if uso_existente:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Este serviço já foi registrado "
                    "como pago pelo plano nesta comanda"
                )
            )

        servico_permitido = (
            db.query(models.PlanoServico)
            .filter(
                models.PlanoServico.plano_id ==
                assinatura.plano_id,
                models.PlanoServico.servico_id ==
                dados.servico_id
            )
            .first()
        )

        if not servico_permitido:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Este serviço não está incluído "
                    "no plano do cliente"
                )
            )

        if assinatura.usos_disponiveis is None:
            assinatura.usos_disponiveis = 0

        if assinatura.usos_disponiveis <= 0:
            raise HTTPException(
                status_code=400,
                detail="Sem usos disponíveis no plano"
            )

        uso = models.UsoPlano(
            assinatura_id=assinatura.id,
            comanda_id=dados.comanda_id,
            servico_id=dados.servico_id
        )

        assinatura.usos_disponiveis -= 1

        db.add(uso)

        # Gera o ID sem finalizar a transação.
        db.flush()
        db.refresh(uso)

        if realizar_commit:
            db.commit()
            db.refresh(uso)

        return uso

    except HTTPException:
        if realizar_commit:
            db.rollback()

        raise

    except Exception as erro:
        if realizar_commit:
            db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Erro ao utilizar o plano: "
                f"{str(erro)}"
            )
        )

# =========================
# PAGAMENTOS DE PLANOS
# =========================

def registrar_pagamento_plano_service(
    db,
    dados
):
    assinatura = (
        db.query(models.AssinaturaCliente)
        .filter(
            models.AssinaturaCliente.id ==
            dados.assinatura_id
        )
        .first()
    )

    if not assinatura:
        raise HTTPException(
            status_code=404,
            detail="Assinatura não encontrada"
        )

    plano = (
        db.query(models.Plano)
        .filter(
            models.Plano.id ==
            assinatura.plano_id,
            models.Plano.ativo == True
        )
        .first()
    )

    if not plano:
        raise HTTPException(
            status_code=404,
            detail="Plano não encontrado ou inativo"
        )

    agora = datetime.now()

    assinatura.data_ultimo_pagamento = agora
    assinatura.data_proximo_vencimento = (
        agora
        + timedelta(days=plano.validade_dias)
    )
    assinatura.data_fim = (
        assinatura.data_proximo_vencimento
    )
    assinatura.usos_disponiveis = (
        plano.quantidade_servicos
    )
    assinatura.valor_mensal = plano.valor
    assinatura.status_pagamento = PAGAMENTO_PAGO
    assinatura.status = STATUS_ATIVO

    movimentacao = models.Caixa(
        tipo="entrada",
        descricao=(
            f"Pagamento plano {plano.nome} "
            f"- assinatura #{assinatura.id}"
        ),
        valor=plano.valor,
        forma_pagamento=dados.forma_pagamento
    )

    historico_pagamento = models.PagamentoPlano(
        assinatura_id=assinatura.id,
        cliente_id=assinatura.cliente_id,
        plano_id=assinatura.plano_id,
        valor=plano.valor,
        forma_pagamento=dados.forma_pagamento,
        status=PAGAMENTO_PAGO,
        referencia_mes=agora.strftime("%Y-%m"),
        observacoes="Pagamento mensal do plano"
    )

    db.add(movimentacao)
    db.add(historico_pagamento)

    db.commit()
    db.refresh(assinatura)

    return assinatura


def listar_pagamentos_planos_service(db):
    return (
        db.query(models.PagamentoPlano)
        .order_by(
            models.PagamentoPlano
            .data_pagamento
            .desc()
        )
        .all()
    )


def listar_pagamentos_assinatura_service(
    db,
    assinatura_id: int
):
    return (
        db.query(models.PagamentoPlano)
        .filter(
            models.PagamentoPlano.assinatura_id
            == assinatura_id
        )
        .order_by(
            models.PagamentoPlano
            .data_pagamento
            .desc()
        )
        .all()
    )


def listar_pagamentos_cliente_service(
    db,
    cliente_id: int
):
    return (
        db.query(models.PagamentoPlano)
        .filter(
            models.PagamentoPlano.cliente_id
            == cliente_id
        )
        .order_by(
            models.PagamentoPlano
            .data_pagamento
            .desc()
        )
        .all()
    )


# =========================
# RENOVAÇÃO DE ASSINATURA
# =========================

def renovar_assinatura_service(
    db,
    assinatura_id: int,
    dados
):
    assinatura = (
        db.query(models.AssinaturaCliente)
        .filter(
            models.AssinaturaCliente.id ==
            assinatura_id
        )
        .first()
    )

    if not assinatura:
        raise HTTPException(
            status_code=404,
            detail="Assinatura não encontrada"
        )

    plano = (
        db.query(models.Plano)
        .filter(
            models.Plano.id ==
            assinatura.plano_id,
            models.Plano.ativo == True
        )
        .first()
    )

    if not plano:
        raise HTTPException(
            status_code=404,
            detail="Plano não encontrado ou inativo"
        )

    agora = datetime.now()

    assinatura.data_ultimo_pagamento = agora
    assinatura.data_proximo_vencimento = (
        agora
        + timedelta(days=plano.validade_dias)
    )
    assinatura.data_fim = (
        assinatura.data_proximo_vencimento
    )
    assinatura.usos_disponiveis = (
        plano.quantidade_servicos
    )
    assinatura.valor_mensal = plano.valor
    assinatura.status_pagamento = PAGAMENTO_PAGO
    assinatura.status = STATUS_ATIVO

    movimentacao = models.Caixa(
        tipo="entrada",
        descricao=(
            f"Renovação plano {plano.nome} "
            f"- assinatura #{assinatura.id}"
        ),
        valor=plano.valor,
        forma_pagamento=dados.forma_pagamento
    )

    observacoes = (
        dados.observacoes
        or "Renovação mensal do plano"
    )

    historico_pagamento = models.PagamentoPlano(
        assinatura_id=assinatura.id,
        cliente_id=assinatura.cliente_id,
        plano_id=assinatura.plano_id,
        valor=plano.valor,
        forma_pagamento=dados.forma_pagamento,
        status=PAGAMENTO_PAGO,
        referencia_mes=agora.strftime("%Y-%m"),
        observacoes=observacoes
    )

    db.add(movimentacao)
    db.add(historico_pagamento)

    db.commit()
    db.refresh(assinatura)

    return assinatura


# =========================
# SUSPENSÃO E REATIVAÇÃO
# =========================

def suspender_assinatura_service(
    db,
    assinatura_id: int,
    dados
):
    assinatura = (
        db.query(models.AssinaturaCliente)
        .filter(
            models.AssinaturaCliente.id ==
            assinatura_id
        )
        .first()
    )

    if not assinatura:
        raise HTTPException(
            status_code=404,
            detail="Assinatura não encontrada"
        )

    if assinatura.status == STATUS_SUSPENSO:
        raise HTTPException(
            status_code=400,
            detail="Assinatura já está suspensa"
        )

    assinatura.status = STATUS_SUSPENSO
    assinatura.status_pagamento = (
        PAGAMENTO_PENDENTE
    )

    db.commit()
    db.refresh(assinatura)

    return assinatura


def reativar_assinatura_service(
    db,
    assinatura_id: int,
    dados
):
    assinatura = (
        db.query(models.AssinaturaCliente)
        .filter(
            models.AssinaturaCliente.id ==
            assinatura_id
        )
        .first()
    )

    if not assinatura:
        raise HTTPException(
            status_code=404,
            detail="Assinatura não encontrada"
        )

    if dados.forma_pagamento:
        return renovar_assinatura_service(
            db=db,
            assinatura_id=assinatura_id,
            dados=dados
        )

    assinatura.status = STATUS_ATIVO

    atualizar_status_assinatura(assinatura)

    if assinatura.status != STATUS_ATIVO:
        raise HTTPException(
            status_code=400,
            detail=(
                "Não foi possível reativar a assinatura "
                "sem regularizar o pagamento"
            )
        )

    db.commit()
    db.refresh(assinatura)

    return assinatura


# =========================
# INADIMPLÊNCIA
# =========================

def verificar_inadimplencia_service(db):
    assinaturas = (
        db.query(models.AssinaturaCliente)
        .filter(
            models.AssinaturaCliente.status.in_([
                STATUS_ATIVO,
                STATUS_VENCIDO
            ])
        )
        .all()
    )

    for assinatura in assinaturas:
        atualizar_status_assinatura(assinatura)

    db.commit()

    return assinaturas