
from datetime import datetime
from types import SimpleNamespace

from fastapi import HTTPException

import models

from services.caixa_service import registrar_entrada_caixa
from services.comissao_service import calcular_e_registrar_comissao
from services.plano_service import (
    atualizar_status_assinatura,
    usar_plano_service,
    selecionar_plano_para_cobranca_service,
    valor_cobranca_assinatura,
    referencia_cobranca_assinatura,
    confirmar_pagamento_assinatura_service,
)
from services.estoque_service import (
    devolver_estoque,
    obter_produto_para_movimentacao,
)

from auth.tenant import (
    buscar_da_barbearia,
    obter_barbearia_id
)

def _validar_acesso_barbeiro_comanda(
    usuario_logado,
    comanda,
):
    """
    Barbeiro operacional só pode atuar em sua própria comanda.
    Admin, gerente, recepção e superadmin contextual seguem as permissões
    da rota.
    """
    perfil = (getattr(usuario_logado, "perfil", "") or "").lower()

    if perfil != "barbeiro":
        return

    barbeiro_id = getattr(usuario_logado, "barbeiro_id", None)

    if barbeiro_id is None or comanda.barbeiro_id != barbeiro_id:
        raise HTTPException(
            status_code=403,
            detail="O barbeiro só pode operar suas próprias comandas.",
        )


def _buscar_comanda_para_operacao(
    db,
    comanda_id: int,
    usuario_logado,
):
    """
    Faz leitura com lock pessimista no PostgreSQL para serializar
    fechamento, cancelamento e remoção de itens.
    """
    barbearia_id = obter_barbearia_id(usuario_logado)

    comanda = (
        db.query(models.Comanda)
        .filter(
            models.Comanda.id == comanda_id,
            models.Comanda.barbearia_id == barbearia_id,
        )
        .with_for_update()
        .first()
    )

    if comanda is None:
        raise HTTPException(
            status_code=404,
            detail="Comanda não encontrada.",
        )

    _validar_acesso_barbeiro_comanda(
        usuario_logado,
        comanda,
    )

    return comanda


def calcular_total_devido_comanda(itens):
    """
    Calcula somente o valor que deve ser pago no fechamento.

    Serviços utilizados pelo plano não entram no total devido.
    Produtos e serviços avulsos entram normalmente.
    """
    return sum(
        item.subtotal or 0
        for item in itens
        if not (
            item.tipo == "servico"
            and item.pago_com_plano is True
        )
    )


def adicionar_mensalidade_plano_comanda_service(
    db, comanda_id: int, assinatura_id: int, usuario_logado
):
    comanda = _buscar_comanda_para_operacao(db, comanda_id, usuario_logado)

    if comanda.status != "aberta":
        raise HTTPException(status_code=400, detail="A comanda não está aberta.")
    if comanda.cliente_id is None:
        raise HTTPException(status_code=400, detail="Vincule um cliente à comanda.")

    validar_sem_pagamento_online_pendente(
        db, comanda.id, comanda.barbearia_id
    )

    assinatura = (
        db.query(models.AssinaturaCliente)
        .filter(
            models.AssinaturaCliente.id == assinatura_id,
            models.AssinaturaCliente.barbearia_id == comanda.barbearia_id,
            models.AssinaturaCliente.cliente_id == comanda.cliente_id,
        )
        .first()
    )
    if assinatura is None:
        raise HTTPException(status_code=404, detail="Assinatura do cliente não encontrada.")

    atualizar_status_assinatura(assinatura)
    status = (assinatura.status or "").upper()
    status_pagamento = (assinatura.status_pagamento or "").upper()
    if status in {"CANCELADO", "ENCERRADO"}:
        raise HTTPException(
            status_code=400,
            detail="Assinatura cancelada ou encerrada não pode ser cobrada pela comanda.",
        )
    if status == "ATIVO" and status_pagamento == "PAGO":
        raise HTTPException(status_code=409, detail="A assinatura não possui mensalidade pendente.")

    plano = selecionar_plano_para_cobranca_service(db, assinatura, usuario_logado)
    referencia = referencia_cobranca_assinatura(assinatura, datetime.now())
    valor = round(float(valor_cobranca_assinatura(assinatura, plano.valor)), 2)
    if valor <= 0:
        raise HTTPException(status_code=400, detail="A mensalidade não possui valor para cobrança.")

    item_existente = (
        db.query(models.ItemComanda)
        .join(models.Comanda, models.Comanda.id == models.ItemComanda.comanda_id)
        .filter(
            models.ItemComanda.assinatura_id == assinatura.id,
            models.ItemComanda.referencia_mes == referencia,
            models.ItemComanda.tipo == "mensalidade_plano",
            models.Comanda.status == "aberta",
        )
        .first()
    )
    if item_existente:
        raise HTTPException(
            status_code=409,
            detail=f"A mensalidade {referencia} já está em uma comanda aberta.",
        )

    item = models.ItemComanda(
        comanda_id=comanda.id,
        tipo="mensalidade_plano",
        descricao=f"Mensalidade {plano.nome} - {referencia}",
        quantidade=1,
        valor_unitario=valor,
        subtotal=valor,
        assinatura_id=assinatura.id,
        plano_id=plano.id,
        referencia_mes=referencia,
        pago_com_plano=False,
    )
    db.add(item)
    comanda.total = round(float(comanda.total or 0) + valor, 2)
    db.commit()
    db.refresh(item)
    return item


