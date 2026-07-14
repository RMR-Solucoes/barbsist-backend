from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm

from database import get_db

from schemas import (
    UsuarioResponse,
    TokenResponse
)

from auth.auth_service import (
    login_service
)

from auth.dependencies import get_usuario_logado


router = APIRouter(
    prefix="/auth",
    tags=["Autenticação"]
)



@router.post("/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    return login_service(
        db=db,
        email=form_data.username,
        senha=form_data.password
    )


@router.get("/me", response_model=UsuarioResponse)
def usuario_logado(
    usuario=Depends(get_usuario_logado)
):
    return usuario