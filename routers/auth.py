from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db

from schemas import (
    AlterarMinhaSenhaRequest,
    CadastroBarbeariaRequest,
    CadastroBarbeariaResponse,
    EsqueciSenhaRequest,
    LoginRequest,
    MensagemResponse,
    RedefinirSenhaRequest,
    TokenResponse,
    UsuarioResponse,
    SuperadminContextoTokenResponse,
)

from auth.auth_service import (
    login_service,
    selecionar_contexto_superadmin_service,
    limpar_contexto_superadmin_service,
)
from auth.cadastro_service import cadastrar_barbearia_service
from auth.dependencies import get_usuario_logado
from auth.permissions import superadmin
from auth.password_service import (
    alterar_minha_senha_service,
    redefinir_senha_service,
    solicitar_recuperacao_senha_service,
)


router = APIRouter(
    prefix="/auth",
    tags=["Autenticação"],
)


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    dados: LoginRequest,
    db: Session = Depends(get_db),
):
    return login_service(
        db=db,
        barbearia_slug=dados.barbearia_slug,
        email=dados.email,
        senha=dados.senha,
    )


@router.post(
    "/cadastrar-barbearia",
    response_model=CadastroBarbeariaResponse,
    status_code=201,
)
def cadastrar_barbearia(
    dados: CadastroBarbeariaRequest,
    db: Session = Depends(get_db),
):
    return cadastrar_barbearia_service(
        db=db,
        dados=dados,
    )


@router.get(
    "/me",
    response_model=UsuarioResponse,
)
def usuario_logado(
    usuario=Depends(get_usuario_logado),
):
    return usuario


@router.put(
    "/minha-senha",
    response_model=MensagemResponse,
)
def alterar_minha_senha(
    dados: AlterarMinhaSenhaRequest,
    db: Session = Depends(get_db),
    usuario=Depends(get_usuario_logado),
):
    return alterar_minha_senha_service(
        senha_atual=dados.senha_atual,
        nova_senha=dados.nova_senha,
        confirmar_nova_senha=dados.confirmar_nova_senha,
        db=db,
        usuario_logado=usuario,
    )


@router.post(
    "/esqueci-senha",
    response_model=MensagemResponse,
)
def esqueci_senha(
    dados: EsqueciSenhaRequest,
    db: Session = Depends(get_db),
):
    return solicitar_recuperacao_senha_service(
        barbearia_slug=dados.barbearia_slug,
        email=dados.email,
        db=db,
    )


@router.post(
    "/redefinir-senha",
    response_model=MensagemResponse,
)
def redefinir_senha(
    dados: RedefinirSenhaRequest,
    db: Session = Depends(get_db),
):
    return redefinir_senha_service(
        token=dados.token,
        nova_senha=dados.nova_senha,
        confirmar_nova_senha=dados.confirmar_nova_senha,
        db=db,
    )

@router.post(
    "/superadmin/contexto/{barbearia_id}",
    response_model=SuperadminContextoTokenResponse,
)
def selecionar_contexto_superadmin(
    barbearia_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(superadmin),
):
    """
    Seleciona explicitamente a barbearia em que o superadmin atuará.

    Retorna um novo token JWT contextual. O registro do superadmin
    permanece global, com usuarios.barbearia_id = NULL.
    """
    return selecionar_contexto_superadmin_service(
        db=db,
        usuario_logado=usuario,
        barbearia_id=barbearia_id,
    )


@router.delete(
    "/superadmin/contexto",
    response_model=SuperadminContextoTokenResponse,
)
def limpar_contexto_superadmin(
    usuario=Depends(superadmin),
):
    """
    Retorna o superadmin ao contexto global da plataforma.
    """
    return limpar_contexto_superadmin_service(
        usuario_logado=usuario,
    )

