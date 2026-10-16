"""
Cria as estruturas independentes do teste
gratuito SaaS e seus claims antifraude.

IMPORTANTE:
Este arquivo deve ser executado somente
em etapa de migracao controlada.

A simples importacao nao altera o banco.
"""

from database import engine
import models


def executar():
    models.TesteGratuitoSaaS.__table__.create(
        bind=engine,
        checkfirst=True,
    )

    models.TesteGratuitoSaaSClaim.__table__.create(
        bind=engine,
        checkfirst=True,
    )

    print(
        "TABELA_TESTES_GRATUITOS_SAAS=OK"
    )

    print(
        "TABELA_TESTE_GRATUITO_SAAS_CLAIMS=OK"
    )


if __name__ == "__main__":
    executar()
