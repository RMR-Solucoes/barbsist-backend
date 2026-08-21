from sqlalchemy import inspect, text

from database import engine


TABELA = "caixa"


def obter_colunas(conexao) -> set[str]:
    inspetor = inspect(conexao)

    if TABELA not in inspetor.get_table_names():
        raise RuntimeError(
            f"A tabela '{TABELA}' não foi encontrada."
        )

    return {
        coluna["name"]
        for coluna in inspetor.get_columns(TABELA)
    }


def adicionar_coluna(
    conexao,
    colunas_existentes: set[str],
    nome: str,
    definicao_sql: str,
) -> None:
    if nome in colunas_existentes:
        print(f"[OK] Coluna já existe: {nome}")
        return

    conexao.execute(
        text(
            f'ALTER TABLE "{TABELA}" '
            f'ADD COLUMN "{nome}" {definicao_sql}'
        )
    )

    colunas_existentes.add(nome)
    print(f"[CRIADA] Coluna: {nome}")


def criar_indice(
    conexao,
    nome_indice: str,
    coluna: str,
) -> None:
    conexao.execute(
        text(
            f'CREATE INDEX IF NOT EXISTS "{nome_indice}" '
            f'ON "{TABELA}" ("{coluna}")'
        )
    )

    print(f"[OK] Índice: {nome_indice}")


def constraint_postgresql_existe(
    conexao,
    nome_constraint: str,
) -> bool:
    resultado = conexao.execute(
        text(
            """
            SELECT 1
            FROM pg_constraint
            WHERE conname = :nome
            LIMIT 1
            """
        ),
        {"nome": nome_constraint},
    ).first()

    return resultado is not None


def validar_sem_orfaos(
    conexao,
    coluna: str,
    tabela_referencia: str,
    coluna_referencia: str = "id",
) -> None:
    quantidade = conexao.execute(
        text(
            f'''
            SELECT COUNT(*)
            FROM "{TABELA}" origem
            LEFT JOIN "{tabela_referencia}" destino
                ON destino."{coluna_referencia}" = origem."{coluna}"
            WHERE origem."{coluna}" IS NOT NULL
              AND destino."{coluna_referencia}" IS NULL
            '''
        )
    ).scalar() or 0

    if quantidade:
        raise RuntimeError(
            f"Não foi possível criar FK de {TABELA}.{coluna}: "
            f"{quantidade} registro(s) órfão(s)."
        )


def criar_fk_postgresql(
    conexao,
    nome_constraint: str,
    coluna: str,
    tabela_referencia: str,
    coluna_referencia: str = "id",
) -> None:
    if constraint_postgresql_existe(
        conexao,
        nome_constraint,
    ):
        print(f"[OK] Foreign key já existe: {nome_constraint}")
        return

    validar_sem_orfaos(
        conexao,
        coluna,
        tabela_referencia,
        coluna_referencia,
    )

    conexao.execute(
        text(
            f'''
            ALTER TABLE "{TABELA}"
            ADD CONSTRAINT "{nome_constraint}"
            FOREIGN KEY ("{coluna}")
            REFERENCES "{tabela_referencia}" ("{coluna_referencia}")
            '''
        )
    )

    print(f"[CRIADA] Foreign key: {nome_constraint}")


