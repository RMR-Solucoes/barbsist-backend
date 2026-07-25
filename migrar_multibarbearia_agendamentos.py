import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


PASTA_BACKEND = Path(__file__).resolve().parent
CAMINHO_BANCO = PASTA_BACKEND / "barbearia.db"
TABELA = "agendamentos"
INDICE = "ix_agendamentos_barbearia_id"


def criar_backup() -> Path:
    if not CAMINHO_BANCO.exists():
        raise FileNotFoundError(
            f"Banco não encontrado em: {CAMINHO_BANCO}"
        )

    data_backup = datetime.now().strftime("%Y%m%d_%H%M%S")
    caminho_backup = PASTA_BACKEND / (
        "barbearia_backup_multibarbearia_agendamentos_"
        f"{data_backup}.db"
    )
    shutil.copy2(CAMINHO_BANCO, caminho_backup)
    return caminho_backup


def tabela_existe(cursor: sqlite3.Cursor, tabela: str) -> bool:
    cursor.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (tabela,),
    )
    return cursor.fetchone() is not None


def coluna_existe(
    cursor: sqlite3.Cursor,
    tabela: str,
    coluna: str,
) -> bool:
    cursor.execute(f"PRAGMA table_info({tabela})")
    return coluna in {registro[1] for registro in cursor.fetchall()}


def indice_existe(cursor: sqlite3.Cursor, indice: str) -> bool:
    cursor.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'index' AND name = ?
        """,
        (indice,),
    )
    return cursor.fetchone() is not None


def validar_tabelas(cursor: sqlite3.Cursor):
    obrigatorias = (
        "barbearias",
        "clientes",
        "barbeiros",
        "servicos",
        TABELA,
    )
    ausentes = [
        tabela
        for tabela in obrigatorias
        if not tabela_existe(cursor, tabela)
    ]

    if ausentes:
        raise RuntimeError(
            "Tabelas obrigatórias ausentes: " + ", ".join(ausentes)
        )


def adicionar_coluna(cursor: sqlite3.Cursor):
    if coluna_existe(cursor, TABELA, "barbearia_id"):
        print("[OK] agendamentos.barbearia_id já existe.")
        return

    cursor.execute(
        """
        ALTER TABLE agendamentos
        ADD COLUMN barbearia_id INTEGER
        REFERENCES barbearias(id)
        ON DELETE RESTRICT
        """
    )
    print("[CRIADO] agendamentos.barbearia_id")


def preencher_por_barbeiro(cursor: sqlite3.Cursor):
    cursor.execute(
        """
        UPDATE agendamentos
        SET barbearia_id = (
            SELECT barbeiro.barbearia_id
            FROM barbeiros AS barbeiro
            WHERE barbeiro.id = agendamentos.barbeiro_id
        )
        WHERE barbearia_id IS NULL
        """
    )
    print(
        "[OK] Agendamentos associados pela barbearia do barbeiro: "
        f"{cursor.rowcount}"
    )


def validar_preenchimento(cursor: sqlite3.Cursor):
    cursor.execute(
        """
        SELECT id
        FROM agendamentos
        WHERE barbearia_id IS NULL
        ORDER BY id
        """
    )
    sem_barbearia = [registro[0] for registro in cursor.fetchall()]

    if sem_barbearia:
        raise RuntimeError(
            "Agendamentos sem barbearia após a associação: "
            + str(sem_barbearia)
        )


def validar_relacionamentos(cursor: sqlite3.Cursor):
    cursor.execute(
        """
        SELECT
            agendamento.id,
            agendamento.barbearia_id,
            barbeiro.barbearia_id
        FROM agendamentos AS agendamento
        INNER JOIN barbeiros AS barbeiro
            ON barbeiro.id = agendamento.barbeiro_id
        WHERE agendamento.barbearia_id != barbeiro.barbearia_id
        """
    )
    barbeiros_incorretos = cursor.fetchall()

    if barbeiros_incorretos:
        raise RuntimeError(
            "Agendamentos com barbeiro de outra barbearia: "
            + str(barbeiros_incorretos)
        )

    cursor.execute(
        """
        SELECT
            agendamento.id,
            agendamento.barbearia_id,
            cliente.barbearia_id
        FROM agendamentos AS agendamento
        INNER JOIN clientes AS cliente
            ON cliente.id = agendamento.cliente_id
        WHERE agendamento.cliente_id IS NOT NULL
          AND agendamento.barbearia_id != cliente.barbearia_id
        """
    )
    clientes_incorretos = cursor.fetchall()

    if clientes_incorretos:
        raise RuntimeError(
            "Agendamentos com cliente de outra barbearia: "
            + str(clientes_incorretos)
        )

    cursor.execute(
        """
        SELECT
            agendamento.id,
            agendamento.barbearia_id,
            servico.barbearia_id
        FROM agendamentos AS agendamento
        INNER JOIN servicos AS servico
            ON servico.id = agendamento.servico_id
        WHERE agendamento.barbearia_id != servico.barbearia_id
        """
    )
    servicos_incorretos = cursor.fetchall()

    if servicos_incorretos:
        raise RuntimeError(
            "Agendamentos com serviço de outra barbearia: "
            + str(servicos_incorretos)
        )

    print("[OK] Relacionamentos dos agendamentos são consistentes.")


def criar_indice(cursor: sqlite3.Cursor):
    if indice_existe(cursor, INDICE):
        print(f"[OK] Índice {INDICE} já existe.")
        return

    cursor.execute(
        """
        CREATE INDEX ix_agendamentos_barbearia_id
        ON agendamentos(barbearia_id)
        """
    )
    print(f"[CRIADO] Índice {INDICE}")


def validar_chaves_estrangeiras(cursor: sqlite3.Cursor):
    cursor.execute("PRAGMA foreign_key_check")
    erros = cursor.fetchall()

    if erros:
        raise RuntimeError(
            "Inconsistências de chaves estrangeiras: " + str(erros)
        )


def mostrar_resultado(cursor: sqlite3.Cursor):
    cursor.execute(
        """
        SELECT barbearia_id, COUNT(*)
        FROM agendamentos
        GROUP BY barbearia_id
        ORDER BY barbearia_id
        """
    )
    print(f"agendamentos: {cursor.fetchall()}")


def executar_migracao():
    print("=" * 80)
    print("MIGRAÇÃO MULTI-BARBEARIA — AGENDAMENTOS")
    print("=" * 80)

    backup = criar_backup()
    print(f"\n[BACKUP] Criado em: {backup}")

    conexao = sqlite3.connect(CAMINHO_BANCO)

    try:
        conexao.execute("PRAGMA foreign_keys = ON")
        cursor = conexao.cursor()
        cursor.execute("BEGIN")

        validar_tabelas(cursor)
        adicionar_coluna(cursor)
        preencher_por_barbeiro(cursor)
        validar_preenchimento(cursor)
        validar_relacionamentos(cursor)
        criar_indice(cursor)
        validar_chaves_estrangeiras(cursor)
        mostrar_resultado(cursor)

        conexao.commit()
        print("\nMIGRAÇÃO CONCLUÍDA COM SUCESSO")

    except Exception:
        conexao.rollback()
        print("\nERRO: nenhuma alteração foi confirmada.")
        print("O backup foi preservado.")
        raise

    finally:
        conexao.close()


if __name__ == "__main__":
    executar_migracao()
