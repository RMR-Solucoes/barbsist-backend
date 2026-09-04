"""
Migração incremental do schema SaaS BarbSist.

Sincroniza colunas adicionadas aos modelos:
- planos_saas
- assinaturas_saas
- pagamentos_saas

Idempotente: somente adiciona colunas ausentes.
Compatível com SQLite local e PostgreSQL/Railway.
"""

from sqlalchemy import inspect, text
from database import engine


def colunas(tabela):
    return {
        c["name"]
        for c in inspect(engine).get_columns(tabela)
    }


def adicionar(tabela, coluna, ddl):
    existentes = colunas(tabela)

    if coluna in existentes:
        print(f"[OK] {tabela}.{coluna} ja existe")
        return

    with engine.begin() as conn:
        conn.execute(
            text(
                f"ALTER TABLE {tabela} "
                f"ADD COLUMN {coluna} {ddl}"
            )
        )

    print(f"[CRIADA] {tabela}.{coluna}")


def main():
    tabelas = set(inspect(engine).get_table_names())

    obrigatorias = {
        "planos_saas",
        "assinaturas_saas",
        "pagamentos_saas",
    }

    faltantes = obrigatorias - tabelas

    if faltantes:
        raise RuntimeError(
            "Tabelas SaaS ausentes: "
            + ", ".join(sorted(faltantes))
        )

    dialect = engine.dialect.name

    print("===== MIGRACAO SCHEMA SAAS =====")
    print("Banco:", dialect)

    # -------------------------
    # PLANOS SAAS
    # -------------------------

    adicionar(
        "planos_saas",
        "limite_barbeiros",
        "INTEGER NOT NULL DEFAULT 1",
    )

    # -------------------------
    # ASSINATURAS SAAS
    # -------------------------

    adicionar(
        "assinaturas_saas",
        "promocao_codigo",
        "VARCHAR NULL",
    )

    adicionar(
        "assinaturas_saas",
        "promocao_inicio",
        "DATETIME NULL"
        if dialect == "sqlite"
        else "TIMESTAMP NULL",
    )

    adicionar(
        "assinaturas_saas",
        "promocao_fim",
        "DATETIME NULL"
        if dialect == "sqlite"
        else "TIMESTAMP NULL",
    )

    adicionar(
        "assinaturas_saas",
        "fundador_posicao",
        "INTEGER NULL",
    )

    # -------------------------
    # PAGAMENTOS SAAS
    # -------------------------

    adicionar(
        "pagamentos_saas",
        "valor_original",
        "FLOAT NULL",
    )

    adicionar(
        "pagamentos_saas",
        "valor_credito",
        "FLOAT NOT NULL DEFAULT 0",
    )

    # -------------------------
    # INDICES
    # -------------------------

    with engine.begin() as conn:
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS "
            "ix_assinaturas_saas_promocao_codigo "
            "ON assinaturas_saas (promocao_codigo)"
        ))

        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS "
            "uq_assinaturas_saas_fundador_posicao_idx "
            "ON assinaturas_saas (fundador_posicao) "
            "WHERE fundador_posicao IS NOT NULL"
        ))

    print()
    print("[OK] Schema SaaS sincronizado.")


if __name__ == "__main__":
    main()
