from datetime import date, datetime, timedelta
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
import models
from schemas import AgendamentoCreate, AgendamentoResponse

from services.agendamento_service import criar_agendamento_service


router = APIRouter(
    prefix="/agendamento-online",
    tags=["Agendamento Online"]
)


class AgendamentoOnlineCreate(BaseModel):
    nome_cliente: str
    telefone_cliente: str
    barbeiro_id: int
    servico_id: int
    data_hora_inicio: datetime
    tipo_atendimento: str = "avulso"
    observacoes: str | None = None


@router.get("/barbeiros")
def listar_barbeiros_online(db: Session = Depends(get_db)):
    return db.query(models.Barbeiro).filter(
        models.Barbeiro.ativo == True
    ).order_by(models.Barbeiro.nome.asc()).all()


@router.get("/servicos")
def listar_servicos_online(db: Session = Depends(get_db)):
    return db.query(models.Servico).order_by(
        models.Servico.nome.asc()
    ).all()


@router.get("/horarios-dia")
def horarios_disponiveis_dia(
    servico_id: int = Query(...),
    data: date = Query(...),
    db: Session = Depends(get_db),
):
    servico = db.query(models.Servico).filter(
        models.Servico.id == servico_id
    ).first()

    if not servico:
        raise HTTPException(status_code=404, detail="Serviço não encontrado.")

    duracao = servico.tempo_medio_minutos or 30

    barbeiros = db.query(models.Barbeiro).filter(
        models.Barbeiro.ativo == True
    ).order_by(models.Barbeiro.nome.asc()).all()

    horarios_livres = []

    for barbeiro in barbeiros:
        horarios = gerar_horarios_livres_para_barbeiro(
            db=db,
            barbeiro_id=barbeiro.id,
            barbeiro_nome=barbeiro.nome,
            data_agenda=data,
            duracao=duracao,
        )

        horarios_livres.extend(horarios)

    horarios_livres.sort(key=lambda item: item["data_hora_inicio"])

    return horarios_livres


@router.get("/horarios-semana")
def horarios_disponiveis_semana(
    barbeiro_id: int = Query(...),
    servico_id: int = Query(...),
    data_inicio: date = Query(...),
    db: Session = Depends(get_db),
):
    barbeiro = db.query(models.Barbeiro).filter(
        models.Barbeiro.id == barbeiro_id,
        models.Barbeiro.ativo == True
    ).first()

    if not barbeiro:
        raise HTTPException(status_code=404, detail="Barbeiro não encontrado.")

    servico = db.query(models.Servico).filter(
        models.Servico.id == servico_id
    ).first()

    if not servico:
        raise HTTPException(status_code=404, detail="Serviço não encontrado.")

    duracao = servico.tempo_medio_minutos or 30

    semana = []

    for i in range(7):
        data_agenda = data_inicio + timedelta(days=i)

        horarios = gerar_horarios_livres_para_barbeiro(
            db=db,
            barbeiro_id=barbeiro.id,
            barbeiro_nome=barbeiro.nome,
            data_agenda=data_agenda,
            duracao=duracao,
        )

        semana.append({
            "data": data_agenda.isoformat(),
            "dia_semana": data_agenda.weekday(),
            "barbeiro_id": barbeiro.id,
            "barbeiro_nome": barbeiro.nome,
            "horarios": horarios,
        })

    return semana


@router.post("", response_model=AgendamentoResponse)
def criar_agendamento_online(
    dados: AgendamentoOnlineCreate,
    db: Session = Depends(get_db)
):
    cliente = obter_ou_criar_cliente_por_telefone(
        db=db,
        nome=dados.nome_cliente,
        telefone=dados.telefone_cliente
    )

    dados_agendamento = AgendamentoCreate(
        cliente_id=cliente.id,
        barbeiro_id=dados.barbeiro_id,
        servico_id=dados.servico_id,
        data_hora_inicio=dados.data_hora_inicio,
        tipo_atendimento=dados.tipo_atendimento,
        observacoes=dados.observacoes,
        origem="ONLINE"
    )

    return criar_agendamento_service(db, dados_agendamento)


