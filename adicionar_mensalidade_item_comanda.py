from sqlalchemy import inspect, text

from database import engine


COLUNAS = {
    "assinatura_id": "INTEGER NULL",
    "plano_id": "INTEGER NULL",
    "referencia_mes": "VARCHAR(100) NULL",
}


def executar():
    existentes = {
        coluna["name"]
        for coluna in inspect(engine).get_columns("itens_comanda")
    }

    with engine.begin() as conexao:
        for nome, tipo in COLUNAS.items():
            if nome not in existentes:
                conexao.execute(
                    text(f"ALTER TABLE itens_comanda ADD COLUMN {nome} {tipo}")
                )

        conexao.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_itens_comanda_assinatura_id "
                "ON itens_comanda (assinatura_id)"
            )
        )

    print("MIGRACAO_MENSALIDADE_ITEM_COMANDA_CONCLUIDA")


if __name__ == "__main__":
    executar()
