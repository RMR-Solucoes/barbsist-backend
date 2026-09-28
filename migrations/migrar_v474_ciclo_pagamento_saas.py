"""
BarbSist - Migracao V4.7.4
Adiciona os limites explicitos do ciclo financeiro ao PagamentoSaaS.

Colunas:
- ciclo_inicio
- ciclo_fim

A migracao e idempotente.
Nao realiza backfill de pagamentos historicos.
"""

from sqlalchemy import inspect, text

from database import engine


TABELA = "pagamentos_saas"


def migrar():
    inspector = inspect(engine)

    tabelas = inspector.get_table_names()

    if TABELA not in tabelas:
        raise RuntimeError(
            f"Tabela obrigatoria nao encontrada: {TABELA}"
        )

    colunas_antes = {
        coluna["name"]
        for coluna in inspector.get_columns(TABELA)
    }

    print(f"COLUNAS_ANTES={len(colunas_antes)}")
    print(
        "CICLO_INICIO_ANTES="
        + str("ciclo_inicio" in colunas_antes)
    )
    print(
        "CICLO_FIM_ANTES="
        + str("ciclo_fim" in colunas_antes)
    )

    with engine.begin() as conn:
        conn.execute(text("""
            ALTER TABLE pagamentos_saas
            ADD COLUMN IF NOT EXISTS ciclo_inicio TIMESTAMP NULL
        """))

        conn.execute(text("""
            ALTER TABLE pagamentos_saas
            ADD COLUMN IF NOT EXISTS ciclo_fim TIMESTAMP NULL
        """))

    inspector = inspect(engine)

    colunas_depois = {
        coluna["name"]: coluna
        for coluna in inspector.get_columns(TABELA)
    }

    if "ciclo_inicio" not in colunas_depois:
        raise RuntimeError("CICLO_INICIO_NAO_CRIADO")

    if "ciclo_fim" not in colunas_depois:
        raise RuntimeError("CICLO_FIM_NAO_CRIADO")

    print(f"COLUNAS_DEPOIS={len(colunas_depois)}")
    print("CICLO_INICIO_DEPOIS=True")
    print("CICLO_FIM_DEPOIS=True")
    print("MIGRACAO_V474=OK")


if __name__ == "__main__":
    migrar()
