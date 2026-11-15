"""Calculo puro de compromissos de reservas por ciclo.

Nao consulta banco nem modifica saldos financeiros.

Os servicos consumidos devem ser comprovadamente vinculados
a mesma comanda/agendamento e ao mesmo ciclo da reserva.
"""

from collections import Counter


def compromissos_pendentes(
    servicos_reservados: list[int],
    servicos_consumidos: list[int],
) -> int:
    """Quantidade de servicos reservados ainda nao consumidos.

    As listas representam ocorrencias, nao apenas IDs distintos.
    """
    if not servicos_reservados:
        raise ValueError("Reserva sem servicos.")

    if any(not isinstance(x, int) or x <= 0 for x in
           servicos_reservados + servicos_consumidos):
        raise ValueError("Identificador de servico invalido.")

    reservados = Counter(servicos_reservados)
    consumidos = Counter(servicos_consumidos)

    # Um consumo de servico estranho nao pode liberar outro
    # compromisso. Tampouco pode exceder a quantidade reservada.
    for servico_id, quantidade in consumidos.items():
        if quantidade > reservados[servico_id]:
            raise ValueError(
                "Consumo nao corresponde aos servicos reservados."
            )

    return sum(
        reservados[id_servico] - consumidos[id_servico]
        for id_servico in reservados
    )


def saldo_livre_ciclo(
    creditos_concedidos: int,
    usos_consumidos: int,
    compromissos_pendentes_total: int,
) -> int:
    valores = (
        creditos_concedidos,
        usos_consumidos,
        compromissos_pendentes_total,
    )
    if any(
        not isinstance(valor, int) or valor < 0
        for valor in valores
    ):
        raise ValueError("Contagem invalida.")

    return (
        creditos_concedidos
        - usos_consumidos
        - compromissos_pendentes_total
    )
