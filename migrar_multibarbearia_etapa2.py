import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


PASTA_BACKEND = Path(__file__).resolve().parent
CAMINHO_BANCO = PASTA_BACKEND / "barbearia.db"


CONFIGURACOES = {
    "clientes": {
        "tipo": "CLIENTE",
        "prefixo": "CLI"
    },
    "barbeiros": {
        "tipo": "BARBEIRO",
        "prefixo": "BAR"
    },
    "servicos": {
        "tipo": "SERVICO",
        "prefixo": "SER"
    },
    "produtos": {
        "tipo": "PRODUTO",
        "prefixo": "PRO"
    }
}


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
        f"etapa2_{data_backup}.db"
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


def adicionar_coluna_se_necessario(
    cursor: sqlite3.Cursor,
    tabela: str,
    coluna: str,
    definicao: str
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
        ADD COLUMN {coluna} {definicao}
        """
    )

    print(
        f"[CRIADO] {tabela}.{coluna}"
    )


def obter_barbearia_principal(
    cursor: sqlite3.Cursor
) -> tuple[int, int]:
    cursor.execute(
        """
        SELECT id, codigo
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

    barbearia_id = int(resultado[0])
    codigo_barbearia = int(resultado[1])

    return barbearia_id, codigo_barbearia


def formatar_codigo(
    prefixo: str,
    codigo_barbearia: int,
    numero: int
) -> str:
    return (
        f"{prefixo}-"
        f"{codigo_barbearia:03d}-"
        f"{numero:06d}"
    )


def preparar_tabela(
    cursor: sqlite3.Cursor,
    tabela: str
):
    if not tabela_existe(
        cursor,
        tabela
    ):
        raise RuntimeError(
            f"A tabela {tabela} não foi encontrada."
        )

    adicionar_coluna_se_necessario(
        cursor=cursor,
        tabela=tabela,
        coluna="barbearia_id",
        definicao="INTEGER"
    )

    adicionar_coluna_se_necessario(
        cursor=cursor,
        tabela=tabela,
        coluna="numero_sequencial",
        definicao="INTEGER"
    )

    adicionar_coluna_se_necessario(
        cursor=cursor,
        tabela=tabela,
        coluna="codigo",
        definicao="TEXT"
    )


def preencher_registros(
    cursor: sqlite3.Cursor,
    tabela: str,
    barbearia_id: int,
    codigo_barbearia: int,
    prefixo: str
) -> int:
    cursor.execute(
        f"""
        SELECT
            id,
            barbearia_id,
            numero_sequencial,
            codigo
        FROM {tabela}
        ORDER BY id
        """
    )

    registros = cursor.fetchall()

    maior_numero = 0
    numeros_utilizados = set()

    for registro in registros:
        registro_id = int(registro[0])
        barbearia_atual = registro[1]
        numero_atual = registro[2]
        codigo_atual = registro[3]

        barbearia_registro = (
            int(barbearia_atual)
            if barbearia_atual is not None
            else barbearia_id
        )

        if numero_atual is not None:
            numero = int(numero_atual)
        else:
            numero = registro_id

        while numero in numeros_utilizados:
            numero += 1

        numeros_utilizados.add(numero)

        codigo = codigo_atual

        if not codigo:
            codigo = formatar_codigo(
                prefixo=prefixo,
                codigo_barbearia=codigo_barbearia,
                numero=numero
            )

        cursor.execute(
            f"""
            UPDATE {tabela}
            SET
                barbearia_id = ?,
                numero_sequencial = ?,
                codigo = ?
            WHERE id = ?
            """,
            (
                barbearia_registro,
                numero,
                codigo,
                registro_id
            )
        )

        maior_numero = max(
            maior_numero,
            numero
        )

    return maior_numero


def criar_indices_basicos(
    cursor: sqlite3.Cursor,
    tabela: str
):
    indices = {
        f"ix_{tabela}_barbearia_id": (
            f"CREATE INDEX "
            f"ix_{tabela}_barbearia_id "
            f"ON {tabela}(barbearia_id)"
        ),
        f"ix_{tabela}_numero_sequencial": (
            f"CREATE INDEX "
            f"ix_{tabela}_numero_sequencial "
            f"ON {tabela}(numero_sequencial)"
        ),
        f"ix_{tabela}_codigo": (
            f"CREATE INDEX "
            f"ix_{tabela}_codigo "
            f"ON {tabela}(codigo)"
        )
    }

    for nome_indice, sql in indices.items():
        if indice_existe(
            cursor,
            nome_indice
        ):
            continue

        cursor.execute(sql)

        print(
            f"[CRIADO] Índice {nome_indice}"
        )


def validar_codigos_duplicados(
    cursor: sqlite3.Cursor,
    tabela: str
):
    cursor.execute(
        f"""
        SELECT
            barbearia_id,
            codigo,
            COUNT(*)
        FROM {tabela}
        GROUP BY
            barbearia_id,
            codigo
        HAVING COUNT(*) > 1
        """
    )

    duplicados = cursor.fetchall()

    if duplicados:
        detalhes = ", ".join(
            f"barbearia={item[0]}, "
            f"codigo={item[1]}, "
            f"quantidade={item[2]}"
            for item in duplicados
        )

        raise RuntimeError(
            f"Códigos duplicados em {tabela}: "
            f"{detalhes}"
        )


def criar_indice_unico_codigo(
    cursor: sqlite3.Cursor,
    tabela: str
):
    nome_indice = (
        f"uq_{tabela}_barbearia_codigo"
    )

    if indice_existe(
        cursor,
        nome_indice
    ):
        print(
            f"[OK] Índice único {nome_indice} já existe."
        )
        return

    validar_codigos_duplicados(
        cursor=cursor,
        tabela=tabela
    )

    cursor.execute(
        f"""
        CREATE UNIQUE INDEX {nome_indice}
        ON {tabela}(
            barbearia_id,
            codigo
        )
        """
    )

    print(
        f"[CRIADO] Índice único {nome_indice}"
    )


def existem_servicos_duplicados(
    cursor: sqlite3.Cursor
) -> bool:
    cursor.execute(
        """
        SELECT
            barbearia_id,
            LOWER(TRIM(nome)),
            COUNT(*)
        FROM servicos
        WHERE nome IS NOT NULL
          AND TRIM(nome) != ''
        GROUP BY
            barbearia_id,
            LOWER(TRIM(nome))
        HAVING COUNT(*) > 1
        """
    )

    duplicados = cursor.fetchall()

    if not duplicados:
        return False

    print()
    print(
        "[AVISO] Existem serviços com nomes duplicados:"
    )

    for item in duplicados:
        print(
            f"  Barbearia {item[0]} | "
            f"Nome: {item[1]} | "
            f"Quantidade: {item[2]}"
        )

    print(
        "[AVISO] A unicidade do nome do serviço "
        "não foi criada nesta etapa."
    )

    return True


def criar_indice_unico_nome_servico(
    cursor: sqlite3.Cursor
):
    nome_indice = (
        "uq_servicos_barbearia_nome"
    )

    if indice_existe(
        cursor,
        nome_indice
    ):
        print(
            f"[OK] Índice {nome_indice} já existe."
        )
        return

    if existem_servicos_duplicados(cursor):
        return

    cursor.execute(
        """
        CREATE UNIQUE INDEX
        uq_servicos_barbearia_nome
        ON servicos(
            barbearia_id,
            nome
        )
        """
    )

    print(
        "[CRIADO] Índice único "
        "uq_servicos_barbearia_nome"
    )


def atualizar_sequencia(
    cursor: sqlite3.Cursor,
    barbearia_id: int,
    tipo: str,
    ultimo_numero: int
):
    cursor.execute(
        """
        SELECT id, ultimo_numero
        FROM sequencias_barbearia
        WHERE barbearia_id = ?
          AND tipo = ?
        """,
        (
            barbearia_id,
            tipo
        )
    )

    sequencia = cursor.fetchone()

    if sequencia:
        numero_atual = int(
            sequencia[1] or 0
        )

        novo_numero = max(
            numero_atual,
            ultimo_numero
        )

        cursor.execute(
            """
            UPDATE sequencias_barbearia
            SET
                ultimo_numero = ?,
                data_atualizacao = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                novo_numero,
                sequencia[0]
            )
        )

        print(
            f"[OK] Sequência {tipo}: "
            f"{novo_numero}"
        )

        return

    cursor.execute(
        """
        INSERT INTO sequencias_barbearia (
            barbearia_id,
            tipo,
            ultimo_numero,
            data_atualizacao
        )
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            barbearia_id,
            tipo,
            ultimo_numero
        )
    )

    print(
        f"[CRIADO] Sequência {tipo}: "
        f"{ultimo_numero}"
    )


