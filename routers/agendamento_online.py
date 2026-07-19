from datetime import date, datetime, timedelta
import re
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
import models
from schemas import AgendamentoCreate, AgendamentoResponse
from services.agendamento_service import criar_agendamento_service
from services.barbeiro_disponibilidade_service import (
    buscar_disponibilidade_publica,
)
from services.configuracao_funcionamento_service import (
    buscar_configuracao_publica_por_dia,
)
from services.sequencia_service import gerar_codigo_comercial


router = APIRouter(
    prefix="/agendamento-online",
    tags=["Agendamento Online"],
)


class AgendamentoOnlineCreate(BaseModel):
    nome_cliente: str
    telefone_cliente: str
    barbeiro_id: int
    servico_id: int
    data_hora_inicio: datetime
    tipo_atendimento: str = "avulso"
    observacoes: str | None = None


def obter_barbearia_publica(
    db: Session,
    barbearia_slug: str,
) -> models.Barbearia:
    barbearia = (
        db.query(models.Barbearia)
        .filter(
            models.Barbearia.slug == barbearia_slug.strip().lower(),
            models.Barbearia.ativa.is_(True),
        )
        .first()
    )

    if not barbearia:
        raise HTTPException(
            status_code=404,
            detail="Barbearia não encontrada ou indisponível.",
        )

    return barbearia


def criar_contexto_publico(barbearia_id: int):
    return SimpleNamespace(
        perfil="publico",
        barbearia_id=barbearia_id,
    )


@router.get("/{barbearia_slug}/barbearia")
def consultar_barbearia_publica(
    barbearia_slug: str,
    db: Session = Depends(get_db),
):
    barbearia = obter_barbearia_publica(db, barbearia_slug)
    return {
        "id": barbearia.id,
        "codigo": barbearia.codigo,
        "slug": barbearia.slug,
        "nome": barbearia.nome,
        "telefone": barbearia.telefone,
        "telefone_whatsapp": barbearia.telefone_whatsapp,
        "endereco": barbearia.endereco,
        "cidade": barbearia.cidade,
        "estado": barbearia.estado,
        "instagram": barbearia.instagram,
        "logo_url": barbearia.logo_url,
        "slogan": barbearia.slogan,
        "imagem_capa_url": barbearia.imagem_capa_url,
        "cor_primaria": barbearia.cor_primaria,
        "cor_secundaria": barbearia.cor_secundaria,
        "cor_fundo": barbearia.cor_fundo,
        "cor_destaque": barbearia.cor_destaque,
    }


@router.get("/{barbearia_slug}/barbeiros")
def listar_barbeiros_online(
    barbearia_slug: str,
    db: Session = Depends(get_db),
):
    barbearia = obter_barbearia_publica(db, barbearia_slug)
    return (
        db.query(models.Barbeiro)
        .filter(
            models.Barbeiro.barbearia_id == barbearia.id,
            models.Barbeiro.ativo.is_(True),
        )
        .order_by(models.Barbeiro.nome.asc())
        .all()
    )


@router.get("/{barbearia_slug}/servicos")
def listar_servicos_online(
    barbearia_slug: str,
    db: Session = Depends(get_db),
):
    barbearia = obter_barbearia_publica(db, barbearia_slug)
    return (
        db.query(models.Servico)
        .filter(
            models.Servico.barbearia_id == barbearia.id,
            models.Servico.ativo.is_(True),
        )
        .order_by(models.Servico.nome.asc())
        .all()
    )


def validar_barbeiro_publico(
    db: Session,
    barbearia_id: int,
    barbeiro_id: int,
):
    barbeiro = (
        db.query(models.Barbeiro)
        .filter(
            models.Barbeiro.id == barbeiro_id,
            models.Barbeiro.barbearia_id == barbearia_id,
            models.Barbeiro.ativo.is_(True),
        )
        .first()
    )
    if not barbeiro:
        raise HTTPException(status_code=404, detail="Barbeiro não encontrado.")
    return barbeiro


