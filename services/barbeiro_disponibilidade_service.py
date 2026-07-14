from sqlalchemy.orm import Session

from models import BarbeiroDisponibilidade, Barbeiro
from schemas import BarbeiroDisponibilidadeUpdate


def criar_disponibilidade_padrao_barbeiro(db: Session, barbeiro_id: int):
    barbeiro = db.query(Barbeiro).filter(Barbeiro.id == barbeiro_id).first()

    if not barbeiro:
        return None

    existentes = db.query(BarbeiroDisponibilidade).filter(
        BarbeiroDisponibilidade.barbeiro_id == barbeiro_id
    ).count()

    if existentes > 0:
        return db.query(BarbeiroDisponibilidade).filter(
            BarbeiroDisponibilidade.barbeiro_id == barbeiro_id
        ).order_by(BarbeiroDisponibilidade.dia_semana).all()

    disponibilidades = []

    for dia in range(7):
        item = BarbeiroDisponibilidade(
            barbeiro_id=barbeiro_id,
            usa_padrao=True,
            dia_semana=dia,
            trabalha=True,
            hora_inicio="08:00",
            hora_fim="20:00",
        )

        db.add(item)
        disponibilidades.append(item)

    db.commit()

    for item in disponibilidades:
        db.refresh(item)

    return disponibilidades


def listar_disponibilidade_por_barbeiro(db: Session, barbeiro_id: int):
    return criar_disponibilidade_padrao_barbeiro(db, barbeiro_id)


def atualizar_disponibilidade(
    db: Session,
    disponibilidade_id: int,
    dados: BarbeiroDisponibilidadeUpdate,
):
    disponibilidade = db.query(BarbeiroDisponibilidade).filter(
        BarbeiroDisponibilidade.id == disponibilidade_id
    ).first()

    if not disponibilidade:
        return None

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