from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models

from schemas import (
    UsuarioCreate,
    UsuarioUpdate,
    PERFIS_USUARIO_VALIDOS
)

from auth.security import criar_hash_senha
from auth.tenant import (
    obter_barbearia_id,
    buscar_da_barbearia,
    consultar_da_barbearia,
    usuario_eh_superadmin,
    validar_barbearia_ativa
)


def normalizar_email(email: str) -> str:
    """
    Padroniza o e-mail para evitar duplicidades causadas
    por espaços ou letras maiúsculas.
    """

    return email.strip().lower()


def validar_senha(nova_senha: str):
    """
    Valida os requisitos mínimos da senha.
    """

    if not nova_senha or len(nova_senha) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "A senha deve possuir pelo menos "
                "6 caracteres."
            )
        )


def validar_perfil(perfil: str):
    """
    Impede o cadastro de perfis desconhecidos ou do
    perfil reservado superadmin.
    """

    perfil_normalizado = perfil.strip().lower()

    if perfil_normalizado not in PERFIS_USUARIO_VALIDOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Perfil de usuário inválido. "
                "Utilize admin, gerente, recepcao "
                "ou barbeiro."
            )
        )

    return perfil_normalizado


def validar_vinculo_perfil_barbeiro(
    perfil: str,
    barbeiro_id: int | None
):
    """
    Usuários com perfil barbeiro precisam obrigatoriamente
    estar vinculados a um barbeiro.

    Os demais perfis podem ou não possuir esse vínculo.
    """

    if perfil == "barbeiro" and barbeiro_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Usuários com perfil barbeiro precisam "
                "estar vinculados a um barbeiro."
            )
        )


def validar_barbeiro_vinculado(
    barbeiro_id: int | None,
    barbearia_id: int,
    db: Session
):
    """
    Verifica se o barbeiro existe, está ativo e pertence
    à barbearia na qual o usuário será vinculado.
    """

    if barbeiro_id is None:
        return None

    barbeiro = (
        db.query(models.Barbeiro)
        .filter(
            models.Barbeiro.id == barbeiro_id,
            models.Barbeiro.barbearia_id == barbearia_id
        )
        .first()
    )

    if barbeiro is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Barbeiro não encontrado nesta barbearia."
            )
        )

    if not barbeiro.ativo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Não é possível vincular o usuário "
                "a um barbeiro inativo."
            )
        )

    return barbeiro


def validar_barbeiro_sem_usuario(
    barbeiro_id: int | None,
    barbearia_id: int,
    db: Session,
    usuario_id: int | None = None
):
    """
    Impede que o mesmo barbeiro seja vinculado a mais
    de um usuário ativo na mesma barbearia.
    """

    if barbeiro_id is None:
        return

    query = db.query(
        models.Usuario
    ).filter(
        models.Usuario.barbearia_id == barbearia_id,
        models.Usuario.barbeiro_id == barbeiro_id,
        models.Usuario.ativo.is_(True)
    )

    if usuario_id is not None:
        query = query.filter(
            models.Usuario.id != usuario_id
        )

    usuario_existente = query.first()

    if usuario_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Este barbeiro já está vinculado "
                "a outro usuário ativo."
            )
        )


def contar_administradores_ativos(
    db: Session,
    barbearia_id: int
) -> int:
    """
    Conta somente os administradores ativos da barbearia
    informada.
    """

    return db.query(
        models.Usuario
    ).filter(
        models.Usuario.barbearia_id == barbearia_id,
        models.Usuario.perfil == "admin",
        models.Usuario.ativo.is_(True)
    ).count()


