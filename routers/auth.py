from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db

from schemas import (
    LoginRequest,
    TokenResponse,
    UsuarioResponse
)

from auth.auth_service import login_service
from auth.dependencies import get_usuario_logado


router = APIRouter(
    prefix="/auth",
    tags=["Autenticação"]
)


@router.post(
    "/login",
    response_model=TokenResponse
)
def login(
    dados: LoginRequest,
    db: Session = Depends(get_db)
):
    return login_service(
        db=db,
        barbearia_slug=dados.barbearia_slug,
        email=dados.email,
        senha=dados.senha
    )


@router.get(
    "/me",
    response_model=UsuarioResponse
)
def usuario_logado(
    usuario=Depends(get_usuario_logado)
):
    return usuario