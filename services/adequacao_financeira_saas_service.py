from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from models import (
    AdequacaoPlanoSaaS,
    AssinaturaSaaS,
    PagamentoSaaS,
    PlanoSaaS,
)


CENTAVOS = Decimal("0.01")


def _dinheiro(valor: Any) -> Decimal:
    if valor is None:
        return Decimal("0.00")

    return Decimal(str(valor)).quantize(
        CENTAVOS,
        rounding=ROUND_HALF_UP,
    )


def _decimal_str(valor: Decimal) -> str:
    return str(
        valor.quantize(
            CENTAVOS,
            rounding=ROUND_HALF_UP,
        )
    )


def _normalizar_forma_pagamento(valor: Any) -> str:
    forma = str(valor or "").strip().upper()

    if forma in {"CARTAO", "CARTÃO", "CARD", "CREDIT_CARD"}:
        return "CARTAO"

    if forma == "PIX":
        return "PIX"

    return forma


def _preco_plano_por_forma(plano, forma_pagamento: str) -> Decimal:
    forma = _normalizar_forma_pagamento(forma_pagamento)

    if forma == "PIX":
        return _dinheiro(plano.valor_pix)

    if forma == "CARTAO":
        return _dinheiro(plano.valor_cartao)

    raise ValueError(
        f"Forma de pagamento nao suportada para simulacao: "
        f"{forma_pagamento!r}"
    )


def calcular_adequacao_financeira_saas(
    *,
    valor_origem,
    valor_destino,
    data_inicio,
    data_fim,
    momento_calculo=None,
):
    """
    Motor matematico puro da adequacao financeira SaaS.

    Nao grava banco.
    Nao cria pagamento.
    Nao chama Mercado Pago.
    Nao troca plano.
    """

    agora = momento_calculo or datetime.now()

    origem = _dinheiro(valor_origem)
    destino = _dinheiro(valor_destino)
    diferenca = destino - origem

    resultado = {
        "status_calculo": None,
        "valor_origem": _decimal_str(origem),
        "valor_destino": _decimal_str(destino),
        "diferenca_integral": None,
        "data_inicio": (
            data_inicio.isoformat()
            if data_inicio is not None
            else None
        ),
        "data_fim": (
            data_fim.isoformat()
            if data_fim is not None
            else None
        ),
        "momento_calculo": agora.isoformat(),
        "segundos_total_ciclo": None,
        "segundos_restantes": None,
        "fracao_restante": None,
        "valor_adequacao": None,
        "motivo": None,
    }

    if diferenca <= Decimal("0.00"):
        resultado["diferenca_integral"] = _decimal_str(
            max(diferenca, Decimal("0.00"))
        )
        resultado["status_calculo"] = "DESTINO_NAO_SUPERIOR"
        resultado["motivo"] = (
            "O plano de destino da adequacao obrigatoria deve "
            "possuir valor superior ao plano de origem."
        )
        return resultado

    resultado["diferenca_integral"] = _decimal_str(diferenca)

    if data_inicio is None or data_fim is None:
        resultado["status_calculo"] = "CICLO_INCOMPLETO"
        resultado["motivo"] = (
            "A assinatura nao possui data_inicio e data_fim "
            "suficientes para calcular o periodo restante "
            "com seguranca."
        )
        return resultado

    if data_fim <= data_inicio:
        resultado["status_calculo"] = "CICLO_INVALIDO"
        resultado["motivo"] = (
            "data_fim deve ser posterior a data_inicio."
        )
        return resultado

    total_segundos = Decimal(
        str((data_fim - data_inicio).total_seconds())
    )

    resultado["segundos_total_ciclo"] = str(total_segundos)

    if agora >= data_fim:
        resultado["status_calculo"] = "CICLO_ENCERRADO"
        resultado["segundos_restantes"] = "0"
        resultado["fracao_restante"] = "0"
        resultado["valor_adequacao"] = "0.00"
        resultado["motivo"] = (
            "O ciclo informado ja terminou. "
            "Nao existe saldo proporcional deste ciclo."
        )
        return resultado

    if agora <= data_inicio:
        segundos_restantes = total_segundos
    else:
        segundos_restantes = Decimal(
            str((data_fim - agora).total_seconds())
        )

    fracao_restante = segundos_restantes / total_segundos

    if fracao_restante < Decimal("0"):
        fracao_restante = Decimal("0")

    if fracao_restante > Decimal("1"):
        fracao_restante = Decimal("1")

    valor_adequacao = (
        diferenca * fracao_restante
    ).quantize(
        CENTAVOS,
        rounding=ROUND_HALF_UP,
    )

    resultado["status_calculo"] = "OK"
    resultado["segundos_restantes"] = str(segundos_restantes)
    resultado["fracao_restante"] = str(
        fracao_restante.quantize(
            Decimal("0.00000001"),
            rounding=ROUND_HALF_UP,
        )
    )
    resultado["valor_adequacao"] = _decimal_str(
        valor_adequacao
    )
    resultado["motivo"] = (
        "Valor calculado proporcionalmente ao tempo "
        "restante do ciclo vigente."
    )

    return resultado


