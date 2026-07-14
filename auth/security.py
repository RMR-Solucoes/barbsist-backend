from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
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
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8

SEGURANCA_ATIVA = os.getenv(
    "SEGURANCA_ATIVA",
    "false"
).lower() == "true"


pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login",
    auto_error=False
)


def criar_hash_senha(senha: str) -> str:
    return pwd_context.hash(senha)


def verificar_senha(senha: str, senha_hash: str) -> bool:
    return pwd_context.verify(senha, senha_hash)


def criar_token_acesso(dados: dict):
    dados_token = dados.copy()

    expira = datetime.utcnow() + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    dados_token.update({"exp": expira})

    return jwt.encode(
        dados_token,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


def obter_usuario_logado(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    if not SEGURANCA_ATIVA and not token:
        return None

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acesso não informado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        usuario_id = payload.get("sub")

        if usuario_id is None:
            raise HTTPException(
                status_code=401,
                detail="Token inválido"
            )

    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Token inválido ou expirado"
        )

    usuario = db.query(models.Usuario).filter(
        models.Usuario.id == int(usuario_id)
    ).first()

    if not usuario:
        raise HTTPException(
            status_code=401,
            detail="Usuário não encontrado"
        )

    if not usuario.ativo:
        raise HTTPException(
            status_code=403,
            detail="Usuário inativo"
        )

    return usuario