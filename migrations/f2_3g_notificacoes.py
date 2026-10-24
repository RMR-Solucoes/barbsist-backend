"""F2.3G - Migracao controlada de notificacoes internas.

Nao cria engine, nao acessa variaveis de ambiente e nao executa
automaticamente. Recebe conexao SQLAlchemy explicita.
"""

from sqlalchemy import inspect
from notificacoes.modelo import NotificacaoInterna


def aplicar_migracao(conexao):
    """Cria a tabela e seus indices em uma transacao externa.

    A conexao deve ser fornecida pelo executor da migracao.
    Nao confirma nem encerra a transacao.
    """
    tabela = NotificacaoInterna.__table__

    if inspect(conexao).has_table(tabela.name):
        raise RuntimeError(
            "Tabela notificacoes_internas ja existe. "
            "Interrompido para evitar alteracao nao planejada."
        )

    tabela.create(bind=conexao, checkfirst=False)
    return tabela.name