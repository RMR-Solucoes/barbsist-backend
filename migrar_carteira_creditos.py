import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

DB = Path("barbearia.db")

if not DB.exists():
    raise SystemExit("[ERRO] barbearia.db nao encontrado.")

backup = DB.with_name(
    "barbearia_backup_antes_carteira_creditos_" +
    datetime.now().strftime("%Y%m%d_%H%M%S") +
    ".db"
)

shutil.copy2(DB, backup)

print("[OK] Backup criado:", backup)

con = sqlite3.connect(DB)
cur = con.cursor()

cur.executescript("""
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS resgates_creditos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    parceiro_id INTEGER NOT NULL,
    barbearia_id INTEGER NOT NULL,

    assinatura_saas_id INTEGER,
    pagamento_saas_id INTEGER,

    tipo_aplicacao VARCHAR NOT NULL,

    valor_solicitado FLOAT NOT NULL,
    valor_aplicado FLOAT NOT NULL DEFAULT 0,

    status VARCHAR NOT NULL DEFAULT 'SOLICITADO',

    solicitado_em DATETIME NOT NULL,
    aprovado_em DATETIME,
    aplicado_em DATETIME,

    observacao TEXT,

    FOREIGN KEY(parceiro_id)
        REFERENCES parceiros(id)
        ON DELETE RESTRICT,

    FOREIGN KEY(barbearia_id)
        REFERENCES barbearias(id)
        ON DELETE RESTRICT,

    FOREIGN KEY(assinatura_saas_id)
        REFERENCES assinaturas_saas(id)
        ON DELETE RESTRICT,

    FOREIGN KEY(pagamento_saas_id)
        REFERENCES pagamentos_saas(id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS ix_resgates_creditos_id
    ON resgates_creditos(id);

CREATE INDEX IF NOT EXISTS ix_resgates_creditos_parceiro_id
    ON resgates_creditos(parceiro_id);

CREATE INDEX IF NOT EXISTS ix_resgates_creditos_barbearia_id
    ON resgates_creditos(barbearia_id);

CREATE INDEX IF NOT EXISTS ix_resgates_creditos_assinatura_saas_id
    ON resgates_creditos(assinatura_saas_id);

CREATE INDEX IF NOT EXISTS ix_resgates_creditos_pagamento_saas_id
    ON resgates_creditos(pagamento_saas_id);

CREATE INDEX IF NOT EXISTS ix_resgates_creditos_status
    ON resgates_creditos(status);


CREATE TABLE IF NOT EXISTS resgate_credito_itens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    resgate_id INTEGER NOT NULL,
    credito_id INTEGER NOT NULL,

    valor_utilizado FLOAT NOT NULL,

    criado_em DATETIME NOT NULL,

    FOREIGN KEY(resgate_id)
        REFERENCES resgates_creditos(id)
        ON DELETE RESTRICT,

    FOREIGN KEY(credito_id)
        REFERENCES creditos_barbearia(id)
        ON DELETE RESTRICT,

    UNIQUE(resgate_id, credito_id)
);

CREATE INDEX IF NOT EXISTS ix_resgate_credito_itens_id
    ON resgate_credito_itens(id);

CREATE INDEX IF NOT EXISTS ix_resgate_credito_itens_resgate_id
    ON resgate_credito_itens(resgate_id);

CREATE INDEX IF NOT EXISTS ix_resgate_credito_itens_credito_id
    ON resgate_credito_itens(credito_id);
""")

con.commit()

print("\n===== VALIDACAO =====")

for tabela in [
    "resgates_creditos",
    "resgate_credito_itens",
]:
    cur.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name=?",
        (tabela,),
    )

    existe = cur.fetchone() is not None

    print(
        f"{tabela:<24}",
        "OK" if existe else "ERRO"
    )

con.close()

print("\n[OK] Migracao da carteira de creditos concluida.")
print("[OK] Tabelas anteriores preservadas.")
