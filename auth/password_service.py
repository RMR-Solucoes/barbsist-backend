from datetime import datetime, timedelta
import hashlib
import os
import secrets

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

import models


from auth.security import (
    criar_hash_senha,
    verificar_senha,
)
from auth.usuario_service import validar_senha

from auth.email_service import (
    ErroEnvioEmail,
    enviar_email_recuperacao_senha,
)

RECUPERACAO_SENHA_EXPIRA_MINUTOS = int(
    os.getenv(
        "RECUPERACAO_SENHA_EXPIRA_MINUTOS",
        "30",
    )
)

FRONTEND_URL = (
    os.getenv("FRONTEND_PUBLIC_URL")
    or os.getenv("FRONTEND_URL")
    or "http://localhost:3000"
).strip().rstrip("/")


MENSAGEM_RECUPERACAO = (
    "Se os dados informados estiverem corretos, "
    "enviaremos as instruções para recuperação da senha."
)


def validar_nova_senha(nova_senha: str):
    """
    Mantém compatibilidade interna usando a política única do BarbSist.
    """
    validar_senha(nova_senha)


def gerar_hash_token(token: str) -> str:
    """
    Gera o hash SHA-256 do token.

    O token original nunca será armazenado no banco.
    """

    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def excluir_tokens_anteriores(
    usuario_id: int,
    db: Session,
):
    """
    Remove solicitações anteriores do usuário,
    garantindo que apenas o token mais recente seja válido.
    """

    db.query(
        models.TokenRecuperacaoSenha
    ).filter(
        models.TokenRecuperacaoSenha.usuario_id
        == usuario_id
    ).delete(
        synchronize_session=False
    )


def alterar_minha_senha_service(
    senha_atual: str,
    nova_senha: str,
    confirmar_nova_senha: str,
    db: Session,
    usuario_logado: models.Usuario,
):
    """
    Permite que o próprio usuário autenticado altere
    sua senha após confirmar a senha atual.
    """

    if usuario_logado is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não autenticado.",
        )

    if not senha_atual:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A senha atual é obrigatória.",
        )

    if nova_senha != confirmar_nova_senha:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "A nova senha e a confirmação "
                "não coincidem."
            ),
        )

    validar_nova_senha(
        nova_senha
    )

    if not verificar_senha(
        senha_atual,
        usuario_logado.senha_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A senha atual está incorreta.",
        )

    if verificar_senha(
        nova_senha,
        usuario_logado.senha_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "A nova senha deve ser diferente "
                "da senha atual."
            ),
        )

    usuario_logado.senha_hash = criar_hash_senha(
        nova_senha
    )

    try:
        excluir_tokens_anteriores(
            usuario_id=usuario_logado.id,
            db=db,
        )

        db.commit()
        db.refresh(usuario_logado)

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Não foi possível alterar a senha. "
                "Tente novamente."
            ),
        )

    return {
        "mensagem": "Senha alterada com sucesso."
    }


