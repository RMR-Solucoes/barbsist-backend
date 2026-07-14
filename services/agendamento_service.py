from datetime import datetime, timedelta, date, time
from fastapi import HTTPException 
import models


def validar_cliente(db, cliente_id):
    if cliente_id is None:
        return None

    cliente = db.query(models.Cliente).filter(
        models.Cliente.id == cliente_id,
        models.Cliente.ativo == True
    ).first()

    if not cliente:
        raise HTTPException(
            status_code=404,
            detail="Cliente não encontrado ou inativo"
        )

    return cliente


def validar_barbeiro(db, barbeiro_id):
    barbeiro = db.query(models.Barbeiro).filter(
        models.Barbeiro.id == barbeiro_id,
        models.Barbeiro.ativo == True
    ).first()

    if not barbeiro:
        raise HTTPException(
            status_code=404,
            detail="Barbeiro não encontrado ou inativo"
        )

    return barbeiro


def validar_servico(db, servico_id):
    servico = db.query(models.Servico).filter(
        models.Servico.id == servico_id,
        models.Servico.ativo == True
    ).first()

    if not servico:
        raise HTTPException(
            status_code=404,
            detail="Serviço não encontrado ou inativo"
        )

    return servico


def validar_estilo(db, estilo_id, nome_campo):
    if estilo_id is None:
        return None

    estilo = db.query(models.Estilo).filter(
        models.Estilo.id == estilo_id,
        models.Estilo.ativo == True
    ).first()

    if not estilo:
        raise HTTPException(
            status_code=404,
            detail=f"{nome_campo} não encontrado ou inativo"
        )

    return estilo


def verificar_conflito_horario(
    db,
    barbeiro_id: int,
    inicio,
    fim,
    agendamento_id_ignorar: int | None = None
):
    query = db.query(models.Agendamento).filter(
        models.Agendamento.barbeiro_id == barbeiro_id,
        models.Agendamento.status.in_([
            "agendado",
            "confirmado",
            "em_atendimento"
        ]),
        models.Agendamento.data_hora_inicio < fim,
        models.Agendamento.data_hora_fim > inicio
    )

    if agendamento_id_ignorar is not None:
        query = query.filter(
            models.Agendamento.id != agendamento_id_ignorar
        )

    conflito = query.first()

    if conflito:
        raise HTTPException(
            status_code=400,
            detail="Já existe agendamento para este barbeiro nesse horário"
        )


def criar_agendamento_service(db, dados):
    cliente = validar_cliente(db, dados.cliente_id)
    validar_barbeiro(db, dados.barbeiro_id)
    servico = validar_servico(db, dados.servico_id)

    validar_estilo(db, dados.estilo_corte_id, "Estilo de corte")
    validar_estilo(db, dados.estilo_barba_id, "Estilo de barba")

    tipo_atendimento = getattr(dados, "tipo_atendimento", "avulso")

    if tipo_atendimento not in ["plano", "avulso"]:
        raise HTTPException(
            status_code=400,
            detail="Tipo de atendimento inválido. Use 'plano' ou 'avulso'."
        )

    assinatura = db.query(models.AssinaturaCliente).filter(
        models.AssinaturaCliente.cliente_id == dados.cliente_id
    ).order_by(
        models.AssinaturaCliente.id.desc()
    ).first()

    # 1. Cliente sem plano → pode agendar avulso
    if not assinatura:
        tipo_atendimento = "avulso"

    # 2, 3 e 4. Cliente com plano
    if assinatura:
        if tipo_atendimento == "plano":
            if assinatura.status != "ativo":
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Plano inativo, vencido ou inadimplente. "
                        "Regularize o pagamento ou escolha atendimento avulso."
                    )
                )

            if assinatura.data_fim and assinatura.data_fim.date() < date.today():
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Plano vencido. Regularize o pagamento "
                        "ou escolha atendimento avulso."
                    )
                )

            if assinatura.usos_disponiveis <= 0:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Plano sem usos disponíveis. "
                        "Escolha atendimento avulso."
                    )
                )

        elif tipo_atendimento == "avulso":
            pass

    inicio = dados.data_hora_inicio
    fim = inicio + timedelta(minutes=servico.tempo_medio_minutos)

    verificar_conflito_horario(
        db=db,
        barbeiro_id=dados.barbeiro_id,
        inicio=inicio,
        fim=fim
    )

    agendamento = models.Agendamento(
        cliente_id=dados.cliente_id,
        barbeiro_id=dados.barbeiro_id,
        servico_id=dados.servico_id,
        estilo_corte_id=dados.estilo_corte_id,
        estilo_barba_id=dados.estilo_barba_id,
        data_hora_inicio=inicio,
        data_hora_fim=fim,
        status="agendado",
        observacoes=dados.observacoes,
        tipo_atendimento=tipo_atendimento
    )

    db.add(agendamento)
    db.commit()
    db.refresh(agendamento)

    return agendamento


def listar_agendamentos_service(db):
    return db.query(models.Agendamento).all()


def buscar_agendamento_service(db, agendamento_id: int):
    agendamento = db.query(models.Agendamento).filter(
        models.Agendamento.id == agendamento_id
    ).first()

    if not agendamento:
        raise HTTPException(
            status_code=404,
            detail="Agendamento não encontrado"
        )

    return agendamento


