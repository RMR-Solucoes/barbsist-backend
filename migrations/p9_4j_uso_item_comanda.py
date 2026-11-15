"""P9.4J: vinculo opcional entre uso e item da comanda.

Nao remove o indice legado comanda/servico.
Nao transforma dados antigos automaticamente.
"""

from sqlalchemy import inspect, text

TABELA_ITEM = "itens_comanda"
INDICE = "uq_p94j_uso_item_comanda"


def upgrade(connection):
    insp = inspect(connection)
    necessarias = {"usos_planos", TABELA_ITEM}
    if not necessarias.issubset(set(insp.get_table_names())):
        raise RuntimeError("Tabelas necessarias ausentes.")

    colunas = {
        c["name"]
        for c in inspect(connection).get_columns("usos_planos")
    }

    if "item_comanda_id" not in colunas:
        connection.execute(text(
            "ALTER TABLE usos_planos "
            "ADD COLUMN item_comanda_id INTEGER "
            f"REFERENCES {TABELA_ITEM}(id)"
        ))

    connection.execute(text(
        f"CREATE UNIQUE INDEX IF NOT EXISTS {INDICE} "
        "ON usos_planos(item_comanda_id) "
        "WHERE item_comanda_id IS NOT NULL"
    ))


def downgrade(connection):
    if "usos_planos" not in inspect(connection).get_table_names():
        raise RuntimeError("Tabela usos_planos ausente.")

    connection.execute(text(
        f"DROP INDEX IF EXISTS {INDICE}"
    ))

    colunas = {
        c["name"]
        for c in inspect(connection).get_columns("usos_planos")
    }

    if "item_comanda_id" in colunas:
        connection.execute(text(
            "ALTER TABLE usos_planos DROP COLUMN item_comanda_id"
        ))