def obter_assinatura_disponivel_comanda_service(
    db,
    comanda_id: int,
    usuario_logado
):
    barbearia_id = obter_barbearia_id(
        usuario_logado
    )

    comanda = buscar_da_barbearia(
        db=db,
        model=models.Comanda,
        registro_id=comanda_id,
        usuario=usuario_logado,
        mensagem_nao_encontrado=(
            "Comanda não encontrada."
        )
    )

    if comanda.cliente_id is None:
        return {
            "possui_assinatura": False,
            "pode_usar_plano": False,
            "motivo": (
                "A comanda não está vinculada "
                "a um cliente."
            ),
            "assinatura": None
        }

    assinaturas = (
        db.query(models.AssinaturaCliente)
        .filter(
            models.AssinaturaCliente.barbearia_id
            == barbearia_id,

            models.AssinaturaCliente.cliente_id
            == comanda.cliente_id
        )
        .order_by(
            models.AssinaturaCliente.id.desc()
        )
        .all()
    )

    if not assinaturas:
        return {
            "possui_assinatura": False,
            "pode_usar_plano": False,
            "motivo": (
                "O cliente não possui assinatura "
                "cadastrada."
            ),
            "assinatura": None
        }

    houve_alteracao = False

    for assinatura in assinaturas:
        status_anterior = assinatura.status
        pagamento_anterior = (
            assinatura.status_pagamento
        )

        atualizar_status_assinatura(
            assinatura
        )

        if (
            assinatura.status != status_anterior
            or assinatura.status_pagamento
            != pagamento_anterior
        ):
            houve_alteracao = True

    if houve_alteracao:
        db.commit()

    assinatura_disponivel = next(
        (
            assinatura
            for assinatura in assinaturas
            if assinatura.status == "ATIVO"
            and assinatura.status_pagamento == "PAGO"
        ),
        None
    )

    assinatura_exibida = (
        assinatura_disponivel
        or assinaturas[0]
    )

    plano = (
        db.query(models.Plano)
        .filter(
            models.Plano.id
            == assinatura_exibida.plano_id,

            models.Plano.barbearia_id
            == barbearia_id
        )
        .first()
    )

    servicos_permitidos_ids = [
        vinculo.servico_id
        for vinculo in (
            db.query(models.PlanoServico)
            .join(
                models.Plano,
                models.Plano.id
                == models.PlanoServico.plano_id
            )
            .filter(
                models.PlanoServico.plano_id
                == assinatura_exibida.plano_id,

                models.Plano.barbearia_id
                == barbearia_id
            )
            .all()
        )
    ]

    pode_usar = (
        assinatura_disponivel is not None
        and assinatura_disponivel.usos_disponiveis
        is not None
        and assinatura_disponivel.usos_disponiveis > 0
    )

    if pode_usar:
        motivo = None

    elif assinatura_disponivel is not None:
        motivo = (
            "O plano não possui usos disponíveis."
        )

    else:
        motivo = (
            "Assinatura indisponível para uso. "
            f"Status: {assinatura_exibida.status}. "
            "Pagamento: "
            f"{assinatura_exibida.status_pagamento}."
        )

    status_assinatura = (assinatura_exibida.status or "").upper()
    status_pagamento = (assinatura_exibida.status_pagamento or "").upper()
    pode_pagar_mensalidade = (
        plano is not None
        and status_assinatura not in {"CANCELADO", "ENCERRADO"}
        and not (
            status_assinatura == "ATIVO"
            and status_pagamento == "PAGO"
        )
    )
    referencia_mensalidade = referencia_cobranca_assinatura(
        assinatura_exibida, datetime.now()
    )
    valor_mensalidade = (
        round(float(valor_cobranca_assinatura(assinatura_exibida, plano.valor)), 2)
        if plano is not None
        else 0
    )

    return {
        "possui_assinatura": True,
        "pode_usar_plano": pode_usar,
        "pode_pagar_mensalidade": pode_pagar_mensalidade,
        "valor_mensalidade": valor_mensalidade,
        "referencia_mensalidade": referencia_mensalidade,
        "motivo": motivo,
        "assinatura": {
            "id": assinatura_exibida.id,
            "cliente_id": (
                assinatura_exibida.cliente_id
            ),
            "plano_id": (
                assinatura_exibida.plano_id
            ),
            "plano_nome": (
                plano.nome
                if plano
                else None
            ),
            "status": (
                assinatura_exibida.status
            ),
            "status_pagamento": (
                assinatura_exibida.status_pagamento
            ),
            "usos_disponiveis": (
                assinatura_exibida.usos_disponiveis
            ),
            "data_proximo_vencimento": (
                assinatura_exibida
                .data_proximo_vencimento
            ),
            "servicos_permitidos_ids": (
                servicos_permitidos_ids
            )
        }
    }

