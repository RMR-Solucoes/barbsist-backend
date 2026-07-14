from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
import models

from schemas import CaixaCreate, CaixaResponse
from services.caixa_service import registrar_movimentacao_caixa
from auth.permissions import (
    admin_gerente_ou_recepcao
)

router = APIRouter(
    prefix="/caixa",
    tags=["Caixa"],
    dependencies=[
        Depends(admin_gerente_ou_recepcao)
    ]
)


@router.get("", response_model=list[CaixaResponse])
def listar_caixa(
    db: Session = Depends(get_db)
):
    return db.query(models.Caixa).order_by(
        models.Caixa.data.desc()
    ).all()


@router.post("", response_model=CaixaResponse)
def criar_movimentacao_caixa(
    dados: CaixaCreate,
    db: Session = Depends(get_db)
):
    if dados.tipo not in ["entrada", "saida"]:
        raise HTTPException(
            status_code=400,
            detail="Tipo deve ser 'entrada' ou 'saida'"
        )

    if dados.valor <= 0:
        raise HTTPException(
            status_code=400,
            detail="O valor deve ser maior que zero"
        )

    return registrar_movimentacao_caixa(db, dados)