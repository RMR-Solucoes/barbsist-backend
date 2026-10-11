from datetime import date, datetime, time, timedelta

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func

import models
from services.adequacao_plano_saas_service import validar_barbeiro_liberado_por_plano

from auth.tenant import (
    buscar_da_barbearia,
    consultar_da_barbearia,
    obter_barbearia_id,
)
from services.disponibilidade_service import validar_agendamento_no_expediente


STATUS_COM_CONFLITO = (
    "agendado",
    "confirmado",
    "em_atendimento",
    "reagendado",
)


def _obter_barbeiro_id_restrito(
    usuario_logado,
    barbeiro_id_solicitado=None,
):
    """Restringe o perfil barbeiro ao profissional vinculado."""
    perfil = (
        getattr(usuario_logado, "perfil", "") or ""
    ).strip().lower()

    if perfil != "barbeiro":
        return None

    barbeiro_id = getattr(
        usuario_logado,
        "barbeiro_id",
        None,
    )

    if barbeiro_id is None:
        raise HTTPException(
            status_code=403,
            detail=(
                "Usuário barbeiro não está vinculado "
                "a um barbeiro."
            ),
        )

    if (
        barbeiro_id_solicitado is not None
        and barbeiro_id_solicitado != barbeiro_id
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "O barbeiro só pode administrar "
                "os próprios agendamentos."
            ),
        )

    return barbeiro_id


def _validar_acesso_barbeiro_agendamento(
    usuario_logado,
    agendamento,
):
    barbeiro_id = _obter_barbeiro_id_restrito(
        usuario_logado
    )

    if (
        barbeiro_id is not None
        and agendamento.barbeiro_id != barbeiro_id
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "O barbeiro só pode administrar "
                "os próprios agendamentos."
            ),
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


def validar_estilo(db, estilo_id, nome_campo, usuario_logado):
    if estilo_id is None:
        return None

    estilo = buscar_da_barbearia(
        db=db, model=models.Estilo, registro_id=estilo_id, usuario=usuario_logado,
        mensagem_nao_encontrado=f"{nome_campo} não encontrado ou inativo.",
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



# BARBSIST_MULTI_SERVICE_M2_HELPERS
def _normalizar_servicos_ids_agendamento(dados):
    ids_informados = list(getattr(dados, "servicos_ids", None) or [])
    legado = getattr(dados, "servico_id", None)

    if not ids_informados and legado is not None:
        ids_informados = [legado]

    resultado = []
    vistos = set()

    for valor in ids_informados:
        try:
            servico_id = int(valor)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail="Identificador de servico invalido.",
            )

        if servico_id <= 0:
            raise HTTPException(
                status_code=400,
                detail="Identificador de servico invalido.",
            )

        if servico_id not in vistos:
            vistos.add(servico_id)
            resultado.append(servico_id)

    if not resultado:
        raise HTTPException(
            status_code=400,
            detail="Selecione pelo menos um servico.",
        )

    return resultado


def _validar_servicos_agendamento(
    db,
    servicos_ids,
    usuario_logado,
):
    return [
        validar_servico(
            db,
            servico_id,
            usuario_logado,
        )
        for servico_id in servicos_ids
    ]


def _carregar_servicos_agendamento(
    db,
    agendamento,
    usuario_logado,
):
    vinculos = (
        db.query(models.AgendamentoServico)
        .filter(
            models.AgendamentoServico.agendamento_id
            == agendamento.id
        )
        .order_by(
            models.AgendamentoServico.ordem.asc(),
            models.AgendamentoServico.id.asc(),
        )
        .all()
    )

    if vinculos:
        resultado = []
        for vinculo in vinculos:
            servico = validar_servico(
                db,
                vinculo.servico_id,
                usuario_logado,
            )
            resultado.append((vinculo, servico))
        return resultado

    servico = validar_servico(
        db,
        agendamento.servico_id,
        usuario_logado,
    )
    return [(None, servico)]


def _duracao_total_servicos_catalogo(servicos):
    return sum(
        (servico.tempo_medio_minutos or 30)
        for servico in servicos
    )


def _duracao_total_agendamento(
    db,
    agendamento,
    usuario_logado,
):
    total = 0

    for vinculo, servico in _carregar_servicos_agendamento(
        db,
        agendamento,
        usuario_logado,
    ):
        if vinculo is not None:
            duracao = (
                vinculo.duracao_minutos_snapshot
                or servico.tempo_medio_minutos
                or 30
            )
        else:
            duracao = servico.tempo_medio_minutos or 30

        total += duracao

    return total


