from datetime import datetime, timedelta

import models


STATUS_ABERTOS = ("PENDENTE", "SEM_PLANO_COMPATIVEL")


def _assinatura_ativa(db, barbearia_id):
    return (
        db.query(models.AssinaturaSaaS)
        .filter(
            models.AssinaturaSaaS.barbearia_id == barbearia_id,
            models.AssinaturaSaaS.status == "ATIVA",
        )
        .first()
    )


def _eh_teste(assinatura):
    return (
        str(getattr(assinatura, "status_pagamento", "") or "").strip().upper() == "TESTE_GRATUITO"
        or str(getattr(assinatura, "forma_pagamento", "") or "").strip().upper() == "TESTE"
    )


def _contar_ativos(db, barbearia_id):
    return (
        db.query(models.Barbeiro)
        .filter(
            models.Barbeiro.barbearia_id == barbearia_id,
            models.Barbeiro.ativo.is_(True),
        )
        .count()
    )


def _menor_plano_compativel(db, plano_origem, quantidade):
    return (
        db.query(models.PlanoSaaS)
        .filter(
            models.PlanoSaaS.ativo.is_(True),
            models.PlanoSaaS.periodo_meses == plano_origem.periodo_meses,
            models.PlanoSaaS.limite_barbeiros >= quantidade,
        )
        .order_by(models.PlanoSaaS.limite_barbeiros.asc(), models.PlanoSaaS.id.asc())
        .first()
    )


def reconciliar_adequacao_plano_saas(db, barbearia_id, barbeiro_evento_id=None):
    """Cria, atualiza ou cancela a adequacao de capacidade. V4.7.2A nao cobra nem bloqueia."""
    (
        db.query(models.Barbearia)
        .filter(models.Barbearia.id == barbearia_id)
        .with_for_update()
        .first()
    )

    assinatura = _assinatura_ativa(db, barbearia_id)
    if assinatura is None or _eh_teste(assinatura):
        return None

    plano = db.query(models.PlanoSaaS).filter(models.PlanoSaaS.id == assinatura.plano_id).first()
    if plano is None:
        return None

    ativos = _contar_ativos(db, barbearia_id)
    limite = max(1, int(plano.limite_barbeiros or 1))
    agora = datetime.now()

    adequacao = (
        db.query(models.AdequacaoPlanoSaaS)
        .filter(
            models.AdequacaoPlanoSaaS.barbearia_id == barbearia_id,
            models.AdequacaoPlanoSaaS.status.in_(STATUS_ABERTOS),
        )
        .order_by(models.AdequacaoPlanoSaaS.id.desc())
        .first()
    )

    if ativos <= limite:
        if adequacao is not None:
            adequacao.status = "CANCELADA_AUTOMATICAMENTE"
            adequacao.quantidade_barbeiros = ativos
            adequacao.finalizado_em = agora
            adequacao.atualizado_em = agora
            adequacao.observacao = "Equipe retornou ao limite do plano vigente antes da regularizacao."
            for item in db.query(models.AdequacaoPlanoSaaSBarbeiro).filter(models.AdequacaoPlanoSaaSBarbeiro.adequacao_id == adequacao.id).all():
                item.excedente = False
                item.bloqueado_por_plano = False
                item.bloqueado_em = None
        db.commit()
        return None

    destino = _menor_plano_compativel(db, plano, ativos)
    novo_status = "PENDENTE" if destino is not None else "SEM_PLANO_COMPATIVEL"

    if adequacao is None:
        adequacao = models.AdequacaoPlanoSaaS(
            assinatura_id=assinatura.id,
            barbearia_id=barbearia_id,
            plano_origem_id=plano.id,
            plano_destino_id=destino.id if destino else None,
            quantidade_barbeiros=ativos,
            limite_origem=limite,
            status=novo_status,
            criado_em=agora,
            atualizado_em=agora,
            prazo_regularizacao=agora + timedelta(days=7),
            observacao="Adequacao automatica aberta por excesso de barbeiros ativos.",
        )
        db.add(adequacao)
        db.flush()
    else:
        adequacao.assinatura_id = assinatura.id
        adequacao.plano_origem_id = plano.id
        adequacao.plano_destino_id = destino.id if destino else None
        adequacao.quantidade_barbeiros = ativos
        adequacao.limite_origem = limite
        adequacao.status = novo_status
        adequacao.atualizado_em = agora
        adequacao.observacao = "Adequacao recalculada conforme a equipe ativa."

    if barbeiro_evento_id is not None:
        item = (
            db.query(models.AdequacaoPlanoSaaSBarbeiro)
            .filter(
                models.AdequacaoPlanoSaaSBarbeiro.adequacao_id == adequacao.id,
                models.AdequacaoPlanoSaaSBarbeiro.barbeiro_id == barbeiro_evento_id,
            )
            .first()
        )
        if item is None:
            db.add(models.AdequacaoPlanoSaaSBarbeiro(
                adequacao_id=adequacao.id,
                barbeiro_id=barbeiro_evento_id,
                excedente=True,
                bloqueado_por_plano=False,
                incluido_em=agora,
            ))
        else:
            item.excedente = True
            item.bloqueado_por_plano = False
            item.bloqueado_em = None

    db.commit()
    db.refresh(adequacao)
    return adequacao



