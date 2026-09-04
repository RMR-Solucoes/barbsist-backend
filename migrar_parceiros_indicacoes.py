import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

DB = Path("barbearia.db")

if not DB.exists():
    raise SystemExit("[ERRO] barbearia.db nao encontrado.")

backup = DB.with_name(
    "barbearia_backup_antes_parceiros_" +
    datetime.now().strftime("%Y%m%d_%H%M%S") +
    ".db"
)

shutil.copy2(DB, backup)

print("[OK] Backup criado:", backup)

con = sqlite3.connect(DB)
cur = con.cursor()

cur.executescript("""
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS parceiros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo VARCHAR NOT NULL,
    nome VARCHAR NOT NULL,
    email VARCHAR NOT NULL UNIQUE,
    telefone VARCHAR,
    barbearia_id INTEGER,
    codigo_ref VARCHAR NOT NULL UNIQUE,
    tipo_beneficio VARCHAR NOT NULL DEFAULT 'COMISSAO',
    regra_beneficio VARCHAR NOT NULL DEFAULT 'PERCENTUAL',
    percentual_beneficio FLOAT,
    valor_fixo_beneficio FLOAT,
    ativo BOOLEAN NOT NULL DEFAULT 1,
    observacao TEXT,
    criado_em DATETIME NOT NULL,
    atualizado_em DATETIME NOT NULL,
    FOREIGN KEY(barbearia_id)
        REFERENCES barbearias(id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS ix_parceiros_id
    ON parceiros(id);

CREATE INDEX IF NOT EXISTS ix_parceiros_tipo
    ON parceiros(tipo);

CREATE INDEX IF NOT EXISTS ix_parceiros_email
    ON parceiros(email);

CREATE INDEX IF NOT EXISTS ix_parceiros_barbearia_id
    ON parceiros(barbearia_id);

CREATE INDEX IF NOT EXISTS ix_parceiros_codigo_ref
    ON parceiros(codigo_ref);


CREATE TABLE IF NOT EXISTS indicacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parceiro_id INTEGER NOT NULL,
    codigo_ref VARCHAR NOT NULL,
    barbearia_indicada_id INTEGER NOT NULL UNIQUE,
    assinatura_saas_id INTEGER,
    status VARCHAR NOT NULL DEFAULT 'CADASTRADA',
    data_cadastro DATETIME NOT NULL,
    data_conversao DATETIME,
    observacao TEXT,
    FOREIGN KEY(parceiro_id)
        REFERENCES parceiros(id)
        ON DELETE RESTRICT,
    FOREIGN KEY(barbearia_indicada_id)
        REFERENCES barbearias(id)
        ON DELETE RESTRICT,
    FOREIGN KEY(assinatura_saas_id)
        REFERENCES assinaturas_saas(id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS ix_indicacoes_id
    ON indicacoes(id);

CREATE INDEX IF NOT EXISTS ix_indicacoes_parceiro_id
    ON indicacoes(parceiro_id);

CREATE INDEX IF NOT EXISTS ix_indicacoes_codigo_ref
    ON indicacoes(codigo_ref);

CREATE INDEX IF NOT EXISTS ix_indicacoes_barbearia_indicada_id
    ON indicacoes(barbearia_indicada_id);

CREATE INDEX IF NOT EXISTS ix_indicacoes_assinatura_saas_id
    ON indicacoes(assinatura_saas_id);

CREATE INDEX IF NOT EXISTS ix_indicacoes_status
    ON indicacoes(status);


CREATE TABLE IF NOT EXISTS comissoes_parceiros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parceiro_id INTEGER NOT NULL,
    indicacao_id INTEGER NOT NULL,
    pagamento_saas_id INTEGER NOT NULL,
    valor_base FLOAT NOT NULL,
    percentual FLOAT,
    valor_comissao FLOAT NOT NULL,
    status VARCHAR NOT NULL DEFAULT 'PENDENTE',
    data_geracao DATETIME NOT NULL,
    data_liberacao DATETIME,
    data_pagamento DATETIME,
    observacao TEXT,
    FOREIGN KEY(parceiro_id)
        REFERENCES parceiros(id)
        ON DELETE RESTRICT,
    FOREIGN KEY(indicacao_id)
        REFERENCES indicacoes(id)
        ON DELETE RESTRICT,
    FOREIGN KEY(pagamento_saas_id)
        REFERENCES pagamentos_saas(id)
        ON DELETE RESTRICT,
    UNIQUE(indicacao_id, pagamento_saas_id)
);

CREATE INDEX IF NOT EXISTS ix_comissoes_parceiros_id
    ON comissoes_parceiros(id);

CREATE INDEX IF NOT EXISTS ix_comissoes_parceiros_parceiro_id
    ON comissoes_parceiros(parceiro_id);

CREATE INDEX IF NOT EXISTS ix_comissoes_parceiros_indicacao_id
    ON comissoes_parceiros(indicacao_id);

CREATE INDEX IF NOT EXISTS ix_comissoes_parceiros_pagamento_saas_id
    ON comissoes_parceiros(pagamento_saas_id);

CREATE INDEX IF NOT EXISTS ix_comissoes_parceiros_status
    ON comissoes_parceiros(status);


CREATE TABLE IF NOT EXISTS creditos_barbearia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parceiro_id INTEGER NOT NULL,
    barbearia_parceira_id INTEGER NOT NULL,
    indicacao_id INTEGER NOT NULL,
    pagamento_saas_id INTEGER NOT NULL,
    valor_base FLOAT NOT NULL,
    percentual FLOAT,
    valor_credito FLOAT NOT NULL,
    status VARCHAR NOT NULL DEFAULT 'DISPONIVEL',
    referencia_mensalidade VARCHAR,
    data_geracao DATETIME NOT NULL,
    data_aplicacao DATETIME,
    observacao TEXT,
    FOREIGN KEY(parceiro_id)
        REFERENCES parceiros(id)
        ON DELETE RESTRICT,
    FOREIGN KEY(barbearia_parceira_id)
        REFERENCES barbearias(id)
        ON DELETE RESTRICT,
    FOREIGN KEY(indicacao_id)
        REFERENCES indicacoes(id)
        ON DELETE RESTRICT,
    FOREIGN KEY(pagamento_saas_id)
        REFERENCES pagamentos_saas(id)
        ON DELETE RESTRICT,
    UNIQUE(indicacao_id, pagamento_saas_id)
);

CREATE INDEX IF NOT EXISTS ix_creditos_barbearia_id
    ON creditos_barbearia(id);

CREATE INDEX IF NOT EXISTS ix_creditos_barbearia_parceiro_id
    ON creditos_barbearia(parceiro_id);

CREATE INDEX IF NOT EXISTS ix_creditos_barbearia_barbearia_parceira_id
    ON creditos_barbearia(barbearia_parceira_id);

CREATE INDEX IF NOT EXISTS ix_creditos_barbearia_indicacao_id
    ON creditos_barbearia(indicacao_id);

CREATE INDEX IF NOT EXISTS ix_creditos_barbearia_pagamento_saas_id
    ON creditos_barbearia(pagamento_saas_id);

CREATE INDEX IF NOT EXISTS ix_creditos_barbearia_status
    ON creditos_barbearia(status);
""")

con.commit()

tabelas = [
    "parceiros",
    "indicacoes",
    "comissoes_parceiros",
    "creditos_barbearia",
]

print("\n===== VALIDACAO =====")

for tabela in tabelas:
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (tabela,),
    )
    existe = cur.fetchone() is not None
    print(f"{tabela:<24}", "OK" if existe else "ERRO")

con.close()

print("\n[OK] Migracao Parceiros/Indicacoes concluida.")
print("[OK] Nenhuma tabela existente foi alterada.")
