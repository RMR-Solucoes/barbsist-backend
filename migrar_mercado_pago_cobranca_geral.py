"""
Migração incremental para generalizar MercadoPagoCobranca.

Objetivo:
- permitir cobranças originadas por PLANO_CLIENTE, COMANDA e VENDA;
- preservar cobranças existentes de assinaturas;
- tornar assinatura_id opcional;
- preencher origem_negocio/origem_id nas cobranças antigas.

Faça backup do banco antes de executar.
"""
from sqlalchemy import inspect, text
from database import engine


def _sqlite_recriar_tabela():
    insp = inspect(engine)
    cols = {c["name"]: c for c in insp.get_columns("mercado_pago_cobrancas")}
    ja_tem_origem = "origem_negocio" in cols and "origem_id" in cols
    assinatura_nullable = bool(cols.get("assinatura_id", {}).get("nullable", False))
    if ja_tem_origem and assinatura_nullable:
        with engine.begin() as conn:
            conn.execute(text(
                "UPDATE mercado_pago_cobrancas "
                "SET origem_negocio='PLANO_CLIENTE' "
                "WHERE origem_negocio IS NULL OR TRIM(origem_negocio)=''"
            ))
            conn.execute(text(
                "UPDATE mercado_pago_cobrancas "
                "SET origem_id=assinatura_id "
                "WHERE origem_id IS NULL AND assinatura_id IS NOT NULL"
            ))
        print("[OK] SQLite: estrutura genérica já existente; dados normalizados.")
        return

    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.execute(text("""
            CREATE TABLE mercado_pago_cobrancas_new (
                id INTEGER PRIMARY KEY,
                barbearia_id INTEGER NOT NULL REFERENCES barbearias(id),
                assinatura_id INTEGER NULL REFERENCES assinaturas_clientes(id),
                origem_negocio VARCHAR NOT NULL DEFAULT 'PLANO_CLIENTE',
                origem_id INTEGER NULL,
                payment_id VARCHAR NULL,
                idempotency_key VARCHAR NOT NULL,
                external_reference VARCHAR NOT NULL,
                valor FLOAT NOT NULL,
                tipo_pagamento VARCHAR NOT NULL DEFAULT 'PIX',
                installments INTEGER NOT NULL DEFAULT 1,
                valor_parcela FLOAT NULL,
                payment_method_id VARCHAR NULL,
                payment_type_id VARCHAR NULL,
                status VARCHAR NOT NULL DEFAULT 'pending',
                status_detail VARCHAR NULL,
                payer_email VARCHAR NULL,
                qr_code VARCHAR NULL,
                qr_code_base64 VARCHAR NULL,
                ticket_url VARCHAR NULL,
                processado BOOLEAN NOT NULL DEFAULT 0,
                processado_em DATETIME NULL,
                data_criacao DATETIME NOT NULL,
                data_atualizacao DATETIME NOT NULL,
                CONSTRAINT uq_mp_cobranca_idempotency UNIQUE (idempotency_key),
                CONSTRAINT uq_mp_cobranca_external_reference UNIQUE (external_reference),
                CONSTRAINT uq_mp_cobranca_payment_id UNIQUE (payment_id)
            )
        """))

        origem_expr = "origem_negocio" if "origem_negocio" in cols else "'PLANO_CLIENTE'"
        origem_id_expr = "origem_id" if "origem_id" in cols else "assinatura_id"
        conn.execute(text(f"""
            INSERT INTO mercado_pago_cobrancas_new (
                id, barbearia_id, assinatura_id, origem_negocio, origem_id,
                payment_id, idempotency_key, external_reference, valor,
                tipo_pagamento, installments, valor_parcela, payment_method_id,
                payment_type_id, status, status_detail, payer_email, qr_code,
                qr_code_base64, ticket_url, processado, processado_em,
                data_criacao, data_atualizacao
            )
            SELECT
                id, barbearia_id, assinatura_id,
                COALESCE({origem_expr}, 'PLANO_CLIENTE'),
                COALESCE({origem_id_expr}, assinatura_id),
                payment_id, idempotency_key, external_reference, valor,
                tipo_pagamento, installments, valor_parcela, payment_method_id,
                payment_type_id, status, status_detail, payer_email, qr_code,
                qr_code_base64, ticket_url, processado, processado_em,
                data_criacao, data_atualizacao
            FROM mercado_pago_cobrancas
        """))
        conn.execute(text("DROP TABLE mercado_pago_cobrancas"))
        conn.execute(text("ALTER TABLE mercado_pago_cobrancas_new RENAME TO mercado_pago_cobrancas"))
        for stmt in [
            "CREATE INDEX IF NOT EXISTS ix_mercado_pago_cobrancas_id ON mercado_pago_cobrancas (id)",
            "CREATE INDEX IF NOT EXISTS ix_mercado_pago_cobrancas_barbearia_id ON mercado_pago_cobrancas (barbearia_id)",
            "CREATE INDEX IF NOT EXISTS ix_mercado_pago_cobrancas_assinatura_id ON mercado_pago_cobrancas (assinatura_id)",
            "CREATE INDEX IF NOT EXISTS ix_mercado_pago_cobrancas_origem_negocio ON mercado_pago_cobrancas (origem_negocio)",
            "CREATE INDEX IF NOT EXISTS ix_mercado_pago_cobrancas_origem_id ON mercado_pago_cobrancas (origem_id)",
            "CREATE INDEX IF NOT EXISTS ix_mercado_pago_cobrancas_payment_id ON mercado_pago_cobrancas (payment_id)",
            "CREATE INDEX IF NOT EXISTS ix_mercado_pago_cobrancas_idempotency_key ON mercado_pago_cobrancas (idempotency_key)",
            "CREATE INDEX IF NOT EXISTS ix_mercado_pago_cobrancas_external_reference ON mercado_pago_cobrancas (external_reference)",
            "CREATE INDEX IF NOT EXISTS ix_mercado_pago_cobrancas_status ON mercado_pago_cobrancas (status)",
        ]:
            conn.execute(text(stmt))
        conn.execute(text("PRAGMA foreign_keys=ON"))
    print("[OK] SQLite: mercado_pago_cobrancas generalizada.")