def _sincronizar_barbeiros_excedentes(db, adequacao, agora):
    """Marca somente profissionais excedentes ativos; preserva cadastro e historico."""
    ativos = (
        db.query(models.Barbeiro)
        .filter(
            models.Barbeiro.barbearia_id == adequacao.barbearia_id,
            models.Barbeiro.ativo.is_(True),
        )
        .count()
    )
    limite = max(1, int(adequacao.limite_origem or 1))
    quantidade_excedente = max(0, ativos - limite)

    itens = (
        db.query(models.AdequacaoPlanoSaaSBarbeiro)
        .filter(models.AdequacaoPlanoSaaSBarbeiro.adequacao_id == adequacao.id)
        .order_by(
            models.AdequacaoPlanoSaaSBarbeiro.incluido_em.asc(),
            models.AdequacaoPlanoSaaSBarbeiro.id.asc(),
        )
        .all()
    )

    candidatos = []
    for item in itens:
        barbeiro = (
            db.query(models.Barbeiro)
            .filter(
                models.Barbeiro.id == item.barbeiro_id,
                models.Barbeiro.barbearia_id == adequacao.barbearia_id,
                models.Barbeiro.ativo.is_(True),
            )
            .first()
        )
        if barbeiro is None:
            item.excedente = False
            item.bloqueado_por_plano = False
            item.bloqueado_em = None
            continue
        candidatos.append(item)

    ids_excedentes = {item.id for item in candidatos[:quantidade_excedente]}
    prazo_vencido = (
        adequacao.prazo_regularizacao is not None
        and agora >= adequacao.prazo_regularizacao
    )

    for item in candidatos:
        deve_ser_excedente = item.id in ids_excedentes
        item.excedente = deve_ser_excedente
        if deve_ser_excedente and prazo_vencido:
            if not item.bloqueado_por_plano:
                item.bloqueado_em = agora
            item.bloqueado_por_plano = True
        else:
            item.bloqueado_por_plano = False
            item.bloqueado_em = None


def avaliar_prazo_adequacao_saas(db, barbearia_id):
    """V4.7.3: aplica/limpa bloqueio operacional sem inativar o barbeiro."""
    adequacao = reconciliar_adequacao_plano_saas(
        db=db,
        barbearia_id=barbearia_id,
    )
    if adequacao is None:
        return None

    assinatura = _assinatura_ativa(db, barbearia_id)
    if assinatura is None or _eh_teste(assinatura):
        return adequacao

    agora = datetime.now()
    _sincronizar_barbeiros_excedentes(db, adequacao, agora)
    db.commit()
    db.refresh(adequacao)
    return adequacao


