"""Adiciona a regra de vencimento fixo e primeiro ciclo proporcional.

É idempotente e preserva todas as assinaturas existentes.
"""
from sqlalchemy import inspect, text

from database import engine


COLUNAS = {
    "dia_vencimento": "INTEGER NULL",
    "fator_primeiro_ciclo": "FLOAT NULL",
    "valor_proxima_cobranca": "FLOAT NULL",
    "usos_proximo_ciclo": "INTEGER NULL",
    "primeiro_ciclo_processado": "BOOLEAN NOT NULL DEFAULT FALSE",
}


def main():
    inspetor = inspect(engine)
    if "assinaturas_clientes" not in inspetor.get_table_names():
        raise RuntimeError("Tabela assinaturas_clientes não encontrada.")

    existentes = {
        coluna["name"]
        for coluna in inspetor.get_columns("assinaturas_clientes")
    }

    with engine.begin() as conexao:
        for nome, definicao in COLUNAS.items():
            if nome not in existentes:
                conexao.execute(text(
                    f"ALTER TABLE assinaturas_clientes ADD COLUMN {nome} {definicao}"
                ))
                print(f"CRIADA: {nome}")
            else:
                print(f"JÁ EXISTE: {nome}")

        # Tudo o que existia antes da migração continua no fluxo antigo.
        conexao.execute(text("""
            UPDATE assinaturas_clientes
               SET primeiro_ciclo_processado = TRUE
             WHERE primeiro_ciclo_processado IS NULL
                OR dia_vencimento IS NULL
        """))

    print("MIGRACAO_VENCIMENTO_PROPORCIONAL_OK")


if __name__ == "__main__":
    main()
