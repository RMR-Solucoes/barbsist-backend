import re
import shutil
import sqlite3
import unicodedata
from datetime import datetime
from pathlib import Path


PASTA_BACKEND = Path(__file__).resolve().parent
CAMINHO_BANCO = PASTA_BACKEND / "barbearia.db"


def normalizar_slug(texto: str) -> str:
    """
    Converte um nome em slug.

    Exemplo:
        Barbearia do Mário -> barbearia-do-mario
    """

    texto_normalizado = unicodedata.normalize("NFKD", texto)

    texto_sem_acentos = "".join(
        caractere
        for caractere in texto_normalizado
        if not unicodedata.combining(caractere)
    )

    texto_sem_acentos = texto_sem_acentos.lower().strip()

    slug = re.sub(
        r"[^a-z0-9]+",
        "-",
        texto_sem_acentos
    )

    return slug.strip("-") or "barbearia"


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


def criar_backup() -> Path:
    if not CAMINHO_BANCO.exists():
        raise FileNotFoundError(
            f"Banco não encontrado em: {CAMINHO_BANCO}"
        )

    data_backup = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    caminho_backup = PASTA_BACKEND / (
        f"barbearia_backup_multibarbearia_"
        f"{data_backup}.db"
    )

    shutil.copy2(
        CAMINHO_BANCO,
        caminho_backup
    )

    return caminho_backup


def adicionar_coluna_se_nao_existir(
    cursor: sqlite3.Cursor,
    tabela: str,
    coluna: str,
    definicao_sql: str
):
    if coluna_existe(
        cursor,
        tabela,
        coluna
    ):
        print(
            f"[OK] {tabela}.{coluna} já existe."
        )
        return

    cursor.execute(
        f"""
        ALTER TABLE {tabela}
        ADD COLUMN {coluna} {definicao_sql}
        """
    )

    print(
        f"[CRIADO] {tabela}.{coluna}"
    )


def ajustar_tabela_barbearias(
    cursor: sqlite3.Cursor
):
    if not tabela_existe(
        cursor,
        "barbearias"
    ):
        raise RuntimeError(
            "A tabela barbearias não foi encontrada."
        )

    adicionar_coluna_se_nao_existir(
        cursor,
        "barbearias",
        "codigo",
        "INTEGER"
    )

    adicionar_coluna_se_nao_existir(
        cursor,
        "barbearias",
        "slug",
        "TEXT"
    )

    adicionar_coluna_se_nao_existir(
        cursor,
        "barbearias",
        "cor_primaria",
        "TEXT DEFAULT '#111827'"
    )

    adicionar_coluna_se_nao_existir(
        cursor,
        "barbearias",
        "cor_secundaria",
        "TEXT DEFAULT '#2563EB'"
    )

    adicionar_coluna_se_nao_existir(
        cursor,
        "barbearias",
        "cor_fundo",
        "TEXT DEFAULT '#F3F4F6'"
    )

    adicionar_coluna_se_nao_existir(
        cursor,
        "barbearias",
        "cor_sidebar",
        "TEXT DEFAULT '#111827'"
    )

    adicionar_coluna_se_nao_existir(
        cursor,
        "barbearias",
        "cor_texto_sidebar",
        "TEXT DEFAULT '#FFFFFF'"
    )

    adicionar_coluna_se_nao_existir(
        cursor,
        "barbearias",
        "cor_destaque",
        "TEXT DEFAULT '#2563EB'"
    )

    cursor.execute(
        """
        SELECT id, nome, codigo, slug
        FROM barbearias
        ORDER BY id
        """
    )

    barbearias = cursor.fetchall()

    if not barbearias:
        cursor.execute(
            """
            INSERT INTO barbearias (
                codigo,
                slug,
                nome,
                responsavel,
                ativa,
                created_at,
                cor_primaria,
                cor_secundaria,
                cor_fundo,
                cor_sidebar,
                cor_texto_sidebar,
                cor_destaque
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                "barbearia-principal",
                "Barbearia Principal",
                None,
                1,
                datetime.now().isoformat(),
                "#111827",
                "#2563EB",
                "#F3F4F6",
                "#111827",
                "#FFFFFF",
                "#2563EB"
            )
        )

        print(
            "[CRIADO] Barbearia principal."
        )

    else:
        codigos_usados = set()
        slugs_usados = set()

        for posicao, registro in enumerate(
            barbearias,
            start=1
        ):
            barbearia_id = registro[0]
            nome = registro[1] or (
                f"Barbearia {posicao}"
            )
            codigo_atual = registro[2]
            slug_atual = registro[3]

            codigo = codigo_atual or posicao

            while codigo in codigos_usados:
                codigo += 1

            slug_base = (
                slug_atual
                or normalizar_slug(nome)
            )

            slug = slug_base
            contador = 2

            while slug in slugs_usados:
                slug = f"{slug_base}-{contador}"
                contador += 1

            codigos_usados.add(codigo)
            slugs_usados.add(slug)

            cursor.execute(
                """
                UPDATE barbearias
                SET
                    codigo = ?,
                    slug = ?,
                    cor_primaria = COALESCE(
                        cor_primaria,
                        '#111827'
                    ),
                    cor_secundaria = COALESCE(
                        cor_secundaria,
                        '#2563EB'
                    ),
                    cor_fundo = COALESCE(
                        cor_fundo,
                        '#F3F4F6'
                    ),
                    cor_sidebar = COALESCE(
                        cor_sidebar,
                        '#111827'
                    ),
                    cor_texto_sidebar = COALESCE(
                        cor_texto_sidebar,
                        '#FFFFFF'
                    ),
                    cor_destaque = COALESCE(
                        cor_destaque,
                        '#2563EB'
                    )
                WHERE id = ?
                """,
                (
                    codigo,
                    slug,
                    barbearia_id
                )
            )

    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS
        uq_barbearias_codigo
        ON barbearias(codigo)
        """
    )

    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS
        uq_barbearias_slug
        ON barbearias(slug)
        """
    )

    print(
        "[OK] Tabela barbearias atualizada."
    )


def obter_barbearia_principal_id(
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
            "Não foi possível localizar a barbearia principal."
        )

    return int(resultado[0])


def usuarios_tem_unicidade_global(
    cursor: sqlite3.Cursor
) -> bool:
    cursor.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type = 'table'
          AND name = 'usuarios'
        """
    )

    resultado = cursor.fetchone()

    if not resultado or not resultado[0]:
        return False

    sql_tabela = resultado[0].lower()

    return (
        "email varchar unique" in sql_tabela
        or "email text unique" in sql_tabela
        or "unique (email)" in sql_tabela
        or "unique(email)" in sql_tabela
    )


