from datetime import date, datetime, time, timedelta

from fastapi import HTTPException
from sqlalchemy import func

import models

from auth.tenant import (
    buscar_da_barbearia,
    consultar_da_barbearia,
    obter_barbearia_id,
)


STATUS_COM_CONFLITO = (
    "agendado",
    "confirmado",
    "em_atendimento",
    "reagendado",
)


def validar_cliente(db, cliente_id, usuario_logado):
    if cliente_id is None:
        return None

    cliente = buscar_da_barbearia(
        db=db,
        model=models.Cliente,
        registro_id=cliente_id,
        usuario=usuario_logado,
        mensagem_nao_encontrado="Cliente não encontrado ou inativo.",
    )

    if not cliente.ativo:
        raise HTTPException(
            status_code=404,
            detail="Cliente não encontrado ou inativo.",
        )

    return cliente


def validar_barbeiro(db, barbeiro_id, usuario_logado):
    barbeiro = buscar_da_barbearia(
        db=db,
        model=models.Barbeiro,
        registro_id=barbeiro_id,
        usuario=usuario_logado,
        mensagem_nao_encontrado="Barbeiro não encontrado ou inativo.",
    )

    if not barbeiro.ativo:
        raise HTTPException(
            status_code=404,
            detail="Barbeiro não encontrado ou inativo.",
        )

    return barbeiro


def validar_servico(db, servico_id, usuario_logado):
    servico = buscar_da_barbearia(
        db=db,
        model=models.Servico,
        registro_id=servico_id,
        usuario=usuario_logado,
        mensagem_nao_encontrado="Serviço não encontrado ou inativo.",
    )

    if not servico.ativo:
        raise HTTPException(
            status_code=404,
            detail="Serviço não encontrado ou inativo.",
        )

    return servico


def validar_estilo(db, estilo_id, nome_campo):
    """
    Estilos ainda são globais no model atual. O isolamento desta entidade
    será tratado na etapa própria de Estilos/Configurações.
    """
    if estilo_id is None:
        return None

    estilo = (
        db.query(models.Estilo)
        .filter(
            models.Estilo.id == estilo_id,
            models.Estilo.ativo.is_(True),
        )
        .first()
    )

    if not estilo:
        raise HTTPException(
            status_code=404,
            detail=f"{nome_campo} não encontrado ou inativo.",
        )

    return estilo


def verificar_conflito_horario(
    db,
    barbeiro_id: int,
    inicio,
    fim,
    usuario_logado,
    agendamento_id_ignorar: int | None = None,
):
    query = consultar_da_barbearia(
        db=db,
        model=models.Agendamento,
        usuario=usuario_logado,
    ).filter(
        models.Agendamento.barbeiro_id == barbeiro_id,
        func.lower(models.Agendamento.status).in_(STATUS_COM_CONFLITO),
        models.Agendamento.data_hora_inicio < fim,
        models.Agendamento.data_hora_fim > inicio,
    )

    if agendamento_id_ignorar is not None:
        query = query.filter(
            models.Agendamento.id != agendamento_id_ignorar
        )

    if query.first():
        raise HTTPException(
            status_code=400,
            detail="Já existe agendamento para este barbeiro nesse horário.",
        )


