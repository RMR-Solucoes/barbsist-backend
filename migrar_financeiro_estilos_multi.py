"""
Migração SQLite: adiciona barbearia_id a caixa, comissoes, estilos,
contas_receber e contas_pagar.

Uso:
    python .\migrations\migrar_financeiro_estilos_multi.py

A migração:
- cria backup automático;
- é idempotente;
- atribui registros antigos à barbearia 1;
- cria índices;
- valida valores nulos e barbearias inexistentes.

Observação:
SQLite não permite adicionar facilmente uma FK NOT NULL completa em tabela
existente sem recriá-la. A aplicação passa a garantir NOT NULL pelo model.
Para PostgreSQL, use uma migração Alembic específica antes da publicação.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil
import sqlite3
import sys


BARBEARIA_PADRAO_ID = 1
TABELAS = (
    "caixa",
    "comissoes",
    "estilos",
    "contas_receber",
    "contas_pagar",
)


def encontrar_banco() -> Path:
    raiz_backend = Path(__file__).resolve().parents[1]
    banco = raiz_backend / "barbearia.db"

    if not banco.exists():
        raise FileNotFoundError(
            f"Banco não encontrado: {banco}"
        )

    return banco


def coluna_existe(
    cursor: sqlite3.Cursor,
    tabela: str,
    coluna: str,
) -> bool:
    colunas = cursor.execute(
        f"PRAGMA table_info({tabela})"
    ).fetchall()

    return any(item[1] == coluna for item in colunas)


def tabela_existe(
    cursor: sqlite3.Cursor,
    tabela: str,
) -> bool:
    return (
        cursor.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
              AND name = ?
            """,
            (tabela,),
        ).fetchone()
        is not None
    )


def main() -> None:
    banco = encontrar_banco()
    horario = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = banco.with_name(
        f"barbearia_backup_antes_financeiro_multi_{horario}.db"
    )

    shutil.copy2(banco, backup)
    print(f"[BACKUP] {backup}")

    conexao = sqlite3.connect(banco)
    conexao.execute("PRAGMA foreign_keys = ON")
    cursor = conexao.cursor()

    try:
        barbearia = cursor.execute(
            "SELECT id, nome FROM barbearias WHERE id = ?",
            (BARBEARIA_PADRAO_ID,),
        ).fetchone()

        if not barbearia:
            raise RuntimeError(
                "A barbearia padrão ID 1 não existe."
            )

        for tabela in TABELAS:
            if not tabela_existe(cursor, tabela):
                raise RuntimeError(
                    f"A tabela '{tabela}' não existe."
                )

            if not coluna_existe(
                cursor,
                tabela,
                "barbearia_id",
            ):
                cursor.execute(
                    f"""
                    ALTER TABLE {tabela}
                    ADD COLUMN barbearia_id INTEGER
                    REFERENCES barbearias(id)
                    """
                )
                print(
                    f"[COLUNA] {tabela}.barbearia_id criada"
                )
            else:
                print(
                    f"[OK] {tabela}.barbearia_id já existe"
                )

            cursor.execute(
                f"""
                UPDATE {tabela}
                SET barbearia_id = ?
                WHERE barbearia_id IS NULL
                """,
                (BARBEARIA_PADRAO_ID,),
            )

            indice = (
                f"ix_{tabela}_barbearia_id"
            )
            cursor.execute(
                f"""
                CREATE INDEX IF NOT EXISTS {indice}
                ON {tabela}(barbearia_id)
                """
            )

        conexao.commit()

        erros = []
        for tabela in TABELAS:
            nulos = cursor.execute(
                f"""
                SELECT COUNT(*)
                FROM {tabela}
                WHERE barbearia_id IS NULL
                """
            ).fetchone()[0]

            invalidos = cursor.execute(
                f"""
                SELECT COUNT(*)
                FROM {tabela} t
                LEFT JOIN barbearias b
                  ON b.id = t.barbearia_id
                WHERE b.id IS NULL
                """
            ).fetchone()[0]

            total = cursor.execute(
                f"SELECT COUNT(*) FROM {tabela}"
            ).fetchone()[0]

            print(
                f"[VALIDAÇÃO] {tabela}: "
                f"total={total}, nulos={nulos}, "
                f"inválidos={invalidos}"
            )

            if nulos or invalidos:
                erros.append(tabela)

        if erros:
            raise RuntimeError(
                "Falha de validação nas tabelas: "
                + ", ".join(erros)
            )

        print(
            "[SUCESSO] Migração multi-barbearia concluída."
        )

    except Exception:
        conexao.rollback()
        print(
            "[ERRO] Migração cancelada. "
            "O backup foi preservado."
        )
        raise

    finally:
        conexao.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as erro:
        print(f"Detalhes: {erro}")
        sys.exit(1)
