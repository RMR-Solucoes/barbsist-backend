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
    prefix="/contas-receber",
    tags=["Contas a Receber"],
    dependencies=[
        Depends(admin_ou_gerente)
    ]
)


@router.post("", response_model=schemas.ContaReceberResponse)
def criar_conta_receber(
    dados: schemas.ContaReceberCreate,
    db: Session = Depends(get_db)
):
    nova_conta = models.ContaReceber(
        descricao=dados.descricao,
        cliente_id=dados.cliente_id,
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


@router.get("", response_model=list[schemas.ContaReceberResponse])
def listar_contas_receber(
    status: str | None = None,
    db: Session = Depends(get_db)
):
    query = db.query(models.ContaReceber)

    if status:
        query = query.filter(models.ContaReceber.status == status)

    return query.order_by(models.ContaReceber.vencimento.asc()).all()


@router.get("/{conta_id}", response_model=schemas.ContaReceberResponse)
def buscar_conta_receber(
    conta_id: int,
    db: Session = Depends(get_db)
):
    conta = db.query(models.ContaReceber).filter(
        models.ContaReceber.id == conta_id
    ).first()

    if not conta:
        raise HTTPException(status_code=404, detail="Conta a receber não encontrada.")

    return conta


@router.put("/{conta_id}/receber", response_model=schemas.ContaReceberResponse)
def receber_conta(
    conta_id: int,
    forma_pagamento: str | None = None,
    db: Session = Depends(get_db)
):
    conta = db.query(models.ContaReceber).filter(
        models.ContaReceber.id == conta_id
    ).first()

    if not conta:
        raise HTTPException(status_code=404, detail="Conta a receber não encontrada.")

    if conta.status == "RECEBIDA":
        raise HTTPException(status_code=400, detail="Conta já recebida.")

    conta.status = "RECEBIDA"
    conta.data_pagamento = date.today()

    if forma_pagamento:
        conta.forma_pagamento = forma_pagamento

    db.commit()
    db.refresh(conta)

    return conta


@router.delete("/{conta_id}")
def excluir_conta_receber(
    conta_id: int,
    db: Session = Depends(get_db)
):
    conta = db.query(models.ContaReceber).filter(
        models.ContaReceber.id == conta_id
    ).first()

    if not conta:
        raise HTTPException(status_code=404, detail="Conta a receber não encontrada.")

    db.delete(conta)
    db.commit()

    return {"mensagem": "Conta a receber excluída com sucesso."}