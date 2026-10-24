"""Modelo de notificacoes internas do BarbSist."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
)

from database import Base


class NotificacaoInterna(Base):
    __tablename__ = "notificacoes_internas"

    id = Column(Integer, primary_key=True, index=True)

    barbearia_id = Column(Integer, nullable=False)
    agendamento_id = Column(Integer, nullable=True)

    chave_evento = Column(String(160), nullable=False)
    tipo = Column(String(50), nullable=False)

    titulo = Column(String(160), nullable=False)
    mensagem = Column(String(1000), nullable=False)

    lida = Column(Boolean, nullable=False, default=False)

    criada_em = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )

    __table_args__ = (
        UniqueConstraint(
            "barbearia_id",
            "chave_evento",
            name="uq_notificacao_barbearia_evento",
        ),
        Index(
            "ix_notificacao_barbearia_lida",
            "barbearia_id",
            "lida",
        ),
    )