from fastapi import HTTPException, status


FORMAS_PAGAMENTO = {
    "DINHEIRO",
    "PIX",
    "CARTAO_CREDITO",
    "CARTAO_DEBITO",
    "TRANSFERENCIA",
    "BOLETO",
    "OUTRO",
}


ALIASES_FORMA_PAGAMENTO = {
    "CARTAO": "CARTAO_CREDITO",
    "CREDITO": "CARTAO_CREDITO",
    "CARTÃO": "CARTAO_CREDITO",
    "CARTÃO CRÉDITO": "CARTAO_CREDITO",
    "CARTAO CREDITO": "CARTAO_CREDITO",
    "DEBITO": "CARTAO_DEBITO",
    "DÉBITO": "CARTAO_DEBITO",
    "CARTÃO DÉBITO": "CARTAO_DEBITO",
    "CARTAO DEBITO": "CARTAO_DEBITO",
    "TRANSFERÊNCIA": "TRANSFERENCIA",
}


def normalizar_forma_pagamento(
    valor: str | None,
    *,
    permitir_none: bool = True,
) -> str | None:
    if valor is None:
        if permitir_none:
            return None
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Forma de pagamento é obrigatória.",
        )

    texto = valor.strip().upper()
    if not texto:
        if permitir_none:
            return None
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Forma de pagamento é obrigatória.",
        )

    texto = ALIASES_FORMA_PAGAMENTO.get(texto, texto)

    if texto not in FORMAS_PAGAMENTO:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Forma de pagamento inválida. "
                f"Valores permitidos: {', '.join(sorted(FORMAS_PAGAMENTO))}."
            ),
        )

    return texto


def validar_status_filtro(
    valor: str | None,
    permitidos: set[str],
) -> str | None:
    if valor is None or not valor.strip():
        return None

    status_normalizado = valor.strip().upper()

    if status_normalizado not in permitidos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Status inválido. "
                f"Valores permitidos: {', '.join(sorted(permitidos))}."
            ),
        )

    return status_normalizado
