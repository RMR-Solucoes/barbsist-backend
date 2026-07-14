from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
import models

from schemas import ProdutoCreate, ProdutoResponse

from auth.permissions import (
    admin_ou_gerente,
    admin_gerente_ou_recepcao
)


router = APIRouter(
    prefix="/produtos",
    tags=["Produtos"],
    dependencies=[
        Depends(admin_gerente_ou_recepcao)
    ]
)


@router.post("", response_model=ProdutoResponse)
def criar_produto(
    produto: ProdutoCreate,
    db: Session = Depends(get_db),
    
):
    novo_produto = models.Produto(
        nome=produto.nome,
        categoria=produto.categoria,
        preco_custo=produto.preco_custo,
        preco_venda=produto.preco_venda,
        estoque=produto.estoque,
        codigo_qr=produto.codigo_qr,
        ativo=True
    )

    db.add(novo_produto)
    db.commit()
    db.refresh(novo_produto)

    return novo_produto


@router.get("", response_model=list[ProdutoResponse])
def listar_produtos(
    db: Session = Depends(get_db)
):
    return db.query(models.Produto).filter(
        models.Produto.ativo == True
    ).all()


@router.get("/{produto_id}", response_model=ProdutoResponse)
def buscar_produto(
    produto_id: int,
    db: Session = Depends(get_db),
    
):
    produto = db.query(models.Produto).filter(
        models.Produto.id == produto_id,
        models.Produto.ativo == True
    ).first()

    if not produto:
        raise HTTPException(
            status_code=404,
            detail="Produto não encontrado ou inativo"
        )

    return produto


@router.put("/{produto_id}", response_model=ProdutoResponse)
def atualizar_produto(
    produto_id: int,
    dados: ProdutoCreate,
    db: Session = Depends(get_db),
    
):
    produto = db.query(models.Produto).filter(
        models.Produto.id == produto_id,
        models.Produto.ativo == True
    ).first()

    if not produto:
        raise HTTPException(
            status_code=404,
            detail="Produto não encontrado ou inativo"
        )

    produto.nome = dados.nome
    produto.categoria = dados.categoria
    produto.preco_custo = dados.preco_custo
    produto.preco_venda = dados.preco_venda
    produto.estoque = dados.estoque
    produto.codigo_qr = dados.codigo_qr

    db.commit()
    db.refresh(produto)

    return produto


@router.delete("/{produto_id}")
def deletar_produto(
    produto_id: int,
    db: Session = Depends(get_db),
    
):
    produto = db.query(models.Produto).filter(
        models.Produto.id == produto_id,
        models.Produto.ativo == True
    ).first()

    if not produto:
        raise HTTPException(
            status_code=404,
            detail="Produto não encontrado ou já inativo"
        )

    produto.ativo = False
    db.commit()
    db.refresh(produto)

    return {
        "mensagem": "Produto desativado com sucesso",
        "produto": {
            "id": produto.id,
            "nome": produto.nome,
            "ativo": produto.ativo
        }
    }