def reconstruir_tabela_usuarios(
    cursor: sqlite3.Cursor,
    barbearia_principal_id: int
):
    if not tabela_existe(
        cursor,
        "usuarios"
    ):
        print(
            "[AVISO] Tabela usuarios não encontrada."
        )
        return

    possui_barbearia_id = coluna_existe(
        cursor,
        "usuarios",
        "barbearia_id"
    )

    precisa_reconstruir = (
        not possui_barbearia_id
        or usuarios_tem_unicidade_global(cursor)
    )

    if not precisa_reconstruir:
        cursor.execute(
            """
            UPDATE usuarios
            SET barbearia_id = ?
            WHERE barbearia_id IS NULL
            """,
            (barbearia_principal_id,)
        )

        print(
            "[OK] Usuários já estão na estrutura multi-barbearia."
        )
        return

    cursor.execute(
        """
        DROP TABLE IF EXISTS usuarios_novo
        """
    )

    cursor.execute(
        """
        CREATE TABLE usuarios_novo (
            id INTEGER NOT NULL,
            nome VARCHAR NOT NULL,
            email VARCHAR NOT NULL,
            senha_hash VARCHAR NOT NULL,
            perfil VARCHAR NOT NULL DEFAULT 'admin',
            barbeiro_id INTEGER,
            ativo BOOLEAN NOT NULL DEFAULT 1,
            data_criacao DATETIME NOT NULL,
            barbearia_id INTEGER NOT NULL,

            PRIMARY KEY (id),

            FOREIGN KEY(barbeiro_id)
                REFERENCES barbeiros (id),

            FOREIGN KEY(barbearia_id)
                REFERENCES barbearias (id)
                ON DELETE RESTRICT,

            CONSTRAINT uq_usuario_barbearia_email
                UNIQUE (
                    barbearia_id,
                    email
                )
        )
        """
    )

    if possui_barbearia_id:
        cursor.execute(
            """
            INSERT INTO usuarios_novo (
                id,
                nome,
                email,
                senha_hash,
                perfil,
                barbeiro_id,
                ativo,
                data_criacao,
                barbearia_id
            )
            SELECT
                id,
                nome,
                LOWER(TRIM(email)),
                senha_hash,
                COALESCE(perfil, 'admin'),
                barbeiro_id,
                COALESCE(ativo, 1),
                COALESCE(
                    data_criacao,
                    CURRENT_TIMESTAMP
                ),
                COALESCE(
                    barbearia_id,
                    ?
                )
            FROM usuarios
            """,
            (barbearia_principal_id,)
        )

    else:
        cursor.execute(
            """
            INSERT INTO usuarios_novo (
                id,
                nome,
                email,
                senha_hash,
                perfil,
                barbeiro_id,
                ativo,
                data_criacao,
                barbearia_id
            )
            SELECT
                id,
                nome,
                LOWER(TRIM(email)),
                senha_hash,
                COALESCE(perfil, 'admin'),
                barbeiro_id,
                COALESCE(ativo, 1),
                COALESCE(
                    data_criacao,
                    CURRENT_TIMESTAMP
                ),
                ?
            FROM usuarios
            """,
            (barbearia_principal_id,)
        )

    cursor.execute(
        """
        DROP TABLE usuarios
        """
    )

    cursor.execute(
        """
        ALTER TABLE usuarios_novo
        RENAME TO usuarios
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        ix_usuarios_id
        ON usuarios(id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        ix_usuarios_email
        ON usuarios(email)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        ix_usuarios_barbearia_id
        ON usuarios(barbearia_id)
        """
    )

    print(
        "[OK] Tabela usuarios reconstruída."
    )


