from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from database import Base


class Parceiro(Base):
    __tablename__ = "parceiros"

    id = Column(Integer, primary_key=True, index=True)

    tipo = Column(
        String,
        nullable=False,
        index=True,
    )
    # VENDEDOR | COLABORADOR | BARBEARIA

    nome = Column(
        String,
        nullable=False,
    )

    email = Column(
        String,
        nullable=False,
        unique=True,
        index=True,
    )

    telefone = Column(
        String,
        nullable=True,
    )

    barbearia_id = Column(
        Integer,
        ForeignKey("barbearias.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    codigo_ref = Column(
        String,
        nullable=False,
        unique=True,
        index=True,
    )

    tipo_beneficio = Column(
        String,
        nullable=False,
        default="COMISSAO",
    )
    # COMISSAO | CREDITO

    regra_beneficio = Column(
        String,
        nullable=False,
        default="PERCENTUAL",
    )
    # PERCENTUAL | VALOR_FIXO

    percentual_beneficio = Column(
        Float,
        nullable=True,
    )

    valor_fixo_beneficio = Column(
        Float,
        nullable=True,
    )

    ativo = Column(
        Boolean,
        nullable=False,
        default=True,
    )

    observacao = Column(
        Text,
        nullable=True,
    )

    criado_em = Column(
        DateTime,
        nullable=False,
        default=datetime.now,
    )

    atualizado_em = Column(
        DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
    )

    barbearia = relationship("Barbearia")


class Indicacao(Base):
    __tablename__ = "indicacoes"

    __table_args__ = (
        UniqueConstraint(
            "barbearia_indicada_id",
            name="uq_indicacao_barbearia_indicada",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    parceiro_id = Column(
        Integer,
        ForeignKey("parceiros.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    codigo_ref = Column(
        String,
        nullable=False,
        index=True,
    )

    barbearia_indicada_id = Column(
        Integer,
        ForeignKey("barbearias.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    assinatura_saas_id = Column(
        Integer,
        ForeignKey("assinaturas_saas.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    status = Column(
        String,
        nullable=False,
        default="CADASTRADA",
        index=True,
    )
    # CADASTRADA | ASSINANTE | CONVERTIDA | CANCELADA

    data_cadastro = Column(
        DateTime,
        nullable=False,
        default=datetime.now,
    )

    data_conversao = Column(
        DateTime,
        nullable=True,
    )

    observacao = Column(
        Text,
        nullable=True,
    )

    parceiro = relationship("Parceiro")
    barbearia_indicada = relationship("Barbearia")
    assinatura_saas = relationship("AssinaturaSaaS")


class ComissaoParceiro(Base):
    __tablename__ = "comissoes_parceiros"

    __table_args__ = (
        UniqueConstraint(
            "indicacao_id",
            "pagamento_saas_id",
            name="uq_comissao_indicacao_pagamento",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    parceiro_id = Column(
        Integer,
        ForeignKey("parceiros.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    indicacao_id = Column(
        Integer,
        ForeignKey("indicacoes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    pagamento_saas_id = Column(
        Integer,
        ForeignKey("pagamentos_saas.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    valor_base = Column(
        Float,
        nullable=False,
    )

    percentual = Column(
        Float,
        nullable=True,
    )

    valor_comissao = Column(
        Float,
        nullable=False,
    )

    status = Column(
        String,
        nullable=False,
        default="PENDENTE",
        index=True,
    )
    # PENDENTE | LIBERADA | PAGA | CANCELADA

    data_geracao = Column(
        DateTime,
        nullable=False,
        default=datetime.now,
    )

    data_liberacao = Column(
        DateTime,
        nullable=True,
    )

    data_pagamento = Column(
        DateTime,
        nullable=True,
    )

    observacao = Column(
        Text,
        nullable=True,
    )

    parceiro = relationship("Parceiro")
    indicacao = relationship("Indicacao")
    pagamento_saas = relationship("PagamentoSaaS")


class CreditoBarbearia(Base):
    __tablename__ = "creditos_barbearia"

    __table_args__ = (
        UniqueConstraint(
            "indicacao_id",
            "pagamento_saas_id",
            name="uq_credito_indicacao_pagamento",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    parceiro_id = Column(
        Integer,
        ForeignKey("parceiros.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    barbearia_parceira_id = Column(
        Integer,
        ForeignKey("barbearias.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    indicacao_id = Column(
        Integer,
        ForeignKey("indicacoes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    pagamento_saas_id = Column(
        Integer,
        ForeignKey("pagamentos_saas.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    valor_base = Column(
        Float,
        nullable=False,
    )

    percentual = Column(
        Float,
        nullable=True,
    )

    valor_credito = Column(
        Float,
        nullable=False,
    )

    status = Column(
        String,
        nullable=False,
        default="DISPONIVEL",
        index=True,
    )
    # DISPONIVEL | APLICADO | CANCELADO

    referencia_mensalidade = Column(
        String,
        nullable=True,
    )

    data_geracao = Column(
        DateTime,
        nullable=False,
        default=datetime.now,
    )

    data_aplicacao = Column(
        DateTime,
        nullable=True,
    )

    observacao = Column(
        Text,
        nullable=True,
    )

    parceiro = relationship("Parceiro")
    barbearia_parceira = relationship("Barbearia")
    indicacao = relationship("Indicacao")
    pagamento_saas = relationship("PagamentoSaaS")



class ResgateCreditoBarbearia(Base):
    __tablename__ = "resgates_creditos"

    id = Column(Integer, primary_key=True, index=True)

    parceiro_id = Column(
        Integer,
        ForeignKey("parceiros.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    barbearia_id = Column(
        Integer,
        ForeignKey("barbearias.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    assinatura_saas_id = Column(
        Integer,
        ForeignKey("assinaturas_saas.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    pagamento_saas_id = Column(
        Integer,
        ForeignKey("pagamentos_saas.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    tipo_aplicacao = Column(
        String,
        nullable=False,
    )
    # MENSALIDADE_AUTOMATICA | RESGATE_SOLICITADO | RENOVACAO

    valor_solicitado = Column(
        Float,
        nullable=False,
    )

    valor_aplicado = Column(
        Float,
        nullable=False,
        default=0,
    )

    status = Column(
        String,
        nullable=False,
        default="SOLICITADO",
        index=True,
    )
    # SOLICITADO | APROVADO | APLICADO | CANCELADO

    solicitado_em = Column(
        DateTime,
        nullable=False,
        default=datetime.now,
    )

    aprovado_em = Column(
        DateTime,
        nullable=True,
    )

    aplicado_em = Column(
        DateTime,
        nullable=True,
    )

    observacao = Column(
        Text,
        nullable=True,
    )

    parceiro = relationship("Parceiro")
    barbearia = relationship("Barbearia")
    assinatura_saas = relationship("AssinaturaSaaS")
    pagamento_saas = relationship("PagamentoSaaS")


class ResgateCreditoItem(Base):
    __tablename__ = "resgate_credito_itens"

    __table_args__ = (
        UniqueConstraint(
            "resgate_id",
            "credito_id",
            name="uq_resgate_credito_item",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    resgate_id = Column(
        Integer,
        ForeignKey("resgates_creditos.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    credito_id = Column(
        Integer,
        ForeignKey("creditos_barbearia.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    valor_utilizado = Column(
        Float,
        nullable=False,
    )

    criado_em = Column(
        DateTime,
        nullable=False,
        default=datetime.now,
    )

    resgate = relationship("ResgateCreditoBarbearia")
    credito = relationship("CreditoBarbearia")