def validar_tabela(
    cursor: sqlite3.Cursor,
    tabela: str
):
    cursor.execute(
        f"""
        SELECT COUNT(*)
        FROM {tabela}
        WHERE barbearia_id IS NULL
           OR numero_sequencial IS NULL
           OR codigo IS NULL
           OR TRIM(codigo) = ''
        """
    )

    incompletos = cursor.fetchone()[0]

    if incompletos:
        raise RuntimeError(
            f"A tabela {tabela} possui "
            f"{incompletos} registros incompletos."
        )

    cursor.execute(
        f"""
        SELECT
            id,
            barbearia_id,
            numero_sequencial,
            codigo
        FROM {tabela}
        ORDER BY id
        LIMIT 5
        """
    )

    exemplos = cursor.fetchall()

    print()
    print(
        f"{tabela.upper()} — exemplos:"
    )
    print("-" * 70)

    if not exemplos:
        print(
            "Nenhum registro cadastrado."
        )
        return

    for exemplo in exemplos:
        print(exemplo)


def executar_migracao():
    print("=" * 70)
    print("MIGRAÇÃO MULTI-BARBEARIA — ETAPA 2")
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

        (
            barbearia_id,
            codigo_barbearia
        ) = obter_barbearia_principal(
            cursor
        )

        print(
            f"[BARBEARIA] ID: {barbearia_id} | "
            f"Código: {codigo_barbearia:03d}"
        )

        maiores_numeros = {}

        for tabela, configuracao in (
            CONFIGURACOES.items()
        ):
            print()
            print(
                f"Preparando tabela: {tabela}"
            )

            preparar_tabela(
                cursor=cursor,
                tabela=tabela
            )

            maior_numero = preencher_registros(
                cursor=cursor,
                tabela=tabela,
                barbearia_id=barbearia_id,
                codigo_barbearia=codigo_barbearia,
                prefixo=configuracao["prefixo"]
            )

            maiores_numeros[
                configuracao["tipo"]
            ] = maior_numero

            criar_indices_basicos(
                cursor=cursor,
                tabela=tabela
            )

            criar_indice_unico_codigo(
                cursor=cursor,
                tabela=tabela
            )

        criar_indice_unico_nome_servico(
            cursor
        )

        for tipo, ultimo_numero in (
            maiores_numeros.items()
        ):
            atualizar_sequencia(
                cursor=cursor,
                barbearia_id=barbearia_id,
                tipo=tipo,
                ultimo_numero=ultimo_numero
            )

        for tabela in CONFIGURACOES:
            validar_tabela(
                cursor=cursor,
                tabela=tabela
            )

        conexao.commit()

        print()
        print("=" * 70)
        print(
            "MIGRAÇÃO CONCLUÍDA COM SUCESSO"
        )
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
            "As alterações não foram confirmadas."
        )
        print(
            "O backup foi preservado para recuperação."
        )

        raise

    finally:
        conexao.close()


if __name__ == "__main__":
    executar_migracao()