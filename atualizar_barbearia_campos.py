from database import engine

with engine.connect() as conn:
    conn.exec_driver_sql(
        "ALTER TABLE barbearias ADD COLUMN slogan TEXT"
    )

    conn.exec_driver_sql(
        "ALTER TABLE barbearias ADD COLUMN imagem_capa_url TEXT"
    )

    conn.commit()

print("Campos adicionados com sucesso.")