def _preco_vinculo_ou_catalogo(vinculo, servico):
    if vinculo is not None and vinculo.preco_snapshot is not None:
        return vinculo.preco_snapshot
    return servico.preco


def criar_agendamento_service(db, dados, usuario_logado):
    barbearia_id = obter_barbearia_id(usuario_logado)

    _obter_barbeiro_id_restrito(
        usuario_logado,
        dados.barbeiro_id,
    )

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
    try:
        validar_barbeiro_liberado_por_plano(db, barbearia_id, dados.barbeiro_id)
    except ValueError as erro:
        raise HTTPException(status_code=403, detail=str(erro))
    servicos_ids = _normalizar_servicos_ids_agendamento(dados)
    servicos = _validar_servicos_agendamento(
        db,
        servicos_ids,
        usuario_logado,
    )
    servico = servicos[0]

    validar_estilo(db, dados.estilo_corte_id, "Estilo de corte", usuario_logado)
    validar_estilo(db, dados.estilo_barba_id, "Estilo de barba", usuario_logado)

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

        usos_necessarios = len(servicos)
        if (assinatura.usos_disponiveis or 0) < usos_necessarios:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Plano sem usos suficientes para os serviÃ§os selecionados. "
                    f"NecessÃ¡rios: {usos_necessarios}. "
                    f"DisponÃ­veis: {assinatura.usos_disponiveis or 0}."
                ),
            )

        servicos_no_plano = {
            item[0]
            for item in (
                db.query(models.PlanoServico.servico_id)
                .join(
                    models.Plano,
                    models.Plano.id == models.PlanoServico.plano_id,
                )
                .filter(
                    models.PlanoServico.plano_id == assinatura.plano_id,
                    models.PlanoServico.servico_id.in_(servicos_ids),
                    models.Plano.barbearia_id == barbearia_id,
                )
                .all()
            )
        }

        servicos_fora_plano = [
            servico_item.id
            for servico_item in servicos
            if servico_item.id not in servicos_no_plano
        ]

        if servicos_fora_plano:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Todos os serviÃ§os selecionados devem estar incluÃ­dos "
                    "no plano do cliente."
                ),
            )

    inicio = dados.data_hora_inicio
    duracao_total = _duracao_total_servicos_catalogo(servicos)
    fim = inicio + timedelta(minutes=duracao_total)

    validar_agendamento_no_expediente(
        db=db,
        barbearia_id=barbearia_id,
        barbeiro_id=dados.barbeiro_id,
        inicio=inicio,
        fim=fim,
    )

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
        servico_id=servicos_ids[0],
        estilo_corte_id=dados.estilo_corte_id,
        estilo_barba_id=dados.estilo_barba_id,
        data_hora_inicio=inicio,
        data_hora_fim=fim,
        status="agendado",
        observacoes=dados.observacoes,
        tipo_atendimento=tipo_atendimento,
        origem=getattr(dados, "origem", "INTERNO") or "INTERNO",
    )

    try:
        db.add(agendamento)
        db.flush()

        for ordem, servico_item in enumerate(servicos, start=1):
            db.add(
                models.AgendamentoServico(
                    agendamento_id=agendamento.id,
                    servico_id=servico_item.id,
                    ordem=ordem,
                    preco_snapshot=servico_item.preco,
                    duracao_minutos_snapshot=(
                        servico_item.tempo_medio_minutos or 30
                    ),
                )
            )

        db.commit()
        db.refresh(agendamento)

    except Exception:
        db.rollback()
        raise

    return agendamento


def listar_agendamentos_service(db, usuario_logado):
    query = consultar_da_barbearia(
        db=db,
        model=models.Agendamento,
        usuario=usuario_logado,
    )

    barbeiro_id = _obter_barbeiro_id_restrito(
        usuario_logado
    )

    if barbeiro_id is not None:
        query = query.filter(
            models.Agendamento.barbeiro_id == barbeiro_id
        )

    return (
        query
        .order_by(models.Agendamento.data_hora_inicio.asc())
        .all()
    )


