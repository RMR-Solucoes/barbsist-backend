"""
Migracao da troca segura de plano de assinaturas de clientes.

Idempotente e compativel com SQLite local e PostgreSQL/Railway.
"""

from sqlalchemy import inspect, text

from database import engine


def columns(table):
    return {item["name"] for item in inspect(engine).get_columns(table)}


def add_column(table, column, ddl):
    if column in columns(table):
        print(f"[OK] {table}.{column} ja existe")
        return

    with engine.begin() as connection:
        connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
    print(f"[CRIADA] {table}.{column}")


def main():
    tables = set(inspect(engine).get_table_names())
    required = {
        "assinaturas_clientes",
        "mercado_pago_cobrancas",
        "planos",
        "barbearias",
        "usuarios",
    }
    missing = required - tables
    if missing:
        raise RuntimeError("Tabelas ausentes: " + ", ".join(sorted(missing)))

    timestamp_type = "DATETIME" if engine.dialect.name == "sqlite" else "TIMESTAMP"
    id_type = (
        "INTEGER PRIMARY KEY AUTOINCREMENT"
        if engine.dialect.name == "sqlite"
        else "SERIAL PRIMARY KEY"
    )

    print("===== MIGRACAO TROCA DE PLANO DE CLIENTE =====")
    print("Banco:", engine.dialect.name)

    add_column(
        "assinaturas_clientes",
        "plano_programado_id",
        "INTEGER NULL REFERENCES planos(id)",
    )
    add_column(
        "assinaturas_clientes",
        "troca_plano_solicitada_em",
        f"{timestamp_type} NULL",
    )
    add_column(
        "assinaturas_clientes",
        "troca_plano_usuario_id",
        "INTEGER NULL REFERENCES usuarios(id)",
    )
    add_column(
        "mercado_pago_cobrancas",
        "plano_id",
        "INTEGER NULL REFERENCES planos(id)",
    )

    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS assinaturas_clientes_trocas_planos (
                id {id_type},
                assinatura_id INTEGER NOT NULL REFERENCES assinaturas_clientes(id),
                barbearia_id INTEGER NOT NULL REFERENCES barbearias(id),
                plano_anterior_id INTEGER NOT NULL REFERENCES planos(id),
                plano_novo_id INTEGER NOT NULL REFERENCES planos(id),
                usuario_id INTEGER NULL REFERENCES usuarios(id),
                acao VARCHAR NOT NULL,
                observacoes VARCHAR NULL,
                criado_em {timestamp_type} NOT NULL
            )
        """.format(timestamp_type=timestamp_type, id_type=id_type)))

        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_ass_cliente_plano_programado "
            "ON assinaturas_clientes (plano_programado_id)"
        ))
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_mp_cobranca_plano_id "
            "ON mercado_pago_cobrancas (plano_id)"
        ))
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_troca_plano_assinatura "
            "ON assinaturas_clientes_trocas_planos (assinatura_id)"
        ))
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_troca_plano_barbearia "
            "ON assinaturas_clientes_trocas_planos (barbearia_id)"
        ))
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_troca_plano_acao "
            "ON assinaturas_clientes_trocas_planos (acao)"
        ))

    print("[OK] tabela e indices de auditoria verificados")
    print("MIGRACAO CONCLUIDA")


if __name__ == "__main__":
    main()
