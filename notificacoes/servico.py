"""Operacoes transacionais de notificacoes internas."""

from sqlalchemy import func, select

from notificacoes.modelo import NotificacaoInterna


def registrar_notificacao(
    db,
    *,
    barbearia_id: int,
    chave_evento: str,
    tipo: str,
    titulo: str,
    mensagem: str,
    agendamento_id: int | None = None,
):
    """Adiciona notificacao a transacao corrente.

    Nao executa commit. O servico chamador deve confirmar
    a notificacao junto da operacao de negocio.
    """
    if not isinstance(barbearia_id, int) or barbearia_id <= 0:
        raise ValueError("Barbearia invalida.")

    campos = {
        "chave_evento": (chave_evento, 160),
        "tipo": (tipo, 50),
        "titulo": (titulo, 160),
        "mensagem": (mensagem, 1000),
    }

    valores = {}

    for nome, (valor, tamanho) in campos.items():
        if not isinstance(valor, str) or not valor.strip():
            raise ValueError(f"Campo obrigatorio: {nome}")

        normalizado = valor.strip()

        if len(normalizado) > tamanho:
            raise ValueError(f"Campo muito longo: {nome}")

        valores[nome] = normalizado

    if agendamento_id is not None:
        if not isinstance(agendamento_id, int) or agendamento_id <= 0:
            raise ValueError("Agendamento invalido.")

    notificacao = NotificacaoInterna(
        barbearia_id=barbearia_id,
        agendamento_id=agendamento_id,
        **valores,
    )

    db.add(notificacao)
    return notificacao


def listar_notificacoes(db, *, barbearia_id: int, limite: int = 30):
    if not isinstance(barbearia_id, int) or barbearia_id <= 0:
        raise ValueError("Barbearia invalida.")

    limite = max(1, min(int(limite), 100))

    return db.scalars(
        select(NotificacaoInterna)
        .where(NotificacaoInterna.barbearia_id == barbearia_id)
        .order_by(
            NotificacaoInterna.criada_em.desc(),
            NotificacaoInterna.id.desc(),
        )
        .limit(limite)
    ).all()


def contar_nao_lidas(db, *, barbearia_id: int):
    if not isinstance(barbearia_id, int) or barbearia_id <= 0:
        raise ValueError("Barbearia invalida.")

    return db.scalar(
        select(func.count(NotificacaoInterna.id))
        .where(
            NotificacaoInterna.barbearia_id == barbearia_id,
            NotificacaoInterna.lida.is_(False),
        )
    ) or 0


def marcar_como_lida(db, *, barbearia_id: int, notificacao_id: int):
    """Altera somente a notificacao da barbearia informada.

    Nao executa commit.
    """
    if not isinstance(barbearia_id, int) or barbearia_id <= 0:
        raise ValueError("Barbearia invalida.")

    notificacao = db.scalar(
        select(NotificacaoInterna)
        .where(
            NotificacaoInterna.id == notificacao_id,
            NotificacaoInterna.barbearia_id == barbearia_id,
        )
    )

    if notificacao is None:
        return None

    notificacao.lida = True
    return notificacao