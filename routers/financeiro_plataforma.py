from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from auth.permissions import superadmin
from database import get_db
from schemas import (
    FinanceiroPlataformaFluxoResponse,
    FinanceiroPlataformaMovimentacaoCreate,
    FinanceiroPlataformaMovimentacaoOut,
    FinanceiroPlataformaMovimentacaoUpdate,
    FinanceiroPlataformaResumo,
)
from services.financeiro_plataforma_service import (
    atualizar_movimentacao_plataforma_service,
    criar_movimentacao_plataforma_service,
    fluxo_caixa_plataforma_service,
    listar_movimentacoes_plataforma_service,
    obter_resumo_financeiro_plataforma_service,
)


router = APIRouter(
    prefix="/admin/financeiro-plataforma",
    tags=["Admin - Financeiro Plataforma"],
)


@router.get(
    "/resumo",
    response_model=FinanceiroPlataformaResumo,
)
def resumo_financeiro_plataforma(
    data_inicio: date | None = None,
    data_fim: date | None = None,
    db: Session = Depends(get_db),
    usuario_logado=Depends(superadmin),
):
    return obter_resumo_financeiro_plataforma_service(
        db=db,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )


@router.get(
    "/fluxo-caixa",
    response_model=FinanceiroPlataformaFluxoResponse,
)
def fluxo_caixa_plataforma(
    data_inicio: date | None = None,
    data_fim: date | None = None,
    db: Session = Depends(get_db),
    usuario_logado=Depends(superadmin),
):
    return fluxo_caixa_plataforma_service(
        db=db,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )


@router.get(
    "/movimentacoes",
    response_model=list[
        FinanceiroPlataformaMovimentacaoOut
    ],
)
def listar_movimentacoes_plataforma(
    data_inicio: date | None = None,
    data_fim: date | None = None,
    tipo: str | None = Query(default=None),
    categoria: str | None = Query(default=None),
    status_movimentacao: str | None = Query(
        default=None,
        alias="status",
    ),
    db: Session = Depends(get_db),
    usuario_logado=Depends(superadmin),
):
    return listar_movimentacoes_plataforma_service(
        db=db,
        data_inicio=data_inicio,
        data_fim=data_fim,
        tipo=tipo,
        categoria=categoria,
        status_movimentacao=status_movimentacao,
    )


@router.post(
    "/movimentacoes",
    response_model=FinanceiroPlataformaMovimentacaoOut,
    status_code=status.HTTP_201_CREATED,
)
def criar_movimentacao_plataforma(
    dados: FinanceiroPlataformaMovimentacaoCreate,
    db: Session = Depends(get_db),
    usuario_logado=Depends(superadmin),
):
    return criar_movimentacao_plataforma_service(
        db=db,
        dados=dados,
        usuario_logado=usuario_logado,
    )


@router.put(
    "/movimentacoes/{movimentacao_id}",
    response_model=FinanceiroPlataformaMovimentacaoOut,
)
def atualizar_movimentacao_plataforma(
    movimentacao_id: int,
    dados: FinanceiroPlataformaMovimentacaoUpdate,
    db: Session = Depends(get_db),
    usuario_logado=Depends(superadmin),
):
    return atualizar_movimentacao_plataforma_service(
        db=db,
        movimentacao_id=movimentacao_id,
        dados=dados,
    )