def solicitar_recuperacao_senha_service(
    barbearia_slug: str | None,
    email: str,
    db: Session,
):
    """
    Cria token temporário para usuário de barbearia ou superadmin global.
    A resposta pública permanece genérica para evitar enumeração de contas.
    """
    slug_normalizado = (barbearia_slug or "").strip().lower()
    email_normalizado = (email or "").strip().lower()

    # Superadmin global: recuperação não depende de slug.
    usuario = (
        db.query(models.Usuario)
        .filter(
            models.Usuario.email == email_normalizado,
            models.Usuario.perfil == "superadmin",
            models.Usuario.ativo.is_(True),
        )
        .first()
    )
    barbearia_id = None

    if usuario is None:
        if slug_normalizado:
            # Compatibilidade temporária com clientes antigos da API.
            barbearia = (
                db.query(models.Barbearia)
                .filter(
                    models.Barbearia.slug == slug_normalizado,
                    models.Barbearia.ativa.is_(True),
                )
                .first()
            )
            if barbearia is None:
                return {"mensagem": MENSAGEM_RECUPERACAO}

            usuario = (
                db.query(models.Usuario)
                .filter(
                    models.Usuario.barbearia_id == barbearia.id,
                    models.Usuario.email == email_normalizado,
                    models.Usuario.ativo.is_(True),
                )
                .first()
            )
            if usuario is None:
                return {"mensagem": MENSAGEM_RECUPERACAO}
            barbearia_id = barbearia.id
        else:
            # Fluxo oficial: o e-mail identifica a conta interna sem expor slug.
            candidatos = (
                db.query(models.Usuario)
                .join(
                    models.Barbearia,
                    models.Barbearia.id == models.Usuario.barbearia_id,
                )
                .filter(
                    models.Usuario.email == email_normalizado,
                    models.Usuario.perfil != "superadmin",
                    models.Usuario.ativo.is_(True),
                    models.Barbearia.ativa.is_(True),
                )
                .all()
            )

            # Nunca escolhe silenciosamente entre contas ambíguas.
            if len(candidatos) != 1:
                return {"mensagem": MENSAGEM_RECUPERACAO}

            usuario = candidatos[0]
            barbearia_id = usuario.barbearia_id

    token_original = secrets.token_urlsafe(48)
    token_hash = gerar_hash_token(token_original)
    agora = datetime.utcnow()

    token_registro = models.TokenRecuperacaoSenha(
        usuario_id=usuario.id,
        barbearia_id=barbearia_id,
        token_hash=token_hash,
        criado_em=agora,
        expira_em=agora + timedelta(minutes=RECUPERACAO_SENHA_EXPIRA_MINUTOS),
        utilizado=False,
        utilizado_em=None,
    )

    try:
        excluir_tokens_anteriores(usuario_id=usuario.id, db=db)
        db.add(token_registro)
        db.commit()
    except Exception:
        db.rollback()
        return {"mensagem": MENSAGEM_RECUPERACAO}

    link_recuperacao = f"{FRONTEND_URL}/redefinir-senha?token={token_original}"

    try:
        enviar_email_recuperacao_senha(
            destinatario=usuario.email,
            nome_usuario=usuario.nome,
            link_recuperacao=link_recuperacao,
            expira_minutos=RECUPERACAO_SENHA_EXPIRA_MINUTOS,
        )
    except ErroEnvioEmail:
        # Nunca imprime token/link de recuperação em produção.
        print("ERRO AO ENVIAR E-MAIL DE RECUPERAÇÃO")

    return {"mensagem": MENSAGEM_RECUPERACAO}


def redefinir_senha_service(
    token: str,
    nova_senha: str,
    confirmar_nova_senha: str,
    db: Session,
):
    """
    Redefine a senha utilizando um token temporário,
    válido e ainda não utilizado.
    """

    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token de recuperação não informado.",
        )

    if nova_senha != confirmar_nova_senha:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "A nova senha e a confirmação "
                "não coincidem."
            ),
        )

    validar_nova_senha(
        nova_senha
    )

    token_hash = gerar_hash_token(
        token
    )

    registro = db.query(
        models.TokenRecuperacaoSenha
    ).filter(
        models.TokenRecuperacaoSenha.token_hash
        == token_hash,
        models.TokenRecuperacaoSenha.utilizado.is_(False),
    ).first()

    if registro is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Token de recuperação inválido "
                "ou já utilizado."
            ),
        )

    agora = datetime.utcnow()

    if registro.expira_em < agora:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token de recuperação expirado.",
        )

    if registro.barbearia_id is None:
        # Superadmin global: não possui vínculo com barbearia.
        usuario = db.query(
            models.Usuario
        ).filter(
            models.Usuario.id == registro.usuario_id,
            models.Usuario.barbearia_id.is_(None),
            models.Usuario.perfil == "superadmin",
            models.Usuario.ativo.is_(True),
        ).first()

        if usuario is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Não foi possível concluir a recuperação da senha.",
            )
    else:
        barbearia = db.query(
            models.Barbearia
        ).filter(
            models.Barbearia.id == registro.barbearia_id,
            models.Barbearia.ativa.is_(True),
        ).first()

        usuario = db.query(
            models.Usuario
        ).filter(
            models.Usuario.id == registro.usuario_id,
            models.Usuario.barbearia_id == registro.barbearia_id,
            models.Usuario.ativo.is_(True),
        ).first()

        if barbearia is None or usuario is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Não foi possível concluir a recuperação da senha.",
            )

    if verificar_senha(
        nova_senha,
        usuario.senha_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "A nova senha deve ser diferente "
                "da senha atual."
            ),
        )

    usuario.senha_hash = criar_hash_senha(
        nova_senha
    )

    registro.utilizado = True
    registro.utilizado_em = agora

    try:
        db.query(
            models.TokenRecuperacaoSenha
        ).filter(
            models.TokenRecuperacaoSenha.usuario_id
            == usuario.id,
            models.TokenRecuperacaoSenha.id
            != registro.id,
        ).delete(
            synchronize_session=False
        )

        db.commit()
        db.refresh(usuario)

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Não foi possível redefinir a senha. "
                "Tente novamente."
            ),
        )

    return {
        "mensagem": "Senha redefinida com sucesso."
    }