def barbeiro_bloqueado_por_plano(db, barbearia_id, barbeiro_id):
    avaliar_prazo_adequacao_saas(db, barbearia_id)
    return (
        db.query(models.AdequacaoPlanoSaaSBarbeiro)
        .join(
            models.AdequacaoPlanoSaaS,
            models.AdequacaoPlanoSaaS.id == models.AdequacaoPlanoSaaSBarbeiro.adequacao_id,
        )
        .filter(
            models.AdequacaoPlanoSaaS.barbearia_id == barbearia_id,
            models.AdequacaoPlanoSaaS.status.in_(STATUS_ABERTOS),
            models.AdequacaoPlanoSaaSBarbeiro.barbeiro_id == barbeiro_id,
            models.AdequacaoPlanoSaaSBarbeiro.excedente.is_(True),
            models.AdequacaoPlanoSaaSBarbeiro.bloqueado_por_plano.is_(True),
        )
        .first()
        is not None
    )


def validar_barbeiro_liberado_por_plano(db, barbearia_id, barbeiro_id):
    """Bloqueia apenas uso operacional futuro do profissional excedente."""
    if barbeiro_bloqueado_por_plano(db, barbearia_id, barbeiro_id):
        raise ValueError(
            "BARBEIRO_BLOQUEADO_POR_PLANO: Este profissional esta temporariamente indisponivel porque "
            "o limite de barbeiros do plano foi excedido e o prazo de regularizacao terminou. "
            "Regularize a assinatura para liberar este profissional."
        )
    return True


def obter_adequacao_pendente_saas(db, barbearia_id):
    """Retorna a adequacao aberta da barbearia em formato seguro para o portal interno."""
    avaliar_prazo_adequacao_saas(db, barbearia_id)
    adequacao = (
        db.query(models.AdequacaoPlanoSaaS)
        .filter(
            models.AdequacaoPlanoSaaS.barbearia_id == barbearia_id,
            models.AdequacaoPlanoSaaS.status.in_(STATUS_ABERTOS),
        )
        .order_by(models.AdequacaoPlanoSaaS.id.desc())
        .first()
    )
    if adequacao is None:
        return None

    origem = (
        db.query(models.PlanoSaaS)
        .filter(models.PlanoSaaS.id == adequacao.plano_origem_id)
        .first()
    )
    destino = None
    if adequacao.plano_destino_id:
        destino = (
            db.query(models.PlanoSaaS)
            .filter(models.PlanoSaaS.id == adequacao.plano_destino_id)
            .first()
        )

    return {
        "id": adequacao.id,
        "status": adequacao.status,
        "plano_origem_id": adequacao.plano_origem_id,
        "plano_origem_nome": origem.nome if origem else None,
        "plano_destino_id": adequacao.plano_destino_id,
        "plano_destino_nome": destino.nome if destino else None,
        "quantidade_barbeiros": adequacao.quantidade_barbeiros,
        "limite_origem": adequacao.limite_origem,
        "criado_em": adequacao.criado_em,
        "prazo_regularizacao": adequacao.prazo_regularizacao,
        "barbeiros_bloqueados": [
            item.barbeiro_id
            for item in db.query(models.AdequacaoPlanoSaaSBarbeiro).filter(
                models.AdequacaoPlanoSaaSBarbeiro.adequacao_id == adequacao.id,
                models.AdequacaoPlanoSaaSBarbeiro.bloqueado_por_plano.is_(True),
            ).all()
        ],
    }


# V474_C51_FINALIZAR_ADEQUACAO_PAGA

def external_reference_adequacao_saas(
    adequacao_id,
    tentativa=1,
):
    """
    Referencia deterministica da cobranca de adequacao.

    Compatibilidade:
    T1 -> BARBSIST-ADEQ-2
    T2 -> BARBSIST-ADEQ-2-T2
    T3 -> BARBSIST-ADEQ-2-T3
    """
    adequacao_id = int(adequacao_id)
    tentativa = int(tentativa or 1)

    if tentativa <= 1:
        return f"BARBSIST-ADEQ-{adequacao_id}"

    return (
        f"BARBSIST-ADEQ-{adequacao_id}"
        f"-T{tentativa}"
    )


