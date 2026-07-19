"""Migra agendamentos e horarios para multi-barbearia no PostgreSQL.

Uso (no ambiente que possui DATABASE_URL):
    python migrar_multibarbearia_postgresql.py

A migracao e transacional e idempotente. Em qualquer inconsistencia, todas as
alteracoes da execucao sao revertidas.
"""

from sqlalchemy import text

from database import engine


TABELAS = (
    "barbearias",
    "barbeiros",
    "clientes",
    "servicos",
    "agendamentos",
    "configuracao_funcionamento",
    "barbeiro_disponibilidade",
)


def valor_escalar(conexao, sql, parametros=None):
    return conexao.execute(text(sql), parametros or {}).scalar_one()


def validar_tabelas(conexao):
    ausentes = [
        tabela
        for tabela in TABELAS
        if valor_escalar(
            conexao,
            "SELECT to_regclass(:tabela) IS NOT NULL",
            {"tabela": f"public.{tabela}"},
        )
        is False
    ]
    if ausentes:
        raise RuntimeError("Tabelas ausentes: " + ", ".join(ausentes))


def adicionar_colunas(conexao):
    for tabela in (
        "agendamentos",
        "configuracao_funcionamento",
        "barbeiro_disponibilidade",
    ):
        conexao.execute(
            text(
                f"ALTER TABLE {tabela} "
                "ADD COLUMN IF NOT EXISTS barbearia_id INTEGER"
            )
        )
        print(f"[OK] Coluna {tabela}.barbearia_id disponível.")


def preencher_dados(conexao):
    principal = conexao.execute(
        text("SELECT id FROM barbearias ORDER BY codigo, id LIMIT 1")
    ).scalar_one_or_none()
    if principal is None:
        raise RuntimeError("Nenhuma barbearia cadastrada.")

    resultado = conexao.execute(
        text(
            """
            UPDATE agendamentos AS a
               SET barbearia_id = b.barbearia_id
              FROM barbeiros AS b
             WHERE b.id = a.barbeiro_id
               AND a.barbearia_id IS NULL
            """
        )
    )
    print(f"[OK] Agendamentos atualizados: {resultado.rowcount}")

    resultado = conexao.execute(
        text(
            """
            UPDATE configuracao_funcionamento
               SET barbearia_id = :principal
             WHERE barbearia_id IS NULL
            """
        ),
        {"principal": principal},
    )
    print(f"[OK] Configurações atualizadas: {resultado.rowcount}")

    resultado = conexao.execute(
        text(
            """
            UPDATE barbeiro_disponibilidade AS d
               SET barbearia_id = b.barbearia_id
              FROM barbeiros AS b
             WHERE b.id = d.barbeiro_id
               AND d.barbearia_id IS NULL
            """
        )
    )
    print(f"[OK] Disponibilidades atualizadas: {resultado.rowcount}")


def validar_sem_nulos(conexao):
    for tabela in (
        "agendamentos",
        "configuracao_funcionamento",
        "barbeiro_disponibilidade",
    ):
        quantidade = valor_escalar(
            conexao,
            f"SELECT COUNT(*) FROM {tabela} WHERE barbearia_id IS NULL",
        )
        if quantidade:
            raise RuntimeError(
                f"{tabela} possui {quantidade} registros sem barbearia."
            )


def validar_relacionamentos(conexao):
    verificacoes = (
        (
            "agendamentos com barbeiro de outra barbearia",
            """
            SELECT COUNT(*)
              FROM agendamentos AS a
              JOIN barbeiros AS b ON b.id = a.barbeiro_id
             WHERE a.barbearia_id <> b.barbearia_id
            """,
        ),
        (
            "agendamentos com cliente de outra barbearia",
            """
            SELECT COUNT(*)
              FROM agendamentos AS a
              JOIN clientes AS c ON c.id = a.cliente_id
             WHERE a.cliente_id IS NOT NULL
               AND a.barbearia_id <> c.barbearia_id
            """,
        ),
        (
            "agendamentos com serviço de outra barbearia",
            """
            SELECT COUNT(*)
              FROM agendamentos AS a
              JOIN servicos AS s ON s.id = a.servico_id
             WHERE a.barbearia_id <> s.barbearia_id
            """,
        ),
        (
            "disponibilidades com barbeiro de outra barbearia",
            """
            SELECT COUNT(*)
              FROM barbeiro_disponibilidade AS d
              JOIN barbeiros AS b ON b.id = d.barbeiro_id
             WHERE d.barbearia_id <> b.barbearia_id
            """,
        ),
    )

    for descricao, sql in verificacoes:
        quantidade = valor_escalar(conexao, sql)
        if quantidade:
            raise RuntimeError(f"Existem {quantidade} {descricao}.")
    print("[OK] Relacionamentos consistentes.")