def criar_usuario_service(
    dados: UsuarioCreate,
    db: Session,
    usuario_logado: models.Usuario
):
    """
    Cria um usuário e o vincula à barbearia correta.

    O superadmin deve informar barbearia_id.
    O administrador comum somente pode criar usuários
    dentro da própria barbearia.
    """

    if usuario_eh_superadmin(usuario_logado):
        if dados.barbearia_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "O superadministrador deve informar "
                    "a barbearia do novo usuário."
                )
            )

        barbearia_id = dados.barbearia_id

    else:
        barbearia_id = obter_barbearia_id(
            usuario_logado
        )

        if (
            dados.barbearia_id is not None
            and dados.barbearia_id != barbearia_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Não é permitido criar usuários "
                    "em outra barbearia."
                )
            )

    validar_barbearia_ativa(
        db=db,
        barbearia_id=barbearia_id
    )

    email_normalizado = normalizar_email(
        dados.email
    )

    perfil_normalizado = validar_perfil(
        dados.perfil
    )

    validar_senha(
        dados.senha
    )

    validar_vinculo_perfil_barbeiro(
        perfil=perfil_normalizado,
        barbeiro_id=dados.barbeiro_id
    )

    usuario_existente = (
        db.query(models.Usuario)
        .filter(
            models.Usuario.barbearia_id == barbearia_id,
            models.Usuario.email == email_normalizado
        )
        .first()
    )

    if usuario_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Já existe um usuário com este e-mail "
                "nesta barbearia."
            )
        )

    validar_barbeiro_vinculado(
        barbeiro_id=dados.barbeiro_id,
        barbearia_id=barbearia_id,
        db=db
    )

    validar_barbeiro_sem_usuario(
        barbeiro_id=dados.barbeiro_id,
        barbearia_id=barbearia_id,
        db=db
    )

    usuario = models.Usuario(
        nome=dados.nome.strip(),
        email=email_normalizado,
        senha_hash=criar_hash_senha(
            dados.senha
        ),
        perfil=perfil_normalizado,
        barbeiro_id=dados.barbeiro_id,
        barbearia_id=barbearia_id,
        ativo=True
    )

    try:
        db.add(usuario)
        db.commit()
        db.refresh(usuario)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Não foi possível cadastrar o usuário. "
                "Verifique se o e-mail ou o barbeiro "
                "já está sendo utilizado."
            )
        )

    return usuario

def listar_usuarios_service(
    db: Session,
    usuario_logado: models.Usuario
):
    """
    Lista somente os usuários pertencentes à barbearia
    do administrador autenticado.
    """

    return consultar_da_barbearia(
        db=db,
        model=models.Usuario,
        usuario=usuario_logado
    ).order_by(
        models.Usuario.ativo.desc(),
        models.Usuario.nome.asc()
    ).all()


def buscar_usuario_service(
    usuario_id: int,
    db: Session,
    usuario_logado: models.Usuario
):
    """
    Busca um usuário pelo ID dentro da barbearia atual.
    """

    return buscar_da_barbearia(
        db=db,
        model=models.Usuario,
        registro_id=usuario_id,
        usuario=usuario_logado,
        mensagem_nao_encontrado=(
            "Usuário não encontrado."
        )
    )


