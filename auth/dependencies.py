from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session

import models
from database import get_db
from auth.security import SECRET_KEY, ALGORITHM


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login"
)


def get_usuario_logado(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
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
        models.Usuario.id == int(usuario_id),
        models.Usuario.ativo == True
    ).first()

    if not usuario:
        raise HTTPException(
            status_code=401,
            detail="Usuário não encontrado ou inativo"
        )

    return usuario


def get_barbeiro_logado(
    usuario=Depends(get_usuario_logado)
):
    if usuario.perfil != "barbeiro":
        raise HTTPException(
            status_code=403,
            detail="Acesso permitido apenas para barbeiros"
        )

    if usuario.barbeiro_id is None:
        raise HTTPException(
            status_code=403,
            detail="Usuário barbeiro não está vinculado a um barbeiro"
        )

    return usuario.barbeiro_id