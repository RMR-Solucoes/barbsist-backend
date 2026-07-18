from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db

from schemas import (
    ClienteCreate,
    ClienteUpdate,
    ClienteResponse,
    ClienteComAssinaturaResponse
)

from auth.permissions import (
    admin_gerente_ou_recepcao,
    admin_gerente_recepcao_ou_barbeiro
)

from auth.dependencies import (
    get_barbeiro_logado
)

from services.cliente_service import (
    criar_cliente_service,
    listar_clientes_service,
    buscar_cliente_service,
    atualizar_cliente_service,
    inativar_cliente_service,
    reativar_cliente_service,
    listar_clientes_com_assinaturas_service,
    listar_clientes_do_barbeiro_service
)


router = APIRouter(
    prefix="/clientes",
    tags=["Clientes"]
)


@router.post(
    "",
    response_model=ClienteResponse
)
def criar_cliente(
    dados: ClienteCreate,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_ou_recepcao
    )
):
    """
    Cria um cliente na barbearia do usuário autenticado.
    """

    return criar_cliente_service(
        dados=dados,
        db=db,
        usuario_logado=usuario_logado
    )


@router.get(
    "",
    response_model=list[ClienteResponse]
)
def listar_clientes(
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_recepcao_ou_barbeiro
    )
):
    """
    Lista os clientes ativos da barbearia atual.
    """

    return listar_clientes_service(
        db=db,
        usuario_logado=usuario_logado,
        apenas_ativos=True
    )


@router.get(
    "/com-assinaturas",
    response_model=list[
        ClienteComAssinaturaResponse
    ]
)
def listar_clientes_com_assinaturas(
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_recepcao_ou_barbeiro
    )
):
    """
    Lista os clientes ativos com dados de assinatura,
    limitados à barbearia atual.
    """

    return listar_clientes_com_assinaturas_service(
        db=db,
        usuario_logado=usuario_logado
    )


@router.get(
    "/meus",
    response_model=list[ClienteResponse]
)
def meus_clientes(
    barbeiro_id: int = Depends(
        get_barbeiro_logado
    ),
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_recepcao_ou_barbeiro
    )
):
    """
    Lista os clientes já atendidos pelo barbeiro logado.
    """

    return listar_clientes_do_barbeiro_service(
        barbeiro_id=barbeiro_id,
        db=db,
        usuario_logado=usuario_logado
    )


@router.get(
    "/{cliente_id}",
    response_model=ClienteResponse
)
def buscar_cliente(
    cliente_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_recepcao_ou_barbeiro
    )
):
    """
    Busca um cliente ativo da barbearia atual.
    """

    return buscar_cliente_service(
        cliente_id=cliente_id,
        db=db,
        usuario_logado=usuario_logado,
        exigir_ativo=True
    )


@router.put(
    "/{cliente_id}",
    response_model=ClienteResponse
)
def atualizar_cliente(
    cliente_id: int,
    dados: ClienteUpdate,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_ou_recepcao
    )
):
    return atualizar_cliente_service(
        cliente_id=cliente_id,
        dados=dados,
        db=db,
        usuario_logado=usuario_logado
    )


@router.delete(
    "/{cliente_id}"
)
def inativar_cliente(
    cliente_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_ou_recepcao
    )
):
    """
    Inativa um cliente sem excluir seus dados.
    """

    inativar_cliente_service(
        cliente_id=cliente_id,
        db=db,
        usuario_logado=usuario_logado
    )

    return {
        "mensagem": "Cliente inativado com sucesso."
    }


@router.put(
    "/{cliente_id}/reativar",
    response_model=ClienteResponse
)
def reativar_cliente(
    cliente_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_ou_recepcao
    )
):
    """
    Reativa um cliente da barbearia atual.
    """

    return reativar_cliente_service(
        cliente_id=cliente_id,
        db=db,
        usuario_logado=usuario_logado
    )