def criar_tabela_sequencias(
    cursor: sqlite3.Cursor
):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS
        sequencias_barbearia (
            id INTEGER NOT NULL,
            barbearia_id INTEGER NOT NULL,
            tipo VARCHAR NOT NULL,
            ultimo_numero INTEGER NOT NULL DEFAULT 0,
            data_atualizacao DATETIME NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            PRIMARY KEY (id),

            FOREIGN KEY(barbearia_id)
                REFERENCES barbearias (id)
                ON DELETE RESTRICT,

            CONSTRAINT uq_sequencia_barbearia_tipo
                UNIQUE (
                    barbearia_id,
                    tipo
                )
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        ix_sequencias_barbearia_id
        ON sequencias_barbearia(barbearia_id)
        """
    )

    print(
        "[OK] Tabela sequencias_barbearia criada."
    )


def validar_resultado(
    cursor: sqlite3.Cursor
):
    cursor.execute(
        """
        SELECT
            id,
            codigo,
            slug,
            nome,
            ativa
        FROM barbearias
        ORDER BY codigo
        """
    )

    barbearias = cursor.fetchall()

    cursor.execute(
        """
        SELECT
            id,
            nome,
            email,
            perfil,
            barbearia_id,
            ativo
        FROM usuarios
        ORDER BY id
        """
    )

    usuarios = cursor.fetchall()

    print()
    print("BARBEARIAS:")
    print("-" * 70)

    for registro in barbearias:
        print(registro)

    print()
    print("USUÁRIOS:")
    print("-" * 70)

    for registro in usuarios:
        print(registro)

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM usuarios
        WHERE barbearia_id IS NULL
        """
    )

    usuarios_sem_barbearia = cursor.fetchone()[0]

    if usuarios_sem_barbearia:
        raise RuntimeError(
            f"Existem {usuarios_sem_barbearia} "
            "usuários sem barbearia."
        )

    print()
    print("[OK] Nenhum usuário sem barbearia.")


def executar_migracao():
    print("=" * 70)
    print("MIGRAÇÃO MULTI-BARBEARIA — ETAPA 1")
    print("=" * 70)

    backup = criar_backup()

    print(
        f"[BACKUP] Criado em: {backup}"
    )

    conexao = sqlite3.connect(
        CAMINHO_BANCO
    )

    try:
        conexao.execute(
            "PRAGMA foreign_keys = OFF"
        )

        cursor = conexao.cursor()

        cursor.execute("BEGIN")

        ajustar_tabela_barbearias(cursor)

        barbearia_principal_id = (
            obter_barbearia_principal_id(cursor)
        )

        reconstruir_tabela_usuarios(
            cursor,
            barbearia_principal_id
        )

        criar_tabela_sequencias(cursor)

        validar_resultado(cursor)

        conexao.commit()

        print()
        print("=" * 70)
        print("MIGRAÇÃO CONCLUÍDA COM SUCESSO")
        print("=" * 70)

    except Exception as erro:
        conexao.rollback()

        print()
        print("=" * 70)
        print("ERRO NA MIGRAÇÃO")
        print("=" * 70)
        print(str(erro))
        print()
        print(
            "Nenhuma alteração foi confirmada. "
            "O backup também foi preservado."
        )

        raise

    finally:
        conexao.close()


if __name__ == "__main__":
    executar_migracao()