def atualizar_usuario_service(
    usuario_id: int,
    dados: UsuarioUpdate,
    db: Session,
    usuario_logado: models.Usuario
):
    """
    Atualiza um usuário sem permitir a transferência para
    outra barbearia.
    """

    barbearia_id = obter_barbearia_id(
        usuario_logado
    )

    usuario = buscar_usuario_service(
        usuario_id=usuario_id,
        db=db,
        usuario_logado=usuario_logado
    )

    email_normalizado = normalizar_email(
        dados.email
    )

    perfil_normalizado = validar_perfil(
        dados.perfil
    )

    validar_vinculo_perfil_barbeiro(
        perfil=perfil_normalizado,
        barbeiro_id=dados.barbeiro_id
    )

    usuario_email = db.query(
        models.Usuario
    ).filter(
        models.Usuario.barbearia_id == barbearia_id,
        models.Usuario.email == email_normalizado,
        models.Usuario.id != usuario_id
    ).first()

    if usuario_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Já existe um usuário com este e-mail "
                "nesta barbearia."
            )
        )

    validar_barbeiro_vinculado(
        barbeiro_id=dados.barbeiro_id,
        barbearia_id=barbearia_id,
        db=db
    )

    validar_barbeiro_sem_usuario(
        barbeiro_id=dados.barbeiro_id,
        barbearia_id=barbearia_id,
        db=db,
        usuario_id=usuario_id
    )

    removendo_perfil_admin = (
        usuario.perfil == "admin"
        and perfil_normalizado != "admin"
    )

    inativando_admin = (
        usuario.perfil == "admin"
        and usuario.ativo
        and not dados.ativo
    )

    if removendo_perfil_admin or inativando_admin:
        total_admins = contar_administradores_ativos(
            db=db,
            barbearia_id=barbearia_id
        )

        if total_admins <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Não é permitido remover ou inativar "
                    "o último administrador da barbearia."
                )
            )

    usuario.nome = dados.nome.strip()
    usuario.email = email_normalizado
    usuario.perfil = perfil_normalizado
    usuario.barbeiro_id = dados.barbeiro_id
    usuario.ativo = dados.ativo

    try:
        db.commit()
        db.refresh(usuario)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Não foi possível atualizar o usuário. "
                "Verifique os dados informados."
            )
        )

    return usuario


def alterar_senha_service(
    usuario_id: int,
    nova_senha: str,
    db: Session,
    usuario_logado: models.Usuario
):
    """
    Altera a senha de um usuário pertencente à mesma
    barbearia.
    """

    validar_senha(
        nova_senha
    )

    usuario = buscar_usuario_service(
        usuario_id=usuario_id,
        db=db,
        usuario_logado=usuario_logado
    )

    usuario.senha_hash = criar_hash_senha(
        nova_senha
    )

    db.commit()
    db.refresh(usuario)

    return usuario


def inativar_usuario_service(
    usuario_id: int,
    db: Session,
    usuario_logado: models.Usuario
):
    """
    Inativa um usuário da própria barbearia.
    """

    barbearia_id = obter_barbearia_id(
        usuario_logado
    )

    usuario = buscar_usuario_service(
        usuario_id=usuario_id,
        db=db,
        usuario_logado=usuario_logado
    )

    if not usuario.ativo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuário já está inativo."
        )

    if usuario.id == usuario_logado.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Você não pode inativar o próprio usuário."
            )
        )

    if usuario.perfil == "admin":
        total_admins = contar_administradores_ativos(
            db=db,
            barbearia_id=barbearia_id
        )

        if total_admins <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Não é permitido inativar o último "
                    "administrador da barbearia."
                )
            )

    usuario.ativo = False

    db.commit()
    db.refresh(usuario)

    return usuario


def reativar_usuario_service(
    usuario_id: int,
    db: Session,
    usuario_logado: models.Usuario
):
    """
    Reativa um usuário da própria barbearia.
    """

    barbearia_id = obter_barbearia_id(
        usuario_logado
    )

    usuario = buscar_usuario_service(
        usuario_id=usuario_id,
        db=db,
        usuario_logado=usuario_logado
    )

    if usuario.ativo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuário já está ativo."
        )

    validar_barbeiro_vinculado(
        barbeiro_id=usuario.barbeiro_id,
        barbearia_id=barbearia_id,
        db=db
    )

    validar_barbeiro_sem_usuario(
        barbeiro_id=usuario.barbeiro_id,
        barbearia_id=barbearia_id,
        db=db,
        usuario_id=usuario.id
    )

    usuario.ativo = True

    db.commit()
    db.refresh(usuario)

    return usuario


def buscar_usuario_por_email(
    email: str,
    barbearia_id: int,
    db: Session
):
    """
    Busca um usuário por e-mail dentro de uma barbearia
    específica.

    Não deve ser usada sem barbearia_id.
    """

    email_normalizado = normalizar_email(
        email
    )

    return db.query(
        models.Usuario
    ).filter(
        models.Usuario.barbearia_id == barbearia_id,
        models.Usuario.email == email_normalizado
    ).first()