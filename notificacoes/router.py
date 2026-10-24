"""API interna de notificacoes do BarbSist.

Isolamento obrigatorio pela barbearia do usuario autenticado.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from auth.permissions import admin_gerente_recepcao_ou_barbeiro
from auth.tenant import obter_barbearia_id

from notificacoes.servico import (
    listar_notificacoes,
    contar_nao_lidas,
    marcar_como_lida,
)


router = APIRouter(
    prefix="/notificacoes",
    tags=["Notificacoes"],
)


def _resposta_notificacao(item):
    return {
        "id": item.id,
        "agendamento_id": item.agendamento_id,
        "tipo": item.tipo,
        "titulo": item.titulo,
        "mensagem": item.mensagem,
        "lida": item.lida,
        "criada_em": (
            item.criada_em.isoformat()
            if item.criada_em is not None
            else None
        ),
    }


@router.get("")
def consultar_notificacoes(
    limite: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_recepcao_ou_barbeiro
    ),
):
    barbearia_id = obter_barbearia_id(usuario_logado)

    itens = listar_notificacoes(
        db,
        barbearia_id=barbearia_id,
        limite=limite,
    )

    return {
        "notificacoes": [
            _resposta_notificacao(item)
            for item in itens
        ],
        "total": len(itens),
    }


@router.get("/nao-lidas")
def consultar_nao_lidas(
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_recepcao_ou_barbeiro
    ),
):
    barbearia_id = obter_barbearia_id(usuario_logado)

    return {
        "nao_lidas": contar_nao_lidas(
            db,
            barbearia_id=barbearia_id,
        )
    }


@router.put("/{notificacao_id}/ler")
def ler_notificacao(
    notificacao_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_recepcao_ou_barbeiro
    ),
):
    barbearia_id = obter_barbearia_id(usuario_logado)

    notificacao = marcar_como_lida(
        db,
        barbearia_id=barbearia_id,
        notificacao_id=notificacao_id,
    )

    if notificacao is None:
        raise HTTPException(
            status_code=404,
            detail="Notificacao nao encontrada.",
        )

    try:
        db.commit()
        db.refresh(notificacao)
    except Exception:
        db.rollback()
        raise

    return {
        "mensagem": "Notificacao marcada como lida.",
        "notificacao": _resposta_notificacao(notificacao),
    }