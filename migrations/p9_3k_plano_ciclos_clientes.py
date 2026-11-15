"""P9.3O - Ciclos pagos com isolamento composto.

BARBSIST_P9_3O_ISOLAMENTO_COMPOSTO

Executar somente apos homologacao e planejamento de migracao.
Nao concede nem consome creditos automaticamente.
"""

from datetime import datetime
from sqlalchemy import (
    MetaData, Table, Column, Integer, String, DateTime,
    ForeignKeyConstraint, Index, UniqueConstraint,
    CheckConstraint
)

metadata_ciclos = MetaData()

barbearias = Table(
    "barbearias", metadata_ciclos,
    Column("id", Integer, primary_key=True),
)

assinaturas = Table(
    "assinaturas_clientes", metadata_ciclos,
    Column("id", Integer, primary_key=True),
    Column("barbearia_id", Integer, nullable=False),
)

planos = Table(
    "planos", metadata_ciclos,
    Column("id", Integer, primary_key=True),
    Column("barbearia_id", Integer, nullable=False),
)

pagamentos = Table(
    "pagamentos_planos", metadata_ciclos,
    Column("id", Integer, primary_key=True),
    Column("assinatura_id", Integer, nullable=False),
    Column("plano_id", Integer, nullable=False),
)

# Indices unicos auxiliares necessarios para FKs compostas.
# A PK individual nao substitui essa exigencia do PostgreSQL.
ix_assinatura = Index(
    "uq_p93o_assinatura_tenant",
    assinaturas.c.id, assinaturas.c.barbearia_id,
    unique=True,
)
ix_plano = Index(
    "uq_p93o_plano_tenant",
    planos.c.id, planos.c.barbearia_id,
    unique=True,
)
ix_pagamento = Index(
    "uq_p93o_pagamento_vinculo",
    pagamentos.c.id,
    pagamentos.c.assinatura_id,
    pagamentos.c.plano_id,
    unique=True,
)

ciclos = Table(
    "plano_ciclos_clientes", metadata_ciclos,
    Column("id", Integer, primary_key=True),
    Column("barbearia_id", Integer, nullable=False),
    Column("assinatura_id", Integer, nullable=False),
    Column("plano_id", Integer, nullable=False),
    Column("pagamento_plano_id", Integer, nullable=False),
    Column("periodo_inicio", DateTime, nullable=False),
    Column("periodo_fim", DateTime, nullable=False),
    Column("creditos_concedidos", Integer, nullable=False),
    Column("referencia_mes", String(20), nullable=True),
    Column(
        "criado_em", DateTime,
        nullable=False, default=datetime.now,
    ),
    ForeignKeyConstraint(
        ["barbearia_id"], ["barbearias.id"],
        name="fk_p93o_barbearia",
    ),
    ForeignKeyConstraint(
        ["assinatura_id", "barbearia_id"],
        ["assinaturas_clientes.id", "assinaturas_clientes.barbearia_id"],
        name="fk_p93o_assinatura_tenant",
    ),
    ForeignKeyConstraint(
        ["plano_id", "barbearia_id"],
        ["planos.id", "planos.barbearia_id"],
        name="fk_p93o_plano_tenant",
    ),
    ForeignKeyConstraint(
        ["pagamento_plano_id", "assinatura_id", "plano_id"],
        [
            "pagamentos_planos.id",
            "pagamentos_planos.assinatura_id",
            "pagamentos_planos.plano_id",
        ],
        name="fk_p93o_pagamento_vinculo",
    ),
    UniqueConstraint(
        "pagamento_plano_id",
        name="uq_plano_ciclo_pagamento",
    ),
    CheckConstraint(
        "creditos_concedidos >= 0",
        name="ck_plano_ciclo_creditos",
    ),
    CheckConstraint(
        "periodo_fim > periodo_inicio",
        name="ck_plano_ciclo_periodo",
    ),
)

Index(
    "ix_plano_ciclos_tenant_assinatura",
    ciclos.c.barbearia_id, ciclos.c.assinatura_id,
)


def upgrade(connection):
    # Nunca cria ou modifica dados das tabelas financeiras existentes.
    ix_assinatura.create(bind=connection, checkfirst=True)
    ix_plano.create(bind=connection, checkfirst=True)
    ix_pagamento.create(bind=connection, checkfirst=True)
    ciclos.create(bind=connection, checkfirst=True)


def downgrade(connection):
    # Ordem inversa das dependencias.
    ciclos.drop(bind=connection, checkfirst=True)
    ix_pagamento.drop(bind=connection, checkfirst=True)
    ix_plano.drop(bind=connection, checkfirst=True)
    ix_assinatura.drop(bind=connection, checkfirst=True)