def criar_restricoes_e_indices(conexao):
    for tabela in (
        "agendamentos",
        "configuracao_funcionamento",
        "barbeiro_disponibilidade",
    ):
        conexao.execute(
            text(
                f"ALTER TABLE {tabela} "
                "ALTER COLUMN barbearia_id SET NOT NULL"
            )
        )

    restricoes = (
        (
            "agendamentos",
            "fk_agendamentos_barbearia_id",
        ),
        (
            "configuracao_funcionamento",
            "fk_configuracao_funcionamento_barbearia_id",
        ),
        (
            "barbeiro_disponibilidade",
            "fk_barbeiro_disponibilidade_barbearia_id",
        ),
    )
    for tabela, nome in restricoes:
        conexao.execute(
            text(
                f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = '{nome}'
                    ) THEN
                        ALTER TABLE {tabela}
                        ADD CONSTRAINT {nome}
                        FOREIGN KEY (barbearia_id)
                        REFERENCES barbearias(id)
                        ON DELETE RESTRICT;
                    END IF;
                END $$;
                """
            )
        )

    comandos = (
        "CREATE INDEX IF NOT EXISTS ix_agendamentos_barbearia_id "
        "ON agendamentos(barbearia_id)",
        "CREATE INDEX IF NOT EXISTS "
        "ix_configuracao_funcionamento_barbearia_id "
        "ON configuracao_funcionamento(barbearia_id)",
        "CREATE INDEX IF NOT EXISTS "
        "ix_barbeiro_disponibilidade_barbearia_id "
        "ON barbeiro_disponibilidade(barbearia_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS "
        "uq_config_funcionamento_barbearia_dia "
        "ON configuracao_funcionamento(barbearia_id, dia_semana)",
        "CREATE UNIQUE INDEX IF NOT EXISTS "
        "uq_disponibilidade_barbearia_barbeiro_dia "
        "ON barbeiro_disponibilidade(barbearia_id, barbeiro_id, dia_semana)",
    )
    for comando in comandos:
        conexao.execute(text(comando))
    print("[OK] Restrições e índices disponíveis.")


def mostrar_resultado(conexao):
    for tabela in (
        "agendamentos",
        "configuracao_funcionamento",
        "barbeiro_disponibilidade",
    ):
        linhas = conexao.execute(
            text(
                f"""
                SELECT barbearia_id, COUNT(*)
                  FROM {tabela}
                 GROUP BY barbearia_id
                 ORDER BY barbearia_id
                """
            )
        ).all()
        print(f"{tabela}: {linhas}")


def executar_migracao():
    if engine.dialect.name != "postgresql":
        raise RuntimeError(
            "Esta migração só pode ser executada em PostgreSQL. "
            f"Banco detectado: {engine.dialect.name}."
        )

    print("=" * 80)
    print("MIGRAÇÃO MULTI-BARBEARIA — POSTGRESQL")
    print("=" * 80)

    with engine.begin() as conexao:
        # Impede duas execuções simultâneas desta migração.
        conexao.execute(text("SELECT pg_advisory_xact_lock(2026071901)"))
        validar_tabelas(conexao)
        adicionar_colunas(conexao)
        preencher_dados(conexao)
        validar_sem_nulos(conexao)
        validar_relacionamentos(conexao)
        criar_restricoes_e_indices(conexao)
        mostrar_resultado(conexao)

    print("MIGRAÇÃO CONCLUÍDA COM SUCESSO")


if __name__ == "__main__":
    executar_migracao()
