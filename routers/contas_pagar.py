from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date

import models
import schemas
from database import get_db
from auth.permissions import (
    admin_ou_gerente
)

router = APIRouter(
    prefix="/contas-pagar",
    tags=["Contas a Pagar"],
    dependencies=[
        Depends(admin_ou_gerente)
    ]
)


@router.post("", response_model=schemas.ContaPagarResponse)
def criar_conta_pagar(
    dados: schemas.ContaPagarCreate,
    db: Session = Depends(get_db)
):
    nova_conta = models.ContaPagar(
        descricao=dados.descricao,
        fornecedor=dados.fornecedor,
        valor=dados.valor,
        vencimento=dados.vencimento,
        forma_pagamento=dados.forma_pagamento,
        observacoes=dados.observacoes,
        status="PENDENTE"
    )

    db.add(nova_conta)
    db.commit()
    db.refresh(nova_conta)

    return nova_conta


@router.get("", response_model=list[schemas.ContaPagarResponse])
def listar_contas_pagar(
    status: str | None = None,
    db: Session = Depends(get_db)
):
    query = db.query(models.ContaPagar)

    if status:
        query = query.filter(models.ContaPagar.status == status)

    return query.order_by(models.ContaPagar.vencimento.asc()).all()


@router.get("/{conta_id}", response_model=schemas.ContaPagarResponse)
def buscar_conta_pagar(
    conta_id: int,
    db: Session = Depends(get_db)
):
    conta = db.query(models.ContaPagar).filter(
        models.ContaPagar.id == conta_id
    ).first()

    if not conta:
        raise HTTPException(status_code=404, detail="Conta a pagar não encontrada.")

    return conta


@router.put("/{conta_id}/pagar", response_model=schemas.ContaPagarResponse)
def pagar_conta(
    conta_id: int,
    forma_pagamento: str | None = None,
    db: Session = Depends(get_db)
):
    conta = db.query(models.ContaPagar).filter(
        models.ContaPagar.id == conta_id
    ).first()

    if not conta:
        raise HTTPException(status_code=404, detail="Conta a pagar não encontrada.")

    if conta.status == "PAGA":
        raise HTTPException(status_code=400, detail="Conta já paga.")

    conta.status = "PAGA"
    conta.data_pagamento = date.today()

    if forma_pagamento:
        conta.forma_pagamento = forma_pagamento

    db.commit()
    db.refresh(conta)

    return conta


@router.delete("/{conta_id}")
def excluir_conta_pagar(
    conta_id: int,
    db: Session = Depends(get_db)
):
    conta = db.query(models.ContaPagar).filter(
        models.ContaPagar.id == conta_id
    ).first()

    if not conta:
        raise HTTPException(status_code=404, detail="Conta a pagar não encontrada.")

    db.delete(conta)
    db.commit()

    return {"mensagem": "Conta a pagar excluída com sucesso."}