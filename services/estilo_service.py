from fastapi import HTTPException

import models


def criar_estilo_service(db, dados):
    novo_estilo = models.Estilo(
        nome=dados.nome,
        categoria=dados.categoria,
        tipo_cabelo=dados.tipo_cabelo,
        descricao=dados.descricao,
        imagem_url=dados.imagem_url,
        ativo=True
    )

    db.add(novo_estilo)
    db.commit()
    db.refresh(novo_estilo)

    return novo_estilo


def listar_estilos_service(db):
    return db.query(models.Estilo).filter(
        models.Estilo.ativo == True
    ).all()


def buscar_estilo_service(db, estilo_id: int):
    estilo = db.query(models.Estilo).filter(
        models.Estilo.id == estilo_id,
        models.Estilo.ativo == True
    ).first()

    if not estilo:
        raise HTTPException(
            status_code=404,
            detail="Estilo não encontrado ou inativo"
        )

    return estilo


def atualizar_estilo_service(db, estilo_id: int, dados):
    estilo = buscar_estilo_service(db, estilo_id)

    estilo.nome = dados.nome
    estilo.categoria = dados.categoria
    estilo.tipo_cabelo = dados.tipo_cabelo
    estilo.descricao = dados.descricao
    estilo.imagem_url = dados.imagem_url

    db.commit()
    db.refresh(estilo)

    return estilo


def desativar_estilo_service(db, estilo_id: int):
    estilo = buscar_estilo_service(db, estilo_id)

    estilo.ativo = False

    db.commit()
    db.refresh(estilo)

    return {
        "mensagem": "Estilo desativado com sucesso",
        "estilo": {
            "id": estilo.id,
            "nome": estilo.nome,
            "ativo": estilo.ativo
        }
    }