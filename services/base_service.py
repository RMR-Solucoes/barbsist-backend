from typing import Any, Type

from fastapi import HTTPException, status
from sqlalchemy.orm import Query, Session

import models

from auth.tenant import (
    aplicar_filtro_barbearia,
    obter_barbearia_id
)


def iniciar_consulta(
    db: Session,
    model: Type[Any],
    usuario: models.Usuario
) -> Query:
    """
    Inicia uma consulta limitada à barbearia do usuário.
    """

    query = db.query(model)

    return aplicar_filtro_barbearia(
        query=query,
        model=model,
        usuario=usuario
    )


def buscar_registro(
    db: Session,
    model: Type[Any],
    registro_id: int,
    usuario: models.Usuario,
    mensagem_nao_encontrado: str = "Registro não encontrado."
):
    """
    Busca um registro pelo ID dentro da barbearia atual.

    Mesmo que o ID exista em outra barbearia, será retornado 404.
    """

    registro = iniciar_consulta(
        db=db,
        model=model,
        usuario=usuario
    ).filter(
        model.id == registro_id
    ).first()

    if not registro:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=mensagem_nao_encontrado
        )

    return registro


def listar_registros(
    db: Session,
    model: Type[Any],
    usuario: models.Usuario
) -> list[Any]:
    """
    Lista os registros da barbearia atual.
    """

    return iniciar_consulta(
        db=db,
        model=model,
        usuario=usuario
    ).all()


def criar_instancia(
    model: Type[Any],
    dados: dict,
    usuario: models.Usuario
):
    """
    Cria uma instância já vinculada à barbearia do usuário.

    Esta função não salva no banco.
    """

    barbearia_id = obter_barbearia_id(
        usuario
    )

    return model(
        **dados,
        barbearia_id=barbearia_id
    )


def salvar_registro(
    db: Session,
    registro: Any
):
    """
    Salva um registro e atualiza seus dados.
    """

    try:
        db.add(registro)
        db.commit()
        db.refresh(registro)

    except Exception:
        db.rollback()
        raise

    return registro


def excluir_logicamente(
    db: Session,
    registro: Any
):
    """
    Inativa um registro que possua a coluna ativo.

    Não realiza exclusão física.
    """

    if not hasattr(registro, "ativo"):
        raise RuntimeError(
            f"O modelo {registro.__class__.__name__} "
            "não possui a coluna ativo."
        )

    registro.ativo = False

    try:
        db.commit()
        db.refresh(registro)

    except Exception:
        db.rollback()
        raise

    return registro


def reativar_registro(
    db: Session,
    registro: Any
):
    """
    Reativa um registro que possua a coluna ativo.
    """

    if not hasattr(registro, "ativo"):
        raise RuntimeError(
            f"O modelo {registro.__class__.__name__} "
            "não possui a coluna ativo."
        )

    registro.ativo = True

    try:
        db.commit()
        db.refresh(registro)

    except Exception:
        db.rollback()
        raise

    return registro