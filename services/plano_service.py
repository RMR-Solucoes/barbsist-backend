from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

import models

from auth.tenant import (
    buscar_da_barbearia,
    consultar_da_barbearia,
    obter_barbearia_id,
    validar_ids_da_barbearia,
)
from services.caixa_service import registrar_entrada_caixa


# =========================
# CONSTANTES DE STATUS
# =========================

STATUS_ATIVO = "ATIVO"
STATUS_INATIVO = "INATIVO"
STATUS_VENCIDO = "VENCIDO"
STATUS_SUSPENSO = "SUSPENSO"
STATUS_CANCELADO = "CANCELADO"
STATUS_ENCERRADO = "ENCERRADO"
STATUS_PENDENTE = "PENDENTE"

PAGAMENTO_PAGO = "PAGO"
PAGAMENTO_VENCIDO = "VENCIDO"
PAGAMENTO_INADIMPLENTE = "INADIMPLENTE"
PAGAMENTO_PENDENTE = "PENDENTE_PAGAMENTO"

STATUS_ASSINATURA_BLOQUEANTES = {
    STATUS_CANCELADO,
    STATUS_INATIVO,
    STATUS_SUSPENSO,
    STATUS_ENCERRADO,
}

STATUS_ASSINATURA_EM_ABERTO = {
    STATUS_PENDENTE,
    STATUS_ATIVO,
    STATUS_VENCIDO,
    STATUS_SUSPENSO,
}


# =========================
# FUNÇÕES AUXILIARES
# =========================

def _dados_parciais(dados):
    if hasattr(dados, "model_dump"):
        return dados.model_dump(exclude_unset=True)

    return dados.dict(exclude_unset=True)


def _normalizar_texto(valor):
    if valor is None:
        return None

    if isinstance(valor, str):
        return valor.strip()

    return valor


def validar_servicos_plano(
    db,
    servicos_ids,
    usuario_logado,
):
    registros_servicos = validar_ids_da_barbearia(
        db=db,
        model=models.Servico,
        registros_ids=servicos_ids or [],
        usuario=usuario_logado,
        mensagem_invalida=(
            "Um ou mais serviços não foram encontrados "
            "nesta barbearia."
        ),
    )

    servicos_inativos = [
        servico.id
        for servico in registros_servicos
        if hasattr(servico, "ativo") and not servico.ativo
    ]

    if servicos_inativos:
        raise HTTPException(
            status_code=400,
            detail=(
                "Um ou mais serviços informados estão inativos "
                "nesta barbearia."
            ),
        )

    return [servico.id for servico in registros_servicos]


def criar_vinculos_servicos_plano(
    db,
    plano_id: int,
    servicos_ids,
):
    for servico_id in dict.fromkeys(servicos_ids or []):
        db.add(
            models.PlanoServico(
                plano_id=plano_id,
                servico_id=servico_id,
            )
        )


def atualizar_status_assinatura(assinatura):
    """Atualiza vigência sem inferir pagamento inexistente."""
    agora = datetime.now()
    status_atual = (assinatura.status or STATUS_PENDENTE).upper()
    pagamento_atual = (assinatura.status_pagamento or PAGAMENTO_PENDENTE).upper()
    assinatura.status = status_atual
    assinatura.status_pagamento = pagamento_atual

    if status_atual in STATUS_ASSINATURA_BLOQUEANTES:
        return assinatura
    if assinatura.data_proximo_vencimento is None:
        if pagamento_atual != PAGAMENTO_PAGO:
            assinatura.status = STATUS_PENDENTE
            assinatura.status_pagamento = PAGAMENTO_PENDENTE
        return assinatura

    limite = assinatura.data_proximo_vencimento + timedelta(days=assinatura.dias_tolerancia or 0)
    if agora <= assinatura.data_proximo_vencimento:
        assinatura.status = STATUS_ATIVO if pagamento_atual == PAGAMENTO_PAGO else STATUS_PENDENTE
    elif agora <= limite:
        assinatura.status = STATUS_VENCIDO
        if pagamento_atual != PAGAMENTO_PAGO:
            assinatura.status_pagamento = PAGAMENTO_VENCIDO
    else:
        assinatura.status = STATUS_INATIVO
        if pagamento_atual != PAGAMENTO_PAGO:
            assinatura.status_pagamento = PAGAMENTO_INADIMPLENTE
    return assinatura


