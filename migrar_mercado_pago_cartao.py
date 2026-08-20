r"""Adiciona suporte a preços PIX/cartão e parcelamento Mercado Pago.

Execute uma única vez no ambiente local antes de testar o novo endpoint de cartão:
    python .\migrar_mercado_pago_cartao.py

O script é idempotente: só adiciona colunas ausentes.
"""
from sqlalchemy import inspect
from database import engine


def add_column(conn, table: str, column: str, ddl_type: str, default_sql: str | None = None):
    inspector = inspect(conn)
    existing = {c["name"] for c in inspector.get_columns(table)}
    if column in existing:
        print(f"OK   {table}.{column} já existe")
        return
    default = f" DEFAULT {default_sql}" if default_sql is not None else ""
    conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}{default}")
    print(f"ADD  {table}.{column}")


def main():
    with engine.begin() as conn:
        tables = set(inspect(conn).get_table_names())
        if "planos" not in tables:
            raise RuntimeError("Tabela 'planos' não encontrada. Verifique DATABASE_URL.")
        if "mercado_pago_cobrancas" not in tables:
            raise RuntimeError("Tabela 'mercado_pago_cobrancas' não encontrada. Inicie o backend ajustado uma vez antes da migração.")

        add_column(conn, "planos", "valor_pix", "FLOAT")
        add_column(conn, "planos", "valor_cartao", "FLOAT")
        add_column(conn, "planos", "max_parcelas_cartao", "INTEGER", "1")

        add_column(conn, "mercado_pago_cobrancas", "tipo_pagamento", "VARCHAR", "'PIX'")
        add_column(conn, "mercado_pago_cobrancas", "installments", "INTEGER", "1")
        add_column(conn, "mercado_pago_cobrancas", "valor_parcela", "FLOAT")
        add_column(conn, "mercado_pago_cobrancas", "payment_method_id", "VARCHAR")
        add_column(conn, "mercado_pago_cobrancas", "payment_type_id", "VARCHAR")
        add_column(conn, "mercado_pago_cobrancas", "status_detail", "VARCHAR")

    print("\nMIGRAÇÃO MERCADO PAGO CARTÃO CONCLUÍDA")


if __name__ == "__main__":
    main()
