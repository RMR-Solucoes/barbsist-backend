from sqlalchemy import inspect

from database import engine
from models import TokenRecuperacaoSenha


NOME_TABELA = "tokens_recuperacao_senha"


def executar_migracao():
    inspector = inspect(engine)

    if NOME_TABELA in inspector.get_table_names():
        print(
            f"A tabela '{NOME_TABELA}' já existe. "
            "Nenhuma alteração necessária."
        )
        return

    TokenRecuperacaoSenha.__table__.create(
        bind=engine,
        checkfirst=True,
    )

    inspector = inspect(engine)

    if NOME_TABELA not in inspector.get_table_names():
        raise RuntimeError(
            f"Não foi possível criar a tabela '{NOME_TABELA}'."
        )

    colunas = [
        coluna["name"]
        for coluna in inspector.get_columns(NOME_TABELA)
    ]

    print(f"Tabela '{NOME_TABELA}' criada com sucesso.")
    print("Colunas:", ", ".join(colunas))


if __name__ == "__main__":
    executar_migracao()