from sqlalchemy import inspect, text

from database import engine


COLUNAS = (
    (
        "catalogo_publico_ativo",
        {
            "sqlite": "BOOLEAN NOT NULL DEFAULT 0",
            "postgresql": "BOOLEAN NOT NULL DEFAULT FALSE",
        },
    ),
    (
        "latitude",
        {
            "sqlite": "FLOAT",
            "postgresql": "DOUBLE PRECISION",
        },
    ),
    (
        "longitude",
        {
            "sqlite": "FLOAT",
            "postgresql": "DOUBLE PRECISION",
        },
    ),
)


def migrar():
    insp = inspect(engine)

    if "barbearias" not in set(insp.get_table_names()):
        raise RuntimeError("Tabela barbearias nao encontrada.")

    existentes = {c["name"] for c in insp.get_columns("barbearias")}
    dialeto = engine.dialect.name

    if dialeto not in {"sqlite", "postgresql"}:
        raise RuntimeError(
            f"Dialeto nao suportado nesta migracao: {dialeto}"
        )

    with engine.begin() as conexao:
        for nome, definicoes in COLUNAS:
            if nome in existentes:
                print(f"JA_EXISTE={nome}")
                continue

            conexao.execute(
                text(
                    "ALTER TABLE barbearias "
                    f"ADD COLUMN {nome} {definicoes[dialeto]}"
                )
            )
            print(f"CRIADA={nome}")

    finais = {
        c["name"]
        for c in inspect(engine).get_columns("barbearias")
    }

    for nome, _ in COLUNAS:
        if nome not in finais:
            raise RuntimeError(
                f"Coluna nao encontrada apos migracao: {nome}"
            )

    with engine.connect() as conexao:
        total = conexao.execute(
            text("SELECT COUNT(*) FROM barbearias")
        ).scalar_one()

        catalogo_false = conexao.execute(
            text(
                "SELECT COUNT(*) FROM barbearias "
                "WHERE catalogo_publico_ativo = FALSE"
            )
        ).scalar_one()

        catalogo_true = conexao.execute(
            text(
                "SELECT COUNT(*) FROM barbearias "
                "WHERE catalogo_publico_ativo = TRUE"
            )
        ).scalar_one()

    print(f"DB_DIALECT={dialeto}")
    print(f"BARBEARIAS_TOTAL={total}")
    print(f"BARBEARIAS_CATALOGO_FALSE={catalogo_false}")
    print(f"BARBEARIAS_CATALOGO_TRUE={catalogo_true}")

    if catalogo_true != 0:
        raise RuntimeError(
            "Seguranca: alguma barbearia foi publicada automaticamente."
        )

    if catalogo_false != total:
        raise RuntimeError(
            "Seguranca: nem todas as barbearias existentes ficaram opt-out."
        )

    print("BARBEARIAS_EXISTENTES_OPT_OUT=OK")
    print("MIGRACAO_P2A_CATALOGO_PUBLICO=OK")


if __name__ == "__main__":
    migrar()
