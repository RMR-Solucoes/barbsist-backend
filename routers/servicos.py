from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
import models
from schemas import ServicoCreate, ServicoResponse
from auth.permissions import (
    admin_ou_gerente
)

router = APIRouter(
    prefix="/servicos",
    tags=["Serviços"],
    dependencies=[
        Depends(admin_ou_gerente)
    ]
)


@router.post("", response_model=ServicoResponse)
def criar_servico(
    servico: ServicoCreate,
    db: Session = Depends(get_db)
):
    novo_servico = models.Servico(
        nome=servico.nome,
        preco=servico.preco,
        tempo_medio_minutos=servico.tempo_medio_minutos
    )

    db.add(novo_servico)
    db.commit()
    db.refresh(novo_servico)

    return novo_servico


@router.get("", response_model=list[ServicoResponse])
def listar_servicos(db: Session = Depends(get_db)):
    return db.query(models.Servico).all()


@router.get("/{servico_id}", response_model=ServicoResponse)
def buscar_servico(
    servico_id: int,
    db: Session = Depends(get_db)
):
    servico = db.query(models.Servico).filter(
        models.Servico.id == servico_id
    ).first()

    if not servico:
        raise HTTPException(
            status_code=404,
            detail="Serviço não encontrado"
        )

    return servico


@router.put("/{servico_id}", response_model=ServicoResponse)
def atualizar_servico(
    servico_id: int,
    dados: ServicoCreate,
    db: Session = Depends(get_db)
):
    servico = db.query(models.Servico).filter(
        models.Servico.id == servico_id
    ).first()

    if not servico:
        raise HTTPException(
            status_code=404,
            detail="Serviço não encontrado"
        )

    servico.nome = dados.nome
    servico.preco = dados.preco
    servico.tempo_medio_minutos = dados.tempo_medio_minutos

    db.commit()
    db.refresh(servico)

    return servico


@router.delete("/{servico_id}")
def deletar_servico(
    servico_id: int,
    db: Session = Depends(get_db)
):
    servico = db.query(models.Servico).filter(
        models.Servico.id == servico_id
    ).first()

    if not servico:
        raise HTTPException(
            status_code=404,
            detail="Serviço não encontrado"
        )

    servico.ativo = False
    db.commit()

    return {
        "mensagem": "Serviço desativado com sucesso",
        "servico_id": servico_id
    }