from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
import models

from schemas import (
    ClienteCreate,
    ClienteResponse,
    ClienteComAssinaturaResponse
)

from auth.permissions import (
    admin_gerente_recepcao_ou_barbeiro
)

from auth.dependencies import (
    get_barbeiro_logado
)

from services.cliente_service import (
    listar_clientes_com_assinaturas_service
)

router = APIRouter(
    prefix="/clientes",
    tags=["Clientes"],
    dependencies=[
        Depends(admin_gerente_recepcao_ou_barbeiro)
    ]
)


@router.post("", response_model=ClienteResponse)
def criar_cliente(
    cliente: ClienteCreate,
    db: Session = Depends(get_db)
):
    novo_cliente = models.Cliente(
        nome=cliente.nome,
        telefone=cliente.telefone,
        email=cliente.email,
        observacoes=cliente.observacoes
    )

    db.add(novo_cliente)
    db.commit()
    db.refresh(novo_cliente)

    return novo_cliente


@router.get("", response_model=list[ClienteResponse])
def listar_clientes(
    db: Session = Depends(get_db),
    usuario=Depends(admin_gerente_recepcao_ou_barbeiro)
):
    return db.query(models.Cliente).filter(
        models.Cliente.ativo == True
    ).all()


@router.get(
    "/com-assinaturas",
    response_model=list[
        ClienteComAssinaturaResponse
    ]
)
def listar_clientes_com_assinaturas(
    db: Session = Depends(get_db)
):
    return listar_clientes_com_assinaturas_service(
        db=db
    )

@router.get(
    "/meus",
    response_model=list[ClienteResponse]
)
def meus_clientes(
    barbeiro_id: int = Depends(get_barbeiro_logado),
    db: Session = Depends(get_db)
):
    clientes = (
        db.query(models.Cliente)
        .join(models.Comanda, models.Comanda.cliente_id == models.Cliente.id)
        .filter(
            models.Comanda.barbeiro_id == barbeiro_id,
            models.Cliente.ativo == True
        )
        .distinct()
        .all()
    )

    return clientes


@router.get("/{cliente_id}", response_model=ClienteResponse)
def buscar_cliente(
    cliente_id: int,
    db: Session = Depends(get_db)
):
    cliente = db.query(models.Cliente).filter(
        models.Cliente.id == cliente_id,
        models.Cliente.ativo == True
    ).first()

    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    return cliente


@router.put("/{cliente_id}", response_model=ClienteResponse)
def atualizar_cliente(
    cliente_id: int,
    cliente: ClienteCreate,
    db: Session = Depends(get_db)
):
    cliente_db = db.query(models.Cliente).filter(
        models.Cliente.id == cliente_id,
        models.Cliente.ativo == True
    ).first()

    if not cliente_db:
        raise HTTPException(
            status_code=404,
            detail="Cliente não encontrado"
        )

    cliente_db.nome = cliente.nome
    cliente_db.telefone = cliente.telefone
    cliente_db.email = cliente.email
    cliente_db.observacoes = cliente.observacoes

    db.commit()
    db.refresh(cliente_db)

    return cliente_db


@router.delete("/{cliente_id}")
def deletar_cliente(
    cliente_id: int,
    db: Session = Depends(get_db)
):
    cliente = db.query(models.Cliente).filter(
        models.Cliente.id == cliente_id,
        models.Cliente.ativo == True
    ).first()

    if not cliente:
        raise HTTPException(
            status_code=404,
            detail="Cliente não encontrado"
        )

    cliente.ativo = False

    db.commit()

    return {
        "mensagem": "Cliente deletado com sucesso"
    }