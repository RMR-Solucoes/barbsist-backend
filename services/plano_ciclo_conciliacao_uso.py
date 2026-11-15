"""Reconciliacao pura entre reservas e consumos.

Nao acessa banco, nao cria UsoPlano, nao faz commit.
Os IDs recebidos devem ter origem comprovada na mesma
assinatura, comanda/agendamento e ciclo pago.
"""

from collections import Counter
from dataclasses import dataclass

from services.plano_ciclo_compromissos import (
    compromissos_pendentes,
)


@dataclass(frozen=True)
class ResultadoConciliacao:
    pendentes_antes: int
    pendentes_depois: int
    novo_consumo: int = 1


def conciliar_consumo_reservado(
    *,
    servicos_reservados: list[int],
    servicos_consumidos: list[int],
    novo_servico_id: int,
) -> ResultadoConciliacao:
    """Valida uma unidade adicional de consumo reservado.

    Por seguranca, respeita a restricao atual de unicidade
    de servico por comanda, inclusive em multisservico.
    """
    if (
        not isinstance(novo_servico_id, int)
        or isinstance(novo_servico_id, bool)
        or novo_servico_id <= 0
    ):
        raise ValueError("Servico de consumo invalido.")

    if not isinstance(servicos_reservados, list):
        raise ValueError("Lista de reservas invalida.")

    if not isinstance(servicos_consumidos, list):
        raise ValueError("Lista de consumos invalida.")

    for identificador in (
        servicos_reservados + servicos_consumidos
    ):
        if (
            not isinstance(identificador, int)
            or isinstance(identificador, bool)
            or identificador <= 0
        ):
            raise ValueError("Identificador invalido.")

    antes = compromissos_pendentes(
        servicos_reservados,
        servicos_consumidos,
    )

    contagem = Counter(servicos_reservados)

    if contagem[novo_servico_id] == 0:
        raise ValueError(
            "Servico nao pertence a reserva original."
        )

    if novo_servico_id in servicos_consumidos:
        raise ValueError(
            "Servico ja consumido nesta comanda. "
            "Repeticoes exigem suporte por item."
        )

    depois = compromissos_pendentes(
        servicos_reservados,
        servicos_consumidos + [novo_servico_id],
    )

    if depois != antes - 1:
        raise ValueError(
            "Inconsistencia na conciliacao dos creditos."
        )

    return ResultadoConciliacao(
        pendentes_antes=antes,
        pendentes_depois=depois,
    )
