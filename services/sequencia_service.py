from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from datetime import datetime

import models


PREFIXOS_CODIGO = {
    "CLIENTE": "CLI",
    "BARBEIRO": "BAR",
    "SERVICO": "SER",
    "PRODUTO": "PRO",
    "COMANDA": "COM",
    "AGENDAMENTO": "AGE",
    "PLANO": "PLA",
    "ASSINATURA": "ASS",
    "CONTA_RECEBER": "REC",
    "CONTA_PAGAR": "PAG"
}


def obter_prefixo(tipo: str) -> str:
    tipo_normalizado = tipo.strip().upper()

    prefixo = PREFIXOS_CODIGO.get(
        tipo_normalizado
    )

    if not prefixo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Tipo de sequência inválido: "
                f"{tipo_normalizado}."
            )
        )

    return prefixo


def obter_proximo_numero(
    db: Session,
    barbearia_id: int,
    tipo: str
) -> int:
    """
    Obtém e incrementa a sequência de uma entidade
    dentro da barbearia.

    A operação utiliza flush, mas o commit ficará sob
    responsabilidade do service que está criando o registro.
    """

    tipo_normalizado = tipo.strip().upper()

    obter_prefixo(
        tipo_normalizado
    )

    sequencia = db.query(
        models.SequenciaBarbearia
    ).filter(
        models.SequenciaBarbearia.barbearia_id
        == barbearia_id,

        models.SequenciaBarbearia.tipo
        == tipo_normalizado
    ).first()

    if sequencia:
        sequencia.ultimo_numero += 1
        sequencia.data_atualizacao = datetime.now()

        db.flush()

        return sequencia.ultimo_numero

    sequencia = models.SequenciaBarbearia(
        barbearia_id=barbearia_id,
        tipo=tipo_normalizado,
        ultimo_numero=1
    )

    try:
        db.add(sequencia)
        db.flush()

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Não foi possível gerar a sequência. "
                "Tente novamente."
            )
        )

    return 1


def formatar_codigo(
    codigo_barbearia: int,
    tipo: str,
    numero: int
) -> str:
    """
    Formata o código comercial.

    Exemplo:
        CLI-001-000025
    """

    prefixo = obter_prefixo(
        tipo
    )

    return (
        f"{prefixo}-"
        f"{codigo_barbearia:03d}-"
        f"{numero:06d}"
    )


def gerar_codigo_comercial(
    db: Session,
    barbearia: models.Barbearia,
    tipo: str
) -> tuple[int, str]:
    """
    Retorna o número sequencial e o código formatado.

    Exemplo:
        (25, "CLI-001-000025")
    """

    numero = obter_proximo_numero(
        db=db,
        barbearia_id=barbearia.id,
        tipo=tipo
    )

    codigo = formatar_codigo(
        codigo_barbearia=barbearia.codigo,
        tipo=tipo,
        numero=numero
    )

    return numero, codigo