def _atualizar_status_em_lista(db, assinaturas):
    houve_alteracao = False

    for assinatura in assinaturas:
        status_anterior = assinatura.status
        pagamento_anterior = assinatura.status_pagamento

        atualizar_status_assinatura(assinatura)

        if (
            assinatura.status != status_anterior
            or assinatura.status_pagamento != pagamento_anterior
        ):
            houve_alteracao = True

    if houve_alteracao:
        db.commit()

    return assinaturas


def _aplicar_renovacao_assinatura(assinatura, plano, agora):
    primeiro_pagamento = assinatura.data_ultimo_pagamento is None

    # Primeiro pagamento:
    # a vigencia comeca quando o pagamento e confirmado.
    if primeiro_pagamento:
        base_renovacao = agora

    else:
        vencimento_atual = (
            assinatura.data_proximo_vencimento
            or assinatura.data_fim
        )

        # Renovacao antecipada preserva o periodo ja pago.
        # Renovacao vencida passa a contar da data do pagamento.
        base_renovacao = (
            vencimento_atual
            if vencimento_atual and vencimento_atual > agora
            else agora
        )

    assinatura.data_ultimo_pagamento = agora

    assinatura.data_proximo_vencimento = (
        base_renovacao + timedelta(days=plano.validade_dias)
    )
    assinatura.data_fim = assinatura.data_proximo_vencimento

    # Renovação recompõe os usos contratados.
    # Nesta versão, créditos não utilizados não acumulam.
    assinatura.usos_disponiveis = plano.quantidade_servicos

    assinatura.valor_mensal = plano.valor
    assinatura.status_pagamento = PAGAMENTO_PAGO
    assinatura.status = STATUS_ATIVO


def _registrar_historico_pagamento(
    db,
    assinatura,
    plano,
    forma_pagamento,
    observacoes,
    usuario_logado,
):
    agora = datetime.now()

    registrar_entrada_caixa(
        db=db,
        descricao=(
            f"Pagamento plano {plano.nome} "
            f"- assinatura #{assinatura.id}"
        ),
        valor=plano.valor,
        forma_pagamento=forma_pagamento,
        barbearia_id=assinatura.barbearia_id,
        origem="PLANO",
        referencia_id=assinatura.id,
        observacoes=observacoes,
        usuario_id=usuario_logado.id,
    )

    historico_pagamento = models.PagamentoPlano(
        assinatura_id=assinatura.id,
        cliente_id=assinatura.cliente_id,
        plano_id=assinatura.plano_id,
        valor=plano.valor,
        forma_pagamento=forma_pagamento,
        status=PAGAMENTO_PAGO,
        referencia_mes=agora.strftime("%Y-%m"),
        observacoes=observacoes,
    )

    db.add(historico_pagamento)
    return historico_pagamento


# =========================
# PLANOS
# =========================