def validar_servico_publico(
    db: Session,
    barbearia_id: int,
    servico_id: int,
):
    servico = (
        db.query(models.Servico)
        .filter(
            models.Servico.id == servico_id,
            models.Servico.barbearia_id == barbearia_id,
            models.Servico.ativo.is_(True),
        )
        .first()
    )
    if not servico:
        raise HTTPException(status_code=404, detail="Serviço não encontrado.")
    return servico


@router.get("/{barbearia_slug}/horarios-dia")
def horarios_disponiveis_dia(
    barbearia_slug: str,
    servico_id: int = Query(...),
    data: date = Query(...),
    db: Session = Depends(get_db),
):
    barbearia = obter_barbearia_publica(db, barbearia_slug)
    servico = validar_servico_publico(db, barbearia.id, servico_id)

    barbeiros = (
        db.query(models.Barbeiro)
        .filter(
            models.Barbeiro.barbearia_id == barbearia.id,
            models.Barbeiro.ativo.is_(True),
        )
        .order_by(models.Barbeiro.nome.asc())
        .all()
    )

    horarios_livres = []
    for barbeiro in barbeiros:
        horarios_livres.extend(
            gerar_horarios_livres_para_barbeiro(
                db=db,
                barbearia_id=barbearia.id,
                barbeiro_id=barbeiro.id,
                barbeiro_nome=barbeiro.nome,
                data_agenda=data,
                duracao=servico.tempo_medio_minutos or 30,
            )
        )

    horarios_livres.sort(key=lambda item: item["data_hora_inicio"])
    return horarios_livres


@router.get("/{barbearia_slug}/horarios-semana")
def horarios_disponiveis_semana(
    barbearia_slug: str,
    barbeiro_id: int = Query(...),
    servico_id: int = Query(...),
    data_inicio: date = Query(...),
    db: Session = Depends(get_db),
):
    barbearia = obter_barbearia_publica(db, barbearia_slug)
    barbeiro = validar_barbeiro_publico(db, barbearia.id, barbeiro_id)
    servico = validar_servico_publico(db, barbearia.id, servico_id)

    semana = []
    for indice in range(7):
        data_agenda = data_inicio + timedelta(days=indice)
        horarios = gerar_horarios_livres_para_barbeiro(
            db=db,
            barbearia_id=barbearia.id,
            barbeiro_id=barbeiro.id,
            barbeiro_nome=barbeiro.nome,
            data_agenda=data_agenda,
            duracao=servico.tempo_medio_minutos or 30,
        )
        semana.append({
            "data": data_agenda.isoformat(),
            "dia_semana": data_agenda.weekday(),
            "barbeiro_id": barbeiro.id,
            "barbeiro_nome": barbeiro.nome,
            "horarios": horarios,
        })

    return semana


@router.post("/{barbearia_slug}", response_model=AgendamentoResponse)
def criar_agendamento_online(
    barbearia_slug: str,
    dados: AgendamentoOnlineCreate,
    db: Session = Depends(get_db),
):
    barbearia = obter_barbearia_publica(db, barbearia_slug)
    validar_barbeiro_publico(db, barbearia.id, dados.barbeiro_id)
    validar_servico_publico(db, barbearia.id, dados.servico_id)

    cliente = obter_ou_criar_cliente_por_telefone(
        db=db,
        barbearia=barbearia,
        nome=dados.nome_cliente,
        telefone=dados.telefone_cliente,
    )

    dados_agendamento = AgendamentoCreate(
        cliente_id=cliente.id,
        barbeiro_id=dados.barbeiro_id,
        servico_id=dados.servico_id,
        data_hora_inicio=dados.data_hora_inicio,
        tipo_atendimento=dados.tipo_atendimento,
        observacoes=dados.observacoes,
        origem="ONLINE",
    )

    return criar_agendamento_service(
        db=db,
        dados=dados_agendamento,
        usuario_logado=criar_contexto_publico(barbearia.id),
    )


