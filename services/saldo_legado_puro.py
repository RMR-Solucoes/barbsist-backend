"""Calculo puro do saldo legado. Nao acessa banco nem altera dados."""

from datetime import date, datetime


def calcular_saldo_legado_puro(
    *,
    status,
    status_pagamento,
    data_fim,
    data_atendimento,
    usos_disponiveis,
    quantidades_reservadas,
    hoje=None,
):
    if status not in ("ATIVO", "ATIVA") or status_pagamento != "PAGO":
        raise ValueError("Assinatura sem direito ativo para agendar.")

    if not isinstance(data_atendimento, datetime):
        raise ValueError("Data de atendimento invalida.")

    if not isinstance(data_fim, (date, datetime)):
        raise ValueError("Plano sem data de vencimento valida.")

    if hoje is None:
        hoje = date.today()

    if isinstance(data_fim, datetime):
        if data_fim.date() < hoje:
            raise ValueError("Plano vencido.")
        fora_vigencia = data_atendimento >= data_fim
    else:
        if data_fim < hoje:
            raise ValueError("Plano vencido.")
        fora_vigencia = data_atendimento.date() >= data_fim

    if fora_vigencia:
        raise ValueError("Atendimento fora da vigencia do plano.")

    if (
        type(usos_disponiveis) is not int
        or usos_disponiveis < 0
    ):
        raise ValueError("Saldo geral invalido.")

    if not isinstance(quantidades_reservadas, (list, tuple)):
        raise ValueError("Reservas invalidas.")

    if any(
        type(quantidade) is not int or quantidade < 1
        for quantidade in quantidades_reservadas
    ):
        raise ValueError("Quantidade de servicos reservados invalida.")

    reservados = sum(quantidades_reservadas)
    livres = usos_disponiveis - reservados

    if livres < 0:
        raise ValueError("Saldo comprometido excede saldo disponivel.")

    return {
        "modo_saldo": "legado",
        "ciclo_id": None,
        "creditos_livres": livres,
        "creditos_reservados": reservados,
        "usos_disponiveis": usos_disponiveis,
        "creditos_consumidos_ciclo": None,
    }