def simular_adequacao_pendente_saas(
    db,
    *,
    barbearia_id: int,
    forma_pagamento: str | None = None,
    momento_calculo: datetime | None = None,
):
    """
    Camada de leitura da adequacao real.

    Busca:
    - assinatura atual;
    - adequacao PENDENTE;
    - plano de origem;
    - plano de destino;
    - ultimo pagamento aprovado/processado.

    Esta funcao e SOMENTE LEITURA.
    """

    agora = momento_calculo or datetime.now()

    assinatura = (
        db.query(AssinaturaSaaS)
        .filter(AssinaturaSaaS.barbearia_id == barbearia_id)
        .first()
    )

    if assinatura is None:
        return {
            "status_simulacao": "SEM_ASSINATURA",
            "barbearia_id": barbearia_id,
        }

    adequacao = (
        db.query(AdequacaoPlanoSaaS)
        .filter(
            AdequacaoPlanoSaaS.barbearia_id == barbearia_id,
            AdequacaoPlanoSaaS.status == "PENDENTE",
        )
        .order_by(AdequacaoPlanoSaaS.id.desc())
        .first()
    )

    if adequacao is None:
        return {
            "status_simulacao": "SEM_ADEQUACAO_PENDENTE",
            "barbearia_id": barbearia_id,
            "assinatura_id": assinatura.id,
        }

    plano_origem_id = getattr(
        adequacao,
        "plano_origem_id",
        None,
    )

    plano_destino_id = getattr(
        adequacao,
        "plano_destino_id",
        None,
    )

    if plano_origem_id is None:
        plano_origem_id = assinatura.plano_id

    if plano_destino_id is None:
        return {
            "status_simulacao": "SEM_PLANO_DESTINO",
            "barbearia_id": barbearia_id,
            "assinatura_id": assinatura.id,
            "adequacao_id": adequacao.id,
        }

    plano_origem = (
        db.query(PlanoSaaS)
        .filter(PlanoSaaS.id == plano_origem_id)
        .first()
    )

    plano_destino = (
        db.query(PlanoSaaS)
        .filter(PlanoSaaS.id == plano_destino_id)
        .first()
    )

    if plano_origem is None or plano_destino is None:
        return {
            "status_simulacao": "PLANO_NAO_ENCONTRADO",
            "barbearia_id": barbearia_id,
            "assinatura_id": assinatura.id,
            "adequacao_id": adequacao.id,
        }

    if plano_origem.periodo_meses != plano_destino.periodo_meses:
        return {
            "status_simulacao": "PERIODO_DIVERGENTE",
            "barbearia_id": barbearia_id,
            "assinatura_id": assinatura.id,
            "adequacao_id": adequacao.id,
            "plano_origem": plano_origem.nome,
            "plano_destino": plano_destino.nome,
            "periodo_origem_meses": plano_origem.periodo_meses,
            "periodo_destino_meses": plano_destino.periodo_meses,
        }

    forma_original = _normalizar_forma_pagamento(
        assinatura.forma_pagamento
    )

    forma_nova = _normalizar_forma_pagamento(
        forma_pagamento or forma_original
    )

    if forma_nova not in {"PIX", "CARTAO"}:
        return {
            "status_simulacao": "FORMA_PAGAMENTO_INVALIDA",
            "barbearia_id": barbearia_id,
            "forma_pagamento": forma_nova,
        }

    ultimo_pagamento = (
        db.query(PagamentoSaaS)
        .filter(
            PagamentoSaaS.assinatura_id == assinatura.id,
            PagamentoSaaS.status == "approved",
        )
        .order_by(PagamentoSaaS.id.desc())
        .first()
    )

    valor_tabela_origem = _preco_plano_por_forma(
        plano_origem,
        forma_original or forma_nova,
    )

    valor_tabela_destino = _preco_plano_por_forma(
        plano_destino,
        forma_nova,
    )

    valor_historico = None

    if ultimo_pagamento is not None:
        valor_historico = _dinheiro(
            getattr(ultimo_pagamento, "valor_original", None)
            if getattr(ultimo_pagamento, "valor_original", None) is not None
            else getattr(ultimo_pagamento, "valor", None)
        )

    # IMPORTANTE:
    # Nesta C2 o pagamento historico e apenas exibido para auditoria.
    # Ainda NAO o usamos automaticamente como preco-base,
    # pois ele pode conter preco antigo, promocao ou outra regra comercial.
    valor_origem_calculo = valor_tabela_origem

    calculo = calcular_adequacao_financeira_saas(
        valor_origem=valor_origem_calculo,
        valor_destino=valor_tabela_destino,
        data_inicio=assinatura.data_inicio,
        data_fim=assinatura.data_fim,
        momento_calculo=agora,
    )

    return {
        "status_simulacao": "CALCULADO",
        "barbearia_id": barbearia_id,
        "assinatura_id": assinatura.id,
        "adequacao_id": adequacao.id,

        "plano_origem_id": plano_origem.id,
        "plano_origem": plano_origem.nome,

        "plano_destino_id": plano_destino.id,
        "plano_destino": plano_destino.nome,

        "periodo_meses": plano_origem.periodo_meses,

        "forma_pagamento_original": forma_original,
        "forma_pagamento_simulada": forma_nova,

        "valor_tabela_origem": _decimal_str(
            valor_tabela_origem
        ),
        "valor_tabela_destino": _decimal_str(
            valor_tabela_destino
        ),

        "ultimo_pagamento_id": (
            ultimo_pagamento.id
            if ultimo_pagamento is not None
            else None
        ),

        "valor_historico_ultimo_pagamento": (
            _decimal_str(valor_historico)
            if valor_historico is not None
            else None
        ),

        "data_inicio": (
            assinatura.data_inicio.isoformat()
            if assinatura.data_inicio
            else None
        ),

        "data_fim": (
            assinatura.data_fim.isoformat()
            if assinatura.data_fim
            else None
        ),

        "prazo_regularizacao": (
            adequacao.prazo_regularizacao.isoformat()
            if getattr(adequacao, "prazo_regularizacao", None)
            else None
        ),

        "calculo": calculo,

        "observacao": (
            "C2 somente leitura. Nenhuma cobranca, alteracao "
            "de plano ou escrita no banco foi realizada."
        ),
    }


