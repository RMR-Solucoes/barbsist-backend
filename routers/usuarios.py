from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db

from schemas import (
    UsuarioCreate,
    UsuarioResponse,
    UsuarioUpdate,
    AlterarSenhaUsuarioRequest
)

from auth.usuario_service import (
    criar_usuario_service,
    listar_usuarios_service,
    buscar_usuario_service,
    atualizar_usuario_service,
    alterar_senha_service,
    inativar_usuario_service,
    reativar_usuario_service
)

from auth.permissions import (
    admin,
    superadmin_ou_admin
)


router = APIRouter(
    prefix="/usuarios",
    tags=["Usuários"]
)


@router.post(
    "",
    response_model=UsuarioResponse
)
def criar_usuario(
    dados: UsuarioCreate,
    db: Session = Depends(get_db),
    usuario_logado=Depends(superadmin_ou_admin)
):
    return criar_usuario_service(
        dados=dados,
        db=db,
        usuario_logado=usuario_logado
    )


@router.get(
    "",
    response_model=list[UsuarioResponse]
)
def listar_usuarios(
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin)
):
    return listar_usuarios_service(
        db=db,
        usuario_logado=usuario_logado
    )


@router.get(
    "/{usuario_id}",
    response_model=UsuarioResponse
)
def buscar_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin)
):
    return buscar_usuario_service(
        usuario_id=usuario_id,
        db=db,
        usuario_logado=usuario_logado
    )


@router.put(
    "/{usuario_id}",
    response_model=UsuarioResponse
)
def atualizar_usuario(
    usuario_id: int,
    dados: UsuarioUpdate,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin)
):
    return atualizar_usuario_service(
        usuario_id=usuario_id,
        dados=dados,
        db=db,
        usuario_logado=usuario_logado
    )


@router.put(
    "/{usuario_id}/senha"
)
def alterar_senha(
    usuario_id: int,
    dados: AlterarSenhaUsuarioRequest,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin)
):
    alterar_senha_service(
        usuario_id=usuario_id,
        nova_senha=dados.nova_senha,
        db=db,
        usuario_logado=usuario_logado
    )

    return {
        "mensagem": "Senha alterada com sucesso."
    }


@router.delete(
    "/{usuario_id}"
)
def inativar_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin)
):
    inativar_usuario_service(
        usuario_id=usuario_id,
        db=db,
        usuario_logado=usuario_logado
    )

    return {
        "mensagem": "Usuário inativado com sucesso."
    }


@router.put(
    "/{usuario_id}/reativar",
    response_model=UsuarioResponse
)
def reativar_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin)
):
    return reativar_usuario_service(
        usuario_id=usuario_id,
        db=db,
        usuario_logado=usuario_logado
    )