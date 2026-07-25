import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


PASTA_BACKEND = Path(__file__).resolve().parent
CAMINHO_BANCO = PASTA_BACKEND / "barbearia.db"


def criar_backup():
    if not CAMINHO_BANCO.exists():
        raise FileNotFoundError(f"Banco não encontrado: {CAMINHO_BANCO}")

    data = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = PASTA_BACKEND / (
        f"barbearia_backup_multibarbearia_horarios_{data}.db"
    )
    shutil.copy2(CAMINHO_BANCO, destino)
    return destino


def coluna_existe(cursor, tabela, coluna):
    cursor.execute(f"PRAGMA table_info({tabela})")
    return coluna in {item[1] for item in cursor.fetchall()}


def indice_existe(cursor, indice):
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
        (indice,),
    )
    return cursor.fetchone() is not None


def obter_barbearia_principal(cursor):
    cursor.execute(
        "SELECT id FROM barbearias ORDER BY codigo, id LIMIT 1"
    )
    resultado = cursor.fetchone()
    if not resultado:
        raise RuntimeError("Nenhuma barbearia cadastrada.")
    return int(resultado[0])


def adicionar_coluna(cursor, tabela):
    if coluna_existe(cursor, tabela, "barbearia_id"):
        print(f"[OK] {tabela}.barbearia_id já existe.")
        return

    cursor.execute(
        f"""
        ALTER TABLE {tabela}
        ADD COLUMN barbearia_id INTEGER
        REFERENCES barbearias(id)
        ON DELETE RESTRICT
        """
    )
    print(f"[CRIADO] {tabela}.barbearia_id")


def preencher(cursor, barbearia_principal_id):
    cursor.execute(
        """
        UPDATE configuracao_funcionamento
        SET barbearia_id = ?
        WHERE barbearia_id IS NULL
        """,
        (barbearia_principal_id,),
    )
    print(f"[OK] Configurações atualizadas: {cursor.rowcount}")

    cursor.execute(
        """
        UPDATE barbeiro_disponibilidade
        SET barbearia_id = (
            SELECT barbeiros.barbearia_id
            FROM barbeiros
            WHERE barbeiros.id = barbeiro_disponibilidade.barbeiro_id
        )
        WHERE barbearia_id IS NULL
        """
    )
    print(f"[OK] Disponibilidades atualizadas: {cursor.rowcount}")


def validar(cursor):
    for tabela in (
        "configuracao_funcionamento",
        "barbeiro_disponibilidade",
    ):
        cursor.execute(
            f"SELECT COUNT(*) FROM {tabela} WHERE barbearia_id IS NULL"
        )
        quantidade = cursor.fetchone()[0]
        if quantidade:
            raise RuntimeError(
                f"{tabela} possui {quantidade} registros sem barbearia."
            )

    cursor.execute(
        """
        SELECT d.id, d.barbearia_id, b.barbearia_id
        FROM barbeiro_disponibilidade AS d
        INNER JOIN barbeiros AS b ON b.id = d.barbeiro_id
        WHERE d.barbearia_id != b.barbearia_id
        """
    )
    inconsistencias = cursor.fetchall()
    if inconsistencias:
        raise RuntimeError(
            "Disponibilidades associadas à barbearia incorreta: "
            + str(inconsistencias)
        )


def criar_indices(cursor):
    indices = {
        "ix_configuracao_funcionamento_barbearia_id": """
            CREATE INDEX ix_configuracao_funcionamento_barbearia_id
            ON configuracao_funcionamento(barbearia_id)
        """,
        "ix_barbeiro_disponibilidade_barbearia_id": """
            CREATE INDEX ix_barbeiro_disponibilidade_barbearia_id
            ON barbeiro_disponibilidade(barbearia_id)
        """,
        "uq_config_funcionamento_barbearia_dia": """
            CREATE UNIQUE INDEX uq_config_funcionamento_barbearia_dia
            ON configuracao_funcionamento(barbearia_id, dia_semana)
        """,
        "uq_disponibilidade_barbearia_barbeiro_dia": """
            CREATE UNIQUE INDEX uq_disponibilidade_barbearia_barbeiro_dia
            ON barbeiro_disponibilidade(
                barbearia_id, barbeiro_id, dia_semana
            )
        """,
    }

    for nome, sql in indices.items():
        if indice_existe(cursor, nome):
            print(f"[OK] Índice {nome} já existe.")
            continue
        cursor.execute(sql)
        print(f"[CRIADO] Índice {nome}")


def executar_migracao():
    print("=" * 80)
    print("MIGRAÇÃO MULTI-BARBEARIA — HORÁRIOS")
    print("=" * 80)
    backup = criar_backup()
    print(f"[BACKUP] {backup}")

    conexao = sqlite3.connect(CAMINHO_BANCO)
    try:
        conexao.execute("PRAGMA foreign_keys = ON")
        cursor = conexao.cursor()
        cursor.execute("BEGIN")

        principal = obter_barbearia_principal(cursor)
        adicionar_coluna(cursor, "configuracao_funcionamento")
        adicionar_coluna(cursor, "barbeiro_disponibilidade")
        preencher(cursor, principal)
        validar(cursor)
        criar_indices(cursor)

        cursor.execute("PRAGMA foreign_key_check")
        erros = cursor.fetchall()
        if erros:
            raise RuntimeError(f"Erros de chave estrangeira: {erros}")

        conexao.commit()
        print("MIGRAÇÃO CONCLUÍDA COM SUCESSO")
    except Exception:
        conexao.rollback()
        print("ERRO: alterações canceladas; backup preservado.")
        raise
    finally:
        conexao.close()


if __name__ == "__main__":
    executar_migracao()
