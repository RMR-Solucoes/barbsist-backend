from fastapi import HTTPException, status
from sqlalchemy.orm import Session

import models

from auth.security import (
    verificar_senha,
    criar_token_acesso
)
from auth.tenant import usuario_eh_superadmin




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
    barbearia_slug: str | None,
    email: str,
    senha: str
):
    email_normalizado = normalizar_email(email)

    # 1) Superadmin global do BarbSist: não depende de slug/barbearia.
    superadmin = (
        db.query(models.Usuario)
        .filter(
            models.Usuario.email == email_normalizado,
            models.Usuario.perfil == "superadmin",
            models.Usuario.ativo.is_(True),
        )
        .first()
    )

    if superadmin is not None:
        if not verificar_senha(senha, superadmin.senha_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuário ou senha inválidos.",
            )

        token = criar_token_acesso({
            "sub": str(superadmin.id),
            "email": superadmin.email,
            "perfil": "superadmin",
            "barbearia_id": None,
            "barbearia_slug": None,
            "barbeiro_id": None,
        })

        return {
            "access_token": token,
            "token_type": "bearer",
        }

    # 2) Usuários operacionais continuam obrigatoriamente vinculados a uma barbearia.
    if not barbearia_slug or not barbearia_slug.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Barbearia, usuário ou senha inválidos.",
        )

    slug_normalizado = normalizar_slug(barbearia_slug)

    barbearia = (
        db.query(models.Barbearia)
        .filter(models.Barbearia.slug == slug_normalizado)
        .first()
    )

    if not barbearia:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Barbearia, usuário ou senha inválidos.",
        )

    if not barbearia.ativa:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "O acesso desta barbearia está inativo. "
                "Entre em contato com o suporte."
            ),
        )

    usuario = (
        db.query(models.Usuario)
        .filter(
            models.Usuario.barbearia_id == barbearia.id,
            models.Usuario.email == email_normalizado,
            models.Usuario.ativo.is_(True),
        )
        .first()
    )

    if not usuario or not verificar_senha(senha, usuario.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Barbearia, usuário ou senha inválidos.",
        )

    token = criar_token_acesso({
        "sub": str(usuario.id),
        "email": usuario.email,
        "perfil": usuario.perfil,
        "barbearia_id": usuario.barbearia_id,
        "barbearia_slug": barbearia.slug,
        "barbeiro_id": usuario.barbeiro_id,
    })

    return {
        "access_token": token,
        "token_type": "bearer",
    }

def _dados_token_superadmin(
    usuario: models.Usuario,
    contexto_barbearia: models.Barbearia | None = None,
) -> dict:
    """
    Monta o payload JWT do superadmin sem alterar seu vínculo global.
    """

    return {
        "sub": str(usuario.id),
        "email": usuario.email,
        "perfil": "superadmin",
        "barbearia_id": None,
        "barbearia_slug": None,
        "barbeiro_id": None,
        "contexto_barbearia_id": (
            contexto_barbearia.id
            if contexto_barbearia is not None
            else None
        ),
        "contexto_barbearia_slug": (
            contexto_barbearia.slug
            if contexto_barbearia is not None
            else None
        ),
    }


def selecionar_contexto_superadmin_service(
    db: Session,
    usuario_logado: models.Usuario,
    barbearia_id: int,
):
    """
    Emite novo JWT com contexto explícito de uma barbearia ativa.
    """

    if not usuario_eh_superadmin(usuario_logado):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operação permitida apenas ao superadministrador.",
        )

    barbearia = (
        db.query(models.Barbearia)
        .filter(models.Barbearia.id == barbearia_id)
        .first()
    )

    if barbearia is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Barbearia não encontrada.",
        )

    if not barbearia.ativa:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A barbearia selecionada está inativa.",
        )

    token = criar_token_acesso(
        _dados_token_superadmin(
            usuario=usuario_logado,
            contexto_barbearia=barbearia,
        )
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "contexto": {
            "barbearia_id": barbearia.id,
            "barbearia_nome": barbearia.nome,
            "barbearia_slug": barbearia.slug,
        },
    }


def limpar_contexto_superadmin_service(
    usuario_logado: models.Usuario,
):
    """
    Emite novo JWT global, removendo o contexto operacional.
    """

    if not usuario_eh_superadmin(usuario_logado):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operação permitida apenas ao superadministrador.",
        )

    token = criar_token_acesso(
        _dados_token_superadmin(
            usuario=usuario_logado,
            contexto_barbearia=None,
        )
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "contexto": None,
    }

