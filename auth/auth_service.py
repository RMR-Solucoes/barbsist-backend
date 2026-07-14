from fastapi import HTTPException

import models

from auth.security import (
    criar_hash_senha,
    verificar_senha,
    criar_token_acesso
)


def criar_usuario_service(db, dados):
    usuario_existente = db.query(models.Usuario).filter(
        models.Usuario.email == dados.email
    ).first()

    if usuario_existente:
        raise HTTPException(
            status_code=400,
            detail="E-mail já cadastrado"
        )

    novo_usuario = models.Usuario(
        nome=dados.nome,
        email=dados.email,
        senha_hash=criar_hash_senha(dados.senha),
        perfil=dados.perfil,
        barbeiro_id=dados.barbeiro_id,
        ativo=True
    )

    db.add(novo_usuario)
    db.commit()
    db.refresh(novo_usuario)

    return novo_usuario


def login_service(db, email: str, senha: str):
    usuario = db.query(models.Usuario).filter(
        models.Usuario.email == email,
        models.Usuario.ativo == True
    ).first()

    if not usuario:
        raise HTTPException(
            status_code=401,
            detail="Usuário ou senha inválidos"
        )

    if not verificar_senha(senha, usuario.senha_hash):
        raise HTTPException(
            status_code=401,
            detail="Usuário ou senha inválidos"
        )

    token = criar_token_acesso({
        "sub": str(usuario.id),
        "email": usuario.email,
        "perfil": usuario.perfil,
        "barbeiro_id": usuario.barbeiro_id
    })

    return {
        "access_token": token,
        "token_type": "bearer"
    }