# V474_C4_PREVIA_FINANCEIRA_OFICIAL

def _pagamento_eh_homologacao(pagamento) -> bool:
    if pagamento is None:
        return False

    campos = (
        getattr(pagamento, "external_reference", None),
        getattr(pagamento, "payment_id", None),
        getattr(pagamento, "idempotency_key", None),
    )

    texto = " ".join(
        str(v or "").upper()
        for v in campos
    )

    return (
        "HOMOLOGACAO" in texto
        or "TESTE-CREDITO" in texto
    )


def _preco_comercial_origem_ciclo(pagamento):
    """
    Retorna o preco comercial congelado do ciclo.

    valor_original representa o preco antes de eventual
    credito BarbSist.

    Pagamentos artificiais de homologacao nunca podem
    definir o preco comercial de um ciclo real.
    """

    if pagamento is None:
        return {
            "status": "SEM_PAGAMENTO_DO_CICLO",
            "valor": None,
        }

    if _pagamento_eh_homologacao(pagamento):
        return {
            "status": "PAGAMENTO_HOMOLOGACAO",
            "valor": None,
        }

    valor_original = getattr(
        pagamento,
        "valor_original",
        None,
    )

    if valor_original is None:
        valor_credito = _dinheiro(
            getattr(pagamento, "valor_credito", 0) or 0
        )

        if valor_credito > Decimal("0.00"):
            return {
                "status": "PRECO_COMERCIAL_INDETERMINADO",
                "valor": None,
            }

        valor_original = getattr(
            pagamento,
            "valor",
            None,
        )

    valor = _dinheiro(valor_original)

    if valor <= Decimal("0.00"):
        return {
            "status": "PRECO_COMERCIAL_INVALIDO",
            "valor": None,
        }

    return {
        "status": "OK",
        "valor": valor,
    }


