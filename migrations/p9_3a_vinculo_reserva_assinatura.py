"""P9.3A: vinculo opcional da reserva com assinatura e ciclo."""

from sqlalchemy import inspect, text

TABELA = "agendamentos"

COLUNAS = (
    "assinatura_cliente_id",
    "plano_ciclo_inicio",
    "plano_ciclo_fim",
)


def _colunas(connection):
    return {
        coluna["name"]
        for coluna in inspect(connection).get_columns(TABELA)
    }


def upgrade(connection):
    existentes = _colunas(connection)

    if "assinatura_cliente_id" not in existentes:
        connection.execute(text(
            "ALTER TABLE agendamentos "
            "ADD COLUMN assinatura_cliente_id INTEGER "
            "REFERENCES assinaturas_clientes(id)"
        ))

    if "plano_ciclo_inicio" not in existentes:
        connection.execute(text(
            "ALTER TABLE agendamentos "
            "ADD COLUMN plano_ciclo_inicio TIMESTAMP"
        ))

    if "plano_ciclo_fim" not in existentes:
        connection.execute(text(
            "ALTER TABLE agendamentos "
            "ADD COLUMN plano_ciclo_fim TIMESTAMP"
        ))


def downgrade(connection):
    existentes = _colunas(connection)

    for coluna in reversed(COLUNAS):
        if coluna in existentes:
            connection.execute(text(
                f"ALTER TABLE agendamentos DROP COLUMN {coluna}"
            ))