def usar_plano_em_item_comanda_service(
    db,
    comanda_id: int,
    item_id: int,
    assinatura_id: int,
    usuario_logado
):
    try:
        comanda = _buscar_comanda_para_operacao(
            db=db,
            comanda_id=comanda_id,
            usuario_logado=usuario_logado,
        )

        if comanda.status != "aberta":
            raise HTTPException(
                status_code=404,
                detail=(
                    "Comanda não encontrada ou já fechada."
                )
            )

        if comanda.cliente_id is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "A comanda precisa estar vinculada "
                    "a um cliente para utilizar o plano."
                )
            )

        item = (
            db.query(models.ItemComanda)
            .filter(
                models.ItemComanda.id == item_id,
                models.ItemComanda.comanda_id
                == comanda.id
            )
            .first()
        )

        if not item:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Item não encontrado nesta comanda."
                )
            )

        if item.tipo != "servico":
            raise HTTPException(
                status_code=400,
                detail=(
                    "Somente serviços podem ser "
                    "utilizados pelo plano."
                )
            )

        if item.servico_id is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "O item não possui um serviço "
                    "vinculado."
                )
            )

        if item.quantidade != 1:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Para utilizar o plano, o serviço "
                    "deve ser lançado com quantidade 1."
                )
            )

        if item.pago_com_plano is True:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Este serviço já foi utilizado "
                    "pelo plano."
                )
            )

        if item.uso_plano_id is not None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Este item já possui um uso de "
                    "plano registrado."
                )
            )

        assinatura = buscar_da_barbearia(
            db=db,
            model=models.AssinaturaCliente,
            registro_id=assinatura_id,
            usuario=usuario_logado,
            mensagem_nao_encontrado=(
                "Assinatura não encontrada."
            )
        )

        if (
            assinatura.barbearia_id
            != comanda.barbearia_id
        ):
            raise HTTPException(
                status_code=404,
                detail=(
                    "Comanda ou assinatura "
                    "não encontrada."
                )
            )

        if (
            assinatura.cliente_id
            != comanda.cliente_id
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "A assinatura não pertence ao "
                    "cliente desta comanda."
                )
            )

        dados_uso = SimpleNamespace(
            assinatura_id=assinatura.id,
            comanda_id=comanda.id,
            servico_id=item.servico_id
        )

        uso = usar_plano_service(
            db=db,
            dados=dados_uso,
            usuario_logado=usuario_logado,
            realizar_commit=False
        )

        item.pago_com_plano = True
        item.uso_plano_id = uso.id

        db.flush()

        itens = (
            db.query(models.ItemComanda)
            .filter(
                models.ItemComanda.comanda_id
                == comanda.id
            )
            .all()
        )

        comanda.total = (
            calcular_total_devido_comanda(
                itens
            )
        )

        db.commit()

        db.refresh(item)
        db.refresh(comanda)
        db.refresh(assinatura)
        db.refresh(uso)

        return {
            "mensagem": (
                "Serviço utilizado pelo plano "
                "com sucesso."
            ),
            "comanda_id": comanda.id,
            "item_id": item.id,
            "uso_plano_id": uso.id,
            "assinatura_id": assinatura.id,
            "plano_id": assinatura.plano_id,
            "usos_disponiveis": (
                assinatura.usos_disponiveis
            ),
            "total_comanda": comanda.total
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as erro:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Erro ao utilizar plano na comanda: "
                f"{str(erro)}"
            )
        )


