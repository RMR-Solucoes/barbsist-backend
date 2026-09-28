"""
BarbSist - Migracao V4.7.2D-R1

Adiciona campos financeiros opcionais ao cadastro de barbeiros.
Migracao idempotente e preserva os registros existentes.
"""

from sqlalchemy import inspect, text
from database import engine


COLUNAS = {
    "valor_aluguel_cadeira": "FLOAT",
    "periodicidade_aluguel": "VARCHAR",
    "dia_vencimento_aluguel": "INTEGER",
    "valor_diaria": "FLOAT",
}


def executar_migracao():
    inspector = inspect(engine)

    if "barbeiros" not in inspector.get_table_names():
        raise RuntimeError("Tabela barbeiros ausente")

    existentes = {
        coluna["name"]
        for coluna in inspector.get_columns("barbeiros")
    }

    adicionadas = []
    ja_existentes = []

    with engine.begin() as conexao:
        for nome, tipo in COLUNAS.items():
            if nome in existentes:
                ja_existentes.append(nome)
                print(f"JA_EXISTE={nome}")
                continue

            conexao.execute(
                text(f"ALTER TABLE barbeiros ADD COLUMN {nome} {tipo}")
            )

            adicionadas.append(nome)
            print(f"ADICIONADA={nome}")

    inspector_final = inspect(engine)

    finais = {
        coluna["name"]
        for coluna in inspector_final.get_columns("barbeiros")
    }

    faltantes = [
        nome for nome in COLUNAS
        if nome not in finais
    ]

    if faltantes:
        raise RuntimeError(
            "Migracao incompleta. Colunas faltantes: "
            + ", ".join(faltantes)
        )

    print(f"TOTAL_ADICIONADAS={len(adicionadas)}")
    print(f"TOTAL_JA_EXISTENTES={len(ja_existentes)}")
    print("V472D_R1_MIGRACAO_OK")


if __name__ == "__main__":
    executar_migracao()
