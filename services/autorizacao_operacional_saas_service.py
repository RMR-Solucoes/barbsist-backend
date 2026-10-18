import re
from datetime import datetime

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from services.elegibilidade_publica_saas_service import (
    SITUACAO_SEM_ACESSO,
    avaliar_elegibilidade_publica_saas,
)


# ==================================================
# POLITICA COMERCIAL
# ==================================================

# O bloqueio nao transforma a conta em inacessivel.
#
# A barbearia continua podendo:
# - entrar no sistema;
# - consultar dados e historicos;
# - corrigir registros existentes;
# - cancelar operacoes existentes;
# - inativar registros;
# - acessar a propria conta;
# - contratar e pagar o SaaS BarbSist.
#
# Sao bloqueadas operacoes que criem, ampliem,
# reativem ou iniciem nova atividade operacional.


PREFIXO_REGULARIZACAO_SAAS = (
    "/barbsist-assinaturas"
)


# Todo POST dentro destes modulos e considerado
# nova atividade, exceto as rotas explicitamente
# liberadas abaixo.
PREFIXOS_POST_OPERACIONAL = (
    "/agendamentos",
    "/barbeiros",
    "/caixa",
    "/clientes",
    "/comandas",
    "/contas-pagar",
    "/contas-receber",
    "/estilos",
    "/mercado-pago",
    "/planos",
    "/produtos",
    "/servicos",
    "/usuarios",
    "/vendas",
)


# POSTs que apenas encerram/desfazem uma operacao
# existente e nao geram nova atividade comercial.
POSTS_PERMITIDOS_POS_VENCIMENTO = (
    re.compile(
        r"^/comandas/\d+/cancelar-cobranca-online$"
    ),
    re.compile(
        r"^/mercado-pago/oauth/desconectar$"
    ),
)


# PUT/PATCH/DELETE sao, em regra, permitidos para
# preservar correcao, cancelamento e manutencao de
# dados existentes.
#
# Estas rotas especificas, entretanto, voltam a
# gerar ou ampliar atividade e por isso bloqueiam.
MUTACOES_ESPECIFICAS_BLOQUEADAS = (
    # Agendamento
    (
        "PUT",
        re.compile(
            r"^/agendamentos/\d+/reagendar$"
        ),
    ),

    # Reativacoes operacionais
    (
        "PUT",
        re.compile(
            r"^/barbeiros/\d+/reativar$"
        ),
    ),
    (
        "PUT",
        re.compile(
            r"^/clientes/\d+/reativar$"
        ),
    ),
    (
        "PUT",
        re.compile(
            r"^/estilos/\d+/reativar$"
        ),
    ),
    (
        "PUT",
        re.compile(
            r"^/produtos/\d+/reativar$"
        ),
    ),
    (
        "PUT",
        re.compile(
            r"^/servicos/\d+/reativar$"
        ),
    ),
    (
        "PUT",
        re.compile(
            r"^/usuarios/\d+/reativar$"
        ),
    ),

    # Planos de clientes da barbearia
    (
        "PUT",
        re.compile(
            r"^/planos/assinaturas/\d+/reativar$"
        ),
    ),
    (
        "PUT",
        re.compile(
            r"^/planos/assinaturas/\d+/renovar$"
        ),
    ),
    (
        "PUT",
        re.compile(
            r"^/planos/assinaturas/\d+/trocar-plano$"
        ),
    ),
    (
        "PUT",
        re.compile(
            r"^/planos/\d+/reativar$"
        ),
    ),
)


MENSAGEM_BLOQUEIO_SAAS = (
    "Seu per\u00edodo gratuito e a car\u00eancia foram encerrados. "
    "Escolha um plano para continuar utilizando as "
    "opera\u00e7\u00f5es do BarbSist."
)


def _normalizar_caminho(
    caminho: str,
) -> str:

    valor = str(
        caminho or ""
    ).strip()

    if not valor:
        return "/"

    if not valor.startswith("/"):
        valor = "/" + valor

    if valor != "/":
        valor = valor.rstrip("/")

    return valor


def _esta_no_prefixo(
    caminho: str,
    prefixo: str,
) -> bool:

    return (
        caminho == prefixo
        or caminho.startswith(
            prefixo + "/"
        )
    )


def _corresponde(
    caminho: str,
    expressoes,
) -> bool:

    return any(
        expressao.fullmatch(
            caminho
        )
        is not None
        for expressao in expressoes
    )


def operacao_exige_direito_saas(
    metodo: str,
    caminho: str,
) -> bool:
    """
    Retorna True somente para operacoes que devem
    ser bloqueadas quando a barbearia estiver em
    SEM_ACESSO.

    GET/HEAD/OPTIONS continuam livres.

    Alteracoes de registros existentes continuam
    permitidas, exceto reativacoes/reagendamentos
    explicitamente classificados como nova atividade.
    """

    metodo_normalizado = (
        str(
            metodo or ""
        )
        .strip()
        .upper()
    )

    caminho_normalizado = (
        _normalizar_caminho(
            caminho
        )
    )

    # Consultas e navegacao permanecem livres.
    if metodo_normalizado in {
        "GET",
        "HEAD",
        "OPTIONS",
    }:
        return False

    # Contratacao e pagamento do proprio SaaS
    # precisam continuar disponiveis.
    if _esta_no_prefixo(
        caminho_normalizado,
        PREFIXO_REGULARIZACAO_SAAS,
    ):
        return False

    # Conta da propria barbearia permanece editavel.
    if (
        metodo_normalizado == "PUT"
        and caminho_normalizado
        == "/barbearia/minha"
    ):
        return False

    if (
        metodo_normalizado == "POST"
        and caminho_normalizado
        == "/barbearia/minha/geocodificar-endereco"
    ):
        return False

    # Alguns POSTs apenas desfazem/cancelam
    # uma operacao anterior.
    if (
        metodo_normalizado == "POST"
        and _corresponde(
            caminho_normalizado,
            POSTS_PERMITIDOS_POS_VENCIMENTO,
        )
    ):
        return False

    # Reativacoes, renovacoes e reagendamento
    # ampliam novamente a operacao.
    for (
        metodo_regra,
        expressao,
    ) in MUTACOES_ESPECIFICAS_BLOQUEADAS:

        if (
            metodo_normalizado
            == metodo_regra
            and expressao.fullmatch(
                caminho_normalizado
            )
            is not None
        ):
            return True

    # Todo POST em modulo operacional inicia ou
    # amplia atividade, salvo excecoes anteriores.
    if metodo_normalizado == "POST":

        for prefixo in PREFIXOS_POST_OPERACIONAL:

            if _esta_no_prefixo(
                caminho_normalizado,
                prefixo,
            ):
                return True

    # PUT/PATCH/DELETE restantes tratam registros
    # existentes e permanecem disponiveis.
    return False


def validar_operacao_interna_saas(
    db: Session,
    barbearia_id: int,
    request: Request,
    *,
    agora: datetime | None = None,
):
    """
    Aplica a trava comercial apenas quando:

    1. a rota representa nova atividade operacional;
    2. a elegibilidade SaaS esta em SEM_ACESSO.
    """

    metodo = request.method
    caminho = request.url.path

    if not operacao_exige_direito_saas(
        metodo,
        caminho,
    ):
        return None

    elegibilidade = (
        avaliar_elegibilidade_publica_saas(
            db,
            barbearia_id,
            agora=agora,
        )
    )

    if (
        elegibilidade.situacao
        == SITUACAO_SEM_ACESSO
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=MENSAGEM_BLOQUEIO_SAAS,
        )

    return elegibilidade