def previa_financeira_adequacao_saas(
    db,
    *,
    barbearia_id: int,
    forma_pagamento: str,
    momento_calculo: datetime | None = None,
):
    """
    V4.7.4-C4.

    Previa financeira oficial da adequacao.

    SOMENTE LEITURA:
    - nao cria pagamento;
    - nao chama Mercado Pago;
    - nao troca plano;
    - nao altera vencimento;
    - nao finaliza adequacao.
    """

    agora = momento_calculo or datetime.now()

    forma = _normalizar_forma_pagamento(
        forma_pagamento
    )

    if forma not in {"PIX", "CARTAO"}:
        return {
            "status": "FORMA_PAGAMENTO_INVALIDA",
            "forma_pagamento": forma,
        }

    assinatura = (
        db.query(AssinaturaSaaS)
        .filter(
            AssinaturaSaaS.barbearia_id
            == barbearia_id
        )
        .first()
    )

    if assinatura is None:
        return {
            "status": "SEM_ASSINATURA",
            "barbearia_id": barbearia_id,
        }

    adequacao = (
        db.query(AdequacaoPlanoSaaS)
        .filter(
            AdequacaoPlanoSaaS.barbearia_id
            == barbearia_id,
            AdequacaoPlanoSaaS.status
            == "PENDENTE",
        )
        .order_by(
            AdequacaoPlanoSaaS.id.desc()
        )
        .first()
    )

    if adequacao is None:
        return {
            "status": "SEM_ADEQUACAO_PENDENTE",
            "barbearia_id": barbearia_id,
        }

    if (
        adequacao.assinatura_id
        != assinatura.id
    ):
        return {
            "status": "ADEQUACAO_ASSINATURA_DIVERGENTE",
            "adequacao_id": adequacao.id,
            "assinatura_id": assinatura.id,
        }

    if (
        adequacao.plano_origem_id
        != assinatura.plano_id
    ):
        return {
            "status": "PLANO_ORIGEM_DIVERGENTE",
            "adequacao_id": adequacao.id,
            "plano_assinatura_id": assinatura.plano_id,
            "plano_origem_id": adequacao.plano_origem_id,
        }

    if adequacao.plano_destino_id is None:
        return {
            "status": "SEM_PLANO_DESTINO",
            "adequacao_id": adequacao.id,
        }

    origem = (
        db.query(PlanoSaaS)
        .filter(
            PlanoSaaS.id
            == adequacao.plano_origem_id
        )
        .first()
    )

    destino = (
        db.query(PlanoSaaS)
        .filter(
            PlanoSaaS.id
            == adequacao.plano_destino_id
        )
        .first()
    )

    if origem is None or destino is None:
        return {
            "status": "PLANO_NAO_ENCONTRADO",
            "adequacao_id": adequacao.id,
        }

    if (
        origem.periodo_meses
        != destino.periodo_meses
    ):
        return {
            "status": "PERIODO_DIVERGENTE",
            "adequacao_id": adequacao.id,
            "periodo_origem": origem.periodo_meses,
            "periodo_destino": destino.periodo_meses,
        }

    # V474_C42C_PREVIA_USA_RESOLVEDOR
    #
    # A previa financeira nao infere mais o ciclo diretamente
    # de assinatura.data_inicio/data_fim nem escolhe simplesmente
    # o pagamento aprovado mais recente.
    #
    # O ciclo e o preco comercial de origem devem ser comprovados
    # pelo resolvedor C4.2A/C4.2B.
    ciclo = resolver_ciclo_financeiro_vigente_saas(
        db,
        assinatura=assinatura,
        plano=origem,
        momento_calculo=agora,
    )

    if (
        not isinstance(ciclo, dict)
        or ciclo.get("status") != "OK"
        or not ciclo.get("comprovado")
    ):
        return {
            "status": (
                ciclo.get(
                    "status",
                    "CICLO_FINANCEIRO_NAO_COMPROVADO",
                )
                if isinstance(ciclo, dict)
                else "CICLO_FINANCEIRO_NAO_COMPROVADO"
            ),
            "adequacao_id": adequacao.id,
            "assinatura_id": assinatura.id,
            "pagamento_origem_id": (
                ciclo.get("pagamento_id")
                if isinstance(ciclo, dict)
                else None
            ),
            "valor_adequacao": None,
            "pode_pagar": False,
            "motivo": (
                ciclo.get("motivo")
                if isinstance(ciclo, dict)
                else "RETORNO_RESOLVEDOR_INVALIDO"
            ),
        }

    ciclo_inicio = ciclo.get("ciclo_inicio")
    ciclo_fim = ciclo.get("ciclo_fim")
    pagamento_origem_id = ciclo.get("pagamento_id")
    preco_comercial_origem = ciclo.get(
        "preco_comercial_origem"
    )
    valor_credito_origem = ciclo.get(
        "valor_credito",
        0,
    )

    if (
        ciclo_inicio is None
        or ciclo_fim is None
        or pagamento_origem_id is None
        or preco_comercial_origem is None
    ):
        return {
            "status": "CICLO_FINANCEIRO_NAO_COMPROVADO",
            "adequacao_id": adequacao.id,
            "assinatura_id": assinatura.id,
            "pagamento_origem_id": pagamento_origem_id,
            "valor_adequacao": None,
            "pode_pagar": False,
            "motivo": "CONTRATO_RESOLVEDOR_INCOMPLETO",
        }

    # Nesta etapa o preco do destino segue a tabela
    # da forma de pagamento escolhida.
    #
    # A integracao posterior podera substituir esta
    # origem por _valor_checkout_saas_com_db para
    # preservar regras promocionais ativas.
    valor_destino = _preco_plano_por_forma(
        destino,
        forma,
    )

    calculo = calcular_adequacao_financeira_saas(
        valor_origem=preco_comercial_origem,
        valor_destino=valor_destino,
        data_inicio=ciclo_inicio,
        data_fim=ciclo_fim,
        momento_calculo=agora,
    )

    pode_pagar = (
        calculo.get("status_calculo")
        == "OK"
        and _dinheiro(
            calculo.get("valor_adequacao")
        ) > Decimal("0.00")
    )

    max_parcelas = 1

    if forma == "CARTAO":
        max_parcelas = max(
            1,
            int(
                getattr(
                    destino,
                    "max_parcelas_cartao",
                    1,
                )
                or 1
            ),
        )

    return {
        "status": (
            "OK"
            if pode_pagar
            else calculo.get("status_calculo")
        ),
        "pode_pagar": pode_pagar,

        "barbearia_id": barbearia_id,
        "assinatura_id": assinatura.id,
        "adequacao_id": adequacao.id,

        "plano_origem": {
            "id": origem.id,
            "nome": origem.nome,
            "limite_barbeiros": origem.limite_barbeiros,
            "periodo_meses": origem.periodo_meses,
        },

        "plano_destino": {
            "id": destino.id,
            "nome": destino.nome,
            "limite_barbeiros": destino.limite_barbeiros,
            "periodo_meses": destino.periodo_meses,
        },

        "forma_pagamento": forma,

        "pagamento_origem_id": pagamento_origem_id,

        "valor_comercial_origem": (
            _decimal_str(
                preco_comercial_origem
            )
        ),

        "valor_comercial_destino": (
            _decimal_str(
                valor_destino
            )
        ),

        "valor_credito_ciclo_origem": (
            _decimal_str(
                _dinheiro(
                    valor_credito_origem or 0
                )
            )
        ),

        "data_inicio_ciclo": (
            ciclo_inicio.isoformat()
        ),

        "data_fim_ciclo": (
            ciclo_fim.isoformat()
        ),

        "prazo_regularizacao": (
            adequacao.prazo_regularizacao.isoformat()
            if adequacao.prazo_regularizacao
            else None
        ),

        "diferenca_integral": (
            calculo.get(
                "diferenca_integral"
            )
        ),

        "fracao_restante": (
            calculo.get(
                "fracao_restante"
            )
        ),

        "valor_adequacao": (
            calculo.get(
                "valor_adequacao"
            )
        ),

        "max_parcelas_cartao": (
            max_parcelas
        ),

        "calculo": calculo,

        "observacao": (
            "Previa somente leitura. Nenhuma cobranca "
            "ou alteracao contratual foi realizada."
        ),
    }


