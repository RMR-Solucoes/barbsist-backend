import sqlite3

conn = sqlite3.connect("barbearia.db")
cursor = conn.cursor()

# =====================================
# Adiciona novas colunas
# =====================================

comandos = [

    """
    ALTER TABLE assinaturas_clientes
    ADD COLUMN data_ultimo_pagamento DATETIME
    """,

    """
    ALTER TABLE assinaturas_clientes
    ADD COLUMN data_proximo_vencimento DATETIME
    """,

    """
    ALTER TABLE assinaturas_clientes
    ADD COLUMN dias_tolerancia INTEGER DEFAULT 5
    """,

    """
    ALTER TABLE assinaturas_clientes
    ADD COLUMN valor_mensal REAL DEFAULT 0
    """,

    """
    ALTER TABLE assinaturas_clientes
    ADD COLUMN status_pagamento TEXT DEFAULT 'PAGO'
    """
]

for comando in comandos:
    try:
        cursor.execute(comando)
        print("✔", comando.strip().split("\n")[0])
    except sqlite3.OperationalError:
        pass


# =====================================
# Migração dos STATUS
# =====================================

cursor.execute("""
UPDATE assinaturas_clientes
SET status =
CASE
    WHEN LOWER(status)='ativo' THEN 'ATIVO'
    WHEN LOWER(status)='vencido' THEN 'VENCIDO'
    WHEN LOWER(status)='suspenso' THEN 'SUSPENSO'
    WHEN LOWER(status)='cancelado' THEN 'CANCELADO'
    WHEN LOWER(status)='inativo' THEN 'INATIVO'
    ELSE status
END
""")

cursor.execute("""
UPDATE assinaturas_clientes
SET status_pagamento =
CASE
    WHEN LOWER(status_pagamento)='pago' THEN 'PAGO'
    WHEN LOWER(status_pagamento)='vencido' THEN 'VENCIDO'
    WHEN LOWER(status_pagamento)='pendente_pagamento' THEN 'PENDENTE_PAGAMENTO'
    WHEN LOWER(status_pagamento)='inadimplente' THEN 'INADIMPLENTE'
    ELSE status_pagamento
END
""")

conn.commit()
conn.close()

print("===================================")
print("Banco atualizado com sucesso.")
print("===================================")