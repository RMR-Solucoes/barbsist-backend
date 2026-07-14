import sqlite3
from pathlib import Path


CAMINHO_BANCO = Path(__file__).resolve().parent / "barbearia.db"


def coluna_existe(cursor, tabela, coluna):
    cursor.execute(f"PRAGMA table_info({tabela})")
    colunas = cursor.fetchall()

    return any(
        registro[1] == coluna
        for registro in colunas
    )


def executar_migracao():
    conexao = sqlite3.connect(CAMINHO_BANCO)
    cursor = conexao.cursor()

    try:
        if not coluna_existe(
            cursor,
            "itens_comanda",
            "pago_com_plano"
        ):
            cursor.execute("""
                ALTER TABLE itens_comanda
                ADD COLUMN pago_com_plano BOOLEAN
                NOT NULL DEFAULT 0
            """)

            print(
                "Coluna pago_com_plano adicionada."
            )
        else:
            print(
                "Coluna pago_com_plano já existe."
            )

        if not coluna_existe(
            cursor,
            "itens_comanda",
            "uso_plano_id"
        ):
            cursor.execute("""
                ALTER TABLE itens_comanda
                ADD COLUMN uso_plano_id INTEGER
                REFERENCES usos_planos(id)
            """)

            print(
                "Coluna uso_plano_id adicionada."
            )
        else:
            print(
                "Coluna uso_plano_id já existe."
            )

        conexao.commit()

        print(
            "Migração concluída com sucesso."
        )

    except Exception as erro:
        conexao.rollback()

        print(
            f"Erro durante a migração: {erro}"
        )

        raise

    finally:
        conexao.close()


if __name__ == "__main__":
    executar_migracao()