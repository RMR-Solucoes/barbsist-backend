from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import re

from database import get_db
import models
from schemas import BarbeiroCreate, BarbeiroResponse
from auth.permissions import (
    admin_ou_gerente
)

router = APIRouter(
    prefix="/barbeiros",
    tags=["Barbeiros"],
    dependencies=[
        Depends(admin_ou_gerente)
    ]
)


def normalizar_texto(valor: str | None) -> str | None:
    if valor is None:
        return None

    valor = valor.strip()

    if not valor:
        return None

    return valor.upper()


def normalizar_email(valor: str | None) -> str | None:
    if valor is None:
        return None

    valor = valor.strip().lower()

    if not valor:
        return None

    return valor


def limpar_telefone(valor: str | None) -> str | None:
    if valor is None:
        return None

    numeros = re.sub(r"\D", "", valor)

    if not numeros:
        return None

    return numeros


def validar_percentual(percentual: float | None):
    if percentual is None:
        return

    if percentual < 0 or percentual > 100:
        raise HTTPException(
            status_code=400,
            detail="O percentual de comissão deve estar entre 0 e 100."
        )


def verificar_duplicidade_barbeiro(
    db: Session,
    telefone: str | None,
    email: str | None,
    barbeiro_id: int | None = None
):
    if telefone:
        query = db.query(models.Barbeiro).filter(
            models.Barbeiro.telefone == telefone
        )

        if barbeiro_id:
            query = query.filter(models.Barbeiro.id != barbeiro_id)

        barbeiro_existente = query.first()

        if barbeiro_existente:
            raise HTTPException(
                status_code=400,
                detail="Já existe um barbeiro cadastrado com este telefone."
            )

    if email:
        query = db.query(models.Barbeiro).filter(
            models.Barbeiro.email == email
        )

        if barbeiro_id:
            query = query.filter(models.Barbeiro.id != barbeiro_id)

        barbeiro_existente = query.first()

        if barbeiro_existente:
            raise HTTPException(
                status_code=400,
                detail="Já existe um barbeiro cadastrado com este e-mail."
            )


@router.post("", response_model=BarbeiroResponse)
def criar_barbeiro(
    barbeiro: BarbeiroCreate,
    db: Session = Depends(get_db)
):
    nome = normalizar_texto(barbeiro.nome)
    telefone = limpar_telefone(barbeiro.telefone)
    email = normalizar_email(barbeiro.email)
    tipo = normalizar_texto(barbeiro.tipo) or "ASSOCIADO"
    especialidades = normalizar_texto(barbeiro.especialidades)
    observacoes = normalizar_texto(barbeiro.observacoes)

    if not nome:
        raise HTTPException(
            status_code=400,
            detail="Informe o nome do barbeiro."
        )

    if not telefone:
        raise HTTPException(
            status_code=400,
            detail="Informe o telefone do barbeiro."
        )

    if len(telefone) < 10:
        raise HTTPException(
            status_code=400,
            detail="Informe um telefone válido com DDD."
        )

    validar_percentual(barbeiro.percentual_comissao)

    verificar_duplicidade_barbeiro(
        db=db,
        telefone=telefone,
        email=email
    )

    novo_barbeiro = models.Barbeiro(
        nome=nome,
        telefone=telefone,
        email=email,
        tipo=tipo,
        percentual_comissao=barbeiro.percentual_comissao,
        especialidades=especialidades,
        observacoes=observacoes,
        ativo=True
    )

    db.add(novo_barbeiro)
    db.commit()
    db.refresh(novo_barbeiro)

    return novo_barbeiro

@router.get("", response_model=list[BarbeiroResponse])
def listar_barbeiros(
    db: Session = Depends(get_db)
):
    return db.query(models.Barbeiro).order_by(
        models.Barbeiro.nome
    ).all()


@router.put("/{barbeiro_id}/reativar", response_model=BarbeiroResponse)
def reativar_barbeiro(
    barbeiro_id: int,
    db: Session = Depends(get_db)
):
    barbeiro = db.query(models.Barbeiro).filter(
        models.Barbeiro.id == barbeiro_id
    ).first()

    if not barbeiro:
        raise HTTPException(
            status_code=404,
            detail="Barbeiro não encontrado."
        )

    barbeiro.ativo = True

    db.commit()
    db.refresh(barbeiro)

    return barbeiro


@router.delete("/{barbeiro_id}/excluir")
def excluir_barbeiro_definitivamente(
    barbeiro_id: int,
    db: Session = Depends(get_db)
):
    barbeiro = db.query(models.Barbeiro).filter(
        models.Barbeiro.id == barbeiro_id
    ).first()

    if not barbeiro:
        raise HTTPException(
            status_code=404,
            detail="Barbeiro não encontrado."
        )

    db.delete(barbeiro)
    db.commit()

    return {
        "mensagem": "Barbeiro excluído definitivamente.",
        "barbeiro_id": barbeiro_id
    }


@router.get("/{barbeiro_id}", response_model=BarbeiroResponse)
def buscar_barbeiro(
    barbeiro_id: int,
    db: Session = Depends(get_db)
):
    barbeiro = db.query(models.Barbeiro).filter(
        models.Barbeiro.id == barbeiro_id
    ).first()

    if not barbeiro:
        raise HTTPException(
            status_code=404,
            detail="Barbeiro não encontrado."
        )

    return barbeiro


@router.put("/{barbeiro_id}", response_model=BarbeiroResponse)
def atualizar_barbeiro(
    barbeiro_id: int,
    dados: BarbeiroCreate,
    db: Session = Depends(get_db)
):
    barbeiro = db.query(models.Barbeiro).filter(
        models.Barbeiro.id == barbeiro_id
    ).first()

    if not barbeiro:
        raise HTTPException(
            status_code=404,
            detail="Barbeiro não encontrado."
        )

    nome = normalizar_texto(dados.nome)
    telefone = limpar_telefone(dados.telefone)
    email = normalizar_email(dados.email)
    tipo = normalizar_texto(dados.tipo) or "ASSOCIADO"
    especialidades = normalizar_texto(dados.especialidades)
    observacoes = normalizar_texto(dados.observacoes)

    if not nome:
        raise HTTPException(
            status_code=400,
            detail="Informe o nome do barbeiro."
        )

    if not telefone:
        raise HTTPException(
            status_code=400,
            detail="Informe o telefone do barbeiro."
        )

    if len(telefone) < 10:
        raise HTTPException(
            status_code=400,
            detail="Informe um telefone válido com DDD."
        )

    validar_percentual(dados.percentual_comissao)

    verificar_duplicidade_barbeiro(
        db=db,
        telefone=telefone,
        email=email,
        barbeiro_id=barbeiro_id
    )

    barbeiro.nome = nome
    barbeiro.telefone = telefone
    barbeiro.email = email
    barbeiro.tipo = tipo
    barbeiro.percentual_comissao = dados.percentual_comissao
    barbeiro.especialidades = especialidades
    barbeiro.observacoes = observacoes

    db.commit()
    db.refresh(barbeiro)

    return barbeiro


@router.delete("/{barbeiro_id}")
def deletar_barbeiro(
    barbeiro_id: int,
    db: Session = Depends(get_db)
):
    barbeiro = db.query(models.Barbeiro).filter(
        models.Barbeiro.id == barbeiro_id
    ).first()

    if not barbeiro:
        raise HTTPException(
            status_code=404,
            detail="Barbeiro não encontrado."
        )

    barbeiro.ativo = False
    db.commit()

    return {
        "mensagem": "Barbeiro desativado com sucesso.",
        "barbeiro_id": barbeiro_id
    }