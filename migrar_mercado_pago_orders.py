"""
Migração incremental Mercado Pago: Payments API -> Orders API.

Objetivo:
- adicionar order_id em mercado_pago_cobrancas;
- preservar payment_id para rastreabilidade da transação interna da Order;
- criar índice/garantia de unicidade para order_id quando preenchido;
- não alterar cobranças históricas baseadas na Payments API.

Faça backup do banco antes de executar.
"""
from sqlalchemy import inspect, text
from database import engine


def _sqlite_migrar():
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("mercado_pago_cobrancas")}
    with engine.begin() as conn:
        if "order_id" not in cols:
            conn.execute(text("ALTER TABLE mercado_pago_cobrancas ADD COLUMN order_id VARCHAR NULL"))
            print("[CRIADA] coluna: order_id")
        else:
            print("[OK] coluna order_id já existe")
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_mp_cobranca_order_id_idx "
            "ON mercado_pago_cobrancas (order_id) WHERE order_id IS NOT NULL"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_mercado_pago_cobrancas_order_id "
            "ON mercado_pago_cobrancas (order_id)"
        ))
    print("[OK] SQLite: suporte à Orders API disponível.")


def _postgres_migrar():
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("mercado_pago_cobrancas")}
    with engine.begin() as conn:
        if "order_id" not in cols:
            conn.execute(text("ALTER TABLE mercado_pago_cobrancas ADD COLUMN order_id VARCHAR NULL"))
            print("[CRIADA] coluna: order_id")
        else:
            print("[OK] coluna order_id já existe")
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_mp_cobranca_order_id_idx "
            "ON mercado_pago_cobrancas (order_id) WHERE order_id IS NOT NULL"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_mercado_pago_cobrancas_order_id "
            "ON mercado_pago_cobrancas (order_id)"
        ))
    print("[OK] PostgreSQL: suporte à Orders API disponível.")


def main():
    insp = inspect(engine)
    if "mercado_pago_cobrancas" not in insp.get_table_names():
        raise RuntimeError("Tabela mercado_pago_cobrancas não encontrada.")
    dialect = engine.dialect.name
    if dialect == "sqlite":
        _sqlite_migrar()
    elif dialect in {"postgresql", "postgres"}:
        _postgres_migrar()
    else:
        raise RuntimeError(f"Banco não suportado automaticamente: {dialect}")
    print("[OK] Migração Mercado Pago Orders concluída.")


if __name__ == "__main__":
    main()
