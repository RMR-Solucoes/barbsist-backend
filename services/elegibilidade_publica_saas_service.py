from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

import models


DIAS_CARENCIA_PUBLICA = 15

SITUACAO_TESTE = "TESTE"
SITUACAO_ATIVA = "ATIVA"
SITUACAO_CARENCIA = "CARENCIA"
SITUACAO_SEM_ACESSO = "SEM_ACESSO"


@dataclass(frozen=True)
class ElegibilidadePublicaSaaS:
    situacao: str
    permite_catalogo: bool
    permite_perfil: bool
    permite_agendamento: bool
    assinatura_id: int | None = None
    plano_id: int | None = None
    teste_id: int | None = None
    fim_vigencia: datetime | None = None
    fim_carencia: datetime | None = None
    motivo: str | None = None


def _texto_normalizado(valor) -> str:
    return str(valor or "").strip().upper()


def _sem_acesso(
    assinatura=None,
    *,
    teste=None,
    fim_vigencia: datetime | None = None,
    fim_carencia: datetime | None = None,
    motivo: str,
) -> ElegibilidadePublicaSaaS:
    return ElegibilidadePublicaSaaS(
        situacao=SITUACAO_SEM_ACESSO,
        permite_catalogo=False,
        permite_perfil=False,
        permite_agendamento=False,
        assinatura_id=(
            getattr(assinatura, "id", None)
            if assinatura is not None
            else None
        ),
        plano_id=(
            getattr(assinatura, "plano_id", None)
            if assinatura is not None
            else None
        ),
        teste_id=(
            getattr(teste, "id", None)
            if teste is not None
            else None
        ),
        fim_vigencia=fim_vigencia,
        fim_carencia=fim_carencia,
        motivo=motivo,
    )


def _agora_compativel(
    referencia: datetime,
    agora: datetime | None,
) -> datetime:
    if agora is None:
        if referencia.tzinfo is not None:
            return datetime.now(
                tz=referencia.tzinfo
            )

        return datetime.now()

    if (
        referencia.tzinfo is None
        and agora.tzinfo is not None
    ):
        return agora.replace(tzinfo=None)

    if (
        referencia.tzinfo is not None
        and agora.tzinfo is None
    ):
        return agora.replace(
            tzinfo=referencia.tzinfo
        )

    return agora


def avaliar_assinatura_publica_saas(
    assinatura,
    *,
    agora: datetime | None = None,
) -> ElegibilidadePublicaSaaS:
    """
    Avalia assinatura SaaS paga/manual.

    Mantem compatibilidade temporaria com o modelo
    antigo em que TESTE_GRATUITO ficava dentro de
    assinaturas_saas.
    """

    if assinatura is None:
        return _sem_acesso(
            motivo="SEM_ASSINATURA_SAAS",
        )

    status = _texto_normalizado(
        getattr(
            assinatura,
            "status",
            None,
        )
    )

    status_pagamento = _texto_normalizado(
        getattr(
            assinatura,
            "status_pagamento",
            None,
        )
    )

    forma_pagamento = _texto_normalizado(
        getattr(
            assinatura,
            "forma_pagamento",
            None,
        )
    )

    if status != "ATIVA":
        motivo_bloqueio = str(
            getattr(
                assinatura,
                "motivo_bloqueio",
                None,
            )
            or ""
        ).strip()

        motivo = "ASSINATURA_NAO_ATIVA"

        if motivo_bloqueio:
            motivo = (
                f"{motivo}: "
                f"{motivo_bloqueio}"
            )

        return _sem_acesso(
            assinatura,
            motivo=motivo,
        )

    # Compatibilidade com testes antigos.
    eh_teste_legado = (
        status_pagamento == "TESTE_GRATUITO"
        or forma_pagamento == "TESTE"
    )

    eh_paga = (
        status_pagamento == "PAGO"
    )

    eh_liberacao_manual = (
        status_pagamento
        == "LIBERADO_MANUAL"
        and bool(
            getattr(
                assinatura,
                "liberado_manual",
                False,
            )
        )
    )

    if not (
        eh_teste_legado
        or eh_paga
        or eh_liberacao_manual
    ):
        return _sem_acesso(
            assinatura,
            motivo=(
                "STATUS_PAGAMENTO_"
                "SEM_DIREITO_PUBLICO"
            ),
        )

    fim_vigencia = (
        getattr(
            assinatura,
            "data_proximo_vencimento",
            None,
        )
        or getattr(
            assinatura,
            "data_fim",
            None,
        )
    )

    if fim_vigencia is None:
        return _sem_acesso(
            assinatura,
            motivo="VIGENCIA_NAO_DEFINIDA",
        )

    agora_real = _agora_compativel(
        fim_vigencia,
        agora,
    )

    fim_carencia = (
        fim_vigencia
        + timedelta(
            days=DIAS_CARENCIA_PUBLICA
        )
    )

    if agora_real <= fim_vigencia:
        if eh_teste_legado:
            situacao = SITUACAO_TESTE
            motivo = "TESTE_LEGADO_ATIVO"

        elif eh_liberacao_manual:
            situacao = SITUACAO_ATIVA
            motivo = (
                "LIBERACAO_MANUAL_ATIVA"
            )

        else:
            situacao = SITUACAO_ATIVA
            motivo = (
                "ASSINATURA_PAGA_ATIVA"
            )

        return ElegibilidadePublicaSaaS(
            situacao=situacao,
            permite_catalogo=True,
            permite_perfil=True,
            permite_agendamento=True,
            assinatura_id=getattr(
                assinatura,
                "id",
                None,
            ),
            plano_id=getattr(
                assinatura,
                "plano_id",
                None,
            ),
            teste_id=None,
            fim_vigencia=fim_vigencia,
            fim_carencia=fim_carencia,
            motivo=motivo,
        )

    if agora_real <= fim_carencia:
        return ElegibilidadePublicaSaaS(
            situacao=SITUACAO_CARENCIA,
            permite_catalogo=True,
            permite_perfil=True,
            permite_agendamento=True,
            assinatura_id=getattr(
                assinatura,
                "id",
                None,
            ),
            plano_id=getattr(
                assinatura,
                "plano_id",
                None,
            ),
            teste_id=None,
            fim_vigencia=fim_vigencia,
            fim_carencia=fim_carencia,
            motivo="CARENCIA_15_DIAS",
        )

    return _sem_acesso(
        assinatura,
        fim_vigencia=fim_vigencia,
        fim_carencia=fim_carencia,
        motivo="CARENCIA_EXPIRADA",
    )


