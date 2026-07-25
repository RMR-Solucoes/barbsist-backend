from sqlalchemy import inspect, text

from database import engine


TABELA = "barbearias"

NOVAS_COLUNAS = {
    "responsavel": "TEXT",
    "email": "TEXT",
    "telefone": "TEXT",
    "cnpj": "TEXT",
    "cidade": "TEXT",
    "estado": "TEXT",
    "cep": "TEXT",
}


def obter_colunas_existentes() -> set[str]:
    inspector = inspect(engine)

    tabelas = inspector.get_table_names()

    if TABELA not in tabelas:
        raise RuntimeError(
            f"A tabela '{TABELA}' não foi encontrada no banco."
        )

    return {
        coluna["name"]
        for coluna in inspector.get_columns(TABELA)
    }


def executar_migracao() -> None:
    colunas_existentes = obter_colunas_existentes()
    colunas_adicionadas = []
    colunas_ignoradas = []

    with engine.begin() as conexao:
        for nome_coluna, tipo_sql in NOVAS_COLUNAS.items():
            if nome_coluna in colunas_existentes:
                colunas_ignoradas.append(nome_coluna)
                continue

            comando = text(
                f"ALTER TABLE {TABELA} "
                f"ADD COLUMN {nome_coluna} {tipo_sql}"
            )

            conexao.execute(comando)
            colunas_adicionadas.append(nome_coluna)

    print("\nMigração concluída.")

    if colunas_adicionadas:
        print(
            "Colunas adicionadas: "
            + ", ".join(colunas_adicionadas)
        )
    else:
        print("Nenhuma coluna nova precisou ser adicionada.")

    if colunas_ignoradas:
        print(
            "Colunas que já existiam: "
            + ", ".join(colunas_ignoradas)
        )


if __name__ == "__main__":
    executar_migracao()