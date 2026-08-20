"""Migração consolidada multi-barbearia para SQLite.

Execute dentro de backend:
    python .\migrations\migrar_multi_barbearia_consolidado.py

Por padrão, registros antigos recebem barbearia_id=1.
Para usar outro ID no PowerShell:
    $env:MIGRACAO_BARBEARIA_PADRAO_ID="2"
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

TABELAS_MULTI = [
    "usuarios", "clientes", "barbeiros", "servicos", "produtos",
    "planos", "assinaturas_clientes", "uso_plano", "pagamentos_planos",
    "agendamentos", "comandas", "itens_comanda", "caixa", "comissoes",
    "contas_receber", "contas_pagar", "estilos",
    "configuracao_funcionamento", "barbeiro_disponibilidade",
]


def backend_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def resolver_caminho_sqlite() -> Path:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        if database_url.startswith("sqlite:///"):
            caminho = unquote(database_url.removeprefix("sqlite:///"))
        elif database_url.startswith("sqlite://"):
            caminho = unquote(database_url.removeprefix("sqlite://"))
        else:
            raise RuntimeError("Esta migração foi preparada apenas para SQLite.")
        path = Path(caminho)
        if not path.is_absolute():
            path = backend_dir() / path
        return path.resolve()
    return (backend_dir() / "barbearia.db").resolve()


def tabela_existe(conn: sqlite3.Connection, tabela: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (tabela,),
    ).fetchone() is not None


def colunas_tabela(conn: sqlite3.Connection, tabela: str) -> set[str]:
    return {linha[1] for linha in conn.execute(f'PRAGMA table_info("{tabela}")')}


def indice_existe(conn: sqlite3.Connection, indice: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?",
        (indice,),
    ).fetchone() is not None


def validar_barbearia_padrao(conn: sqlite3.Connection, barbearia_id: int) -> None:
    if not tabela_existe(conn, "barbearias"):
        raise RuntimeError("A tabela 'barbearias' não existe.")
    registro = conn.execute(
        "SELECT id, nome FROM barbearias WHERE id=?", (barbearia_id,)
    ).fetchone()
    if registro is None:
        existentes = conn.execute("SELECT id, nome FROM barbearias ORDER BY id").fetchall()
        resumo = ", ".join(f"{i} - {n}" for i, n in existentes) or "nenhuma"
        raise RuntimeError(
            f"A barbearia padrão ID {barbearia_id} não existe. Disponíveis: {resumo}."
        )
    print(f"Barbearia padrão: {registro[0]} - {registro[1]}")


def criar_backup(db_path: Path) -> Path:
    destino_dir = backend_dir() / "backups"
    destino_dir.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = destino_dir / f"{db_path.stem}_antes_multi_{carimbo}{db_path.suffix}"
    shutil.copy2(db_path, destino)
    return destino


def processar_tabela(conn: sqlite3.Connection, tabela: str, barbearia_id: int) -> None:
    colunas = colunas_tabela(conn, tabela)
    criada = False
    if "barbearia_id" not in colunas:
        conn.execute(f'ALTER TABLE "{tabela}" ADD COLUMN barbearia_id INTEGER')
        criada = True

    cursor = conn.execute(
        f'UPDATE "{tabela}" SET barbearia_id=? WHERE barbearia_id IS NULL',
        (barbearia_id,),
    )

    indice = f"ix_{tabela}_barbearia_id"
    indice_criado = False
    if not indice_existe(conn, indice):
        conn.execute(f'CREATE INDEX "{indice}" ON "{tabela}" (barbearia_id)')
        indice_criado = True

    print(
        f"[OK] {tabela}: "
        f"{'coluna criada' if criada else 'coluna já existente'}; "
        f"{cursor.rowcount} registro(s) preenchido(s); "
        f"{'índice criado' if indice_criado else 'índice já existente'}."
    )


def validar(conn: sqlite3.Connection, tabelas: list[str]) -> None:
    erros = []
    for tabela in tabelas:
        if "barbearia_id" not in colunas_tabela(conn, tabela):
            erros.append(f"{tabela}: coluna ausente")
            continue
        nulos = conn.execute(
            f'SELECT COUNT(*) FROM "{tabela}" WHERE barbearia_id IS NULL'
        ).fetchone()[0]
        if nulos:
            erros.append(f"{tabela}: {nulos} registro(s) sem barbearia_id")
    if erros:
        raise RuntimeError("Falha na validação:\n- " + "\n- ".join(erros))


def main() -> int:
    db_path = resolver_caminho_sqlite()
    if not db_path.exists():
        print(f"ERRO: banco não encontrado: {db_path}")
        return 1

    try:
        barbearia_id = int(os.getenv("MIGRACAO_BARBEARIA_PADRAO_ID", "1"))
    except ValueError:
        print("ERRO: MIGRACAO_BARBEARIA_PADRAO_ID deve ser inteiro.")
        return 1

    print("=" * 68)
    print("MIGRAÇÃO CONSOLIDADA MULTI-BARBEARIA")
    print("=" * 68)
    print(f"Banco: {db_path}")

    backup = criar_backup(db_path)
    print(f"Backup: {backup}")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    processadas: list[str] = []

    try:
        conn.execute("BEGIN IMMEDIATE")
        validar_barbearia_padrao(conn, barbearia_id)

        for tabela in TABELAS_MULTI:
            if not tabela_existe(conn, tabela):
                print(f"[IGNORADA] {tabela}: tabela não existe.")
                continue
            processar_tabela(conn, tabela, barbearia_id)
            processadas.append(tabela)

        validar(conn, processadas)
        conn.commit()
    except Exception as exc:
        conn.rollback()
        print("\nMIGRAÇÃO CANCELADA.")
        print(f"Motivo: {exc}")
        print(f"Backup preservado em: {backup}")
        return 1
    finally:
        conn.close()

    print("\n" + "=" * 68)
    print("MIGRAÇÃO CONCLUÍDA COM SUCESSO")
    print("=" * 68)
    print(f"Tabelas processadas: {len(processadas)}")
    print("Nenhum registro processado ficou sem barbearia_id.")
    return 0


if __name__ == "__main__":
    sys.exit(main())