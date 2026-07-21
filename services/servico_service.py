from fastapi import HTTPException, status
from sqlalchemy.orm import Session

import models

from auth.tenant import (
    obter_barbearia_id
)

from services.crud_service import (
    criar_registro_com_codigo,
    consultar_registros,
    buscar_registro,
    salvar_alteracoes,
    inativar_registro,
    reativar_registro
)


def normalizar_nome_servico(
    nome: str
) -> str:
    """
    Remove espaços extras e valida o nome do serviço.
    """

    if nome is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O nome do serviço é obrigatório."
        )

    nome_normalizado = " ".join(
        nome.strip().split()
    )

    if not nome_normalizado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O nome do serviço é obrigatório."
        )

    if len(nome_normalizado) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "O nome do serviço deve possuir "
                "pelo menos 2 caracteres."
            )
        )

    return nome_normalizado


def validar_preco_servico(
    preco: float
) -> float:
    """
    Valida o preço informado para o serviço.
    """

    if preco is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O preço do serviço é obrigatório."
        )

    try:
        preco_validado = float(preco)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O preço do serviço é inválido."
        )

    if preco_validado < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "O preço do serviço não pode "
                "ser negativo."
            )
        )

    return round(
        preco_validado,
        2
    )


def validar_tempo_servico(
    tempo_medio_minutos: int
) -> int:
    """
    Valida o tempo médio do serviço em minutos.
    """

    if tempo_medio_minutos is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "O tempo médio do serviço "
                "é obrigatório."
            )
        )

    try:
        tempo_validado = int(
            tempo_medio_minutos
        )
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "O tempo médio do serviço "
                "é inválido."
            )
        )

    if tempo_validado <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "O tempo médio do serviço deve "
                "ser maior que zero."
            )
        )

    if tempo_validado > 1440:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "O tempo médio do serviço não pode "
                "ultrapassar 1440 minutos."
            )
        )

    return tempo_validado


def validar_duplicidade_servico(
    db: Session,
    usuario_logado: models.Usuario,
    nome: str,
    servico_id_ignorado: int | None = None
):
    """
    Impede nomes duplicados dentro da mesma barbearia.

    Barbearias diferentes podem possuir serviços
    com o mesmo nome.
    """

    barbearia_id = obter_barbearia_id(
        usuario_logado
    )

    query = (
        db.query(models.Servico)
        .filter(
            models.Servico.barbearia_id
            == barbearia_id,

            models.Servico.nome.ilike(
                nome
            )
        )
    )

    if servico_id_ignorado is not None:
        query = query.filter(
            models.Servico.id
            != servico_id_ignorado
        )

    servico_existente = query.first()

    if servico_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Já existe um serviço com este nome "
                "nesta barbearia."
            )
        )


def criar_servico_service(
    dados,
    db: Session,
    usuario_logado: models.Usuario
):
    """
    Cria um serviço vinculado automaticamente à
    barbearia do usuário autenticado.
    """

    nome = normalizar_nome_servico(
        dados.nome
    )

    preco = validar_preco_servico(
        dados.preco
    )

    tempo_medio_minutos = validar_tempo_servico(
        dados.tempo_medio_minutos
    )

    validar_duplicidade_servico(
        db=db,
        usuario_logado=usuario_logado,
        nome=nome
    )

    return criar_registro_com_codigo(
        db=db,
        model=models.Servico,
        tipo_sequencia="SERVICO",
        usuario_logado=usuario_logado,
        dados={
            "nome": nome,
            "preco": preco,
            "tempo_medio_minutos": (
                tempo_medio_minutos
            ),
            "ativo": True
        }
    )


def listar_servicos_service(
    db: Session,
    usuario_logado: models.Usuario,
    apenas_ativos: bool = True
):
    """
    Lista somente os serviços pertencentes à
    barbearia do usuário autenticado.
    """

    query = consultar_registros(
        db=db,
        model=models.Servico,
        usuario_logado=usuario_logado,
        apenas_ativos=apenas_ativos
    )

    return (
        query
        .order_by(
            models.Servico.nome.asc()
        )
        .all()
    )


def buscar_servico_service(
    servico_id: int,
    db: Session,
    usuario_logado: models.Usuario,
    exigir_ativo: bool = True
):
    """
    Busca um serviço dentro da barbearia atual.

    Serviços de outras barbearias são tratados como
    registros inexistentes.
    """

    return buscar_registro(
        db=db,
        model=models.Servico,
        registro_id=servico_id,
        usuario_logado=usuario_logado,
        mensagem_nao_encontrado=(
            "Serviço não encontrado."
        ),
        exigir_ativo=exigir_ativo
    )


def atualizar_servico_service(
    servico_id: int,
    dados,
    db: Session,
    usuario_logado: models.Usuario
):
    """
    Atualiza um serviço pertencente à barbearia atual.
    """

    servico = buscar_servico_service(
        servico_id=servico_id,
        db=db,
        usuario_logado=usuario_logado,
        exigir_ativo=True
    )

    nome = normalizar_nome_servico(
        dados.nome
    )

    preco = validar_preco_servico(
        dados.preco
    )

    tempo_medio_minutos = validar_tempo_servico(
        dados.tempo_medio_minutos
    )

    validar_duplicidade_servico(
        db=db,
        usuario_logado=usuario_logado,
        nome=nome,
        servico_id_ignorado=servico.id
    )

    servico.nome = nome
    servico.preco = preco
    servico.tempo_medio_minutos = (
        tempo_medio_minutos
    )

    return salvar_alteracoes(
        db=db,
        registro=servico,
        mensagem_erro=(
            "Não foi possível atualizar o serviço. "
            "Verifique os dados informados."
        )
    )


def inativar_servico_service(
    servico_id: int,
    db: Session,
    usuario_logado: models.Usuario
):
    """
    Inativa um serviço sem excluir seu histórico.
    """

    servico = buscar_servico_service(
        servico_id=servico_id,
        db=db,
        usuario_logado=usuario_logado,
        exigir_ativo=False
    )

    if not servico.ativo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O serviço já está inativo."
        )

    return inativar_registro(
        db=db,
        registro=servico
    )


def reativar_servico_service(
    servico_id: int,
    db: Session,
    usuario_logado: models.Usuario
):
    """
    Reativa um serviço pertencente à barbearia atual.
    """

    servico = buscar_servico_service(
        servico_id=servico_id,
        db=db,
        usuario_logado=usuario_logado,
        exigir_ativo=False
    )

    if servico.ativo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O serviço já está ativo."
        )

    validar_duplicidade_servico(
        db=db,
        usuario_logado=usuario_logado,
        nome=servico.nome,
        servico_id_ignorado=servico.id
    )

    return reativar_registro(
        db=db,
        registro=servico
    )