def criar_plano_service(
    db,
    dados,
    usuario_logado,
):
    try:
        barbearia_id = obter_barbearia_id(usuario_logado)

        nome = _normalizar_texto(dados.nome)
        if not nome:
            raise HTTPException(
                status_code=400,
                detail="O nome do plano é obrigatório.",
            )

        servicos_ids = validar_servicos_plano(
            db=db,
            servicos_ids=dados.servicos_ids,
            usuario_logado=usuario_logado,
        )

        plano_existente = (
            consultar_da_barbearia(
                db=db,
                model=models.Plano,
                usuario=usuario_logado,
            )
            .filter(models.Plano.nome == nome)
            .first()
        )

        if plano_existente:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Já existe um plano com este nome "
                    "nesta barbearia."
                ),
            )

        plano = models.Plano(
            nome=nome,
            descricao=dados.descricao,
            valor=dados.valor,
            valor_pix=dados.valor_pix,
            valor_cartao=dados.valor_cartao,
            max_parcelas_cartao=max(1, min(int(dados.max_parcelas_cartao or 1), 12)),
            quantidade_servicos=dados.quantidade_servicos,
            validade_dias=dados.validade_dias,
            ativo=True,
            barbearia_id=barbearia_id,
        )

        db.add(plano)
        db.flush()

        criar_vinculos_servicos_plano(
            db=db,
            plano_id=plano.id,
            servicos_ids=servicos_ids,
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
            detail=f"Erro ao criar plano: {str(erro)}",
        )


def listar_planos_service(
    db,
    usuario_logado,
    apenas_ativos: bool = True,
):
    query = consultar_da_barbearia(
        db=db,
        model=models.Plano,
        usuario=usuario_logado,
    )

    if apenas_ativos:
        query = query.filter(models.Plano.ativo.is_(True))

    return query.order_by(models.Plano.nome.asc()).all()


def buscar_plano_service(
    db,
    plano_id: int,
    usuario_logado,
    exigir_ativo: bool = True,
):
    plano = buscar_da_barbearia(
        db=db,
        model=models.Plano,
        registro_id=plano_id,
        usuario=usuario_logado,
        mensagem_nao_encontrado="Plano não encontrado.",
    )

    if exigir_ativo and not plano.ativo:
        raise HTTPException(
            status_code=404,
            detail="Plano não encontrado ou inativo.",
        )

    return plano


def atualizar_plano_service(
    db,
    plano_id: int,
    dados,
    usuario_logado,
):
    try:
        plano = buscar_plano_service(
            db=db,
            plano_id=plano_id,
            usuario_logado=usuario_logado,
            exigir_ativo=False,
        )

        nome = _normalizar_texto(dados.nome)
        if not nome:
            raise HTTPException(
                status_code=400,
                detail="O nome do plano é obrigatório.",
            )

        plano_com_mesmo_nome = (
            consultar_da_barbearia(
                db=db,
                model=models.Plano,
                usuario=usuario_logado,
            )
            .filter(
                models.Plano.nome == nome,
                models.Plano.id != plano.id,
            )
            .first()
        )

        if plano_com_mesmo_nome:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Já existe outro plano com este nome "
                    "nesta barbearia."
                ),
            )

        servicos_ids = validar_servicos_plano(
            db=db,
            servicos_ids=dados.servicos_ids,
            usuario_logado=usuario_logado,
        )

        plano.nome = nome
        plano.descricao = dados.descricao
        plano.valor = dados.valor
        plano.valor_pix = dados.valor_pix
        plano.valor_cartao = dados.valor_cartao
        plano.max_parcelas_cartao = max(1, min(int(dados.max_parcelas_cartao or 1), 12))
        plano.quantidade_servicos = dados.quantidade_servicos
        plano.validade_dias = dados.validade_dias

        (
            db.query(models.PlanoServico)
            .filter(models.PlanoServico.plano_id == plano.id)
            .delete(synchronize_session=False)
        )

        criar_vinculos_servicos_plano(
            db=db,
            plano_id=plano.id,
            servicos_ids=servicos_ids,
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
            detail=f"Erro ao atualizar plano: {str(erro)}",
        )


# =========================
# ASSINATURAS
# =========================

