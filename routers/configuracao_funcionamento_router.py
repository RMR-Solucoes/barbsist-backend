from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from schemas import (
    ConfiguracaoFuncionamentoResponse,
    ConfiguracaoFuncionamentoUpdate,
)
from services.configuracao_funcionamento_service import (
    listar_configuracoes,
    atualizar_configuracao,
    buscar_configuracao_por_dia,
)

router = APIRouter(
    prefix="/configuracao-funcionamento",
    tags=["Configuração de Funcionamento"],
)


@router.get("", response_model=list[ConfiguracaoFuncionamentoResponse])
def listar(db: Session = Depends(get_db)):
    return listar_configuracoes(db)


@router.get("/{dia_semana}", response_model=ConfiguracaoFuncionamentoResponse)
def buscar_por_dia(dia_semana: int, db: Session = Depends(get_db)):
    config = buscar_configuracao_por_dia(db, dia_semana)

    if not config:
        raise HTTPException(status_code=404, detail="Configuração não encontrada.")

    return config


@router.put("/{configuracao_id}", response_model=ConfiguracaoFuncionamentoResponse)
def atualizar(
    configuracao_id: int,
    dados: ConfiguracaoFuncionamentoUpdate,
    db: Session = Depends(get_db),
):
    config = atualizar_configuracao(db, configuracao_id, dados)

    if not config:
        raise HTTPException(status_code=404, detail="Configuração não encontrada.")

    return config