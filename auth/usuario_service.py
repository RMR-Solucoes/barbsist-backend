from fastapi import HTTPException
from sqlalchemy.orm import Session

import models
from schemas import UsuarioCreate, UsuarioUpdate
from auth.security import criar_hash_senha


def validar_barbeiro_vinculado(
    barbeiro_id: int | None,
    db: Session
):
    if barbeiro_id is None:
        return

    barbeiro = db.query(models.Barbeiro).filter(
        models.Barbeiro.id == barbeiro_id
    ).first()

    if not barbeiro:
        raise HTTPException(
            status_code=404,
            detail="Barbeiro vinculado não encontrado."
        )

def validar_barbeiro_sem_usuario(
    barbeiro_id: int | None,
    db: Session,
    usuario_id: int | None = None
):
    if barbeiro_id is None:
        return

    query = db.query(models.Usuario).filter(
        models.Usuario.barbeiro_id == barbeiro_id,
        models.Usuario.ativo == True
    )

    if usuario_id is not None:
        query = query.filter(
            models.Usuario.id != usuario_id
        )

    usuario_existente = query.first()

    if usuario_existente:
        raise HTTPException(
            status_code=400,
            detail="Este barbeiro já está vinculado a outro usuário ativo."
        )

def validar_senha(nova_senha: str):
    if not nova_senha or len(nova_senha) < 6:
        raise HTTPException(
            status_code=400,
            detail="A senha deve possuir pelo menos 6 caracteres."
        )


def criar_usuario_service(
    dados: UsuarioCreate,
    db: Session
):
    usuario_existente = db.query(models.Usuario).filter(
        models.Usuario.email == dados.email
    ).first()

    if usuario_existente:
        raise HTTPException(
            status_code=400,
            detail="Já existe um usuário com este e-mail."
        )

    validar_senha(dados.senha)
    validar_barbeiro_vinculado(dados.barbeiro_id, db)
    validar_barbeiro_sem_usuario(dados.barbeiro_id, db)

    usuario = models.Usuario(
        nome=dados.nome,
        email=dados.email,
        senha_hash=criar_hash_senha(dados.senha),
        perfil=dados.perfil,
        barbeiro_id=dados.barbeiro_id,
        ativo=True
    )

    db.add(usuario)
    db.commit()
    db.refresh(usuario)

    return usuario


def listar_usuarios_service(db: Session):
    return db.query(models.Usuario).order_by(
        models.Usuario.ativo.desc(),
        models.Usuario.nome.asc()
    ).all()


def buscar_usuario_service(
    usuario_id: int,
    db: Session
):
    usuario = db.query(models.Usuario).filter(
        models.Usuario.id == usuario_id
    ).first()

    if not usuario:
        raise HTTPException(
            status_code=404,
            detail="Usuário não encontrado."
        )

    return usuario


def atualizar_usuario_service(
    usuario_id: int,
    dados: UsuarioUpdate,
    db: Session
):
    usuario = buscar_usuario_service(usuario_id, db)

    usuario_email = db.query(models.Usuario).filter(
        models.Usuario.email == dados.email,
        models.Usuario.id != usuario_id
    ).first()

    if usuario_email:
        raise HTTPException(
            status_code=400,
            detail="Já existe um usuário com este e-mail."
        )

    validar_barbeiro_vinculado(dados.barbeiro_id, db)

    validar_barbeiro_sem_usuario(
    dados.barbeiro_id,
    db,
    usuario_id=usuario_id
)

    if usuario.perfil == "admin" and dados.perfil != "admin":
        total_admins = db.query(models.Usuario).filter(
            models.Usuario.perfil == "admin",
            models.Usuario.ativo == True
        ).count()

        if total_admins <= 1:
            raise HTTPException(
                status_code=400,
                detail="Não é permitido remover o último administrador do sistema."
            )

    usuario.nome = dados.nome
    usuario.email = dados.email
    usuario.perfil = dados.perfil
    usuario.barbeiro_id = dados.barbeiro_id
    usuario.ativo = dados.ativo

    db.commit()
    db.refresh(usuario)

    return usuario


def alterar_senha_service(
    usuario_id: int,
    nova_senha: str,
    db: Session
):
    validar_senha(nova_senha)

    usuario = buscar_usuario_service(usuario_id, db)

    usuario.senha_hash = criar_hash_senha(nova_senha)

    db.commit()
    db.refresh(usuario)

    return usuario


def inativar_usuario_service(
    usuario_id: int,
    db: Session
):
    usuario = buscar_usuario_service(usuario_id, db)

    if not usuario.ativo:
        raise HTTPException(
            status_code=400,
            detail="Usuário já está inativo."
        )

    if usuario.perfil == "admin":
        total_admins = db.query(models.Usuario).filter(
            models.Usuario.perfil == "admin",
            models.Usuario.ativo == True
        ).count()

        if total_admins <= 1:
            raise HTTPException(
                status_code=400,
                detail="Não é permitido inativar o último administrador do sistema."
            )

    usuario.ativo = False

    db.commit()
    db.refresh(usuario)

    return usuario


def reativar_usuario_service(
    usuario_id: int,
    db: Session
):
    usuario = buscar_usuario_service(usuario_id, db)

    if usuario.ativo:
        raise HTTPException(
            status_code=400,
            detail="Usuário já está ativo."
        )

    usuario.ativo = True

    db.commit()
    db.refresh(usuario)

    return usuario


def buscar_usuario_por_email(
    email: str,
    db: Session
):
    return db.query(models.Usuario).filter(
        models.Usuario.email == email
    ).first()