# V474_C54C_FINALIZADOR_RETRY
def parse_external_reference_adequacao_saas(
    external_reference,
):
    """
    Parser estrito para referencias de adequacao.

    Retorna:
        (adequacao_id, tentativa)

    Lanca ValueError para qualquer formato invalido.
    """
    ref = str(
        external_reference or ""
    ).strip()

    prefixo = "BARBSIST-ADEQ-"

    if not ref.startswith(prefixo):
        raise ValueError(
            "REFERENCIA_NAO_E_ADEQUACAO"
        )

    restante = ref[len(prefixo):]

    if not restante:
        raise ValueError(
            "REFERENCIA_ADEQUACAO_INVALIDA"
        )

    partes = restante.split("-T")

    if len(partes) == 1:
        adequacao_txt = partes[0]
        tentativa = 1

    elif len(partes) == 2:
        adequacao_txt = partes[0]
        tentativa_txt = partes[1]

        if not tentativa_txt.isdigit():
            raise ValueError(
                "REFERENCIA_ADEQUACAO_INVALIDA"
            )

        tentativa = int(tentativa_txt)

        # T1 possui formato legado sem sufixo.
        # Sufixo somente existe a partir de T2.
        if tentativa < 2:
            raise ValueError(
                "REFERENCIA_ADEQUACAO_INVALIDA"
            )

    else:
        raise ValueError(
            "REFERENCIA_ADEQUACAO_INVALIDA"
        )

    if not adequacao_txt.isdigit():
        raise ValueError(
            "REFERENCIA_ADEQUACAO_INVALIDA"
        )

    adequacao_id = int(adequacao_txt)

    if adequacao_id <= 0:
        raise ValueError(
            "REFERENCIA_ADEQUACAO_INVALIDA"
        )

    return adequacao_id, tentativa


