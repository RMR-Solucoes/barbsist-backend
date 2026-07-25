import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


PASTA_BACKEND = Path(__file__).resolve().parent
CAMINHO_BANCO = PASTA_BACKEND / "barbearia.db"

TABELAS = [
    "planos",
    "assinaturas_clientes",
    "comandas"
]


def criar_backup() -> Path:
    if not CAMINHO_BANCO.exists():
        raise FileNotFoundError(
            f"Banco não encontrado em: {CAMINHO_BANCO}"
        )

    data_backup = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    caminho_backup = PASTA_BACKEND / (
        "barbearia_backup_multibarbearia_"
        f"etapa3_{data_backup}.db"
    )

    shutil.copy2(
        CAMINHO_BANCO,
        caminho_backup
    )

    return caminho_backup


def tabela_existe(
    cursor: sqlite3.Cursor,
    tabela: str
) -> bool:
    cursor.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (tabela,)
    )

    return cursor.fetchone() is not None


def coluna_existe(
    cursor: sqlite3.Cursor,
    tabela: str,
    coluna: str
) -> bool:
    cursor.execute(
        f"PRAGMA table_info({tabela})"
    )

    colunas = {
        registro[1]
        for registro in cursor.fetchall()
    }

    return coluna in colunas


def indice_existe(
    cursor: sqlite3.Cursor,
    indice: str
) -> bool:
    cursor.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'index'
          AND name = ?
        """,
        (indice,)
    )

    return cursor.fetchone() is not None


def validar_tabelas(
    cursor: sqlite3.Cursor
):
    tabelas_obrigatorias = [
        "barbearias",
        "clientes",
        "barbeiros",
        "planos",
        "assinaturas_clientes",
        "comandas"
    ]

    ausentes = [
        tabela
        for tabela in tabelas_obrigatorias
        if not tabela_existe(cursor, tabela)
    ]

    if ausentes:
        raise RuntimeError(
            "Tabelas obrigatórias ausentes: "
            + ", ".join(ausentes)
        )


def obter_barbearia_principal(
    cursor: sqlite3.Cursor
) -> int:
    cursor.execute(
        """
        SELECT id
        FROM barbearias
        ORDER BY codigo, id
        LIMIT 1
        """
    )

    resultado = cursor.fetchone()

    if not resultado:
        raise RuntimeError(
            "Nenhuma barbearia foi encontrada."
        )

    return int(resultado[0])


def adicionar_barbearia_id(
    cursor: sqlite3.Cursor,
    tabela: str
):
    if coluna_existe(
        cursor,
        tabela,
        "barbearia_id"
    ):
        print(
            f"[OK] {tabela}.barbearia_id já existe."
        )
        return

    cursor.execute(
        f"""
        ALTER TABLE {tabela}
        ADD COLUMN barbearia_id INTEGER
        REFERENCES barbearias(id)
        ON DELETE RESTRICT
        """
    )

    print(
        f"[CRIADO] {tabela}.barbearia_id"
    )


def preencher_planos(
    cursor: sqlite3.Cursor,
    barbearia_principal_id: int
):
    cursor.execute(
        """
        UPDATE planos
        SET barbearia_id = ?
        WHERE barbearia_id IS NULL
        """,
        (barbearia_principal_id,)
    )

    print(
        "[OK] Planos associados à barbearia principal: "
        f"{cursor.rowcount}"
    )


def preencher_assinaturas(
    cursor: sqlite3.Cursor
):
    cursor.execute(
        """
        UPDATE assinaturas_clientes
        SET barbearia_id = (
            SELECT cliente.barbearia_id
            FROM clientes AS cliente
            WHERE cliente.id =
                assinaturas_clientes.cliente_id
        )
        WHERE barbearia_id IS NULL
        """
    )

    print(
        "[OK] Assinaturas associadas pela barbearia "
        f"do cliente: {cursor.rowcount}"
    )


def preencher_comandas(
    cursor: sqlite3.Cursor
):
    cursor.execute(
        """
        UPDATE comandas
        SET barbearia_id = (
            SELECT barbeiro.barbearia_id
            FROM barbeiros AS barbeiro
            WHERE barbeiro.id =
                comandas.barbeiro_id
        )
        WHERE barbearia_id IS NULL
        """
    )

    print(
        "[OK] Comandas associadas pela barbearia "
        f"do barbeiro: {cursor.rowcount}"
    )


def validar_campos_preenchidos(
    cursor: sqlite3.Cursor
):
    for tabela in TABELAS:
        cursor.execute(
            f"""
            SELECT COUNT(*)
            FROM {tabela}
            WHERE barbearia_id IS NULL
            """
        )

        quantidade = cursor.fetchone()[0]

        if quantidade:
            raise RuntimeError(
                f"A tabela {tabela} possui "
                f"{quantidade} registros sem barbearia."
            )

        print(
            f"[OK] {tabela}: nenhum registro "
            "sem barbearia."
        )


def validar_assinaturas(
    cursor: sqlite3.Cursor
):
    cursor.execute(
        """
        SELECT
            assinatura.id,
            assinatura.barbearia_id,
            cliente.barbearia_id,
            plano.barbearia_id
        FROM assinaturas_clientes AS assinatura

        INNER JOIN clientes AS cliente
            ON cliente.id = assinatura.cliente_id

        INNER JOIN planos AS plano
            ON plano.id = assinatura.plano_id

        WHERE assinatura.barbearia_id
                != cliente.barbearia_id
           OR assinatura.barbearia_id
                != plano.barbearia_id
        """
    )

    inconsistencias = cursor.fetchall()

    if inconsistencias:
        raise RuntimeError(
            "Foram encontradas assinaturas associadas "
            "a clientes ou planos de outra barbearia: "
            + str(inconsistencias)
        )

    print(
        "[OK] Assinaturas pertencem à mesma "
        "barbearia dos clientes e planos."
    )


def validar_comandas(
    cursor: sqlite3.Cursor
):
    cursor.execute(
        """
        SELECT
            comanda.id,
            comanda.barbearia_id,
            barbeiro.barbearia_id
        FROM comandas AS comanda

        INNER JOIN barbeiros AS barbeiro
            ON barbeiro.id = comanda.barbeiro_id

        WHERE comanda.barbearia_id
            != barbeiro.barbearia_id
        """
    )

    inconsistencias_barbeiro = cursor.fetchall()

    if inconsistencias_barbeiro:
        raise RuntimeError(
            "Foram encontradas comandas associadas "
            "a barbeiros de outra barbearia: "
            + str(inconsistencias_barbeiro)
        )

    cursor.execute(
        """
        SELECT
            comanda.id,
            comanda.barbearia_id,
            cliente.barbearia_id
        FROM comandas AS comanda

        INNER JOIN clientes AS cliente
            ON cliente.id = comanda.cliente_id

        WHERE comanda.cliente_id IS NOT NULL
          AND comanda.barbearia_id
                != cliente.barbearia_id
        """
    )

    inconsistencias_cliente = cursor.fetchall()

    if inconsistencias_cliente:
        raise RuntimeError(
            "Foram encontradas comandas associadas "
            "a clientes de outra barbearia: "
            + str(inconsistencias_cliente)
        )

    print(
        "[OK] Comandas pertencem à mesma barbearia "
        "dos barbeiros e clientes."
    )


def validar_nomes_planos_duplicados(
    cursor: sqlite3.Cursor
):
    cursor.execute(
        """
        SELECT
            barbearia_id,
            LOWER(TRIM(nome)),
            COUNT(*)
        FROM planos
        GROUP BY
            barbearia_id,
            LOWER(TRIM(nome))
        HAVING COUNT(*) > 1
        """
    )

    duplicados = cursor.fetchall()

    if duplicados:
        raise RuntimeError(
            "Existem planos com nomes duplicados "
            "na mesma barbearia: "
            + str(duplicados)
        )


def criar_indices(
    cursor: sqlite3.Cursor
):
    indices = {
        "ix_planos_barbearia_id": """
            CREATE INDEX ix_planos_barbearia_id
            ON planos(barbearia_id)
        """,

        "ix_assinaturas_clientes_barbearia_id": """
            CREATE INDEX
            ix_assinaturas_clientes_barbearia_id
            ON assinaturas_clientes(barbearia_id)
        """,

        "ix_comandas_barbearia_id": """
            CREATE INDEX ix_comandas_barbearia_id
            ON comandas(barbearia_id)
        """,

        "uq_plano_barbearia_nome": """
            CREATE UNIQUE INDEX
            uq_plano_barbearia_nome
            ON planos(barbearia_id, nome)
        """
    }

    for nome, comando in indices.items():
        if indice_existe(cursor, nome):
            print(
                f"[OK] Índice {nome} já existe."
            )
            continue

        cursor.execute(comando)

        print(
            f"[CRIADO] Índice {nome}"
        )


def validar_chaves_estrangeiras(
    cursor: sqlite3.Cursor
):
    cursor.execute(
        "PRAGMA foreign_key_check"
    )

    erros = cursor.fetchall()

    if erros:
        detalhes = "\n".join(
            str(erro)
            for erro in erros
        )

        raise RuntimeError(
            "Foram encontradas inconsistências "
            "de chaves estrangeiras:\n"
            + detalhes
        )

    print(
        "[OK] Nenhuma inconsistência de "
        "chave estrangeira."
    )


def mostrar_resultado(
    cursor: sqlite3.Cursor
):
    print()
    print("RESULTADO:")
    print("-" * 80)

    for tabela in TABELAS:
        cursor.execute(
            f"""
            SELECT
                barbearia_id,
                COUNT(*)
            FROM {tabela}
            GROUP BY barbearia_id
            ORDER BY barbearia_id
            """
        )

        print(
            f"{tabela}: {cursor.fetchall()}"
        )


def executar_migracao():
    print("=" * 80)
    print("MIGRAÇÃO MULTI-BARBEARIA — ETAPA 3")
    print("=" * 80)

    backup = criar_backup()

    print(f"\n[BACKUP] Criado em: {backup}")

    conexao = sqlite3.connect(CAMINHO_BANCO)

    try:
        conexao.execute(
            "PRAGMA foreign_keys = ON"
        )

        cursor = conexao.cursor()
        cursor.execute("BEGIN")

        validar_tabelas(cursor)

        barbearia_principal_id = (
            obter_barbearia_principal(cursor)
        )

        print(
            "\n[BARBEARIA PRINCIPAL] "
            f"ID: {barbearia_principal_id}"
        )

        for tabela in TABELAS:
            adicionar_barbearia_id(
                cursor,
                tabela
            )

        preencher_planos(
            cursor,
            barbearia_principal_id
        )

        preencher_assinaturas(cursor)
        preencher_comandas(cursor)

        validar_campos_preenchidos(cursor)
        validar_assinaturas(cursor)
        validar_comandas(cursor)

        validar_nomes_planos_duplicados(
            cursor
        )

        criar_indices(cursor)

        validar_chaves_estrangeiras(
            cursor
        )

        mostrar_resultado(cursor)

        conexao.commit()

        print()
        print("=" * 80)
        print("MIGRAÇÃO CONCLUÍDA COM SUCESSO")
        print("=" * 80)

    except Exception as erro:
        conexao.rollback()

        print()
        print("=" * 80)
        print("ERRO NA MIGRAÇÃO")
        print("=" * 80)
        print(str(erro))
        print()
        print(
            "Nenhuma alteração foi confirmada. "
            "O backup foi preservado."
        )

        raise

    finally:
        conexao.close()


if __name__ == "__main__":
    executar_migracao()