import re

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

import models

from auth.tenant import obter_barbearia_id

from services.crud_service import (
    criar_registro_com_codigo,
    consultar_registros,
    buscar_registro,
    salvar_alteracoes,
    inativar_registro,
    reativar_registro,
)


def normalizar_texto(
    valor: str | None,
    *,
    maiusculo: bool = True
) -> str | None:
    if valor is None:
        return None

    valor_normalizado = " ".join(
        valor.strip().split()
    )

    if not valor_normalizado:
        return None

    if maiusculo:
        return valor_normalizado.upper()

    return valor_normalizado


def normalizar_email(
    valor: str | None
) -> str | None:
    if valor is None:
        return None

    email = valor.strip().lower()

    if not email:
        return None

    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe um e-mail válido."
        )

    return email


def limpar_telefone(
    valor: str | None
) -> str | None:
    if valor is None:
        return None

    telefone = re.sub(
        r"\D",
        "",
        valor
    )

    if not telefone:
        return None

    if len(telefone) not in (10, 11):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Informe um telefone válido com DDD, "
                "contendo 10 ou 11 dígitos."
            )
        )

    return telefone


def validar_nome(
    nome: str | None
) -> str:
    nome_normalizado = normalizar_texto(
        nome
    )

    if not nome_normalizado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe o nome do barbeiro."
        )

    if len(nome_normalizado) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "O nome do barbeiro deve possuir "
                "pelo menos 2 caracteres."
            )
        )

    return nome_normalizado


def validar_percentual(
    percentual: float | None
) -> float:
    if percentual is None:
        return 50.0

    try:
        percentual_validado = float(
            percentual
        )
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "O percentual de comissão é inválido."
            )
        )

    if percentual_validado < 0 or percentual_validado > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "O percentual de comissão deve estar "
                "entre 0 e 100."
            )
        )

    return round(
        percentual_validado,
        2
    )


def validar_tipo(
    tipo: str | None
) -> str:
    tipo_normalizado = normalizar_texto(
        tipo
    ) or "ASSOCIADO"

    tipos_validos = {
        "ASSOCIADO",
        "FUNCIONARIO",
        "AUTONOMO",
        "PROPRIETARIO",
    }

    if tipo_normalizado not in tipos_validos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Tipo de vínculo inválido. Utilize "
                "ASSOCIADO, FUNCIONARIO, AUTONOMO "
                "ou PROPRIETARIO."
            )
        )

    return tipo_normalizado


def validar_duplicidade_barbeiro(
    db: Session,
    usuario_logado: models.Usuario,
    telefone: str | None,
    email: str | None,
    barbeiro_id_ignorado: int | None = None
):
    barbearia_id = obter_barbearia_id(
        usuario_logado
    )

    if telefone:
        query = db.query(
            models.Barbeiro
        ).filter(
            models.Barbeiro.barbearia_id
            == barbearia_id,

            models.Barbeiro.telefone
            == telefone
        )

        if barbeiro_id_ignorado is not None:
            query = query.filter(
                models.Barbeiro.id
                != barbeiro_id_ignorado
            )

        if query.first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Já existe um barbeiro com este "
                    "telefone nesta barbearia."
                )
            )

    if email:
        query = db.query(
            models.Barbeiro
        ).filter(
            models.Barbeiro.barbearia_id
            == barbearia_id,

            models.Barbeiro.email
            == email
        )

        if barbeiro_id_ignorado is not None:
            query = query.filter(
                models.Barbeiro.id
                != barbeiro_id_ignorado
            )

        if query.first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Já existe um barbeiro com este "
                    "e-mail nesta barbearia."
                )
            )


def criar_barbeiro_service(
    dados,
    db: Session,
    usuario_logado: models.Usuario
):
    nome = validar_nome(
        dados.nome
    )

    telefone = limpar_telefone(
        dados.telefone
    )

    if not telefone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe o telefone do barbeiro."
        )

    email = normalizar_email(
        dados.email
    )

    tipo = validar_tipo(
        dados.tipo
    )

    percentual_comissao = validar_percentual(
        dados.percentual_comissao
    )

    especialidades = normalizar_texto(
        dados.especialidades
    )

    observacoes = normalizar_texto(
        dados.observacoes,
        maiusculo=False
    )

    validar_duplicidade_barbeiro(
        db=db,
        usuario_logado=usuario_logado,
        telefone=telefone,
        email=email
    )

    return criar_registro_com_codigo(
        db=db,
        model=models.Barbeiro,
        tipo_sequencia="BARBEIRO",
        usuario_logado=usuario_logado,
        dados={
            "nome": nome,
            "telefone": telefone,
            "email": email,
            "tipo": tipo,
            "percentual_comissao": percentual_comissao,
            "especialidades": especialidades,
            "observacoes": observacoes,
            "ativo": True,
        }
    )


