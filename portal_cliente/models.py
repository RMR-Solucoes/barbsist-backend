from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from database import Base


class ClienteAcesso(Base):
    __tablename__ = "clientes_acessos"
    __table_args__ = (
        UniqueConstraint("cliente_id", name="uq_cliente_acesso_cliente"),
        UniqueConstraint("barbearia_id", "email", name="uq_cliente_acesso_barbearia_email"),
    )

    id = Column(Integer, primary_key=True, index=True)
    barbearia_id = Column(Integer, ForeignKey("barbearias.id", ondelete="RESTRICT"), nullable=False, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String, nullable=False, index=True)
    senha_hash = Column(String, nullable=False)
    ativo = Column(Boolean, default=False, nullable=False)
    email_confirmado = Column(Boolean, default=False, nullable=False)
    deve_trocar_senha = Column(Boolean, default=False, nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    ultimo_acesso_em = Column(DateTime, nullable=True)

    cliente = relationship("Cliente")
    barbearia = relationship("Barbearia")


class ClienteConfirmacaoEmail(Base):
    __tablename__ = "clientes_confirmacoes_email"

    id = Column(Integer, primary_key=True, index=True)
    acesso_id = Column(Integer, ForeignKey("clientes_acessos.id", ondelete="CASCADE"), nullable=False, index=True)
    codigo_hash = Column(String, nullable=False)
    expira_em = Column(DateTime, nullable=False, index=True)
    utilizado_em = Column(DateTime, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)

    acesso = relationship("ClienteAcesso")


class PortalClienteConfiguracao(Base):
    __tablename__ = "portal_cliente_configuracoes"
    __table_args__ = (UniqueConstraint("barbearia_id", name="uq_portal_cliente_config_barbearia"),)

    id = Column(Integer, primary_key=True, index=True)
    barbearia_id = Column(Integer, ForeignKey("barbearias.id", ondelete="CASCADE"), nullable=False, index=True)
    permitir_agendamento_portal = Column(Boolean, default=False, nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    barbearia = relationship("Barbearia")
