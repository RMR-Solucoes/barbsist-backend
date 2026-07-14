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

from auth.permissions import admin


router = APIRouter(
    prefix="/usuarios",
    tags=["Usuários"],
    dependencies=[Depends(admin)]
)


@router.post(
    "",
    response_model=UsuarioResponse
)
def criar_usuario(
    dados: UsuarioCreate,
    db: Session = Depends(get_db)
):
    return criar_usuario_service(
        dados,
        db
    )


@router.get(
    "",
    response_model=list[UsuarioResponse]
)
def listar_usuarios(
    db: Session = Depends(get_db)
):
    return listar_usuarios_service(db)


@router.get(
    "/{usuario_id}",
    response_model=UsuarioResponse
)
def buscar_usuario(
    usuario_id: int,
    db: Session = Depends(get_db)
):
    return buscar_usuario_service(
        usuario_id,
        db
    )


@router.put(
    "/{usuario_id}",
    response_model=UsuarioResponse
)
def atualizar_usuario(
    usuario_id: int,
    dados: UsuarioUpdate,
    db: Session = Depends(get_db)
):
    return atualizar_usuario_service(
        usuario_id,
        dados,
        db
    )


@router.put(
    "/{usuario_id}/senha"
)
def alterar_senha(
    usuario_id: int,
    dados: AlterarSenhaUsuarioRequest,
    db: Session = Depends(get_db)
):
    alterar_senha_service(
    usuario_id,
    dados.nova_senha,
    db
)

    return {
        "mensagem": "Senha alterada com sucesso."
    }


@router.delete(
    "/{usuario_id}"
)
def inativar_usuario(
    usuario_id: int,
    db: Session = Depends(get_db)
):
    inativar_usuario_service(
        usuario_id,
        db
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
    db: Session = Depends(get_db)
):
    return reativar_usuario_service(
        usuario_id,
        db
    )