def avaliar_teste_gratuito_publico(
    teste,
    *,
    agora: datetime | None = None,
) -> ElegibilidadePublicaSaaS:
    """
    Avalia o novo teste gratuito independente
    de assinatura/plano comercial.
    """

    if teste is None:
        return _sem_acesso(
            motivo="SEM_TESTE_GRATUITO",
        )

    status_teste = _texto_normalizado(
        getattr(
            teste,
            "status",
            None,
        )
        or "ATIVO"
    )

    if status_teste != "ATIVO":
        return _sem_acesso(
            teste=teste,
            motivo=(
                "TESTE_GRATUITO_"
                + status_teste
            ),
        )

    fim_vigencia = getattr(
        teste,
        "data_fim",
        None,
    )

    if fim_vigencia is None:
        return _sem_acesso(
            teste=teste,
            motivo="TESTE_SEM_DATA_FIM",
        )

    agora_real = _agora_compativel(
        fim_vigencia,
        agora,
    )

    data_inicio = getattr(
        teste,
        "data_inicio",
        None,
    )

    if data_inicio is not None:
        inicio_compativel = data_inicio

        if (
            inicio_compativel.tzinfo is None
            and agora_real.tzinfo is not None
        ):
            inicio_compativel = (
                inicio_compativel.replace(
                    tzinfo=agora_real.tzinfo
                )
            )

        elif (
            inicio_compativel.tzinfo is not None
            and agora_real.tzinfo is None
        ):
            inicio_compativel = (
                inicio_compativel.replace(
                    tzinfo=None
                )
            )

        if agora_real < inicio_compativel:
            return _sem_acesso(
                teste=teste,
                fim_vigencia=fim_vigencia,
                motivo="TESTE_AINDA_NAO_INICIADO",
            )

    fim_carencia = (
        fim_vigencia
        + timedelta(
            days=DIAS_CARENCIA_PUBLICA
        )
    )

    if agora_real <= fim_vigencia:
        return ElegibilidadePublicaSaaS(
            situacao=SITUACAO_TESTE,
            permite_catalogo=True,
            permite_perfil=True,
            permite_agendamento=True,
            assinatura_id=None,
            plano_id=None,
            teste_id=getattr(
                teste,
                "id",
                None,
            ),
            fim_vigencia=fim_vigencia,
            fim_carencia=fim_carencia,
            motivo="TESTE_GRATUITO_ATIVO",
        )

    if agora_real <= fim_carencia:
        return ElegibilidadePublicaSaaS(
            situacao=SITUACAO_CARENCIA,
            permite_catalogo=True,
            permite_perfil=True,
            permite_agendamento=True,
            assinatura_id=None,
            plano_id=None,
            teste_id=getattr(
                teste,
                "id",
                None,
            ),
            fim_vigencia=fim_vigencia,
            fim_carencia=fim_carencia,
            motivo=(
                "CARENCIA_TESTE_GRATUITO_"
                "15_DIAS"
            ),
        )

    return _sem_acesso(
        teste=teste,
        fim_vigencia=fim_vigencia,
        fim_carencia=fim_carencia,
        motivo="TESTE_GRATUITO_ENCERRADO",
    )