# V474_C42A_CICLO_FINANCEIRO_VIGENTE

def resolver_ciclo_financeiro_vigente_saas(
    db,
    *,
    assinatura,
    plano,
    momento_calculo=None,
):

    # V474_C42B3_CICLO_EXPLICITO
    #
    # Pagamentos novos registram explicitamente o ciclo
    # financeiro que financiaram. Quando houver um ciclo
    # comprovado e vigente, ele tem precedencia sobre a
    # inferencia legada baseada em assinatura.data_fim.
    #
    # Registros antigos permanecem compativeis com o
    # resolvedor C4.2A-R1 existente.
    momento = momento_calculo or datetime.now()

    pagamentos_ciclo_explicito = (
        db.query(PagamentoSaaS)
        .filter(
            PagamentoSaaS.assinatura_id == assinatura.id,
            PagamentoSaaS.barbearia_id == assinatura.barbearia_id,
            PagamentoSaaS.plano_id == plano.id,
            PagamentoSaaS.status == "approved",
            PagamentoSaaS.processado.is_(True),
            PagamentoSaaS.ciclo_inicio.isnot(None),
            PagamentoSaaS.ciclo_fim.isnot(None),
            PagamentoSaaS.ciclo_inicio <= momento,
            PagamentoSaaS.ciclo_fim > momento,
        )
        .order_by(
            PagamentoSaaS.ciclo_inicio.desc(),
            PagamentoSaaS.id.desc(),
        )
        .all()
    )

    if pagamentos_ciclo_explicito:
        if len(pagamentos_ciclo_explicito) != 1:
            return {
                "status": "CICLO_FINANCEIRO_NAO_COMPROVADO",
                "motivo": "CICLOS_EXPLICITOS_SOBREPOSTOS",
                "comprovado": False,
            }

        pagamento_ciclo = pagamentos_ciclo_explicito[0]

        if pagamento_ciclo.ciclo_fim <= pagamento_ciclo.ciclo_inicio:
            return {
                "status": "CICLO_FINANCEIRO_NAO_COMPROVADO",
                "motivo": "CICLO_EXPLICITO_INVALIDO",
                "comprovado": False,
            }

        # V474_C42B3_R1_PRECO_ORIGEM
        #
        # _preco_comercial_origem_ciclo retorna um contrato:
        # {
        #     "status": "OK",
        #     "valor": Decimal(...)
        # }
        #
        # O resolvedor deve expor somente o Decimal em
        # preco_comercial_origem, preservando o contrato
        # utilizado pelo restante do motor financeiro.
        try:
            resultado_preco = _preco_comercial_origem_ciclo(
                pagamento_ciclo
            )
        except Exception as exc:
            return {
                "status": "CICLO_FINANCEIRO_NAO_COMPROVADO",
                "motivo": str(exc),
                "comprovado": False,
            }

        if not isinstance(resultado_preco, dict):
            return {
                "status": "CICLO_FINANCEIRO_NAO_COMPROVADO",
                "motivo": "RETORNO_PRECO_ORIGEM_INVALIDO",
                "comprovado": False,
            }

        if resultado_preco.get("status") != "OK":
            return {
                "status": "CICLO_FINANCEIRO_NAO_COMPROVADO",
                "motivo": (
                    resultado_preco.get("status")
                    or "PRECO_COMERCIAL_ORIGEM_NAO_COMPROVADO"
                ),
                "comprovado": False,
            }

        preco_origem = resultado_preco.get("valor")

        if preco_origem is None:
            return {
                "status": "CICLO_FINANCEIRO_NAO_COMPROVADO",
                "motivo": "PRECO_COMERCIAL_ORIGEM_AUSENTE",
                "comprovado": False,
            }

        instante_pagamento = (
            pagamento_ciclo.processado_em
            or pagamento_ciclo.data_criacao
        )

        return {
            "status": "OK",
            "comprovado": True,
            "fonte_ciclo": "PAGAMENTO_EXPLICITO",
            "assinatura_id": assinatura.id,
            "plano_id": plano.id,
            "pagamento_id": pagamento_ciclo.id,
            "ciclo_inicio": pagamento_ciclo.ciclo_inicio,
            "ciclo_fim": pagamento_ciclo.ciclo_fim,
            "instante_pagamento": instante_pagamento,
            "preco_comercial_origem": preco_origem,
            "valor_credito": float(
                pagamento_ciclo.valor_credito or 0
            ),
        }

    """
    Resolve de forma conservadora o ciclo financeiro atualmente vigente.

    C4.2A:
    - somente leitura;
    - nao altera assinatura;
    - nao altera pagamentos;
    - nao inventa datas;
    - nao usa assinatura.data_inicio como inicio do ciclo renovado;
    - exige data_fim;
    - deriva o inicio do ciclo a partir de data_fim - periodo_meses;
    - exige pagamento aprovado/processado do plano vigente;
    - exige pagamento temporalmente compativel com o ciclo;
    - rejeita pagamentos de homologacao/teste;
    - falha fechado quando nao consegue comprovar o ciclo.
    """

    from datetime import datetime

    agora = momento_calculo or datetime.now()

    if assinatura is None:
        return {
            "status": "ASSINATURA_NAO_ENCONTRADA",
            "comprovado": False,
        }

    if plano is None:
        return {
            "status": "PLANO_NAO_ENCONTRADO",
            "comprovado": False,
        }

    if assinatura.data_fim is None:
        return {
            "status": "CICLO_FINANCEIRO_NAO_COMPROVADO",
            "motivo": "ASSINATURA_SEM_DATA_FIM",
            "comprovado": False,
        }

    periodo_meses = int(
        getattr(plano, "periodo_meses", 0) or 0
    )

    if periodo_meses <= 0:
        return {
            "status": "CICLO_FINANCEIRO_NAO_COMPROVADO",
            "motivo": "PERIODO_PLANO_INVALIDO",
            "comprovado": False,
        }

    ciclo_fim = assinatura.data_fim

    # C4.2A-R1
    # Subtracao explicita de meses de calendario.
    #
    # Nao usamos _add_months com valor negativo porque o helper
    # existente foi criado para prorrogacao de assinatura.
    import calendar

    indice_mes = (
        ciclo_fim.year * 12
        + (ciclo_fim.month - 1)
        - periodo_meses
    )

    ano_inicio = indice_mes // 12
    mes_inicio = (indice_mes % 12) + 1

    ultimo_dia = calendar.monthrange(
        ano_inicio,
        mes_inicio,
    )[1]

    dia_inicio = min(
        ciclo_fim.day,
        ultimo_dia,
    )

    ciclo_inicio = ciclo_fim.replace(
        year=ano_inicio,
        month=mes_inicio,
        day=dia_inicio,
    )

    if ciclo_inicio >= ciclo_fim:
        return {
            "status": "CICLO_FINANCEIRO_NAO_COMPROVADO",
            "motivo": "INTERVALO_CICLO_INVALIDO",
            "comprovado": False,
        }

    if agora < ciclo_inicio or agora > ciclo_fim:
        return {
            "status": "CICLO_FINANCEIRO_NAO_COMPROVADO",
            "motivo": "MOMENTO_FORA_DO_CICLO",
            "comprovado": False,
            "ciclo_inicio": ciclo_inicio,
            "ciclo_fim": ciclo_fim,
        }

    import models

    pagamentos = (
        db.query(models.PagamentoSaaS)
        .filter(
            models.PagamentoSaaS.assinatura_id
            == assinatura.id,
            models.PagamentoSaaS.barbearia_id
            == assinatura.barbearia_id,
            models.PagamentoSaaS.plano_id
            == assinatura.plano_id,
            models.PagamentoSaaS.status
            == "approved",
            models.PagamentoSaaS.processado.is_(True),
        )
        .order_by(
            models.PagamentoSaaS.processado_em.desc(),
            models.PagamentoSaaS.id.desc(),
        )
        .all()
    )

    candidatos = []

    for pagamento in pagamentos:

        if _pagamento_eh_homologacao(pagamento):
            continue

        instante = (
            pagamento.processado_em
            or pagamento.data_criacao
        )

        if instante is None:
            continue

        # Para o modelo atual, o pagamento que financiou o ciclo
        # precisa ter sido processado no inicio do ciclo ou antes dele.
        #
        # Aceitamos pequena tolerancia temporal de 24 horas porque
        # processamento/webhook e criacao podem atravessar limites
        # operacionais.
        from datetime import timedelta

        tolerancia = timedelta(hours=24)

        if instante > ciclo_inicio + tolerancia:
            continue

        candidatos.append(
            (
                pagamento,
                instante,
            )
        )

    if not candidatos:
        return {
            "status": "CICLO_FINANCEIRO_NAO_COMPROVADO",
            "motivo": "PAGAMENTO_DO_CICLO_NAO_COMPROVADO",
            "comprovado": False,
            "ciclo_inicio": ciclo_inicio,
            "ciclo_fim": ciclo_fim,
        }

    # Escolhe o pagamento elegivel mais proximo do inicio
    # do ciclo, evitando simplesmente pegar qualquer historico.
    candidatos.sort(
        key=lambda item: abs(
            (
                item[1] - ciclo_inicio
            ).total_seconds()
        )
    )

    pagamento, instante_pagamento = candidatos[0]

    preco = _preco_comercial_origem_ciclo(
        pagamento
    )

    if not isinstance(preco, dict):
        return {
            "status": "CICLO_FINANCEIRO_NAO_COMPROVADO",
            "motivo": "PRECO_COMERCIAL_NAO_COMPROVADO",
            "comprovado": False,
            "ciclo_inicio": ciclo_inicio,
            "ciclo_fim": ciclo_fim,
            "pagamento_id": pagamento.id,
        }

    if preco.get("status") != "OK":
        return {
            "status": "CICLO_FINANCEIRO_NAO_COMPROVADO",
            "motivo": preco.get(
                "status",
                "PRECO_COMERCIAL_NAO_COMPROVADO",
            ),
            "comprovado": False,
            "ciclo_inicio": ciclo_inicio,
            "ciclo_fim": ciclo_fim,
            "pagamento_id": pagamento.id,
        }

    valor_comercial = preco.get(
        "valor_comercial"
    )

    if valor_comercial is None:
        # Compatibilidade caso o helper C4 use outro nome.
        valor_comercial = preco.get(
            "valor"
        )

    if valor_comercial is None:
        return {
            "status": "CICLO_FINANCEIRO_NAO_COMPROVADO",
            "motivo": "PRECO_COMERCIAL_AUSENTE",
            "comprovado": False,
            "ciclo_inicio": ciclo_inicio,
            "ciclo_fim": ciclo_fim,
            "pagamento_id": pagamento.id,
        }

    return {
        "status": "OK",
        "comprovado": True,
        "assinatura_id": assinatura.id,
        "plano_id": assinatura.plano_id,
        "pagamento_id": pagamento.id,
        "ciclo_inicio": ciclo_inicio,
        "ciclo_fim": ciclo_fim,
        "instante_pagamento": instante_pagamento,
        "preco_comercial_origem": valor_comercial,
        "valor_credito": float(
            pagamento.valor_credito or 0
        ),
    }