def criar_assinatura_service(
    db,
    dados,
    usuario_logado,
):
    try:
        barbearia_id = obter_barbearia_id(usuario_logado)

        cliente = (
            db.query(models.Cliente)
            .filter(
                models.Cliente.id == dados.cliente_id,
                models.Cliente.barbearia_id == barbearia_id,
                models.Cliente.ativo.is_(True),
            )
            .with_for_update()
            .first()
        )

        if cliente is None:
            raise HTTPException(
                status_code=404,
                detail="Cliente não encontrado ou inativo.",
            )

        plano = buscar_plano_service(
            db=db,
            plano_id=dados.plano_id,
            usuario_logado=usuario_logado,
            exigir_ativo=True,
        )

        assinatura_existente = (
            db.query(models.AssinaturaCliente)
            .filter(
                models.AssinaturaCliente.barbearia_id == barbearia_id,
                models.AssinaturaCliente.cliente_id == cliente.id,
                models.AssinaturaCliente.status.in_(
                    STATUS_ASSINATURA_EM_ABERTO
                ),
            )
            .first()
        )

        if assinatura_existente:
            raise HTTPException(
                status_code=409,
                detail=(
                    "O cliente já possui uma assinatura "
                    "pendente, ativa, vencida ou suspensa."
                ),
            )

        agora = datetime.now()
        data_fim = agora + timedelta(days=plano.validade_dias)

        assinatura = models.AssinaturaCliente(
            cliente_id=cliente.id,
            plano_id=plano.id,
            data_inicio=agora,
            data_fim=data_fim,
            data_ultimo_pagamento=None,
            data_proximo_vencimento=None,
            dias_tolerancia=5,
            valor_mensal=plano.valor,
            usos_disponiveis=0,
            status=STATUS_PENDENTE,
            status_pagamento=PAGAMENTO_PENDENTE,
            barbearia_id=barbearia_id,
        )

        db.add(assinatura)
        db.commit()
        db.refresh(assinatura)
        return assinatura

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="O cliente já possui uma assinatura em aberto.",
        )

    except HTTPException:
        db.rollback()
        raise

    except Exception as erro:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao criar assinatura: {str(erro)}",
        )


def listar_assinaturas_service(
    db,
    usuario_logado,
):
    assinaturas = (
        consultar_da_barbearia(
            db=db,
            model=models.AssinaturaCliente,
            usuario=usuario_logado,
        )
        .order_by(models.AssinaturaCliente.id.desc())
        .all()
    )

    return _atualizar_status_em_lista(db, assinaturas)


def buscar_assinaturas_cliente_service(
    db,
    cliente_id: int,
    usuario_logado,
):
    cliente = buscar_da_barbearia(
        db=db,
        model=models.Cliente,
        registro_id=cliente_id,
        usuario=usuario_logado,
        mensagem_nao_encontrado="Cliente não encontrado.",
    )

    assinaturas = (
        consultar_da_barbearia(
            db=db,
            model=models.AssinaturaCliente,
            usuario=usuario_logado,
        )
        .filter(models.AssinaturaCliente.cliente_id == cliente.id)
        .order_by(models.AssinaturaCliente.id.desc())
        .all()
    )

    return _atualizar_status_em_lista(db, assinaturas)


def atualizar_assinatura_service(
    db,
    assinatura_id: int,
    dados,
    usuario_logado,
):
    try:
        assinatura = buscar_da_barbearia(
            db=db,
            model=models.AssinaturaCliente,
            registro_id=assinatura_id,
            usuario=usuario_logado,
            mensagem_nao_encontrado="Assinatura não encontrada.",
        )

        campos = _dados_parciais(dados)

        campos_protegidos = {
            "id",
            "barbearia_id",
            "cliente_id",
            "plano_id",
            "data_inicio",
            "data_fim",
            "data_proximo_vencimento",
            "data_ultimo_pagamento",
            "usos_disponiveis",
            "valor_mensal",
            "status",
            "status_pagamento",
        }

        for campo in campos_protegidos:
            campos.pop(campo, None)

        for campo, valor in campos.items():
            setattr(assinatura, campo, valor)

        if assinatura.status:
            assinatura.status = assinatura.status.upper()

        if assinatura.status_pagamento:
            assinatura.status_pagamento = (
                assinatura.status_pagamento.upper()
            )

        db.commit()
        db.refresh(assinatura)
        return assinatura

    except HTTPException:
        db.rollback()
        raise
    except Exception as erro:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao atualizar assinatura: {str(erro)}",
        )