def criar_agendamento_service(db, dados, usuario_logado):
    barbearia_id = obter_barbearia_id(usuario_logado)

    cliente = validar_cliente(
        db,
        dados.cliente_id,
        usuario_logado,
    )
    validar_barbeiro(
        db,
        dados.barbeiro_id,
        usuario_logado,
    )
    servico = validar_servico(
        db,
        dados.servico_id,
        usuario_logado,
    )

    validar_estilo(db, dados.estilo_corte_id, "Estilo de corte")
    validar_estilo(db, dados.estilo_barba_id, "Estilo de barba")

    tipo_atendimento = (
        getattr(dados, "tipo_atendimento", "avulso") or "avulso"
    ).lower()

    if tipo_atendimento not in ("plano", "avulso"):
        raise HTTPException(
            status_code=400,
            detail="Tipo de atendimento inválido. Use 'plano' ou 'avulso'.",
        )

    assinatura = None

    if cliente is not None:
        assinatura = (
            db.query(models.AssinaturaCliente)
            .filter(
                models.AssinaturaCliente.barbearia_id == barbearia_id,
                models.AssinaturaCliente.cliente_id == cliente.id,
            )
            .order_by(models.AssinaturaCliente.id.desc())
            .first()
        )

    if assinatura is None:
        tipo_atendimento = "avulso"

    elif tipo_atendimento == "plano":
        if (assinatura.status or "").upper() != "ATIVO":
            raise HTTPException(
                status_code=400,
                detail=(
                    "Plano inativo, vencido ou inadimplente. "
                    "Regularize o pagamento ou escolha atendimento avulso."
                ),
            )

        if (
            hasattr(assinatura, "status_pagamento")
            and (assinatura.status_pagamento or "").upper() != "PAGO"
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Pagamento do plano não está regular. "
                    "Regularize o pagamento ou escolha atendimento avulso."
                ),
            )

        if assinatura.data_fim:
            data_fim = assinatura.data_fim
            if isinstance(data_fim, datetime):
                data_fim = data_fim.date()

            if data_fim < date.today():
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Plano vencido. Regularize o pagamento "
                        "ou escolha atendimento avulso."
                    ),
                )

        if (assinatura.usos_disponiveis or 0) <= 0:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Plano sem usos disponíveis. "
                    "Escolha atendimento avulso."
                ),
            )

    inicio = dados.data_hora_inicio
    fim = inicio + timedelta(minutes=servico.tempo_medio_minutos or 30)

    verificar_conflito_horario(
        db=db,
        barbeiro_id=dados.barbeiro_id,
        inicio=inicio,
        fim=fim,
        usuario_logado=usuario_logado,
    )

    agendamento = models.Agendamento(
        barbearia_id=barbearia_id,
        cliente_id=dados.cliente_id,
        barbeiro_id=dados.barbeiro_id,
        servico_id=dados.servico_id,
        estilo_corte_id=dados.estilo_corte_id,
        estilo_barba_id=dados.estilo_barba_id,
        data_hora_inicio=inicio,
        data_hora_fim=fim,
        status="agendado",
        observacoes=dados.observacoes,
        tipo_atendimento=tipo_atendimento,
        origem=getattr(dados, "origem", "INTERNO") or "INTERNO",
    )

    db.add(agendamento)
    db.commit()
    db.refresh(agendamento)

    return agendamento


def listar_agendamentos_service(db, usuario_logado):
    return (
        consultar_da_barbearia(
            db=db,
            model=models.Agendamento,
            usuario=usuario_logado,
        )
        .order_by(models.Agendamento.data_hora_inicio.asc())
        .all()
    )


def buscar_agendamento_service(db, agendamento_id: int, usuario_logado):
    return buscar_da_barbearia(
        db=db,
        model=models.Agendamento,
        registro_id=agendamento_id,
        usuario=usuario_logado,
        mensagem_nao_encontrado="Agendamento não encontrado.",
    )


def cancelar_agendamento_service(db, agendamento_id: int, usuario_logado):
    agendamento = buscar_agendamento_service(
        db,
        agendamento_id,
        usuario_logado,
    )

    if (agendamento.status or "").lower() in ("concluido", "cancelado"):
        raise HTTPException(
            status_code=400,
            detail="Agendamento já está concluído ou cancelado.",
        )

    agendamento.status = "cancelado"

    db.commit()
    db.refresh(agendamento)

    return agendamento


def listar_agendamentos_por_filtro_service(
    db,
    usuario_logado,
    data_agenda=None,
    barbeiro_id=None,
):
    query = consultar_da_barbearia(
        db=db,
        model=models.Agendamento,
        usuario=usuario_logado,
    )

    if data_agenda:
        inicio_dia = datetime.combine(data_agenda, time.min)
        fim_dia = datetime.combine(data_agenda, time.max)

        query = query.filter(
            models.Agendamento.data_hora_inicio >= inicio_dia,
            models.Agendamento.data_hora_inicio <= fim_dia,
        )

    if barbeiro_id is not None:
        validar_barbeiro(db, barbeiro_id, usuario_logado)
        query = query.filter(
            models.Agendamento.barbeiro_id == barbeiro_id
        )

    return query.order_by(
        models.Agendamento.data_hora_inicio.asc()
    ).all()


def atualizar_status_agendamento_service(
    db,
    agendamento_id: int,
    status: str,
    usuario_logado,
):
    status_normalizado = (status or "").strip().lower()
    status_validos = (
        "agendado",
        "confirmado",
        "em_atendimento",
        "concluido",
        "cancelado",
        "nao_compareceu",
        "reagendado",
    )

    if status_normalizado not in status_validos:
        raise HTTPException(status_code=400, detail="Status inválido.")

    agendamento = buscar_agendamento_service(
        db,
        agendamento_id,
        usuario_logado,
    )
    agendamento.status = status_normalizado

    db.commit()
    db.refresh(agendamento)

    return agendamento