def fechar_comanda_service(
    db,
    comanda_id: int,
    forma_pagamento: str,
    usuario_logado,
    ignorar_cobranca_online_pendente: bool = False,
    realizar_commit: bool = True,
):
    try:
        comanda = _buscar_comanda_para_operacao(
            db=db,
            comanda_id=comanda_id,
            usuario_logado=usuario_logado,
        )

        if comanda.status != "aberta":
            raise HTTPException(
                status_code=404,
                detail=(
                    "Comanda não encontrada ou já fechada."
                )
            )

        if not ignorar_cobranca_online_pendente:
            pendente = (
                db.query(models.MercadoPagoCobranca)
                .filter(
                    models.MercadoPagoCobranca.barbearia_id == comanda.barbearia_id,
                    models.MercadoPagoCobranca.origem_negocio == "COMANDA",
                    models.MercadoPagoCobranca.origem_id == comanda.id,
                    models.MercadoPagoCobranca.processado.is_(False),
                    models.MercadoPagoCobranca.status.in_([
                        "pending", "action_required", "in_process", "created"
                    ]),
                )
                .first()
            )
            if pendente:
                raise HTTPException(
                    status_code=409,
                    detail="Esta comanda possui pagamento online pendente. Aguarde a confirmação ou o vencimento da cobrança.",
                )

        itens = (
            db.query(models.ItemComanda)
            .filter(
                models.ItemComanda.comanda_id
                == comanda.id
            )
            .all()
        )

        if not itens:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Não é possível fechar uma "
                    "comanda sem itens."
                )
            )

        total_devido = (
            calcular_total_devido_comanda(
                itens
            )
        )

        itens_mensalidade = [
            item for item in itens
            if item.tipo == "mensalidade_plano"
        ]
        total_mensalidades = sum(
            float(item.subtotal or 0)
            for item in itens_mensalidade
        )
        total_operacional = round(
            float(total_devido) - total_mensalidades,
            2,
        )

        for item in itens_mensalidade:
            assinatura = db.query(models.AssinaturaCliente).filter(
                models.AssinaturaCliente.id == item.assinatura_id,
                models.AssinaturaCliente.barbearia_id == comanda.barbearia_id,
                models.AssinaturaCliente.cliente_id == comanda.cliente_id,
            ).first()
            plano_mensalidade = db.query(models.Plano).filter(
                models.Plano.id == item.plano_id,
                models.Plano.barbearia_id == comanda.barbearia_id,
            ).first()
            if assinatura is None or plano_mensalidade is None:
                raise HTTPException(
                    status_code=409,
                    detail="Mensalidade da comanda sem assinatura ou plano válido.",
                )
            confirmar_pagamento_assinatura_service(
                db=db,
                assinatura=assinatura,
                plano=plano_mensalidade,
                forma_pagamento=(forma_pagamento or "PIX").upper(),
                observacoes=f"Pagamento pela comanda #{comanda.id}",
                usuario_id=getattr(usuario_logado, "id", None),
                referencia_mes=item.referencia_mes,
                realizar_commit=False,
                valor_pagamento=float(item.subtotal or 0),
                aceitar_plano_cobrado=True,
            )

        possui_item_plano = any(
            item.tipo == "servico"
            and item.pago_com_plano is True
            for item in itens
        )

        if (
            total_devido > 0
            and not forma_pagamento
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Informe a forma de pagamento "
                    "da comanda."
                )
            )

        comanda.total = total_devido

        if (
            total_devido == 0
            and possui_item_plano
        ):
            comanda.forma_pagamento = "plano"

        elif possui_item_plano:
            comanda.forma_pagamento = (
                f"plano + {forma_pagamento}"
            )

        else:
            comanda.forma_pagamento = (
                forma_pagamento
            )

        comanda.status = "fechada"
        comanda.data_fechamento = (
            datetime.now()
        )

        if total_operacional > 0:
            registrar_entrada_caixa(
                db=db,
                descricao=(
                    f"Comanda #{comanda.id}"
                ),
                valor=total_operacional,
                forma_pagamento=forma_pagamento,
                barbearia_id=comanda.barbearia_id,
                origem="COMANDA",
                referencia_id=comanda.id,
                usuario_id=getattr(usuario_logado, "id", None),
            )

        valor_comissao = 0.0

        if comanda.barbeiro_id is not None:
            valor_comissao = (
                calcular_e_registrar_comissao(
                    db=db,
                    barbeiro_id=comanda.barbeiro_id,
                    comanda_id=comanda.id,
                    itens=itens,
                    usuario_logado=usuario_logado
                )
            )

        if realizar_commit:
            db.commit()
        else:
            db.flush()
        db.refresh(comanda)

        return {
            "mensagem": (
                "Comanda fechada com sucesso."
            ),
            "comanda_id": comanda.id,
            "total": total_devido,
            "forma_pagamento": (
                comanda.forma_pagamento
            ),
            "possui_item_plano": (
                possui_item_plano
            ),
            "comissao": valor_comissao
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as erro:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Erro ao fechar comanda: "
                f"{str(erro)}"
            )
        )


