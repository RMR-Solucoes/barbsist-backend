"""P9.3Y: vinculos opcionais de ciclos para reserva e consumo.

Ordem obrigatoria:
1. P9.3A
2. P9.3O
3. P9.3Y

A protecao composta exige PostgreSQL.
"""

from sqlalchemy import inspect, text


def _verificar_tabelas(connection):
    inspetor = inspect(connection)
    necessarias = {
        "agendamentos",
        "usos_planos",
        "plano_ciclos_clientes",
    }
    existentes = set(inspetor.get_table_names())
    faltando = necessarias - existentes
    if faltando:
        raise RuntimeError(
            "Tabelas ausentes: " + ", ".join(sorted(faltando))
        )


def _colunas(connection, tabela):
    return {
        c["name"]
        for c in inspect(connection).get_columns(tabela)
    }


def upgrade(connection):
    if connection.dialect.name != "postgresql":
        raise RuntimeError(
            "P9.3Y exige PostgreSQL para executar "
            "a migracao composta."
        )

    _verificar_tabelas(connection)

    if "assinatura_cliente_id" not in _colunas(
        connection, "agendamentos"
    ):
        raise RuntimeError(
            "Execute primeiro a migracao P9.3A."
        )

    connection.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS "
        "uq_p93y_ciclo_assinatura "
        "ON plano_ciclos_clientes (id, assinatura_id)"
    ))

    for tabela in ("agendamentos", "usos_planos"):
        if "plano_ciclo_id" not in _colunas(connection, tabela):
            connection.execute(text(
                f"ALTER TABLE {tabela} "
                "ADD COLUMN plano_ciclo_id INTEGER"
            ))

    connection.execute(text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'fk_p93y_agendamento_ciclo_assinatura'
                  AND conrelid = 'agendamentos'::regclass
            ) THEN
                ALTER TABLE agendamentos
                ADD CONSTRAINT fk_p93y_agendamento_ciclo_assinatura
                FOREIGN KEY (plano_ciclo_id, assinatura_cliente_id)
                REFERENCES plano_ciclos_clientes (id, assinatura_id);
            END IF;
        END $$;
    """))

    connection.execute(text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'fk_p93y_uso_ciclo_assinatura'
                  AND conrelid = 'usos_planos'::regclass
            ) THEN
                ALTER TABLE usos_planos
                ADD CONSTRAINT fk_p93y_uso_ciclo_assinatura
                FOREIGN KEY (plano_ciclo_id, assinatura_id)
                REFERENCES plano_ciclos_clientes (id, assinatura_id);
            END IF;
        END $$;
    """))

    connection.execute(text("""
        ALTER TABLE agendamentos
        DROP CONSTRAINT IF EXISTS ck_p93y_agendamento_assinatura;
    """))
    connection.execute(text("""
        ALTER TABLE agendamentos
        ADD CONSTRAINT ck_p93y_agendamento_assinatura
        CHECK (
            plano_ciclo_id IS NULL
            OR assinatura_cliente_id IS NOT NULL
        );
    """))


def downgrade(connection):
    if connection.dialect.name != "postgresql":
        raise RuntimeError("P9.3Y exige PostgreSQL.")

    _verificar_tabelas(connection)

    connection.execute(text(
        "ALTER TABLE agendamentos "
        "DROP CONSTRAINT IF EXISTS ck_p93y_agendamento_assinatura"
    ))

    connection.execute(text(
        "ALTER TABLE agendamentos "
        "DROP CONSTRAINT IF EXISTS fk_p93y_agendamento_ciclo_assinatura"
    ))
    connection.execute(text(
        "ALTER TABLE usos_planos "
        "DROP CONSTRAINT IF EXISTS fk_p93y_uso_ciclo_assinatura"
    ))

    for tabela in ("agendamentos", "usos_planos"):
        if "plano_ciclo_id" in _colunas(connection, tabela):
            connection.execute(text(
                f"ALTER TABLE {tabela} "
                "DROP COLUMN plano_ciclo_id"
            ))

    connection.execute(text(
        "DROP INDEX IF EXISTS uq_p93y_ciclo_assinatura"
    ))
