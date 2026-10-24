"""Normalizacao conservadora de telefones brasileiros."""

import re


def somente_digitos(valor):
    return re.sub(r"\D", "", str(valor or ""))


def telefone_nacional(valor):
    """Retorna DDD + numero para telefones brasileiros validos.

    Aceita 10/11 digitos nacionais e 12/13 com DDI 55.
    Retorna None para vazio ou entradas invalidas.
    Nao adiciona o nono digito e nao altera numeros estrangeiros.
    """
    numero = somente_digitos(valor)

    if not numero:
        return None

    if len(numero) in (12, 13) and numero.startswith("55"):
        numero = numero[2:]

    if len(numero) not in (10, 11):
        return None

    ddd = int(numero[:2])
    local = numero[2:]

    if not 11 <= ddd <= 99:
        return None

    if len(local) == 9 and not local.startswith("9"):
        return None

    if len(local) == 8 and local.startswith("0"):
        return None

    return numero


def telefone_whatsapp(valor):
    nacional = telefone_nacional(valor)
    return f"55{nacional}" if nacional else None


def telefones_equivalentes(primeiro, segundo):
    a = telefone_nacional(primeiro)
    b = telefone_nacional(segundo)
    return a is not None and a == b