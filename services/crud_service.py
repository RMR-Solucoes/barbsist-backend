from typing import Any, Type

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models

from auth.tenant import (
    buscar_da_barbearia,
    consultar_da_barbearia,
    obter_barbearia_usuario
)

from services.sequencia_service import (
    gerar_codigo_comercial
)


def criar_registro_com_codigo(
    db: Session,
    model: Type[Any],
    dados: dict,
    tipo_sequencia: str,
    usuario_logado: models.Usuario
):
    """
    Cria um registro vinculado à barbearia atual e gera
    automaticamente seu código comercial.

    O commit fica centralizado nesta função.
    """

    barbearia = obter_barbearia_usuario(
        db=db,
        usuario=usuario_logado
    )

    try:
        numero_sequencial, codigo = (
            gerar_codigo_comercial(
                db=db,
                barbearia=barbearia,
                tipo=tipo_sequencia
            )
        )

        registro = model(
            **dados,
            barbearia_id=barbearia.id,
            numero_sequencial=numero_sequencial,
            codigo=codigo
        )

        db.add(registro)
        db.commit()
        db.refresh(registro)

        return registro

    except HTTPException:
        db.rollback()
        raise

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Não foi possível cadastrar o registro. "
                "Verifique se os dados já estão sendo utilizados."
            )
        )

    except Exception:
        db.rollback()
        raise


def consultar_registros(
    db: Session,
    model: Type[Any],
    usuario_logado: models.Usuario,
    apenas_ativos: bool = False
):
    """
    Inicia uma consulta limitada à barbearia atual.

    Retorna a query para permitir filtros e ordenações
    específicas no service de cada módulo.
    """

    query = consultar_da_barbearia(
        db=db,
        model=model,
        usuario=usuario_logado
    )

    if apenas_ativos:
        if not hasattr(model, "ativo"):
            raise RuntimeError(
                f"O modelo {model.__name__} "
                "não possui a coluna ativo."
            )

        query = query.filter(
            model.ativo.is_(True)
        )

    return query


def listar_registros(
    db: Session,
    model: Type[Any],
    usuario_logado: models.Usuario,
    apenas_ativos: bool = False
) -> list[Any]:
    """
    Lista registros da barbearia atual.
    """

    return consultar_registros(
        db=db,
        model=model,
        usuario_logado=usuario_logado,
        apenas_ativos=apenas_ativos
    ).all()


def buscar_registro(
    db: Session,
    model: Type[Any],
    registro_id: int,
    usuario_logado: models.Usuario,
    mensagem_nao_encontrado: str = (
        "Registro não encontrado."
    ),
    exigir_ativo: bool = False
):
    """
    Busca um registro pelo ID dentro da barbearia atual.

    Registros de outras barbearias serão tratados como
    não encontrados.
    """

    registro = buscar_da_barbearia(
        db=db,
        model=model,
        registro_id=registro_id,
        usuario=usuario_logado,
        mensagem_nao_encontrado=(
            mensagem_nao_encontrado
        )
    )

    if exigir_ativo:
        if not hasattr(registro, "ativo"):
            raise RuntimeError(
                f"O modelo {model.__name__} "
                "não possui a coluna ativo."
            )

        if not registro.ativo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=mensagem_nao_encontrado
            )

    return registro


def salvar_alteracoes(
    db: Session,
    registro: Any,
    mensagem_erro: str = (
        "Não foi possível salvar as alterações."
    )
):
    """
    Confirma alterações em um registro existente.
    """

    try:
        db.commit()
        db.refresh(registro)

        return registro

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=mensagem_erro
        )

    except Exception:
        db.rollback()
        raise


def inativar_registro(
    db: Session,
    registro: Any
):
    """
    Realiza exclusão lógica.
    """

    if not hasattr(registro, "ativo"):
        raise RuntimeError(
            f"O modelo {registro.__class__.__name__} "
            "não possui a coluna ativo."
        )

    if not registro.ativo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registro já está inativo."
        )

    registro.ativo = False

    return salvar_alteracoes(
        db=db,
        registro=registro,
        mensagem_erro=(
            "Não foi possível inativar o registro."
        )
    )


def reativar_registro(
    db: Session,
    registro: Any
):
    """
    Reativa um registro inativo.
    """

    if not hasattr(registro, "ativo"):
        raise RuntimeError(
            f"O modelo {registro.__class__.__name__} "
            "não possui a coluna ativo."
        )

    if registro.ativo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registro já está ativo."
        )

    registro.ativo = True

    return salvar_alteracoes(
        db=db,
        registro=registro,
        mensagem_erro=(
            "Não foi possível reativar o registro."
        )
    )