def fechar_comanda_pagamento_online_service(
    db,
    comanda_id: int,
    barbearia_id: int,
    forma_pagamento: str,
):
    """Fecha a comanda dentro da transação do webhook do Mercado Pago."""
    from types import SimpleNamespace

    contexto = SimpleNamespace(
        id=None,
        barbearia_id=barbearia_id,
        perfil="admin",
    )
    return fechar_comanda_service(
        db=db,
        comanda_id=comanda_id,
        forma_pagamento=forma_pagamento,
        usuario_logado=contexto,
        ignorar_cobranca_online_pendente=True,
        realizar_commit=False,
    )


def validar_sem_pagamento_online_pendente(db, comanda_id: int, barbearia_id: int):
    pendente = (
        db.query(models.MercadoPagoCobranca)
        .filter(
            models.MercadoPagoCobranca.barbearia_id == barbearia_id,
            models.MercadoPagoCobranca.origem_negocio == "COMANDA",
            models.MercadoPagoCobranca.origem_id == comanda_id,
            models.MercadoPagoCobranca.processado.is_(False),
            models.MercadoPagoCobranca.status.in_([
                "pending", "action_required", "in_process", "created"
            ]),
        )
        .first()
    )
    if pendente:
        raise HTTPException(
            status_code=409,
            detail="A comanda possui pagamento online pendente e não pode ser alterada.",
        )