def converter_agendamento_em_comanda_service(
    db,
    agendamento_id: int,
    usuario_logado,
):
    barbearia_id = obter_barbearia_id(usuario_logado)
    agendamento = buscar_agendamento_service(
        db,
        agendamento_id,
        usuario_logado,
    )

    if (agendamento.status or "").lower() in (
        "cancelado",
        "concluido",
        "nao_compareceu",
    ):
        raise HTTPException(
            status_code=400,
            detail="Agendamento não pode ser convertido em comanda.",
        )

    servico = validar_servico(
        db,
        agendamento.servico_id,
        usuario_logado,
    )

    try:
        comanda = models.Comanda(
            barbearia_id=barbearia_id,
            cliente_id=agendamento.cliente_id,
            barbeiro_id=agendamento.barbeiro_id,
            status="aberta",
            total=0,
        )

        db.add(comanda)
        db.flush()

        item = models.ItemComanda(
            comanda_id=comanda.id,
            tipo="servico",
            descricao=servico.nome,
            quantidade=1,
            valor_unitario=servico.preco,
            subtotal=servico.preco,
            servico_id=servico.id,
        )

        comanda.total = servico.preco
        agendamento.status = "em_atendimento"

        db.add(item)
        db.commit()
        db.refresh(comanda)

    except Exception:
        db.rollback()
        raise

    return {
        "mensagem": "Agendamento convertido em comanda com sucesso",
        "agendamento_id": agendamento.id,
        "comanda_id": comanda.id,
        "status_agendamento": agendamento.status,
        "total_comanda": comanda.total,
    }


def reagendar_agendamento_service(
    db,
    agendamento_id: int,
    nova_data_hora_inicio,
    usuario_logado,
):
    agendamento = buscar_agendamento_service(
        db,
        agendamento_id,
        usuario_logado,
    )

    if (agendamento.status or "").lower() == "cancelado":
        raise HTTPException(
            status_code=400,
            detail="Agendamento cancelado não pode ser reagendado.",
        )

    servico = validar_servico(
        db,
        agendamento.servico_id,
        usuario_logado,
    )

    novo_fim = nova_data_hora_inicio + timedelta(
        minutes=servico.tempo_medio_minutos or 30
    )

    verificar_conflito_horario(
        db=db,
        barbeiro_id=agendamento.barbeiro_id,
        inicio=nova_data_hora_inicio,
        fim=novo_fim,
        usuario_logado=usuario_logado,
        agendamento_id_ignorar=agendamento.id,
    )

    agendamento.data_hora_inicio = nova_data_hora_inicio
    agendamento.data_hora_fim = novo_fim
    agendamento.status = "reagendado"

    db.commit()
    db.refresh(agendamento)

    return agendamento


def calendario_agendamentos_service(
    db,
    usuario_logado,
    barbeiro_id=None,
    data_inicio=None,
    data_fim=None,
):
    query = consultar_da_barbearia(
        db=db,
        model=models.Agendamento,
        usuario=usuario_logado,
    )

    if barbeiro_id is not None:
        validar_barbeiro(db, barbeiro_id, usuario_logado)
        query = query.filter(
            models.Agendamento.barbeiro_id == barbeiro_id
        )

    if data_inicio:
        query = query.filter(
            models.Agendamento.data_hora_inicio >= data_inicio
        )

    if data_fim:
        query = query.filter(
            models.Agendamento.data_hora_inicio <= data_fim
        )

    agendamentos = query.order_by(
        models.Agendamento.data_hora_inicio.asc()
    ).all()

    eventos = []

    for agendamento in agendamentos:
        cliente_nome = (
            agendamento.cliente.nome
            if agendamento.cliente
            else "Cliente"
        )
        barbeiro_nome = (
            agendamento.barbeiro.nome
            if agendamento.barbeiro
            else "Barbeiro"
        )
        servico_nome = (
            agendamento.servico.nome
            if agendamento.servico
            else "Serviço"
        )

        status_atual = (agendamento.status or "").lower()
        cor = "#3B82F6"

        if status_atual == "cancelado":
            cor = "#EF4444"
        elif status_atual == "concluido":
            cor = "#10B981"
        elif status_atual == "reagendado":
            cor = "#F59E0B"

        eventos.append({
            "id": agendamento.id,
            "title": f"{cliente_nome} - {servico_nome}",
            "start": agendamento.data_hora_inicio,
            "end": agendamento.data_hora_fim,
            "status": agendamento.status,
            "barbeiro": barbeiro_nome,
            "color": cor,
        })

    return eventos
