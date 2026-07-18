from datetime import datetime, timedelta
import os

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer
)
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from database import get_db
import models


load_dotenv(override=True)


SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "barbsist-chave-temporaria-dev"
)

ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv(
        "ACCESS_TOKEN_EXPIRE_MINUTES",
        str(60 * 8)
    )
)

SEGURANCA_ATIVA = os.getenv(
    "SEGURANCA_ATIVA",
    "false"
).lower() == "true"


pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


bearer_scheme = HTTPBearer(
    auto_error=False
)


def criar_hash_senha(
    senha: str
) -> str:
    return pwd_context.hash(senha)


def verificar_senha(
    senha: str,
    senha_hash: str
) -> bool:
    return pwd_context.verify(
        senha,
        senha_hash
    )


def criar_token_acesso(
    dados: dict
) -> str:
    dados_token = dados.copy()

    expira = datetime.utcnow() + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    dados_token.update({
        "exp": expira
    })

    return jwt.encode(
        dados_token,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


def erro_token_invalido() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido ou expirado.",
        headers={
            "WWW-Authenticate": "Bearer"
        }
    )


def obter_usuario_logado(
    credenciais: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
    db: Session = Depends(get_db)
):
    """
    Valida o token JWT, o usuário e o vínculo com a barbearia.

    Durante a transição, quando SEGURANCA_ATIVA=false e
    nenhum token é enviado, retorna None.
    """

    token = (
        credenciais.credentials
        if credenciais
        else None
    )

    if not SEGURANCA_ATIVA and not token:
        return None

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acesso não informado.",
            headers={
                "WWW-Authenticate": "Bearer"
            }
        )

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        usuario_id = payload.get("sub")
        barbearia_id_token = payload.get(
            "barbearia_id"
        )
        perfil_token = payload.get("perfil")

        if usuario_id is None or perfil_token is None:
            raise erro_token_invalido()

        try:
            usuario_id = int(usuario_id)
        except (TypeError, ValueError):
            raise erro_token_invalido()

        if (
            perfil_token != "superadmin"
            and barbearia_id_token is None
        ):
            raise erro_token_invalido()

        if barbearia_id_token is not None:
            try:
                barbearia_id_token = int(
                    barbearia_id_token
                )
            except (TypeError, ValueError):
                raise erro_token_invalido()

    except JWTError:
        raise erro_token_invalido()

    usuario = db.query(
        models.Usuario
    ).filter(
        models.Usuario.id == usuario_id
    ).first()

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado.",
            headers={
                "WWW-Authenticate": "Bearer"
            }
        )

    if not usuario.ativo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo."
        )

    if usuario.perfil != perfil_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Os dados de acesso foram alterados. "
                "Realize o login novamente."
            ),
            headers={
                "WWW-Authenticate": "Bearer"
            }
        )

    if usuario.perfil == "superadmin":
        return usuario

    if usuario.barbearia_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário sem barbearia vinculada."
        )

    if usuario.barbearia_id != barbearia_id_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "O vínculo do usuário com a barbearia "
                "foi alterado. Realize o login novamente."
            ),
            headers={
                "WWW-Authenticate": "Bearer"
            }
        )

    barbearia = db.query(
        models.Barbearia
    ).filter(
        models.Barbearia.id == usuario.barbearia_id
    ).first()

    if not barbearia:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Barbearia vinculada não encontrada."
        )

    if not barbearia.ativa:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "O acesso desta barbearia está inativo. "
                "Entre em contato com o suporte."
            )
        )

    return usuario