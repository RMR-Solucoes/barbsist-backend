from fastapi import HTTPException, status
from sqlalchemy.orm import Session

import models

from auth.security import (
    verificar_senha,
    criar_token_acesso
)




def normalizar_email(email: str) -> str:
    """
    Padroniza o e-mail antes da consulta.

    Evita diferenças causadas por letras maiúsculas
    ou espaços digitados acidentalmente.
    """

    return email.strip().lower()


def normalizar_slug(slug: str) -> str:
    """
    Padroniza o slug informado no login.
    """

    return slug.strip().lower()


def login_service(
    db: Session,
    barbearia_slug: str,
    email: str,
    senha: str
):
    slug_normalizado = normalizar_slug(
        barbearia_slug
    )

    email_normalizado = normalizar_email(
        email
    )

    barbearia = db.query(
        models.Barbearia
    ).filter(
        models.Barbearia.slug == slug_normalizado
    ).first()

    if not barbearia:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Barbearia, usuário ou senha inválidos."
        )

    if not barbearia.ativa:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "O acesso desta barbearia está inativo. "
                "Entre em contato com o suporte."
            )
        )

    usuario = db.query(
        models.Usuario
    ).filter(
        models.Usuario.barbearia_id == barbearia.id,
        models.Usuario.email == email_normalizado,
        models.Usuario.ativo.is_(True)
    ).first()

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Barbearia, usuário ou senha inválidos."
        )

    if not verificar_senha(
        senha,
        usuario.senha_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Barbearia, usuário ou senha inválidos."
        )

    token = criar_token_acesso({
        "sub": str(usuario.id),
        "email": usuario.email,
        "perfil": usuario.perfil,
        "barbearia_id": usuario.barbearia_id,
        "barbearia_slug": barbearia.slug,
        "barbeiro_id": usuario.barbeiro_id
    })

    return {
        "access_token": token,
        "token_type": "bearer"
    }

    return {
        "access_token": token,
        "token_type": "bearer"
    }