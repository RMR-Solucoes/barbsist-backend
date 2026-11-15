"""P9.4O - integridade entre UsoPlano e ItemComanda.

Requer previamente a P9.4J no banco de destino.
PostgreSQL somente. Execute upgrade(connection) em transacao.
Nao executa automaticamente ao importar.
"""

from sqlalchemy import inspect, text

INDICE = "uq_p94o_item_comanda_par"
FK = "fk_p94o_uso_item_mesma_comanda"
CHECK = "ck_p94o_uso_item_exige_comanda"


def upgrade(connection):
    if connection.dialect.name != "postgresql":
        raise RuntimeError("P9.4O exige PostgreSQL.")

    insp = inspect(connection)
    tabelas = set(insp.get_table_names())

    if not {"itens_comanda", "usos_planos"}.issubset(tabelas):
        raise RuntimeError("Tabelas necessarias ausentes.")

    colunas = {
        c["name"]
        for c in insp.get_columns("usos_planos")
    }
    if not {"item_comanda_id", "comanda_id"}.issubset(colunas):
        raise RuntimeError("Execute P9.4J antes de P9.4O.")

    # Impede dupla execucao ou estado parcialmente aplicado.
    constraints = {
        c["name"]
        for c in insp.get_foreign_keys("usos_planos")
    }
    if FK in constraints:
        raise RuntimeError("P9.4O ja possui a FK composta.")

    divergentes = connection.execute(text("""
        SELECT COUNT(*)
        FROM usos_planos u
        LEFT JOIN itens_comanda i ON i.id = u.item_comanda_id
        WHERE u.item_comanda_id IS NOT NULL
          AND (
              u.comanda_id IS NULL
              OR i.id IS NULL
              OR i.comanda_id <> u.comanda_id
          )
    """)).scalar_one()

    if divergentes:
        raise RuntimeError(
            f"Encontrados {divergentes} consumos incompat?veis. "
            "Corrija-os manualmente antes de migrar."
        )

    # A chave composta de destino precisa ser unica.
    connection.execute(text("""
        CREATE UNIQUE INDEX IF NOT EXISTS
        uq_p94o_item_comanda_par
        ON itens_comanda (id, comanda_id)
    """))

    connection.execute(text("""
        ALTER TABLE usos_planos
        ADD CONSTRAINT ck_p94o_uso_item_exige_comanda
        CHECK (
            item_comanda_id IS NULL
            OR comanda_id IS NOT NULL
        )
    """))

    connection.execute(text("""
        ALTER TABLE usos_planos
        ADD CONSTRAINT fk_p94o_uso_item_mesma_comanda
        FOREIGN KEY (item_comanda_id, comanda_id)
        REFERENCES itens_comanda (id, comanda_id)
    """))


def downgrade(connection):
    if connection.dialect.name != "postgresql":
        raise RuntimeError("P9.4O exige PostgreSQL.")

    connection.execute(text("""
        ALTER TABLE usos_planos
        DROP CONSTRAINT IF EXISTS fk_p94o_uso_item_mesma_comanda
    """))
    connection.execute(text("""
        ALTER TABLE usos_planos
        DROP CONSTRAINT IF EXISTS ck_p94o_uso_item_exige_comanda
    """))
    connection.execute(text("""
        DROP INDEX IF EXISTS uq_p94o_item_comanda_par
    """))
