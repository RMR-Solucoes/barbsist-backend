import sqlite3

conn = sqlite3.connect("barbearia.db")
cursor = conn.cursor()

try:
    cursor.execute("""
        ALTER TABLE agendamentos
        ADD COLUMN origem TEXT DEFAULT 'INTERNO'
    """)

    conn.commit()
    print("✅ Coluna origem criada com sucesso.")

except Exception as e:
    print("⚠️", e)

finally:
    conn.close()