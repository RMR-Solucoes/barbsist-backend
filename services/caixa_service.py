from fastapi import HTTPException, status

import models

from auth.tenant import (
    consultar_da_barbearia,
    obter_barbearia_id,
)


TIPOS_MOVIMENTACAO = {
    "entrada",
    "saida",
}

ORIGENS_MOVIMENTACAO = {
    "MANUAL",
    "COMANDA",
    "PLANO",
    "CONTA_RECEBER",
    "CONTA_PAGAR",
    "ESTORNO",
    "SANGRIA",
    "SUPRIMENTO",
}

STATUS_MOVIMENTACAO = {
    "ATIVO",
    "ESTORNADO",
    "CANCELADO",
}


def _normalizar_tipo(tipo: str) -> str:
    tipo_normalizado = (tipo or "").strip().lower()

    if tipo_normalizado not in TIPOS_MOVIMENTACAO:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tipo deve ser 'entrada' ou 'saida'.",
        )

    return tipo_normalizado


def _normalizar_origem(origem: str | None) -> str:
    origem_normalizada = (
        origem or "MANUAL"
    ).strip().upper()

    if origem_normalizada not in ORIGENS_MOVIMENTACAO:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Origem de movimentação inválida. "
                f"Valores permitidos: "
                f"{', '.join(sorted(ORIGENS_MOVIMENTACAO))}."
            ),
        )

    return origem_normalizada


def _normalizar_status(
    status_movimentacao: str | None,
) -> str:
    status_normalizado = (
        status_movimentacao or "ATIVO"
    ).strip().upper()

    if status_normalizado not in STATUS_MOVIMENTACAO:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Status de movimentação inválido. "
                f"Valores permitidos: "
                f"{', '.join(sorted(STATUS_MOVIMENTACAO))}."
            ),
        )

    return status_normalizado


def _validar_valor(valor: float) -> float:
    if valor is None or valor <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O valor deve ser maior que zero.",
        )

    return valor


def _normalizar_texto_opcional(
    valor: str | None,
) -> str | None:
    if not isinstance(valor, str):
        return None

    valor_normalizado = valor.strip()

    return valor_normalizado or None


def _obter_usuario_id(
    usuario_logado,
) -> int | None:
    if usuario_logado is None:
        return None

    if isinstance(usuario_logado, dict):
        return usuario_logado.get("id")

    return getattr(
        usuario_logado,
        "id",
        None,
    )


def criar_movimentacao_caixa(
    db,
    *,
    tipo: str,
    descricao: str,
    valor: float,
    forma_pagamento: str | None,
    barbearia_id: int,
    origem: str = "MANUAL",
    referencia_id: int | None = None,
    observacoes: str | None = None,
    usuario_id: int | None = None,
    status_movimentacao: str = "ATIVO",
    movimentacao_origem_id: int | None = None,
):
    descricao_normalizada = (
        descricao or ""
    ).strip()

    if not descricao_normalizada:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "A descrição da movimentação "
                "é obrigatória."
            ),
        )

    movimentacao = models.Caixa(
        tipo=_normalizar_tipo(tipo),
        descricao=descricao_normalizada,
        valor=_validar_valor(valor),
        forma_pagamento=(
            _normalizar_texto_opcional(
                forma_pagamento
            )
        ),
        origem=_normalizar_origem(origem),
        referencia_id=referencia_id,
        status=_normalizar_status(
            status_movimentacao
        ),
        observacoes=(
            _normalizar_texto_opcional(
                observacoes
            )
        ),
        usuario_id=usuario_id,
        movimentacao_origem_id=(
            movimentacao_origem_id
        ),
        barbearia_id=barbearia_id,
    )

    db.add(movimentacao)

    return movimentacao


