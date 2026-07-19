from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth.permissions import (
    admin_ou_gerente,
    admin_gerente_recepcao_ou_barbeiro,
)
from database import get_db
from schemas import (
    ConfiguracaoFuncionamentoResponse,
    ConfiguracaoFuncionamentoUpdate,
)
from services.configuracao_funcionamento_service import (
    atualizar_configuracao,
    buscar_configuracao_por_dia,
    listar_configuracoes,
)


router = APIRouter(
    prefix="/configuracao-funcionamento",
    tags=["Configuração de Funcionamento"],
)


@router.get("", response_model=list[ConfiguracaoFuncionamentoResponse])
def listar(
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_gerente_recepcao_ou_barbeiro),
):
    return listar_configuracoes(db, usuario_logado)


@router.get(
    "/{dia_semana}",
    response_model=ConfiguracaoFuncionamentoResponse,
)
def buscar_por_dia(
    dia_semana: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_gerente_recepcao_ou_barbeiro),
):
    config = buscar_configuracao_por_dia(
        db,
        dia_semana,
        usuario_logado,
    )

    if not config:
        raise HTTPException(
            status_code=404,
            detail="Configuração não encontrada.",
        )

    return config


@router.put(
    "/{configuracao_id}",
    response_model=ConfiguracaoFuncionamentoResponse,
)
def atualizar(
    configuracao_id: int,
    dados: ConfiguracaoFuncionamentoUpdate,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_ou_gerente),
):
    return atualizar_configuracao(
        db=db,
        configuracao_id=configuracao_id,
        dados=dados,
        usuario_logado=usuario_logado,
    )