def _reverter_item_aberto(
    db,
    item,
    comanda,
):
    if item.tipo == "produto" and item.produto_id:
        produto = obter_produto_para_movimentacao(
            db,
            produto_id=item.produto_id,
            barbearia_id=comanda.barbearia_id,
        )
        devolver_estoque(
            produto,
            item.quantidade or 0,
        )

    if (
        item.tipo == "servico"
        and item.pago_com_plano
        and item.uso_plano_id
    ):
        uso = (
            db.query(models.UsoPlano)
            .filter(
                models.UsoPlano.id == item.uso_plano_id
            )
            .with_for_update()
            .first()
        )

        if uso:
            assinatura = (
                db.query(models.AssinaturaCliente)
                .filter(
                    models.AssinaturaCliente.id == uso.assinatura_id,
                    models.AssinaturaCliente.barbearia_id
                    == comanda.barbearia_id,
                )
                .with_for_update()
                .first()
            )

            if assinatura:
                assinatura.usos_disponiveis = (
                    assinatura.usos_disponiveis or 0
                ) + 1

            db.delete(uso)

        item.pago_com_plano = False
        item.uso_plano_id = None


def remover_item_comanda_service(
    db,
    comanda_id: int,
    item_id: int,
    usuario_logado,
):
    try:
        comanda = _buscar_comanda_para_operacao(
            db=db,
            comanda_id=comanda_id,
            usuario_logado=usuario_logado,
        )
        validar_sem_pagamento_online_pendente(
            db, comanda.id, comanda.barbearia_id
        )

        if (comanda.status or "").lower() != "aberta":
            raise HTTPException(
                status_code=400,
                detail="Somente comandas abertas permitem remover itens.",
            )

        item = (
            db.query(models.ItemComanda)
            .filter(
                models.ItemComanda.id == item_id,
                models.ItemComanda.comanda_id == comanda.id,
            )
            .first()
        )

        if item is None:
            raise HTTPException(
                status_code=404,
                detail="Item não encontrado nesta comanda.",
            )

        _reverter_item_aberto(
            db,
            item,
            comanda,
        )
        db.delete(item)
        db.flush()

        itens = (
            db.query(models.ItemComanda)
            .filter(
                models.ItemComanda.comanda_id == comanda.id
            )
            .all()
        )

        comanda.total = calcular_total_devido_comanda(itens)

        db.commit()
        db.refresh(comanda)

        return {
            "mensagem": "Item removido com sucesso.",
            "comanda_id": comanda.id,
            "total": comanda.total,
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as erro:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao remover item da comanda: {erro}",
        )


def cancelar_comanda_service(
    db,
    comanda_id: int,
    usuario_logado,
):
    try:
        comanda = _buscar_comanda_para_operacao(
            db=db,
            comanda_id=comanda_id,
            usuario_logado=usuario_logado,
        )
        validar_sem_pagamento_online_pendente(
            db, comanda.id, comanda.barbearia_id
        )

        if (comanda.status or "").lower() != "aberta":
            raise HTTPException(
                status_code=400,
                detail="Somente comandas abertas podem ser canceladas.",
            )

        itens = (
            db.query(models.ItemComanda)
            .filter(
                models.ItemComanda.comanda_id == comanda.id
            )
            .all()
        )

        for item in itens:
            _reverter_item_aberto(
                db,
                item,
                comanda,
            )

        comanda.status = "cancelada"
        comanda.total = 0
        comanda.forma_pagamento = None
        comanda.data_fechamento = datetime.now()

        db.commit()
        db.refresh(comanda)

        return {
            "mensagem": "Comanda cancelada com sucesso.",
            "comanda_id": comanda.id,
            "status": comanda.status,
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as erro:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao cancelar comanda: {erro}",
        )