# =========================
# USO DE PLANO
# =========================

def usar_plano_service(
    db,
    dados,
    usuario_logado,
    realizar_commit: bool = True,
):
    try:
        barbearia_id = obter_barbearia_id(usuario_logado)

        assinatura = (
            db.query(models.AssinaturaCliente)
            .filter(
                models.AssinaturaCliente.id == dados.assinatura_id,
                models.AssinaturaCliente.barbearia_id == barbearia_id,
            )
            .with_for_update()
            .first()
        )

        if assinatura is None:
            raise HTTPException(
                status_code=404,
                detail="Assinatura não encontrada.",
            )

        comanda = buscar_da_barbearia(
            db=db,
            model=models.Comanda,
            registro_id=dados.comanda_id,
            usuario=usuario_logado,
            mensagem_nao_encontrado="Comanda não encontrada.",
        )

        if comanda.barbearia_id != assinatura.barbearia_id:
            raise HTTPException(
                status_code=404,
                detail="Comanda ou assinatura não encontrada.",
            )

        if comanda.cliente_id != assinatura.cliente_id:
            raise HTTPException(
                status_code=400,
                detail=(
                    "A assinatura informada não pertence "
                    "ao cliente desta comanda."
                ),
            )

        status_comanda = (comanda.status or "").upper()
        if status_comanda != "ABERTA":
            raise HTTPException(
                status_code=400,
                detail=(
                    "Não é possível utilizar o plano em uma "
                    "comanda que não esteja aberta. "
                    f"Status atual: {status_comanda}"
                ),
            )

        atualizar_status_assinatura(assinatura)

        if assinatura.status != STATUS_ATIVO:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Assinatura indisponível para uso. "
                    f"Status atual: {assinatura.status}"
                ),
            )

        if assinatura.status_pagamento != PAGAMENTO_PAGO:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Pagamento do plano não está regular. "
                    f"Status atual: {assinatura.status_pagamento}"
                ),
            )

        servico = buscar_da_barbearia(
            db=db,
            model=models.Servico,
            registro_id=dados.servico_id,
            usuario=usuario_logado,
            mensagem_nao_encontrado="Serviço não encontrado ou inativo.",
        )

        if not servico.ativo:
            raise HTTPException(
                status_code=404,
                detail="Serviço não encontrado ou inativo.",
            )

        uso_existente = (
            db.query(models.UsoPlano)
            .filter(
                models.UsoPlano.comanda_id == comanda.id,
                models.UsoPlano.servico_id == servico.id,
            )
            .first()
        )

        if uso_existente:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Este serviço já foi registrado como pago "
                    "pelo plano nesta comanda."
                ),
            )

        servico_permitido = (
            db.query(models.PlanoServico)
            .join(
                models.Plano,
                models.Plano.id == models.PlanoServico.plano_id,
            )
            .filter(
                models.PlanoServico.plano_id == assinatura.plano_id,
                models.PlanoServico.servico_id == servico.id,
                models.Plano.barbearia_id == assinatura.barbearia_id,
            )
            .first()
        )

        if not servico_permitido:
            raise HTTPException(
                status_code=400,
                detail="Este serviço não está incluído no plano do cliente.",
            )

        usos = assinatura.usos_disponiveis or 0
        if usos <= 0:
            raise HTTPException(
                status_code=400,
                detail="Sem usos disponíveis no plano.",
            )

        uso = models.UsoPlano(
            assinatura_id=assinatura.id,
            comanda_id=comanda.id,
            servico_id=servico.id,
        )

        assinatura.usos_disponiveis = usos - 1
        db.add(uso)
        db.flush()
        db.refresh(uso)

        if realizar_commit:
            db.commit()
            db.refresh(uso)
            db.refresh(assinatura)

        return uso

    except IntegrityError:
        if realizar_commit:
            db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Este serviço já possui uso de plano nesta comanda.",
        )

    except HTTPException:
        if realizar_commit:
            db.rollback()
        raise

    except Exception as erro:
        if realizar_commit:
            db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao utilizar o plano: {str(erro)}",
        )