def avaliar_direito_publico_saas(
    assinatura,
    teste,
    *,
    agora: datetime | None = None,
) -> ElegibilidadePublicaSaaS:
    """
    Ordem de prioridade:

    1. bloqueio comercial explicito;
    2. assinatura paga/manual/teste legado com direito;
    3. novo teste gratuito independente;
    4. estado sem acesso.
    """

    resultado_assinatura = (
        avaliar_assinatura_publica_saas(
            assinatura,
            agora=agora,
        )
    )

    if assinatura is not None:
        status = _texto_normalizado(
            getattr(
                assinatura,
                "status",
                None,
            )
        )

        status_pagamento = (
            _texto_normalizado(
                getattr(
                    assinatura,
                    "status_pagamento",
                    None,
                )
            )
        )

        bloqueio_explicito = (
            status == "BLOQUEADA"
            or status_pagamento == "BLOQUEADA"
        )

        if bloqueio_explicito:
            return resultado_assinatura

        if (
            resultado_assinatura.permite_catalogo
            or resultado_assinatura.permite_perfil
            or resultado_assinatura.permite_agendamento
        ):
            return resultado_assinatura

    resultado_teste = (
        avaliar_teste_gratuito_publico(
            teste,
            agora=agora,
        )
    )

    if (
        resultado_teste.permite_catalogo
        or resultado_teste.permite_perfil
        or resultado_teste.permite_agendamento
    ):
        return resultado_teste

    # Se existiu um teste novo, preserva o motivo
    # de encerramento para diagnostico.
    if teste is not None:
        return resultado_teste

    if assinatura is not None:
        return resultado_assinatura

    return _sem_acesso(
        motivo=(
            "SEM_ASSINATURA_OU_"
            "TESTE_GRATUITO"
        ),
    )


def avaliar_elegibilidade_publica_saas(
    db: Session,
    barbearia_id: int,
    *,
    agora: datetime | None = None,
) -> ElegibilidadePublicaSaaS:
    assinatura = (
        db.query(models.AssinaturaSaaS)
        .filter(
            models.AssinaturaSaaS.barbearia_id
            == barbearia_id
        )
        .first()
    )

    teste = (
        db.query(models.TesteGratuitoSaaS)
        .filter(
            models.TesteGratuitoSaaS.barbearia_id
            == barbearia_id
        )
        .first()
    )

    return avaliar_direito_publico_saas(
        assinatura,
        teste,
        agora=agora,
    )


def mapear_elegibilidades_publicas_saas(
    db: Session,
    barbearia_ids,
    *,
    agora: datetime | None = None,
) -> dict[int, ElegibilidadePublicaSaaS]:

    ids = sorted(
        {
            int(barbearia_id)
            for barbearia_id in barbearia_ids
            if barbearia_id is not None
        }
    )

    if not ids:
        return {}

    assinaturas = (
        db.query(models.AssinaturaSaaS)
        .filter(
            models.AssinaturaSaaS.barbearia_id.in_(
                ids
            )
        )
        .all()
    )

    testes = (
        db.query(models.TesteGratuitoSaaS)
        .filter(
            models.TesteGratuitoSaaS.barbearia_id.in_(
                ids
            )
        )
        .all()
    )

    assinaturas_por_barbearia = {
        assinatura.barbearia_id: assinatura
        for assinatura in assinaturas
    }

    testes_por_barbearia = {
        teste.barbearia_id: teste
        for teste in testes
        if teste.barbearia_id is not None
    }

    return {
        barbearia_id: avaliar_direito_publico_saas(
            assinaturas_por_barbearia.get(
                barbearia_id
            ),
            testes_por_barbearia.get(
                barbearia_id
            ),
            agora=agora,
        )
        for barbearia_id in ids
    }