@router.get("/{barbearia_slug}/consultar")
def consultar_agendamento(
    barbearia_slug: str,
    telefone: str,
    db: Session = Depends(get_db),
):
    barbearia = obter_barbearia_publica(db, barbearia_slug)
    cliente = buscar_cliente_por_telefone(db, barbearia.id, telefone)

    if not cliente:
        raise HTTPException(
            status_code=404,
            detail="Nenhum agendamento encontrado.",
        )

    agendamentos = (
        db.query(models.Agendamento)
        .filter(
            models.Agendamento.barbearia_id == barbearia.id,
            models.Agendamento.cliente_id == cliente.id,
            func.lower(models.Agendamento.status) != "cancelado",
            models.Agendamento.data_hora_inicio >= datetime.now(),
        )
        .order_by(models.Agendamento.data_hora_inicio.asc())
        .all()
    )

    resultado = [{
        "id": item.id,
        "servico": item.servico.nome if item.servico else "-",
        "barbeiro": item.barbeiro.nome if item.barbeiro else "-",
        "data_hora_inicio": item.data_hora_inicio,
        "status": item.status,
        "tipo_atendimento": item.tipo_atendimento,
        "origem": item.origem,
    } for item in agendamentos]

    return {
        "cliente": cliente.nome,
        "telefone": cliente.telefone,
        "agendamentos": resultado,
    }


@router.put("/{barbearia_slug}/cancelar")
def cancelar_agendamento_online(
    barbearia_slug: str,
    telefone: str,
    agendamento_id: int,
    db: Session = Depends(get_db),
):
    barbearia = obter_barbearia_publica(db, barbearia_slug)
    cliente = buscar_cliente_por_telefone(db, barbearia.id, telefone)

    if not cliente:
        raise HTTPException(
            status_code=404,
            detail="Cliente não encontrado para este telefone.",
        )

    agendamento = (
        db.query(models.Agendamento)
        .filter(
            models.Agendamento.id == agendamento_id,
            models.Agendamento.barbearia_id == barbearia.id,
            models.Agendamento.cliente_id == cliente.id,
        )
        .first()
    )

    if not agendamento:
        raise HTTPException(
            status_code=404,
            detail="Agendamento não pertence ao telefone informado.",
        )
    if (agendamento.status or "").lower() == "cancelado":
        raise HTTPException(status_code=400, detail="Agendamento já cancelado.")
    if agendamento.data_hora_inicio <= datetime.now():
        raise HTTPException(
            status_code=400,
            detail="Não é possível cancelar agendamentos passados.",
        )

    observacao = agendamento.observacoes or ""
    agendamento.status = "cancelado"
    agendamento.observacoes = (
        observacao + "\nCancelado pelo cliente via portal online."
    ).strip()
    db.commit()
    db.refresh(agendamento)

    return {
        "mensagem": "Agendamento cancelado com sucesso.",
        "agendamento_id": agendamento.id,
        "status": agendamento.status,
    }


def normalizar_telefone(telefone: str) -> str:
    return re.sub(r"\D", "", telefone or "")


def buscar_cliente_por_telefone(
    db: Session,
    barbearia_id: int,
    telefone: str,
):
    telefone_limpo = normalizar_telefone(telefone)
    if not telefone_limpo:
        return None

    clientes = (
        db.query(models.Cliente)
        .filter(models.Cliente.barbearia_id == barbearia_id)
        .all()
    )

    return next(
        (
            cliente
            for cliente in clientes
            if normalizar_telefone(cliente.telefone) == telefone_limpo
        ),
        None,
    )