def auditar_estrutura() -> None:
    inspetor = inspect(engine)

    print()
    print("=" * 72)
    print("AUDITORIA FINAL - CAIXA V2")
    print("=" * 72)

    esperadas = {
        "id",
        "tipo",
        "descricao",
        "valor",
        "forma_pagamento",
        "origem",
        "referencia_id",
        "status",
        "observacoes",
        "usuario_id",
        "movimentacao_origem_id",
        "data",
        "barbearia_id",
    }

    colunas = {
        coluna["name"]: coluna
        for coluna in inspetor.get_columns(TABELA)
    }

    for nome in sorted(colunas):
        coluna = colunas[nome]

        print(
            f"{nome:28} | "
            f"type={str(coluna['type']):20} | "
            f"nullable={coluna['nullable']}"
        )

    ausentes = sorted(
        esperadas - set(colunas)
    )

    print()
    print("Colunas esperadas:", len(esperadas))
    print("Colunas ausentes:", len(ausentes))

    if ausentes:
        print(
            "AUSENTES:",
            ", ".join(ausentes),
        )
        raise RuntimeError(
            "A estrutura da tabela caixa ainda está incompleta."
        )

    print("STATUS: ESTRUTURA CAIXA V2 COMPLETA")


def executar_migracao() -> None:
    print("=" * 72)
    print("MIGRAÇÃO CAIXA V2")
    print("=" * 72)
    print("Banco:", engine.dialect.name)
    print()

    dialect = engine.dialect.name

    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError(
            f"Banco não suportado por esta migração: {dialect}"
        )

    with engine.begin() as conexao:
        colunas = obter_colunas(conexao)

        adicionar_coluna(
            conexao,
            colunas,
            "origem",
            "VARCHAR NOT NULL DEFAULT 'MANUAL'",
        )

        adicionar_coluna(
            conexao,
            colunas,
            "referencia_id",
            "INTEGER NULL",
        )

        adicionar_coluna(
            conexao,
            colunas,
            "status",
            "VARCHAR NOT NULL DEFAULT 'ATIVO'",
        )

        adicionar_coluna(
            conexao,
            colunas,
            "observacoes",
            "VARCHAR NULL",
        )

        adicionar_coluna(
            conexao,
            colunas,
            "usuario_id",
            "INTEGER NULL",
        )

        adicionar_coluna(
            conexao,
            colunas,
            "movimentacao_origem_id",
            "INTEGER NULL",
        )

        # Normaliza registros legados.
        conexao.execute(
            text(
                """
                UPDATE caixa
                SET origem = 'MANUAL'
                WHERE origem IS NULL
                   OR TRIM(origem) = ''
                """
            )
        )

        conexao.execute(
            text(
                """
                UPDATE caixa
                SET status = 'ATIVO'
                WHERE status IS NULL
                   OR TRIM(status) = ''
                """
            )
        )

        criar_indice(
            conexao,
            "ix_caixa_origem",
            "origem",
        )

        criar_indice(
            conexao,
            "ix_caixa_referencia_id",
            "referencia_id",
        )

        criar_indice(
            conexao,
            "ix_caixa_status",
            "status",
        )

        criar_indice(
            conexao,
            "ix_caixa_usuario_id",
            "usuario_id",
        )

        criar_indice(
            conexao,
            "ix_caixa_movimentacao_origem_id",
            "movimentacao_origem_id",
        )

        criar_indice(
            conexao,
            "ix_caixa_data",
            "data",
        )

        if "barbearia_id" in colunas:
            criar_indice(
                conexao,
                "ix_caixa_barbearia_id",
                "barbearia_id",
            )
        else:
            print(
                "[AVISO] caixa.barbearia_id não existe. "
                "Execute a migração multi-barbearia correspondente."
            )

        # SQLite não permite adicionar essas FKs por ALTER TABLE
        # sem reconstrução da tabela. No PostgreSQL podemos completar
        # integralmente a estrutura definida em models.py.
        if dialect == "postgresql":
            criar_fk_postgresql(
                conexao,
                "fk_caixa_usuario_id",
                "usuario_id",
                "usuarios",
            )

            criar_fk_postgresql(
                conexao,
                "fk_caixa_movimentacao_origem_id",
                "movimentacao_origem_id",
                "caixa",
            )

    print()
    print("=" * 72)
    print("MIGRAÇÃO CAIXA V2 CONCLUÍDA")
    print("=" * 72)

    auditar_estrutura()


if __name__ == "__main__":
    executar_migracao()
