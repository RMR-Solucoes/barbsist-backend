from fastapi import HTTPException, status

import models

from auth.tenant import (
    buscar_da_barbearia,
    consultar_da_barbearia,
    obter_barbearia_id,
)


def _normalizar_nome(nome: str) -> str:
    nome_normalizado = (nome or "").strip()

    if not nome_normalizado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O nome do estilo é obrigatório.",
        )

    return nome_normalizado


def criar_estilo_service(
    db,
    dados,
    usuario_logado,
):
    nome = _normalizar_nome(dados.nome)

    existente = (
        consultar_da_barbearia(
            db=db,
            model=models.Estilo,
            usuario=usuario_logado,
        )
        .filter(
            models.Estilo.nome == nome,
            models.Estilo.categoria
            == dados.categoria,
            models.Estilo.ativo.is_(True),
        )
        .first()
    )

    if existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Já existe um estilo ativo com este "
                "nome e categoria nesta barbearia."
            ),
        )

    try:
        novo_estilo = models.Estilo(
            nome=nome,
            categoria=dados.categoria,
            tipo_cabelo=dados.tipo_cabelo,
            descricao=dados.descricao,
            imagem_url=dados.imagem_url,
            ativo=True,
            barbearia_id=obter_barbearia_id(
                usuario_logado
            ),
        )

        db.add(novo_estilo)
        db.commit()
        db.refresh(novo_estilo)
        return novo_estilo

    except HTTPException:
        db.rollback()
        raise

    except Exception as erro:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao criar estilo: {erro}",
        )


def listar_estilos_service(
    db,
    usuario_logado,
    apenas_ativos: bool = True,
):
    query = consultar_da_barbearia(
        db=db,
        model=models.Estilo,
        usuario=usuario_logado,
    )

    if apenas_ativos:
        query = query.filter(
            models.Estilo.ativo.is_(True)
        )

    return query.order_by(
        models.Estilo.categoria.asc(),
        models.Estilo.nome.asc(),
    ).all()


def buscar_estilo_service(
    db,
    estilo_id: int,
    usuario_logado,
    exigir_ativo: bool = True,
):
    estilo = buscar_da_barbearia(
        db=db,
        model=models.Estilo,
        registro_id=estilo_id,
        usuario=usuario_logado,
        mensagem_nao_encontrado=(
            "Estilo não encontrado."
        ),
    )

    if exigir_ativo and not estilo.ativo:
        raise HTTPException(
            status_code=404,
            detail="Estilo não encontrado ou inativo.",
        )

    return estilo


def atualizar_estilo_service(
    db,
    estilo_id: int,
    dados,
    usuario_logado,
):
    estilo = buscar_estilo_service(
        db=db,
        estilo_id=estilo_id,
        usuario_logado=usuario_logado,
    )

    nome = _normalizar_nome(dados.nome)

    duplicado = (
        consultar_da_barbearia(
            db=db,
            model=models.Estilo,
            usuario=usuario_logado,
        )
        .filter(
            models.Estilo.id != estilo.id,
            models.Estilo.nome == nome,
            models.Estilo.categoria
            == dados.categoria,
            models.Estilo.ativo.is_(True),
        )
        .first()
    )

    if duplicado:
        raise HTTPException(
            status_code=400,
            detail=(
                "Já existe outro estilo ativo com este "
                "nome e categoria nesta barbearia."
            ),
        )

    try:
        estilo.nome = nome
        estilo.categoria = dados.categoria
        estilo.tipo_cabelo = dados.tipo_cabelo
        estilo.descricao = dados.descricao
        estilo.imagem_url = dados.imagem_url

        db.commit()
        db.refresh(estilo)
        return estilo

    except Exception as erro:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao atualizar estilo: {erro}",
        )


def desativar_estilo_service(
    db,
    estilo_id: int,
    usuario_logado,
):
    estilo = buscar_estilo_service(
        db=db,
        estilo_id=estilo_id,
        usuario_logado=usuario_logado,
    )

    try:
        estilo.ativo = False
        db.commit()
        db.refresh(estilo)

        return {
            "mensagem": (
                "Estilo desativado com sucesso."
            ),
            "estilo": {
                "id": estilo.id,
                "nome": estilo.nome,
                "ativo": estilo.ativo,
            },
        }

    except Exception as erro:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao desativar estilo: {erro}",
        )