def cancelar_agendamento_service(db, agendamento_id: int):
    agendamento = buscar_agendamento_service(db, agendamento_id)

    if agendamento.status in ["concluido", "cancelado"]:
        raise HTTPException(
            status_code=400,
            detail="Agendamento já está concluído ou cancelado"
        )

    agendamento.status = "cancelado"

    db.commit()
    db.refresh(agendamento)

    return agendamento

def listar_agendamentos_por_filtro_service(
    db,
    data_agenda=None,
    barbeiro_id=None
):
    query = db.query(models.Agendamento)

    if data_agenda:
        inicio_dia = datetime.combine(data_agenda, time.min)
        fim_dia = datetime.combine(data_agenda, time.max)

        query = query.filter(
            models.Agendamento.data_hora_inicio >= inicio_dia,
            models.Agendamento.data_hora_inicio <= fim_dia
        )

    if barbeiro_id:
        query = query.filter(
            models.Agendamento.barbeiro_id == barbeiro_id
        )

    return query.order_by(
        models.Agendamento.data_hora_inicio.asc()
    ).all()


def atualizar_status_agendamento_service(db, agendamento_id: int, status: str):
    status_validos = [
        "agendado",
        "confirmado",
        "em_atendimento",
        "concluido",
        "cancelado",
        "nao_compareceu"
    ]

    if status not in status_validos:
        raise HTTPException(
            status_code=400,
            detail="Status inválido"
        )

    agendamento = buscar_agendamento_service(db, agendamento_id)

    agendamento.status = status

    db.commit()
    db.refresh(agendamento)

    return agendamento


def converter_agendamento_em_comanda_service(db, agendamento_id: int):
    agendamento = buscar_agendamento_service(db, agendamento_id)

    if agendamento.status in ["cancelado", "concluido", "nao_compareceu"]:
        raise HTTPException(
            status_code=400,
            detail="Agendamento não pode ser convertido em comanda"
        )

    comanda = models.Comanda(
        cliente_id=agendamento.cliente_id,
        barbeiro_id=agendamento.barbeiro_id,
        status="aberta",
        total=0
    )

    db.add(comanda)
    db.flush()

    servico = db.query(models.Servico).filter(
        models.Servico.id == agendamento.servico_id,
        models.Servico.ativo == True
    ).first()

    if not servico:
        raise HTTPException(
            status_code=404,
            detail="Serviço do agendamento não encontrado"
        )

    item = models.ItemComanda(
        comanda_id=comanda.id,
        tipo="servico",
        descricao=servico.nome,
        quantidade=1,
        valor_unitario=servico.preco,
        subtotal=servico.preco,
        servico_id=servico.id
    )

    comanda.total = servico.preco
    agendamento.status = "em_atendimento"

    db.add(item)
    db.commit()
    db.refresh(comanda)

    return {
        "mensagem": "Agendamento convertido em comanda com sucesso",
        "agendamento_id": agendamento.id,
        "comanda_id": comanda.id,
        "status_agendamento": agendamento.status,
        "total_comanda": comanda.total
    }

def reagendar_agendamento_service(
    db,
    agendamento_id: int,
    nova_data_hora_inicio
):
    agendamento = db.query(models.Agendamento).filter(
        models.Agendamento.id == agendamento_id
    ).first()

    if not agendamento:
        raise HTTPException(
            status_code=404,
            detail="Agendamento não encontrado"
        )

    if agendamento.status == "cancelado":
        raise HTTPException(
            status_code=400,
            detail="Agendamento cancelado não pode ser reagendado"
        )

    servico = db.query(models.Servico).filter(
        models.Servico.id == agendamento.servico_id
    ).first()

    duracao = servico.tempo_medio_minutos

    novo_fim = (
        nova_data_hora_inicio +
        timedelta(minutes=duracao)
    )

    conflito = db.query(models.Agendamento).filter(
        models.Agendamento.barbeiro_id == agendamento.barbeiro_id,
        models.Agendamento.id != agendamento.id,
        models.Agendamento.status != "cancelado",
        models.Agendamento.data_hora_inicio < novo_fim,
        models.Agendamento.data_hora_fim > nova_data_hora_inicio
    ).first()

    if conflito:
        raise HTTPException(
            status_code=400,
            detail="Já existe agendamento neste horário"
        )

    agendamento.data_hora_inicio = nova_data_hora_inicio
    agendamento.data_hora_fim = novo_fim
    agendamento.status = "reagendado"

    db.commit()
    db.refresh(agendamento)

    return agendamento

def calendario_agendamentos_service(
    db,
    barbeiro_id=None,
    data_inicio=None,
    data_fim=None
):
    query = db.query(models.Agendamento)

    if barbeiro_id:
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

    agendamentos = query.all()

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

        cor = "#3B82F6"

        if agendamento.status == "cancelado":
            cor = "#EF4444"

        elif agendamento.status == "concluido":
            cor = "#10B981"

        elif agendamento.status == "reagendado":
            cor = "#F59E0B"

        eventos.append({
            "id": agendamento.id,

            "title": f"{cliente_nome} - {servico_nome}",

            "start": agendamento.data_hora_inicio,
            "end": agendamento.data_hora_fim,

            "status": agendamento.status,

            "barbeiro": barbeiro_nome,

            "color": cor
        })

    return eventos