def obter_ou_criar_cliente_por_telefone(
    db: Session,
    barbearia: models.Barbearia,
    nome: str,
    telefone: str,
):
    nome_limpo = (nome or "").strip().upper()
    telefone_limpo = normalizar_telefone(telefone)

    if len(nome_limpo) < 2:
        raise HTTPException(status_code=400, detail="Nome do cliente inválido.")
    if not telefone_limpo:
        raise HTTPException(status_code=400, detail="Telefone obrigatório.")

    cliente = buscar_cliente_por_telefone(
        db,
        barbearia.id,
        telefone_limpo,
    )
    if cliente:
        return cliente

    numero, codigo = gerar_codigo_comercial(
        db=db,
        barbearia=barbearia,
        tipo="CLIENTE",
    )
    novo_cliente = models.Cliente(
        barbearia_id=barbearia.id,
        numero_sequencial=numero,
        codigo=codigo,
        nome=nome_limpo,
        telefone=telefone_limpo,
        email=None,
        observacoes=(
            "Cliente cadastrado automaticamente pelo agendamento online."
        ),
        ativo=True,
    )
    db.add(novo_cliente)
    db.commit()
    db.refresh(novo_cliente)
    return novo_cliente


def obter_horario_trabalho_barbeiro(
    db: Session,
    barbearia_id: int,
    barbeiro_id: int,
    data_agenda: date,
):
    dia_semana = data_agenda.weekday()
    config_padrao = buscar_configuracao_publica_por_dia(
        db=db,
        barbearia_id=barbearia_id,
        dia_semana=dia_semana,
    )
    disponibilidade = buscar_disponibilidade_publica(
        db=db,
        barbearia_id=barbearia_id,
        barbeiro_id=barbeiro_id,
        dia_semana=dia_semana,
    )

    if disponibilidade and disponibilidade.usa_padrao is False:
        if disponibilidade.trabalha is False:
            return None
        return {
            "hora_inicio": disponibilidade.hora_inicio,
            "hora_fim": disponibilidade.hora_fim,
        }

    if not config_padrao or config_padrao.trabalha is False:
        return None
    return {
        "hora_inicio": config_padrao.hora_inicio,
        "hora_fim": config_padrao.hora_fim,
    }


def converter_para_time(valor):
    if hasattr(valor, "hour") and hasattr(valor, "minute"):
        return valor
    valor_str = str(valor)
    try:
        return datetime.strptime(valor_str, "%H:%M").time()
    except ValueError:
        return datetime.strptime(valor_str, "%H:%M:%S").time()


def gerar_horarios_livres_para_barbeiro(
    db: Session,
    barbearia_id: int,
    barbeiro_id: int,
    barbeiro_nome: str,
    data_agenda: date,
    duracao: int,
):
    horario_trabalho = obter_horario_trabalho_barbeiro(
        db=db,
        barbearia_id=barbearia_id,
        barbeiro_id=barbeiro_id,
        data_agenda=data_agenda,
    )
    if not horario_trabalho:
        return []

    hora_inicio = datetime.combine(
        data_agenda,
        converter_para_time(horario_trabalho["hora_inicio"]),
    )
    hora_fim = datetime.combine(
        data_agenda,
        converter_para_time(horario_trabalho["hora_fim"]),
    )
    agora = datetime.now()

    agendamentos = (
        db.query(models.Agendamento)
        .filter(
            models.Agendamento.barbearia_id == barbearia_id,
            models.Agendamento.barbeiro_id == barbeiro_id,
            func.lower(models.Agendamento.status) != "cancelado",
            models.Agendamento.data_hora_inicio < hora_fim,
            models.Agendamento.data_hora_fim > hora_inicio,
        )
        .all()
    )

    horarios = []
    atual = hora_inicio
    while atual + timedelta(minutes=duracao) <= hora_fim:
        fim_novo = atual + timedelta(minutes=duracao)
        ocupado = any(
            atual < item.data_hora_fim
            and fim_novo > item.data_hora_inicio
            for item in agendamentos
        )

        if atual >= agora and not ocupado:
            horarios.append({
                "horario": atual.strftime("%H:%M"),
                "data": data_agenda.isoformat(),
                "data_hora_inicio": atual.isoformat(),
                "data_hora_fim": fim_novo.isoformat(),
                "barbeiro_id": barbeiro_id,
                "barbeiro_nome": barbeiro_nome,
            })

        atual += timedelta(minutes=30)

    return horarios
