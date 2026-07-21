from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from schemas import ServicoCreate, ServicoResponse

from auth.permissions import (
    admin_gerente_ou_recepcao,
)


from services.servico_service import (
    criar_servico_service,
    listar_servicos_service,
    buscar_servico_service,
    atualizar_servico_service,
    inativar_servico_service,
    reativar_servico_service,
)
import models

router = APIRouter(
    prefix="/servicos",
    tags=["Serviços"],
    
        
    
)


@router.post(
    "",
    response_model=ServicoResponse
)
def criar_servico(
    dados: ServicoCreate,
    db: Session = Depends(get_db),
    usuario_logado: models.Usuario = Depends(
    admin_gerente_ou_recepcao
)
):
    return criar_servico_service(
        dados=dados,
        db=db,
        usuario_logado=usuario_logado
    )


@router.get(
    "",
    response_model=list[ServicoResponse]
)
def listar_servicos(
    apenas_ativos: bool = True,
    db: Session = Depends(get_db),
    usuario_logado: models.Usuario = Depends(
    admin_gerente_ou_recepcao
)
):
    return listar_servicos_service(
        db=db,
        usuario_logado=usuario_logado,
        apenas_ativos=apenas_ativos
    )


@router.get(
    "/{servico_id}",
    response_model=ServicoResponse
)
def buscar_servico(
    servico_id: int,
    db: Session = Depends(get_db),
    usuario_logado: models.Usuario = Depends(
    admin_gerente_ou_recepcao
)
):
    return buscar_servico_service(
        servico_id=servico_id,
        db=db,
        usuario_logado=usuario_logado,
        exigir_ativo=False
    )


@router.put(
    "/{servico_id}",
    response_model=ServicoResponse
)
def atualizar_servico(
    servico_id: int,
    dados: ServicoCreate,
    db: Session = Depends(get_db),
    usuario_logado: models.Usuario = Depends(
    admin_gerente_ou_recepcao
)
):
    return atualizar_servico_service(
        servico_id=servico_id,
        dados=dados,
        db=db,
        usuario_logado=usuario_logado
    )


@router.delete(
    "/{servico_id}"
)
def inativar_servico(
    servico_id: int,
    db: Session = Depends(get_db),
    usuario_logado: models.Usuario = Depends(
    admin_gerente_ou_recepcao
)
):
    servico = inativar_servico_service(
        servico_id=servico_id,
        db=db,
        usuario_logado=usuario_logado
    )

    return {
        "mensagem": "Serviço desativado com sucesso.",
        "servico_id": servico.id
    }


@router.put(
    "/{servico_id}/reativar",
    response_model=ServicoResponse
)
def reativar_servico(
    servico_id: int,
    db: Session = Depends(get_db),
    usuario_logado: models.Usuario = Depends(
    admin_gerente_ou_recepcao
)
):
    return reativar_servico_service(
        servico_id=servico_id,
        db=db,
        usuario_logado=usuario_logado
    )