from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from schemas import AgendamentoCreate, AgendamentoResponse, AtualizarStatusAgendamento, ReagendarAgendamentoRequest

from services.agendamento_service import (
    criar_agendamento_service,
    listar_agendamentos_service,
    buscar_agendamento_service,
    cancelar_agendamento_service,
    listar_agendamentos_por_filtro_service,
    atualizar_status_agendamento_service,
    converter_agendamento_em_comanda_service,
    reagendar_agendamento_service,
    calendario_agendamentos_service
)

from auth.permissions import (
    admin_ou_gerente,
    admin_gerente_ou_recepcao,
    admin_gerente_ou_barbeiro
)

from auth.dependencies import (
    get_barbeiro_logado
)

router = APIRouter(
    prefix="/agendamentos",
    tags=["Agendamentos"]
)

@router.post("", response_model=AgendamentoResponse)
def criar_agendamento(
    dados: AgendamentoCreate,
    db: Session = Depends(get_db),
   
):
    return criar_agendamento_service(db, dados)


@router.get("", response_model=list[AgendamentoResponse])
def listar_agendamentos(
    data_agenda: date | None = Query(default=None),
    barbeiro_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
   
):
    return listar_agendamentos_por_filtro_service(
        db=db,
        data_agenda=data_agenda,
        barbeiro_id=barbeiro_id
    )


@router.get("/calendario")
def calendario_agendamentos(
    barbeiro_id: int | None = None,
    data_inicio: datetime | None = None,
    data_fim: datetime | None = None,
    db: Session = Depends(get_db),
):
    return calendario_agendamentos_service(
        db=db,
        barbeiro_id=barbeiro_id,
        data_inicio=data_inicio,
        data_fim=data_fim
    )


@router.get(
    "/minha-agenda",
    response_model=list[AgendamentoResponse]
)
def minha_agenda(
    barbeiro_id: int = Depends(get_barbeiro_logado),
    db: Session = Depends(get_db)
):
    return listar_agendamentos_por_filtro_service(
        db=db,
        barbeiro_id=barbeiro_id
    )


@router.get("/{agendamento_id}", response_model=AgendamentoResponse)
def buscar_agendamento(
    agendamento_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(admin_gerente_ou_barbeiro)
):
    return buscar_agendamento_service(db, agendamento_id)


@router.put("/{agendamento_id}/cancelar", response_model=AgendamentoResponse)
def cancelar_agendamento(
    agendamento_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(admin_gerente_ou_recepcao)
):
    return cancelar_agendamento_service(db, agendamento_id)


@router.put("/{agendamento_id}/status", response_model=AgendamentoResponse)
def atualizar_status_agendamento(
    agendamento_id: int,
    dados: AtualizarStatusAgendamento,
    db: Session = Depends(get_db),
    usuario=Depends(admin_gerente_ou_recepcao)
):
    return atualizar_status_agendamento_service(
        db=db,
        agendamento_id=agendamento_id,
        status=dados.status
    )


@router.post("/{agendamento_id}/converter-comanda")
def converter_agendamento_em_comanda(
    agendamento_id: int,
    db: Session = Depends(get_db),
):
    return converter_agendamento_em_comanda_service(
        db=db,
        agendamento_id=agendamento_id
    )


@router.put(
    "/{agendamento_id}/reagendar",
    response_model=AgendamentoResponse
)
def reagendar_agendamento(
    agendamento_id: int,
    dados: ReagendarAgendamentoRequest,
    db: Session = Depends(get_db),
    usuario=Depends(admin_gerente_ou_recepcao)
):
    return reagendar_agendamento_service(
        db=db,
        agendamento_id=agendamento_id,
        nova_data_hora_inicio=dados.nova_data_hora_inicio
    )