@router.get("/consultar")
def consultar_agendamento(
    telefone: str,
    db: Session = Depends(get_db)
):
    telefone_limpo = re.sub(r"\D", "", telefone)

    clientes = db.query(models.Cliente).all()

    clientes_encontrados = []

    for cliente in clientes:
        telefone_cliente = re.sub(
            r"\D",
            "",
            cliente.telefone or ""
        )

        if telefone_cliente == telefone_limpo:
            clientes_encontrados.append(cliente)

    if not clientes_encontrados:
        raise HTTPException(
            status_code=404,
            detail="Nenhum agendamento encontrado."
        )

    ids_clientes = [
        cliente.id for cliente in clientes_encontrados
    ]

    agendamentos = (
        db.query(models.Agendamento)
        .filter(
            models.Agendamento.cliente_id.in_(ids_clientes),
            models.Agendamento.status != "CANCELADO",
            models.Agendamento.data_hora_inicio >= datetime.now()
        )
        .order_by(
            models.Agendamento.data_hora_inicio.asc()
        )
        .all()
    )

    resultado = []

    for agendamento in agendamentos:
        servico = None
        barbeiro = None

        if agendamento.servico_id:
            servico = db.query(models.Servico).filter(
                models.Servico.id == agendamento.servico_id
            ).first()

        if agendamento.barbeiro_id:
            barbeiro = db.query(models.Barbeiro).filter(
                models.Barbeiro.id == agendamento.barbeiro_id
            ).first()

        resultado.append({
            "id": agendamento.id,
            "servico": servico.nome if servico else "-",
            "barbeiro": barbeiro.nome if barbeiro else "-",
            "data_hora_inicio": agendamento.data_hora_inicio,
            "status": agendamento.status,
            "tipo_atendimento": agendamento.tipo_atendimento,
            "origem": agendamento.origem
        })

    return {
        "cliente": clientes_encontrados[0].nome,
        "telefone": clientes_encontrados[0].telefone,
        "agendamentos": resultado
    }


@router.put("/cancelar")
def cancelar_agendamento_online(
    telefone: str,
    agendamento_id: int,
    db: Session = Depends(get_db)
):
    telefone_limpo = re.sub(r"\D", "", telefone)

    clientes = db.query(models.Cliente).all()

    ids_clientes = []

    for cliente in clientes:
        telefone_cliente = re.sub(
            r"\D",
            "",
            cliente.telefone or ""
        )

        if telefone_cliente == telefone_limpo:
            ids_clientes.append(cliente.id)

    if not ids_clientes:
        raise HTTPException(
            status_code=404,
            detail="Cliente não encontrado para este telefone."
        )

    agendamento = (
        db.query(models.Agendamento)
        .filter(
            models.Agendamento.id == agendamento_id,
            models.Agendamento.cliente_id.in_(ids_clientes)
        )
        .first()
    )

    if not agendamento:
        raise HTTPException(
            status_code=404,
            detail="Agendamento não pertence ao telefone informado."
        )

    if agendamento.status.upper() == "CANCELADO":
        raise HTTPException(
            status_code=400,
            detail="Este agendamento já está cancelado."
        )

    if agendamento.data_hora_inicio <= datetime.now():
        raise HTTPException(
            status_code=400,
            detail="Não é possível cancelar agendamentos já iniciados ou passados."
        )

    observacao_atual = agendamento.observacoes or ""

    agendamento.status = "CANCELADO"
    agendamento.observacoes = (
        observacao_atual +
        "\nCancelado pelo cliente via portal online."
    )

    db.commit()
    db.refresh(agendamento)

    return {
        "mensagem": "Agendamento cancelado com sucesso.",
        "agendamento_id": agendamento.id,
        "status": agendamento.status
    }