def registrar_entrada_caixa(
    db,
    descricao: str,
    valor: float,
    forma_pagamento: str | None,
    barbearia_id: int,
    origem: str = "MANUAL",
    referencia_id: int | None = None,
    observacoes: str | None = None,
    usuario_id: int | None = None,
):
    """
    Registra uma entrada sem executar commit.

    O serviço chamador controla a transação para que
    a operação principal e o lançamento no Caixa sejam
    confirmados ou revertidos em conjunto.
    """

    return criar_movimentacao_caixa(
        db=db,
        tipo="entrada",
        descricao=descricao,
        valor=valor,
        forma_pagamento=forma_pagamento,
        barbearia_id=barbearia_id,
        origem=origem,
        referencia_id=referencia_id,
        observacoes=observacoes,
        usuario_id=usuario_id,
    )


def registrar_saida_caixa(
    db,
    descricao: str,
    valor: float,
    forma_pagamento: str | None,
    barbearia_id: int,
    origem: str = "MANUAL",
    referencia_id: int | None = None,
    observacoes: str | None = None,
    usuario_id: int | None = None,
):
    """
    Registra uma saída sem executar commit.

    O serviço chamador controla a transação.
    """

    return criar_movimentacao_caixa(
        db=db,
        tipo="saida",
        descricao=descricao,
        valor=valor,
        forma_pagamento=forma_pagamento,
        barbearia_id=barbearia_id,
        origem=origem,
        referencia_id=referencia_id,
        observacoes=observacoes,
        usuario_id=usuario_id,
    )


def registrar_movimentacao_caixa(
    db,
    dados,
    usuario_logado,
):
    """
    Registra uma movimentação manual.

    A origem, o status, o usuário e a barbearia são
    definidos pelo backend.
    """

    try:
        movimentacao = criar_movimentacao_caixa(
            db=db,
            tipo=dados.tipo,
            descricao=dados.descricao,
            valor=dados.valor,
            forma_pagamento=dados.forma_pagamento,
            observacoes=getattr(
                dados,
                "observacoes",
                None,
            ),
            origem="MANUAL",
            status_movimentacao="ATIVO",
            usuario_id=_obter_usuario_id(
                usuario_logado
            ),
            barbearia_id=obter_barbearia_id(
                usuario_logado
            ),
        )

        db.commit()
        db.refresh(movimentacao)

        return movimentacao

    except HTTPException:
        db.rollback()
        raise

    except Exception as erro:
        db.rollback()

        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Erro ao registrar movimentação "
                f"de caixa: {erro}"
            ),
        )


def listar_caixa_service(
    db,
    usuario_logado,
):
    return (
        consultar_da_barbearia(
            db=db,
            model=models.Caixa,
            usuario=usuario_logado,
        )
        .order_by(
            models.Caixa.data.desc(),
            models.Caixa.id.desc(),
        )
        .all()
    )

def buscar_movimentacao_caixa_service(
    db,
    movimentacao_id: int,
    usuario_logado,
):
    movimentacao = (
        consultar_da_barbearia(
            db=db,
            model=models.Caixa,
            usuario=usuario_logado,
        )
        .filter(
            models.Caixa.id == movimentacao_id
        )
        .first()
    )

    if not movimentacao:
        raise HTTPException(
            status_code=404,
            detail="Movimentação não encontrada."
        )

    return movimentacao
def resumo_caixa_service(
    db,
    usuario_logado,
):
    movimentacoes = (
        consultar_da_barbearia(
            db=db,
            model=models.Caixa,
            usuario=usuario_logado,
        )
        .filter(
            models.Caixa.status == "ATIVO"
        )
        .all()
    )

    entradas = sum(
        m.valor
        for m in movimentacoes
        if m.tipo == "entrada"
    )

    saidas = sum(
        m.valor
        for m in movimentacoes
        if m.tipo == "saida"
    )

    return {
        "entradas": entradas,
        "saidas": saidas,
        "saldo": entradas - saidas,
        "quantidade_movimentacoes": len(
            movimentacoes
        ),
    }