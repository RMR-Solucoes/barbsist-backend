from typing import Any, Type

from fastapi import HTTPException, status
from sqlalchemy.orm import Query, Session

import models



PERFIL_SUPERADMIN = "superadmin"


def usuario_eh_superadmin(usuario: models.Usuario | None) -> bool:
    """
    Retorna True quando o usuário possui acesso global à plataforma.

    O perfil superadmin ficará reservado à administração do BarbSist,
    pertencente à RMR Soluções.
    """

    if usuario is None:
        return False

    return usuario.perfil == PERFIL_SUPERADMIN


def obter_barbearia_id(
    usuario: models.Usuario | None,
    permitir_superadmin_sem_barbearia: bool = False
) -> int | None:
    """
    Obtém o barbearia_id do usuário autenticado.

    Usuários comuns precisam obrigatoriamente estar vinculados a uma
    barbearia.

    O superadmin poderá futuramente não possuir uma barbearia específica,
    pois terá atuação administrativa sobre a plataforma.
    """

    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não autenticado."
        )

    if usuario_eh_superadmin(usuario):
        if usuario.barbearia_id is not None:
            return usuario.barbearia_id

        if permitir_superadmin_sem_barbearia:
            return None

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "O superadministrador deve selecionar uma barbearia "
                "para realizar esta operação."
            )
        )

    if usuario.barbearia_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário sem barbearia vinculada."
        )

    return usuario.barbearia_id


def validar_barbearia_ativa(
    db: Session,
    barbearia_id: int
) -> models.Barbearia:
    """
    Busca a barbearia pelo ID e verifica se ela está ativa.

    Retorna a barbearia quando válida.
    """

    barbearia = (
        db.query(models.Barbearia)
        .filter(
            models.Barbearia.id == barbearia_id
        )
        .first()
    )

    if barbearia is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Barbearia não encontrada."
        )

    if not barbearia.ativa:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Não é possível realizar a operação, "
                "pois a barbearia está inativa."
            )
        )

    return barbearia


def obter_barbearia_usuario(
    db: Session,
    usuario: models.Usuario
) -> models.Barbearia:
    """
    Obtém e valida a barbearia vinculada ao usuário.
    """

    barbearia_id = obter_barbearia_id(usuario)

    return validar_barbearia_ativa(
        db=db,
        barbearia_id=barbearia_id
    )


def aplicar_filtro_barbearia(
    query: Query,
    model: Type[Any],
    usuario: models.Usuario,
    permitir_acesso_global_superadmin: bool = False
) -> Query:
    """
    Aplica o filtro da barbearia à consulta.

    Exemplo:

        query = db.query(models.Cliente)

        query = aplicar_filtro_barbearia(
            query=query,
            model=models.Cliente,
            usuario=usuario
        )
    """

    if not hasattr(model, "barbearia_id"):
        raise RuntimeError(
            f"O modelo {model.__name__} não possui barbearia_id."
        )

    if (
        permitir_acesso_global_superadmin
        and usuario_eh_superadmin(usuario)
        and usuario.barbearia_id is None
    ):
        return query

    barbearia_id = obter_barbearia_id(usuario)

    return query.filter(
        model.barbearia_id == barbearia_id
    )


def consultar_da_barbearia(
    db: Session,
    model: Type[Any],
    usuario: models.Usuario,
    permitir_acesso_global_superadmin: bool = False
) -> Query:
    """
    Cria uma consulta já limitada à barbearia do usuário.

    Exemplo:

        clientes = consultar_da_barbearia(
            db=db,
            model=models.Cliente,
            usuario=usuario
        ).all()
    """

    query = db.query(model)

    return aplicar_filtro_barbearia(
        query=query,
        model=model,
        usuario=usuario,
        permitir_acesso_global_superadmin=(
            permitir_acesso_global_superadmin
        )
    )


def buscar_da_barbearia(
    db: Session,
    model: Type[Any],
    registro_id: int,
    usuario: models.Usuario,
    mensagem_nao_encontrado: str = "Registro não encontrado.",
    permitir_acesso_global_superadmin: bool = False
):
    """
    Busca um registro pelo ID dentro da barbearia do usuário.

    Mesmo quando o registro existe em outra barbearia, o retorno será 404.
    Isso evita revelar a existência de dados de outro estabelecimento.
    """

    query = db.query(model).filter(
        model.id == registro_id
    )

    query = aplicar_filtro_barbearia(
        query=query,
        model=model,
        usuario=usuario,
        permitir_acesso_global_superadmin=(
            permitir_acesso_global_superadmin
        )
    )

    registro = query.first()

    if not registro:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=mensagem_nao_encontrado
        )

    return registro


def atribuir_barbearia(
    registro: Any,
    usuario: models.Usuario
):
    """
    Atribui ao registro a barbearia do usuário autenticado.

    Deve ser utilizada na criação de novos registros.
    """

    if not hasattr(registro, "barbearia_id"):
        raise RuntimeError(
            f"O objeto {registro.__class__.__name__} "
            "não possui barbearia_id."
        )

    registro.barbearia_id = obter_barbearia_id(usuario)

    return registro


def criar_registro_da_barbearia(
    model: Type[Any],
    dados: dict,
    usuario: models.Usuario
):
    """
    Cria uma instância de modelo já vinculada à barbearia do usuário.

    Exemplo:

        cliente = criar_registro_da_barbearia(
            model=models.Cliente,
            dados=dados.model_dump(),
            usuario=usuario
        )
    """

    barbearia_id = obter_barbearia_id(usuario)

    return model(
        **dados,
        barbearia_id=barbearia_id
    )


def validar_registro_da_mesma_barbearia(
    registro: Any,
    usuario: models.Usuario
):
    """
    Verifica se um registro pertence à barbearia do usuário.

    Útil quando o registro foi obtido através de relacionamento ou de
    uma função antiga que ainda não utiliza buscar_da_barbearia().
    """

    if registro is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registro não encontrado."
        )

    if not hasattr(registro, "barbearia_id"):
        raise RuntimeError(
            f"O objeto {registro.__class__.__name__} "
            "não possui barbearia_id."
        )

    barbearia_id = obter_barbearia_id(usuario)

    if registro.barbearia_id != barbearia_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registro não encontrado."
        )

    return registro


def validar_ids_da_barbearia(
    db: Session,
    model: Type[Any],
    registros_ids: list[int],
    usuario: models.Usuario,
    mensagem_invalida: str = (
        "Um ou mais registros não foram encontrados nesta barbearia."
    )
):
    """
    Valida uma lista de IDs dentro da barbearia do usuário.

    Será útil, por exemplo, para validar os serviços permitidos de um plano.
    """

    if not registros_ids:
        return []

    ids_unicos = list(set(registros_ids))

    registros = consultar_da_barbearia(
        db=db,
        model=model,
        usuario=usuario
    ).filter(
        model.id.in_(ids_unicos)
    ).all()

    if len(registros) != len(ids_unicos):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=mensagem_invalida
        )

    return registros