def obter_ou_criar_cliente_por_telefone(
    db: Session,
    nome: str,
    telefone: str
):
    nome_limpo = nome.strip().upper()
    telefone_limpo = telefone.strip()

    if not nome_limpo:
        raise HTTPException(
            status_code=400,
            detail="Nome do cliente é obrigatório."
        )

    if not telefone_limpo:
        raise HTTPException(
            status_code=400,
            detail="Telefone do cliente é obrigatório."
        )

    telefone_apenas_numeros = re.sub(r"\D", "", telefone_limpo)

    clientes = db.query(models.Cliente).all()

    for cliente in clientes:
        telefone_cliente = re.sub(
            r"\D",
            "",
            cliente.telefone or ""
        )

        if telefone_cliente == telefone_apenas_numeros:
            return cliente

    novo_cliente = models.Cliente(
        nome=nome_limpo,
        telefone=telefone_limpo,
        email=None,
        observacoes="Cliente cadastrado automaticamente pelo agendamento online.",
        ativo=True
    )

    db.add(novo_cliente)
    db.commit()
    db.refresh(novo_cliente)

    return novo_cliente


def obter_horario_trabalho_barbeiro(
    db: Session,
    barbeiro_id: int,
    data_agenda: date
):
    dia_semana = data_agenda.weekday()

    config_padrao = db.query(
        models.ConfiguracaoFuncionamento
    ).filter(
        models.ConfiguracaoFuncionamento.dia_semana == dia_semana
    ).first()

    disponibilidade = db.query(
        models.BarbeiroDisponibilidade
    ).filter(
        models.BarbeiroDisponibilidade.barbeiro_id == barbeiro_id,
        models.BarbeiroDisponibilidade.dia_semana == dia_semana
    ).first()

    if disponibilidade and disponibilidade.usa_padrao is False:
        if disponibilidade.trabalha is False:
            return None

        return {
            "hora_inicio": disponibilidade.hora_inicio,
            "hora_fim": disponibilidade.hora_fim,
        }

    if not config_padrao:
        return None

    if config_padrao.trabalha is False:
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
    barbeiro_id: int,
    barbeiro_nome: str,
    data_agenda: date,
    duracao: int
):
    horario_trabalho = obter_horario_trabalho_barbeiro(
        db=db,
        barbeiro_id=barbeiro_id,
        data_agenda=data_agenda
    )

    if not horario_trabalho:
        return []

    hora_inicio = datetime.combine(
        data_agenda,
        converter_para_time(horario_trabalho["hora_inicio"])
    )

    hora_fim = datetime.combine(
        data_agenda,
        converter_para_time(horario_trabalho["hora_fim"])
    )

    intervalo = 30
    agora = datetime.now()

    agendamentos = db.query(models.Agendamento).filter(
        models.Agendamento.barbeiro_id == barbeiro_id,
        models.Agendamento.status != "CANCELADO",
        models.Agendamento.data_hora_inicio < hora_fim,
        models.Agendamento.data_hora_fim > hora_inicio,
    ).all()

    horarios = []
    atual = hora_inicio

    while atual + timedelta(minutes=duracao) <= hora_fim:
        inicio_novo = atual
        fim_novo = atual + timedelta(minutes=duracao)

        if inicio_novo >= agora:
            ocupado = False

            for agendamento in agendamentos:
                inicio_existente = agendamento.data_hora_inicio
                fim_existente = agendamento.data_hora_fim

                if inicio_novo < fim_existente and fim_novo > inicio_existente:
                    ocupado = True
                    break

            if not ocupado:
                horarios.append({
                    "horario": inicio_novo.strftime("%H:%M"),
                    "data": data_agenda.isoformat(),
                    "data_hora_inicio": inicio_novo.isoformat(),
                    "data_hora_fim": fim_novo.isoformat(),
                    "barbeiro_id": barbeiro_id,
                    "barbeiro_nome": barbeiro_nome,
                })

        atual += timedelta(minutes=intervalo)

    return horarios