# =========================
# PAGAMENTOS DE PLANOS
# =========================

def registrar_pagamento_plano_service(db, dados, usuario_logado):
    try:
        assinatura = buscar_da_barbearia(db=db, model=models.AssinaturaCliente, registro_id=dados.assinatura_id, usuario=usuario_logado, mensagem_nao_encontrado="Assinatura não encontrada.")
        plano = buscar_plano_service(db=db, plano_id=assinatura.plano_id, usuario_logado=usuario_logado, exigir_ativo=True)
        return confirmar_pagamento_assinatura_service(
            db=db, assinatura=assinatura, plano=plano, forma_pagamento=(dados.forma_pagamento or "PIX").upper(),
            observacoes="Pagamento manual confirmado no BarbSist", usuario_id=getattr(usuario_logado, "id", None),
        )
    except HTTPException:
        db.rollback(); raise
    except Exception as erro:
        db.rollback(); raise HTTPException(status_code=500, detail=f"Erro ao registrar pagamento do plano: {str(erro)}")


def listar_pagamentos_planos_service(
    db,
    usuario_logado,
):
    barbearia_id = obter_barbearia_id(usuario_logado)

    return (
        db.query(models.PagamentoPlano)
        .join(
            models.AssinaturaCliente,
            models.AssinaturaCliente.id
            == models.PagamentoPlano.assinatura_id,
        )
        .filter(
            models.AssinaturaCliente.barbearia_id == barbearia_id
        )
        .order_by(models.PagamentoPlano.data_pagamento.desc())
        .all()
    )


def listar_pagamentos_assinatura_service(
    db,
    assinatura_id: int,
    usuario_logado,
):
    assinatura = buscar_da_barbearia(
        db=db,
        model=models.AssinaturaCliente,
        registro_id=assinatura_id,
        usuario=usuario_logado,
        mensagem_nao_encontrado="Assinatura não encontrada.",
    )

    return (
        db.query(models.PagamentoPlano)
        .filter(
            models.PagamentoPlano.assinatura_id == assinatura.id
        )
        .order_by(models.PagamentoPlano.data_pagamento.desc())
        .all()
    )


def listar_pagamentos_cliente_service(
    db,
    cliente_id: int,
    usuario_logado,
):
    cliente = buscar_da_barbearia(
        db=db,
        model=models.Cliente,
        registro_id=cliente_id,
        usuario=usuario_logado,
        mensagem_nao_encontrado="Cliente não encontrado.",
    )

    barbearia_id = obter_barbearia_id(usuario_logado)

    return (
        db.query(models.PagamentoPlano)
        .join(
            models.AssinaturaCliente,
            models.AssinaturaCliente.id
            == models.PagamentoPlano.assinatura_id,
        )
        .filter(
            models.PagamentoPlano.cliente_id == cliente.id,
            models.AssinaturaCliente.barbearia_id == barbearia_id,
        )
        .order_by(models.PagamentoPlano.data_pagamento.desc())
        .all()
    )


# =========================
# RENOVAÇÃO DE ASSINATURA
# =========================

