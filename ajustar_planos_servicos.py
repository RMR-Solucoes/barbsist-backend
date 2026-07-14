import sqlite3

DATABASE = "barbearia.db"

conn = sqlite3.connect(DATABASE)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS planos_servicos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    plano_id INTEGER NOT NULL,
    servico_id INTEGER NOT NULL,

    FOREIGN KEY (plano_id)
        REFERENCES planos(id),

    FOREIGN KEY (servico_id)
        REFERENCES servicos(id)
)
""")

conn.commit()
conn.close()

print("Tabela planos_servicos criada com sucesso.")