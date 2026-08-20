r"""Migração incremental do Mercado Pago OAuth por barbearia.

Uso local:
    python .\migrar_mercado_pago_oauth.py

Antes de executar em produção, faça backup do banco.
"""
from sqlalchemy import inspect, text

from database import engine
import models


COLUNAS = {
    "refresh_token_encrypted": "VARCHAR",
    "mercado_pago_user_id": "VARCHAR",
    "token_type": "VARCHAR",
    "scope": "VARCHAR",
    "token_expires_at": "DATETIME",
    "oauth_status": "VARCHAR",
    "conectado_em": "DATETIME",
    "ultima_renovacao_em": "DATETIME",
}


def tipo_datetime():
    return "TIMESTAMP" if engine.dialect.name.startswith("postgres") else "DATETIME"


def main():
    insp = inspect(engine)
    tabelas = set(insp.get_table_names())
    if "mercado_pago_configuracoes" not in tabelas:
        models.MercadoPagoConfiguracao.__table__.create(bind=engine, checkfirst=True)

    insp = inspect(engine)
    existentes = {c["name"] for c in insp.get_columns("mercado_pago_configuracoes")}

    with engine.begin() as conn:
        for nome, tipo in COLUNAS.items():
            if nome in existentes:
                print(f"[OK] coluna já existe: {nome}")
                continue
            tipo_sql = tipo_datetime() if tipo == "DATETIME" else tipo
            conn.execute(text(
                f"ALTER TABLE mercado_pago_configuracoes ADD COLUMN {nome} {tipo_sql}"
            ))
            print(f"[CRIADA] coluna: {nome}")

        conn.execute(text(
            "UPDATE mercado_pago_configuracoes "
            "SET oauth_status = CASE "
            "WHEN access_token_encrypted IS NOT NULL THEN 'MANUAL' "
            "ELSE 'NAO_CONECTADO' END "
            "WHERE oauth_status IS NULL"
        ))

    models.MercadoPagoOAuthState.__table__.create(bind=engine, checkfirst=True)
    print("[OK] tabela mercado_pago_oauth_states disponível")
    print("MIGRAÇÃO MERCADO PAGO OAUTH CONCLUÍDA")


if __name__ == "__main__":
    main()