def renovar_assinatura_service(db, assinatura_id: int, dados, usuario_logado):
    try:
        assinatura = buscar_da_barbearia(db=db, model=models.AssinaturaCliente, registro_id=assinatura_id, usuario=usuario_logado, mensagem_nao_encontrado="Assinatura não encontrada.")
        plano = buscar_plano_service(db=db, plano_id=assinatura.plano_id, usuario_logado=usuario_logado, exigir_ativo=True)
        return confirmar_pagamento_assinatura_service(
            db=db, assinatura=assinatura, plano=plano, forma_pagamento=(dados.forma_pagamento or "PIX").upper(),
            observacoes=getattr(dados, "observacoes", None) or "Renovação manual do plano", usuario_id=getattr(usuario_logado, "id", None),
        )
    except HTTPException:
        db.rollback(); raise
    except Exception as erro:
        db.rollback(); raise HTTPException(status_code=500, detail=f"Erro ao renovar assinatura: {str(erro)}")


# =========================
# SUSPENSÃO E REATIVAÇÃO
# =========================

def suspender_assinatura_service(
    db,
    assinatura_id: int,
    dados,
    usuario_logado,
):
    try:
        assinatura = buscar_da_barbearia(
            db=db,
            model=models.AssinaturaCliente,
            registro_id=assinatura_id,
            usuario=usuario_logado,
            mensagem_nao_encontrado="Assinatura não encontrada.",
        )

        if assinatura.status == STATUS_SUSPENSO:
            raise HTTPException(
                status_code=400,
                detail="Assinatura já está suspensa.",
            )

        assinatura.status = STATUS_SUSPENSO

        db.commit()
        db.refresh(assinatura)
        return assinatura

    except HTTPException:
        db.rollback()
        raise
    except Exception as erro:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao suspender assinatura: {str(erro)}",
        )


def cancelar_assinatura_service(
    db,
    assinatura_id: int,
    usuario_logado,
):
    try:
        assinatura = buscar_da_barbearia(
            db=db,
            model=models.AssinaturaCliente,
            registro_id=assinatura_id,
            usuario=usuario_logado,
            mensagem_nao_encontrado="Assinatura não encontrada.",
        )

        status_atual = (assinatura.status or "").upper()

        if status_atual == STATUS_CANCELADO:
            raise HTTPException(
                status_code=400,
                detail="Assinatura já está cancelada.",
            )

        if status_atual == STATUS_ENCERRADO:
            raise HTTPException(
                status_code=400,
                detail="Assinatura encerrada não pode ser cancelada.",
            )

        assinatura.status = STATUS_CANCELADO

        db.commit()
        db.refresh(assinatura)

        return assinatura

    except HTTPException:
        db.rollback()
        raise

    except Exception as erro:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao cancelar assinatura: {str(erro)}",
        )


def reativar_assinatura_service(
    db,
    assinatura_id: int,
    dados,
    usuario_logado,
):
    try:
        assinatura = buscar_da_barbearia(
            db=db,
            model=models.AssinaturaCliente,
            registro_id=assinatura_id,
            usuario=usuario_logado,
            mensagem_nao_encontrado="Assinatura não encontrada.",
        )

        status_atual = (assinatura.status or "").upper()

        if status_atual in {
            STATUS_CANCELADO,
            STATUS_ENCERRADO,
        }:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Assinatura cancelada ou encerrada não pode ser reativada."
                ),
            )

        if getattr(dados, "forma_pagamento", None):
            return renovar_assinatura_service(
                db=db,
                assinatura_id=assinatura.id,
                dados=dados,
                usuario_logado=usuario_logado,
            )

        assinatura.status = STATUS_ATIVO
        atualizar_status_assinatura(assinatura)

        if assinatura.status != STATUS_ATIVO:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Não foi possível reativar a assinatura "
                    "sem regularizar o pagamento."
                ),
            )

        db.commit()
        db.refresh(assinatura)
        return assinatura

    except HTTPException:
        db.rollback()
        raise
    except Exception as erro:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao reativar assinatura: {str(erro)}",
        )


# =========================
# INADIMPLÊNCIA
# =========================