def finalizar_adequacao_paga_saas(
    db,
    *,
    adequacao_id,
    pagamento_id,
    momento=None,
):
    """
    V4.7.4-C5.1

    Aplica uma adequacao SaaS cujo pagamento ja foi aprovado.

    IMPORTANTE:
    - nao executa commit;
    - nao acrescenta periodo;
    - preserva vencimento;
    - nao altera Barbeiro.ativo;
    - deve participar da mesma transacao do processamento
      definitivo do pagamento.
    """

    agora = momento or datetime.now()

    adequacao = (
        db.query(models.AdequacaoPlanoSaaS)
        .filter(
            models.AdequacaoPlanoSaaS.id
            == adequacao_id
        )
        .with_for_update()
        .first()
    )

    if adequacao is None:
        raise ValueError(
            "ADEQUACAO_NAO_ENCONTRADA"
        )

    if adequacao.status != "PENDENTE":
        raise ValueError(
            "ADEQUACAO_NAO_PENDENTE"
        )

    if adequacao.plano_destino_id is None:
        raise ValueError(
            "ADEQUACAO_SEM_PLANO_DESTINO"
        )

    assinatura = (
        db.query(models.AssinaturaSaaS)
        .filter(
            models.AssinaturaSaaS.id
            == adequacao.assinatura_id,
            models.AssinaturaSaaS.barbearia_id
            == adequacao.barbearia_id,
        )
        .with_for_update()
        .first()
    )

    if assinatura is None:
        raise ValueError(
            "ASSINATURA_ADEQUACAO_NAO_ENCONTRADA"
        )

    if assinatura.plano_id != adequacao.plano_origem_id:
        raise ValueError(
            "PLANO_ATUAL_DIVERGE_DA_ORIGEM_DA_ADEQUACAO"
        )

    pagamento = (
        db.query(models.PagamentoSaaS)
        .filter(
            models.PagamentoSaaS.id
            == pagamento_id,
            models.PagamentoSaaS.assinatura_id
            == assinatura.id,
            models.PagamentoSaaS.barbearia_id
            == adequacao.barbearia_id,
            models.PagamentoSaaS.plano_id
            == adequacao.plano_destino_id,
        )
        .with_for_update()
        .first()
    )

    if pagamento is None:
        raise ValueError(
            "PAGAMENTO_ADEQUACAO_NAO_ENCONTRADO"
        )

    try:
        (
            adequacao_referencia_id,
            tentativa_pagamento,
        ) = parse_external_reference_adequacao_saas(
            pagamento.external_reference
        )
    except (TypeError, ValueError):
        raise ValueError(
            "PAGAMENTO_NAO_PERTENCE_A_ADEQUACAO"
        )

    if (
        int(adequacao_referencia_id)
        != int(adequacao.id)
        or int(tentativa_pagamento) < 1
    ):
        raise ValueError(
            "PAGAMENTO_NAO_PERTENCE_A_ADEQUACAO"
        )

    if str(pagamento.status or "").lower() != "approved":
        raise ValueError(
            "PAGAMENTO_ADEQUACAO_NAO_APROVADO"
        )

    if pagamento.processado:
        raise ValueError(
            "PAGAMENTO_ADEQUACAO_JA_PROCESSADO"
        )

    # Snapshot das datas para garantir que esta operacao
    # nunca renove nem prorrogue a assinatura.
    data_inicio_anterior = assinatura.data_inicio
    data_fim_anterior = assinatura.data_fim
    proximo_vencimento_anterior = (
        assinatura.data_proximo_vencimento
    )

    assinatura.plano_id = adequacao.plano_destino_id

    # Preservacao explicita do ciclo vigente.
    assinatura.data_inicio = data_inicio_anterior
    assinatura.data_fim = data_fim_anterior
    assinatura.data_proximo_vencimento = (
        proximo_vencimento_anterior
    )

    itens = (
        db.query(models.AdequacaoPlanoSaaSBarbeiro)
        .filter(
            models.AdequacaoPlanoSaaSBarbeiro.adequacao_id
            == adequacao.id
        )
        .all()
    )

    for item in itens:
        item.excedente = False
        item.bloqueado_por_plano = False
        item.bloqueado_em = None

    adequacao.status = "REGULARIZADA"
    adequacao.finalizado_em = agora
    adequacao.atualizado_em = agora
    adequacao.observacao = (
        "Adequacao regularizada por pagamento aprovado. "
        "Ciclo e vencimento originais preservados."
    )

    pagamento.processado = True
    pagamento.processado_em = agora

    db.flush()

    # Defesa adicional contra futura regressao.
    if assinatura.data_inicio != data_inicio_anterior:
        raise RuntimeError(
            "C51_ALTEROU_DATA_INICIO"
        )

    if assinatura.data_fim != data_fim_anterior:
        raise RuntimeError(
            "C51_ALTEROU_DATA_FIM"
        )

    if (
        assinatura.data_proximo_vencimento
        != proximo_vencimento_anterior
    ):
        raise RuntimeError(
            "C51_ALTEROU_PROXIMO_VENCIMENTO"
        )

    return {
        "status": "REGULARIZADA",
        "adequacao_id": adequacao.id,
        "pagamento_id": pagamento.id,
        "assinatura_id": assinatura.id,
        "plano_origem_id": adequacao.plano_origem_id,
        "plano_destino_id": adequacao.plano_destino_id,
        "data_inicio_preservada": (
            assinatura.data_inicio.isoformat()
            if assinatura.data_inicio
            else None
        ),
        "data_fim_preservada": (
            assinatura.data_fim.isoformat()
            if assinatura.data_fim
            else None
        ),
        "data_proximo_vencimento_preservada": (
            assinatura.data_proximo_vencimento.isoformat()
            if assinatura.data_proximo_vencimento
            else None
        ),
        "barbeiros_desbloqueados": [
            item.barbeiro_id
            for item in itens
        ],
    }