def listar_barbeiros_service(
    db: Session,
    usuario_logado: models.Usuario,
    apenas_ativos: bool = True
):
    query = consultar_registros(
        db=db,
        model=models.Barbeiro,
        usuario_logado=usuario_logado,
        apenas_ativos=apenas_ativos
    )

    return (
        query
        .order_by(
            models.Barbeiro.ativo.desc(),
            models.Barbeiro.nome.asc()
        )
        .all()
    )


def buscar_barbeiro_service(
    barbeiro_id: int,
    db: Session,
    usuario_logado: models.Usuario,
    exigir_ativo: bool = False
):
    return buscar_registro(
        db=db,
        model=models.Barbeiro,
        registro_id=barbeiro_id,
        usuario_logado=usuario_logado,
        mensagem_nao_encontrado=(
            "Barbeiro não encontrado."
        ),
        exigir_ativo=exigir_ativo
    )


def atualizar_barbeiro_service(
    barbeiro_id: int,
    dados,
    db: Session,
    usuario_logado: models.Usuario
):
    barbeiro = buscar_barbeiro_service(
        barbeiro_id=barbeiro_id,
        db=db,
        usuario_logado=usuario_logado,
        exigir_ativo=True
    )

    nome = validar_nome(
        dados.nome
    )

    telefone = limpar_telefone(
        dados.telefone
    )

    if not telefone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe o telefone do barbeiro."
        )

    email = normalizar_email(
        dados.email
    )

    tipo = validar_tipo(
        dados.tipo
    )

    percentual_comissao = validar_percentual(
        dados.percentual_comissao
    )

    especialidades = normalizar_texto(
        dados.especialidades
    )

    observacoes = normalizar_texto(
        dados.observacoes,
        maiusculo=False
    )

    validar_duplicidade_barbeiro(
        db=db,
        usuario_logado=usuario_logado,
        telefone=telefone,
        email=email,
        barbeiro_id_ignorado=barbeiro.id
    )

    barbeiro.nome = nome
    barbeiro.telefone = telefone
    barbeiro.email = email
    barbeiro.tipo = tipo
    barbeiro.percentual_comissao = (
        percentual_comissao
    )
    barbeiro.especialidades = especialidades
    barbeiro.observacoes = observacoes

    return salvar_alteracoes(
        db=db,
        registro=barbeiro,
        mensagem_erro=(
            "Não foi possível atualizar o barbeiro. "
            "Verifique os dados informados."
        )
    )


def validar_barbeiro_sem_usuario_ativo(
    barbeiro: models.Barbeiro,
    db: Session
):
    usuario_vinculado = (
        db.query(models.Usuario)
        .filter(
            models.Usuario.barbearia_id
            == barbeiro.barbearia_id,

            models.Usuario.barbeiro_id
            == barbeiro.id,

            models.Usuario.ativo.is_(True)
        )
        .first()
    )

    if usuario_vinculado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Não é possível inativar este barbeiro "
                "enquanto houver um usuário ativo "
                "vinculado a ele."
            )
        )


def inativar_barbeiro_service(
    barbeiro_id: int,
    db: Session,
    usuario_logado: models.Usuario
):
    barbeiro = buscar_barbeiro_service(
        barbeiro_id=barbeiro_id,
        db=db,
        usuario_logado=usuario_logado,
        exigir_ativo=False
    )

    if not barbeiro.ativo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O barbeiro já está inativo."
        )

    validar_barbeiro_sem_usuario_ativo(
        barbeiro=barbeiro,
        db=db
    )

    return inativar_registro(
        db=db,
        registro=barbeiro
    )


def reativar_barbeiro_service(
    barbeiro_id: int,
    db: Session,
    usuario_logado: models.Usuario
):
    barbeiro = buscar_barbeiro_service(
        barbeiro_id=barbeiro_id,
        db=db,
        usuario_logado=usuario_logado,
        exigir_ativo=False
    )

    if barbeiro.ativo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O barbeiro já está ativo."
        )

    validar_duplicidade_barbeiro(
        db=db,
        usuario_logado=usuario_logado,
        telefone=barbeiro.telefone,
        email=barbeiro.email,
        barbeiro_id_ignorado=barbeiro.id
    )

    return reativar_registro(
        db=db,
        registro=barbeiro
    )