def _postgres_migrar():
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("mercado_pago_cobrancas")}
    with engine.begin() as conn:
        if "origem_negocio" not in cols:
            conn.execute(text("ALTER TABLE mercado_pago_cobrancas ADD COLUMN origem_negocio VARCHAR NOT NULL DEFAULT 'PLANO_CLIENTE'"))
            print("[CRIADA] origem_negocio")
        if "origem_id" not in cols:
            conn.execute(text("ALTER TABLE mercado_pago_cobrancas ADD COLUMN origem_id INTEGER NULL"))
            print("[CRIADA] origem_id")
        conn.execute(text("ALTER TABLE mercado_pago_cobrancas ALTER COLUMN assinatura_id DROP NOT NULL"))
        conn.execute(text("UPDATE mercado_pago_cobrancas SET origem_negocio='PLANO_CLIENTE' WHERE origem_negocio IS NULL OR BTRIM(origem_negocio)=''"))
        conn.execute(text("UPDATE mercado_pago_cobrancas SET origem_id=assinatura_id WHERE origem_id IS NULL AND assinatura_id IS NOT NULL"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_mercado_pago_cobrancas_origem_negocio ON mercado_pago_cobrancas (origem_negocio)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_mercado_pago_cobrancas_origem_id ON mercado_pago_cobrancas (origem_id)"))
    print("[OK] PostgreSQL: mercado_pago_cobrancas generalizada.")


def main():
    insp = inspect(engine)
    if "mercado_pago_cobrancas" not in insp.get_table_names():
        raise RuntimeError("Tabela mercado_pago_cobrancas não encontrada.")
    dialect = engine.dialect.name
    if dialect == "sqlite":
        _sqlite_recriar_tabela()
    elif dialect in {"postgresql", "postgres"}:
        _postgres_migrar()
    else:
        raise RuntimeError(f"Banco não suportado automaticamente: {dialect}")
    print("[OK] Migração Mercado Pago cobrança geral concluída.")


if __name__ == "__main__":
    main()