# BARBSIST_M5_3_CANCELAMENTO_FIX
def buscar_agendamento_service(db, agendamento_id: int, usuario_logado):
    agendamento = buscar_da_barbearia(
        db=db,
        model=models.Agendamento,
        registro_id=agendamento_id,
        usuario=usuario_logado,
        mensagem_nao_encontrado="Agendamento não encontrado.",
    )


    _validar_acesso_barbeiro_agendamento(
        usuario_logado,
        agendamento,
    )

    return agendamento


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
    barbeiro_id_restrito = _obter_barbeiro_id_restrito(
        usuario_logado,
        barbeiro_id,
    )

    if barbeiro_id_restrito is not None:
        barbeiro_id = barbeiro_id_restrito

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

    if status_normalizado == "em_atendimento":
        try:
            validar_barbeiro_liberado_por_plano(
                db, obter_barbearia_id(usuario_logado), agendamento.barbeiro_id
            )
        except ValueError as erro:
            raise HTTPException(status_code=403, detail=str(erro))

    atual = (agendamento.status or "").strip().lower()
    transicoes = {
        "agendado": {"confirmado", "em_atendimento", "cancelado", "nao_compareceu", "reagendado"},
        "confirmado": {"em_atendimento", "cancelado", "nao_compareceu", "reagendado"},
        "reagendado": {"confirmado", "em_atendimento", "cancelado", "nao_compareceu", "reagendado"},
        "em_atendimento": {"concluido", "cancelado"},
        "concluido": set(),
        "cancelado": set(),
        "nao_compareceu": set(),
    }

    if status_normalizado != atual and status_normalizado not in transicoes.get(atual, set()):
        raise HTTPException(
            status_code=400,
            detail=f"Transição de status inválida: {atual} -> {status_normalizado}.",
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

    # Serializa a conversão no PostgreSQL.
    agendamento = (
        db.query(models.Agendamento)
        .filter(
            models.Agendamento.id == agendamento_id,
            models.Agendamento.barbearia_id == barbearia_id,
        )
        .with_for_update()
        .first()
    )

    if agendamento is None:
        raise HTTPException(
            status_code=404,
            detail="Agendamento não encontrado.",
        )

    _validar_acesso_barbeiro_agendamento(
        usuario_logado,
        agendamento,
    )

    comanda_existente = (
        db.query(models.Comanda)
        .filter(
            models.Comanda.agendamento_id == agendamento.id
        )
        .first()
    )

    if comanda_existente is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Este agendamento já foi convertido em comanda "
                f"#{comanda_existente.id}."
            ),
        )

    if (agendamento.status or "").lower() in (
        "cancelado",
        "concluido",
        "nao_compareceu",
        "em_atendimento",
    ):
        raise HTTPException(
            status_code=400,
            detail="Agendamento não pode ser convertido em comanda.",
        )

    servicos_agendamento = _carregar_servicos_agendamento(
        db,
        agendamento,
        usuario_logado,
    )

    try:
        comanda = models.Comanda(
            barbearia_id=barbearia_id,
            agendamento_id=agendamento.id,
            cliente_id=agendamento.cliente_id,
            barbeiro_id=agendamento.barbeiro_id,
            status="aberta",
            total=0,
        )

        db.add(comanda)
        db.flush()

        total_comanda = 0

        for vinculo, servico_item in servicos_agendamento:
            preco_item = _preco_vinculo_ou_catalogo(
                vinculo,
                servico_item,
            )

            item = models.ItemComanda(
                comanda_id=comanda.id,
                tipo="servico",
                descricao=servico_item.nome,
                quantidade=1,
                valor_unitario=preco_item,
                subtotal=preco_item,
                servico_id=servico_item.id,
            )

            db.add(item)
            total_comanda += preco_item

        comanda.total = total_comanda
        agendamento.status = "em_atendimento"
        db.commit()
        db.refresh(comanda)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Este agendamento já possui uma comanda.",
        )

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

    status_atual = (agendamento.status or "").lower()
    if status_atual in ("cancelado", "concluido", "nao_compareceu", "em_atendimento"):
        raise HTTPException(
            status_code=400,
            detail="Agendamento neste status não pode ser reagendado.",
        )

    duracao_total = _duracao_total_agendamento(
        db,
        agendamento,
        usuario_logado,
    )

    try:
        validar_barbeiro_liberado_por_plano(
            db, obter_barbearia_id(usuario_logado), agendamento.barbeiro_id
        )
    except ValueError as erro:
        raise HTTPException(status_code=403, detail=str(erro))

    novo_fim = nova_data_hora_inicio + timedelta(
        minutes=duracao_total
    )

    validar_agendamento_no_expediente(
        db=db,
        barbearia_id=obter_barbearia_id(usuario_logado),
        barbeiro_id=agendamento.barbeiro_id,
        inicio=nova_data_hora_inicio,
        fim=novo_fim,
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
    barbeiro_id_restrito = _obter_barbeiro_id_restrito(
        usuario_logado,
        barbeiro_id,
    )

    if barbeiro_id_restrito is not None:
        barbeiro_id = barbeiro_id_restrito

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
