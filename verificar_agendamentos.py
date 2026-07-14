import sqlite3

conn = sqlite3.connect("barbearia.db")
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(agendamentos)")

for coluna in cursor.fetchall():
    print(coluna)

conn.close()