def verificar_inadimplencia_service(
    db,
    usuario_logado,
):
    try:
        assinaturas = (
            consultar_da_barbearia(
                db=db,
                model=models.AssinaturaCliente,
                usuario=usuario_logado,
            )
            .filter(
                models.AssinaturaCliente.status.in_(
                    [STATUS_ATIVO, STATUS_VENCIDO]
                )
            )
            .all()
        )

        for assinatura in assinaturas:
            atualizar_status_assinatura(assinatura)

        db.commit()
        return assinaturas

    except HTTPException:
        db.rollback()
        raise
    except Exception as erro:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao verificar inadimplência: {str(erro)}",
        )


def _referencia_mes(atual=None):
    return (atual or datetime.now()).strftime("%Y-%m")


def _validar_pagamento_nao_duplicado(db, assinatura_id: int, referencia_mes: str):
    existente = db.query(models.PagamentoPlano).filter(
        models.PagamentoPlano.assinatura_id == assinatura_id,
        models.PagamentoPlano.referencia_mes == referencia_mes,
        models.PagamentoPlano.status == PAGAMENTO_PAGO,
    ).first()
    if existente:
        raise HTTPException(status_code=409, detail=f"Já existe pagamento confirmado para esta assinatura na referência {referencia_mes}.")


def confirmar_pagamento_assinatura_service(
    db,
    assinatura,
    plano,
    forma_pagamento: str,
    observacoes: str | None = None,
    usuario_id: int | None = None,
    referencia_mes: str | None = None,
    realizar_commit: bool = True,
    valor_pagamento: float | None = None,
):
    referencia = referencia_mes or _referencia_mes(datetime.now())

    try:
        assinatura_bloqueada = (
            db.query(models.AssinaturaCliente)
            .filter(
                models.AssinaturaCliente.id == assinatura.id,
                models.AssinaturaCliente.barbearia_id
                == assinatura.barbearia_id,
            )
            .with_for_update()
            .first()
        )

        if assinatura_bloqueada is None:
            raise HTTPException(
                status_code=404,
                detail="Assinatura não encontrada.",
            )

        _validar_pagamento_nao_duplicado(
            db,
            assinatura_bloqueada.id,
            referencia,
        )

        agora = datetime.now()
        _aplicar_renovacao_assinatura(
            assinatura_bloqueada,
            plano,
            agora,
        )

        valor_recebido = float(
            valor_pagamento
            if valor_pagamento is not None
            else plano.valor
        )

        registrar_entrada_caixa(
            db=db,
            descricao=(
                f"Pagamento plano {plano.nome} - "
                f"assinatura #{assinatura_bloqueada.id}"
            ),
            valor=valor_recebido,
            forma_pagamento=forma_pagamento,
            barbearia_id=assinatura_bloqueada.barbearia_id,
            origem="PLANO",
            referencia_id=assinatura_bloqueada.id,
            observacoes=observacoes,
            usuario_id=usuario_id,
        )

        pagamento = models.PagamentoPlano(
            assinatura_id=assinatura_bloqueada.id,
            cliente_id=assinatura_bloqueada.cliente_id,
            plano_id=assinatura_bloqueada.plano_id,
            valor=valor_recebido,
            forma_pagamento=forma_pagamento,
            status=PAGAMENTO_PAGO,
            referencia_mes=referencia,
            observacoes=observacoes,
        )
        db.add(pagamento)
        db.flush()

        if realizar_commit:
            db.commit()
            db.refresh(assinatura_bloqueada)

        return assinatura_bloqueada

    except IntegrityError:
        if realizar_commit:
            db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "Já existe pagamento confirmado para esta assinatura "
                f"na referência {referencia}."
            ),
        )

    except HTTPException:
        if realizar_commit:
            db.rollback()
        raise

    except Exception as erro:
        if realizar_commit:
            db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao confirmar pagamento do plano: {str(erro)}",
        )

