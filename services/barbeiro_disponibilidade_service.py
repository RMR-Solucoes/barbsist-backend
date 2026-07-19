from sqlalchemy.orm import Session

import models

from auth.tenant import (
    buscar_da_barbearia,
    obter_barbearia_id,
)
from schemas import BarbeiroDisponibilidadeUpdate


def criar_disponibilidade_padrao_por_barbearia(
    db: Session,
    barbeiro_id: int,
    barbearia_id: int,
):
    barbeiro = (
        db.query(models.Barbeiro)
        .filter(
            models.Barbeiro.id == barbeiro_id,
            models.Barbeiro.barbearia_id == barbearia_id,
            models.Barbeiro.ativo.is_(True),
        )
        .first()
    )

    if not barbeiro:
        return None

    existentes = (
        db.query(models.BarbeiroDisponibilidade)
        .filter(
            models.BarbeiroDisponibilidade.barbearia_id
            == barbearia_id,
            models.BarbeiroDisponibilidade.barbeiro_id
            == barbeiro_id,
        )
        .order_by(models.BarbeiroDisponibilidade.dia_semana)
        .all()
    )

    dias_existentes = {item.dia_semana for item in existentes}
    novos = []

    for dia in range(7):
        if dia in dias_existentes:
            continue

        item = models.BarbeiroDisponibilidade(
            barbearia_id=barbearia_id,
            barbeiro_id=barbeiro_id,
            usa_padrao=True,
            dia_semana=dia,
            trabalha=True,
            hora_inicio="08:00",
            hora_fim="20:00",
        )
        db.add(item)
        novos.append(item)

    if novos:
        db.commit()

    return (
        db.query(models.BarbeiroDisponibilidade)
        .filter(
            models.BarbeiroDisponibilidade.barbearia_id
            == barbearia_id,
            models.BarbeiroDisponibilidade.barbeiro_id
            == barbeiro_id,
        )
        .order_by(models.BarbeiroDisponibilidade.dia_semana)
        .all()
    )


def criar_disponibilidade_padrao_barbeiro(
    db: Session,
    barbeiro_id: int,
    usuario_logado=None,
):
    if usuario_logado is None:
        barbeiro = (
            db.query(models.Barbeiro)
            .filter(models.Barbeiro.id == barbeiro_id)
            .first()
        )
        if not barbeiro:
            return None

        return criar_disponibilidade_padrao_por_barbearia(
            db=db,
            barbeiro_id=barbeiro.id,
            barbearia_id=barbeiro.barbearia_id,
        )

    barbeiro = buscar_da_barbearia(
        db=db,
        model=models.Barbeiro,
        registro_id=barbeiro_id,
        usuario=usuario_logado,
        mensagem_nao_encontrado="Barbeiro não encontrado.",
    )

    return criar_disponibilidade_padrao_por_barbearia(
        db=db,
        barbeiro_id=barbeiro.id,
        barbearia_id=obter_barbearia_id(usuario_logado),
    )


def listar_disponibilidade_por_barbeiro(
    db: Session,
    barbeiro_id: int,
    usuario_logado,
):
    return criar_disponibilidade_padrao_barbeiro(
        db,
        barbeiro_id,
        usuario_logado,
    )


def buscar_disponibilidade_publica(
    db: Session,
    barbeiro_id: int,
    barbearia_id: int,
    dia_semana: int,
):
    criar_disponibilidade_padrao_por_barbearia(
        db=db,
        barbeiro_id=barbeiro_id,
        barbearia_id=barbearia_id,
    )

    return (
        db.query(models.BarbeiroDisponibilidade)
        .filter(
            models.BarbeiroDisponibilidade.barbearia_id
            == barbearia_id,
            models.BarbeiroDisponibilidade.barbeiro_id
            == barbeiro_id,
            models.BarbeiroDisponibilidade.dia_semana
            == dia_semana,
        )
        .first()
    )


def atualizar_disponibilidade(
    db: Session,
    disponibilidade_id: int,
    dados: BarbeiroDisponibilidadeUpdate,
    usuario_logado,
):
    disponibilidade = buscar_da_barbearia(
        db=db,
        model=models.BarbeiroDisponibilidade,
        registro_id=disponibilidade_id,
        usuario=usuario_logado,
        mensagem_nao_encontrado="Disponibilidade não encontrada.",
    )

    if dados.usa_padrao is not None:
        disponibilidade.usa_padrao = dados.usa_padrao
    if dados.trabalha is not None:
        disponibilidade.trabalha = dados.trabalha
    if dados.hora_inicio is not None:
        disponibilidade.hora_inicio = dados.hora_inicio
    if dados.hora_fim is not None:
        disponibilidade.hora_fim = dados.hora_fim

    db.commit()
    db.refresh(disponibilidade)
    return disponibilidade
