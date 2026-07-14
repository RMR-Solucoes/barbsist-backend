from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
import models
from schemas import (
    BarbeariaCreate,
    BarbeariaUpdate,
    BarbeariaResponse
)

router = APIRouter(
    prefix="/barbearia",
    tags=["Barbearia"]
)


@router.get("", response_model=BarbeariaResponse)
def obter_barbearia(
    db: Session = Depends(get_db)
):
    barbearia = db.query(
        models.Barbearia
    ).first()

    if not barbearia:
        raise HTTPException(
            status_code=404,
            detail="Barbearia não cadastrada."
        )

    return barbearia


@router.post("", response_model=BarbeariaResponse)
def criar_barbearia(
    dados: BarbeariaCreate,
    db: Session = Depends(get_db)
):
    existente = db.query(
        models.Barbearia
    ).first()

    if existente:
        raise HTTPException(
            status_code=400,
            detail="A barbearia já foi cadastrada."
        )

    barbearia = models.Barbearia(
        nome=dados.nome,
        telefone_whatsapp=dados.telefone_whatsapp,
        endereco=dados.endereco,
        instagram=dados.instagram,
        logo_url=dados.logo_url,
        slogan=dados.slogan,
        imagem_capa_url=dados.imagem_capa_url,
    )

    db.add(barbearia)
    db.commit()
    db.refresh(barbearia)

    return barbearia


@router.put("", response_model=BarbeariaResponse)
def atualizar_barbearia(
    dados: BarbeariaUpdate,
    db: Session = Depends(get_db)
):
    barbearia = db.query(
        models.Barbearia
    ).first()

    if not barbearia:
        raise HTTPException(
            status_code=404,
            detail="Barbearia não encontrada."
        )

    barbearia.nome = dados.nome
    barbearia.telefone_whatsapp = dados.telefone_whatsapp
    barbearia.endereco = dados.endereco
    barbearia.instagram = dados.instagram
    barbearia.logo_url = dados.logo_url
    barbearia.slogan = dados.slogan
    barbearia.imagem_capa_url = dados.imagem_capa_url

    db.commit()
    db.refresh(barbearia)

    return barbearia