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
            f"ALTER TABLE {TABELA} "
            f"ADD COLUMN {nome} {definicao_sql}"
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
            f"CREATE INDEX IF NOT EXISTS "
            f"{nome_indice} "
            f"ON {TABELA} ({coluna})"
        )
    )

    print(f"[OK] Índice: {nome_indice}")


def executar_migracao() -> None:
    print("=" * 60)
    print("MIGRAÇÃO CAIXA V2")
    print("=" * 60)

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

        # Garante valores válidos nos registros antigos.
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

    print("=" * 60)
    print("MIGRAÇÃO CAIXA V2 CONCLUÍDA")
    print("=" * 60)


if __name__ == "__main__":
    executar_migracao()