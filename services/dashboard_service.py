from __future__ import annotations

from collections import defaultdict
# DASHBOARD_PIX_NORMALIZADO_M6
from datetime import date, datetime, time, timedelta

from fastapi import HTTPException
from sqlalchemy import func

import models
from auth.tenant import obter_barbearia_id
from services.financeiro_service import dashboard_financeiro_service


PERIODOS_VALIDOS = {"hoje", "semana", "mes", "ano", "personalizado"}
DIAS_SEMANA = ("Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom")
MESES = ("", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
         "Jul", "Ago", "Set", "Out", "Nov", "Dez")


def _limites(data_inicio: date, data_fim: date):
    inicio = datetime.combine(data_inicio, time.min)
    fim = datetime.combine(data_fim + timedelta(days=1), time.min)
    return inicio, fim


def _resolver_periodo(periodo, data_inicio, data_fim):
    hoje = date.today()
    periodo = (periodo or "mes").strip().lower()

    if periodo not in PERIODOS_VALIDOS:
        raise HTTPException(
            status_code=400,
            detail="periodo deve ser hoje, semana, mes, ano ou personalizado.",
        )

    if periodo == "hoje":
        inicio = fim = hoje
    elif periodo == "semana":
        inicio = hoje - timedelta(days=hoje.weekday())
        fim = hoje
    elif periodo == "mes":
        inicio = hoje.replace(day=1)
        fim = hoje
    elif periodo == "ano":
        inicio = hoje.replace(month=1, day=1)
        fim = hoje
    else:
        if data_inicio is None or data_fim is None:
            raise HTTPException(
                status_code=400,
                detail="Informe data_inicio e data_fim para o periodo personalizado.",
            )
        inicio, fim = data_inicio, data_fim

    if inicio > fim:
        raise HTTPException(
            status_code=400,
            detail="data_inicio nao pode ser posterior a data_fim.",
        )

    dias = (fim - inicio).days + 1
    if periodo == "hoje" or dias == 1:
        granularidade = "hora"
    elif periodo in {"semana", "mes"}:
        granularidade = "dia"
    elif periodo == "ano":
        granularidade = "mes"
    elif dias <= 62:
        granularidade = "dia"
    elif dias <= 730:
        granularidade = "mes"
    else:
        granularidade = "ano"

    return periodo, inicio, fim, granularidade


def _periodos_resumo():
    hoje = date.today()
    return {
        "hoje": (hoje, hoje),
        "semana": (hoje - timedelta(days=hoje.weekday()), hoje),
        "mes": (hoje.replace(day=1), hoje),
        "ano": (hoje.replace(month=1, day=1), hoje),
    }


def _contar_atendimentos(db, barbearia_id, inicio, fim):
    inicio_dt, fim_dt = _limites(inicio, fim)
    return int(
        db.query(func.count(func.distinct(models.Comanda.id)))
        .join(
            models.ItemComanda,
            models.ItemComanda.comanda_id == models.Comanda.id,
        )
        .filter(
            models.Comanda.barbearia_id == barbearia_id,
            func.lower(models.Comanda.status) == "fechada",
            models.Comanda.data_fechamento >= inicio_dt,
            models.Comanda.data_fechamento < fim_dt,
            func.lower(models.ItemComanda.tipo) == "servico",
        )
        .scalar()
        or 0
    )


def _quantidade_servicos(db, barbearia_id, inicio, fim):
    inicio_dt, fim_dt = _limites(inicio, fim)
    return int(
        db.query(func.coalesce(func.sum(models.ItemComanda.quantidade), 0))
        .join(
            models.Comanda,
            models.Comanda.id == models.ItemComanda.comanda_id,
        )
        .filter(
            models.Comanda.barbearia_id == barbearia_id,
            func.lower(models.Comanda.status) == "fechada",
            models.Comanda.data_fechamento >= inicio_dt,
            models.Comanda.data_fechamento < fim_dt,
            func.lower(models.ItemComanda.tipo) == "servico",
        )
        .scalar()
        or 0
    )


def _resumo_estoque(db, barbearia_id):
    base = db.query(models.Produto).filter(
        models.Produto.barbearia_id == barbearia_id,
        models.Produto.ativo.is_(True),
    )

    ativos = base.count()
    sem = base.filter(func.coalesce(models.Produto.estoque, 0) <= 0).count()
    baixo = base.filter(
        func.coalesce(models.Produto.estoque, 0) > 0,
        func.coalesce(models.Produto.estoque, 0)
        <= func.coalesce(models.Produto.estoque_minimo, 2),
    ).count()

    valor_custo = float(
        db.query(
            func.coalesce(
                func.sum(
                    func.coalesce(models.Produto.preco_custo, 0)
                    * func.coalesce(models.Produto.estoque, 0)
                ),
                0,
            )
        )
        .filter(
            models.Produto.barbearia_id == barbearia_id,
            models.Produto.ativo.is_(True),
        )
        .scalar()
        or 0
    )

    alertas = (
        base.filter(
            func.coalesce(models.Produto.estoque, 0)
            <= func.coalesce(models.Produto.estoque_minimo, 2)
        )
        .order_by(models.Produto.estoque.asc(), models.Produto.nome.asc())
        .limit(10)
        .all()
    )

    return {
        "produtos_ativos": int(ativos),
        "sem_estoque": int(sem),
        "estoque_baixo": int(baixo),
        "valor_custo": valor_custo,
        "alertas": [
            {
                "produto_id": p.id,
                "nome": p.nome,
                "estoque": int(p.estoque or 0),
                "estoque_minimo": int(p.estoque_minimo or 0),
                "status": "SEM_ESTOQUE" if int(p.estoque or 0) <= 0 else "BAIXO",
            }
            for p in alertas
        ],
    }


def _buckets(inicio, fim, granularidade):
    if granularidade == "hora":
        return [{"chave": f"{h:02d}", "rotulo": f"{h:02d}h"} for h in range(24)]

    resultado = []
    if granularidade == "dia":
        atual = inicio
        while atual <= fim:
            resultado.append({
                "chave": atual.isoformat(),
                "rotulo": f"{DIAS_SEMANA[atual.weekday()]} {atual.strftime('%d/%m')}",
            })
            atual += timedelta(days=1)
        return resultado

    if granularidade == "mes":
        atual = inicio.replace(day=1)
        limite = fim.replace(day=1)
        while atual <= limite:
            resultado.append({
                "chave": atual.strftime("%Y-%m"),
                "rotulo": f"{MESES[atual.month]}/{str(atual.year)[2:]}",
            })
            if atual.month == 12:
                atual = atual.replace(year=atual.year + 1, month=1)
            else:
                atual = atual.replace(month=atual.month + 1)
        return resultado

    return [{"chave": str(a), "rotulo": str(a)}
            for a in range(inicio.year, fim.year + 1)]


def _bucket_key(valor, granularidade):
    if granularidade == "hora":
        return f"{valor.hour:02d}"
    if granularidade == "dia":
        return valor.date().isoformat()
    if granularidade == "mes":
        return valor.strftime("%Y-%m")
    return str(valor.year)


def _evolucao_atendimentos(db, barbearia_id, inicio, fim, granularidade):
    inicio_dt, fim_dt = _limites(inicio, fim)
    rows = (
        db.query(models.Comanda.data_fechamento)
        .join(models.ItemComanda,
              models.ItemComanda.comanda_id == models.Comanda.id)
        .filter(
            models.Comanda.barbearia_id == barbearia_id,
            func.lower(models.Comanda.status) == "fechada",
            models.Comanda.data_fechamento >= inicio_dt,
            models.Comanda.data_fechamento < fim_dt,
            func.lower(models.ItemComanda.tipo) == "servico",
        )
        .distinct()
        .all()
    )

    contagem = defaultdict(int)
    for (momento,) in rows:
        if momento is not None:
            contagem[_bucket_key(momento, granularidade)] += 1

    return [
        {"label": b["rotulo"], "valor": int(contagem[b["chave"]])}
        for b in _buckets(inicio, fim, granularidade)
    ]


def _evolucao_financeira(db, barbearia_id, inicio, fim, granularidade):
    inicio_dt, fim_dt = _limites(inicio, fim)
    rows = (
        db.query(models.Caixa.data, models.Caixa.tipo, models.Caixa.valor)
        .filter(
            models.Caixa.barbearia_id == barbearia_id,
            func.upper(models.Caixa.status) == "ATIVO",
            models.Caixa.data >= inicio_dt,
            models.Caixa.data < fim_dt,
        )
        .all()
    )

    entradas, saidas = defaultdict(float), defaultdict(float)
    for momento, tipo, valor in rows:
        if momento is None:
            continue
        chave = _bucket_key(momento, granularidade)
        if (tipo or "").lower() == "entrada":
            entradas[chave] += float(valor or 0)
        elif (tipo or "").lower() == "saida":
            saidas[chave] += float(valor or 0)

    return [
        {
            "label": b["rotulo"],
            "entradas": round(entradas[b["chave"]], 2),
            "saidas": round(saidas[b["chave"]], 2),
        }
        for b in _buckets(inicio, fim, granularidade)
    ]


def _ranking_itens(db, barbearia_id, inicio, fim, tipo, id_campo):
    inicio_dt, fim_dt = _limites(inicio, fim)
    rows = (
        db.query(
            id_campo.label("registro_id"),
            func.max(models.ItemComanda.descricao).label("nome"),
            func.coalesce(func.sum(models.ItemComanda.quantidade), 0).label("quantidade"),
            func.coalesce(func.sum(models.ItemComanda.subtotal), 0).label("valor"),
        )
        .join(models.Comanda,
              models.Comanda.id == models.ItemComanda.comanda_id)
        .filter(
            models.Comanda.barbearia_id == barbearia_id,
            func.lower(models.Comanda.status) == "fechada",
            models.Comanda.data_fechamento >= inicio_dt,
            models.Comanda.data_fechamento < fim_dt,
            func.lower(models.ItemComanda.tipo) == tipo,
            id_campo.isnot(None),
        )
        .group_by(id_campo)
        .order_by(
            func.sum(models.ItemComanda.quantidade).desc(),
            func.sum(models.ItemComanda.subtotal).desc(),
        )
        .limit(10)
        .all()
    )
    return [
        {
            "id": r.registro_id,
            "nome": r.nome or f"#{r.registro_id}",
            "quantidade": int(r.quantidade or 0),
            "valor": float(r.valor or 0),
        }
        for r in rows
    ]


def _ranking_barbeiros(db, barbearia_id, inicio, fim):
    inicio_dt, fim_dt = _limites(inicio, fim)
    rows = (
        db.query(
            models.Comanda.barbeiro_id,
            models.Barbeiro.nome,
            func.count(func.distinct(models.Comanda.id)).label("atendimentos"),
            func.coalesce(func.sum(models.ItemComanda.quantidade), 0).label("servicos"),
            func.coalesce(func.sum(models.ItemComanda.subtotal), 0).label("valor_servicos"),
        )
        .join(models.ItemComanda,
              models.ItemComanda.comanda_id == models.Comanda.id)
        .outerjoin(models.Barbeiro,
                   models.Barbeiro.id == models.Comanda.barbeiro_id)
        .filter(
            models.Comanda.barbearia_id == barbearia_id,
            func.lower(models.Comanda.status) == "fechada",
            models.Comanda.data_fechamento >= inicio_dt,
            models.Comanda.data_fechamento < fim_dt,
            func.lower(models.ItemComanda.tipo) == "servico",
            models.Comanda.barbeiro_id.isnot(None),
        )
        .group_by(models.Comanda.barbeiro_id, models.Barbeiro.nome)
        .order_by(func.count(func.distinct(models.Comanda.id)).desc())
        .limit(10)
        .all()
    )
    return [
        {
            "id": r.barbeiro_id,
            "nome": r.nome or f"Barbeiro #{r.barbeiro_id}",
            "atendimentos": int(r.atendimentos or 0),
            "servicos": int(r.servicos or 0),
            "valor_servicos": float(r.valor_servicos or 0),
        }
        for r in rows
    ]


def _dados_planos(db, barbearia_id, inicio, fim):
    inicio_dt, fim_dt = _limites(inicio, fim)
    mapa = {}

    def item(plano_id, nome):
        if plano_id not in mapa:
            mapa[plano_id] = {
                "id": plano_id,
                "nome": nome or f"Plano #{plano_id}",
                "ativos": 0,
                "novas_adesoes": 0,
                "pagamentos": 0,
                "receita": 0.0,
            }
        return mapa[plano_id]

    ativos = (
        db.query(
            models.AssinaturaCliente.plano_id,
            models.Plano.nome,
            func.count(models.AssinaturaCliente.id).label("qtd"),
        )
        .join(models.Plano, models.Plano.id == models.AssinaturaCliente.plano_id)
        .filter(
            models.AssinaturaCliente.barbearia_id == barbearia_id,
            func.upper(models.AssinaturaCliente.status) == "ATIVO",
        )
        .group_by(models.AssinaturaCliente.plano_id, models.Plano.nome)
        .all()
    )
    for r in ativos:
        item(r.plano_id, r.nome)["ativos"] = int(r.qtd or 0)

    novas = (
        db.query(
            models.AssinaturaCliente.plano_id,
            models.Plano.nome,
            func.count(models.AssinaturaCliente.id).label("qtd"),
        )
        .join(models.Plano, models.Plano.id == models.AssinaturaCliente.plano_id)
        .filter(
            models.AssinaturaCliente.barbearia_id == barbearia_id,
            models.AssinaturaCliente.data_inicio >= inicio_dt,
            models.AssinaturaCliente.data_inicio < fim_dt,
        )
        .group_by(models.AssinaturaCliente.plano_id, models.Plano.nome)
        .all()
    )
    for r in novas:
        item(r.plano_id, r.nome)["novas_adesoes"] = int(r.qtd or 0)

    pagos = (
        db.query(
            models.PagamentoPlano.plano_id,
            models.Plano.nome,
            func.count(models.PagamentoPlano.id).label("qtd"),
            func.coalesce(func.sum(models.PagamentoPlano.valor), 0).label("receita"),
        )
        .join(
            models.AssinaturaCliente,
            models.AssinaturaCliente.id == models.PagamentoPlano.assinatura_id,
        )
        .join(models.Plano, models.Plano.id == models.PagamentoPlano.plano_id)
        .filter(
            models.AssinaturaCliente.barbearia_id == barbearia_id,
            func.upper(models.PagamentoPlano.status) == "PAGO",
            models.PagamentoPlano.data_pagamento >= inicio_dt,
            models.PagamentoPlano.data_pagamento < fim_dt,
        )
        .group_by(models.PagamentoPlano.plano_id, models.Plano.nome)
        .all()
    )
    for r in pagos:
        destino = item(r.plano_id, r.nome)
        destino["pagamentos"] = int(r.qtd or 0)
        destino["receita"] = float(r.receita or 0)

    return sorted(
        mapa.values(),
        key=lambda x: (x["ativos"], x["novas_adesoes"], x["receita"]),
        reverse=True,
    )


def _formas_pagamento(db, barbearia_id, inicio, fim):
    inicio_dt, fim_dt = _limites(inicio, fim)

    # Normaliza somente a escrita da mesma forma de pagamento.
    # Exemplos equivalentes: "PIX", "pix", " Pix ".
    #
    # Importante: modalidades realmente diferentes continuam separadas.
    # Ex.: "PIX_MERCADO_PAGO" não é agrupado com "PIX".
    forma_normalizada = func.upper(
        func.coalesce(
            func.nullif(
                func.trim(models.Caixa.forma_pagamento),
                "",
            ),
            "NAO_INFORMADO",
        )
    ).label("forma_pagamento")

    rows = (
        db.query(
            forma_normalizada,
            func.count(models.Caixa.id).label("quantidade"),
            func.coalesce(func.sum(models.Caixa.valor), 0).label("valor"),
        )
        .filter(
            models.Caixa.barbearia_id == barbearia_id,
            func.upper(models.Caixa.status) == "ATIVO",
            func.lower(models.Caixa.tipo) == "entrada",
            models.Caixa.data >= inicio_dt,
            models.Caixa.data < fim_dt,
        )
        .group_by(forma_normalizada)
        .order_by(func.sum(models.Caixa.valor).desc())
        .all()
    )

    return [
        {
            "nome": (r.forma_pagamento or "NAO_INFORMADO").replace("_", " "),
            "quantidade": int(r.quantidade or 0),
            "valor": float(r.valor or 0),
        }
        for r in rows
    ]


def _origens_agendamento(db, barbearia_id, inicio, fim):
    inicio_dt, fim_dt = _limites(inicio, fim)
    rows = (
        db.query(
            models.Agendamento.origem,
            func.count(models.Agendamento.id).label("quantidade"),
        )
        .filter(
            models.Agendamento.barbearia_id == barbearia_id,
            models.Agendamento.data_hora_inicio >= inicio_dt,
            models.Agendamento.data_hora_inicio < fim_dt,
        )
        .group_by(models.Agendamento.origem)
        .order_by(func.count(models.Agendamento.id).desc())
        .all()
    )
    return [
        {"nome": (r.origem or "NAO_INFORMADO").upper(),
         "quantidade": int(r.quantidade or 0)}
        for r in rows
    ]


def _status_agenda(db, barbearia_id, inicio, fim):
    inicio_dt, fim_dt = _limites(inicio, fim)
    rows = (
        db.query(
            func.lower(models.Agendamento.status).label("status"),
            func.count(models.Agendamento.id).label("quantidade"),
        )
        .filter(
            models.Agendamento.barbearia_id == barbearia_id,
            models.Agendamento.data_hora_inicio >= inicio_dt,
            models.Agendamento.data_hora_inicio < fim_dt,
        )
        .group_by(func.lower(models.Agendamento.status))
        .all()
    )
    mapa = {(r.status or "nao_informado"): int(r.quantidade or 0) for r in rows}
    return {
        "total": sum(mapa.values()),
        "cancelados": mapa.get("cancelado", 0),
        "nao_compareceu": mapa.get("nao_compareceu", 0),
        "por_status": mapa,
    }


def _operacao(db, barbearia_id):
    clientes = int(
        db.query(func.count(models.Cliente.id))
        .filter(models.Cliente.barbearia_id == barbearia_id,
                models.Cliente.ativo.is_(True))
        .scalar() or 0
    )
    barbeiros = int(
        db.query(func.count(models.Barbeiro.id))
        .filter(models.Barbeiro.barbearia_id == barbearia_id,
                models.Barbeiro.ativo.is_(True))
        .scalar() or 0
    )
    comandas = int(
        db.query(func.count(models.Comanda.id))
        .filter(models.Comanda.barbearia_id == barbearia_id,
                func.lower(models.Comanda.status) == "aberta")
        .scalar() or 0
    )
    return {
        "clientes_ativos": clientes,
        "barbeiros_ativos": barbeiros,
        "comandas_abertas": comandas,
    }


def dashboard_gerencial_service(
    db,
    usuario_logado,
    periodo="mes",
    incluir_graficos=False,
    data_inicio=None,
    data_fim=None,
):
    barbearia_id = obter_barbearia_id(usuario_logado)
    periodo, inicio, fim, granularidade = _resolver_periodo(
        periodo, data_inicio, data_fim
    )

    contagens = {
        nome: _contar_atendimentos(db, barbearia_id, ini, f)
        for nome, (ini, f) in _periodos_resumo().items()
    }
    atendimentos_periodo = _contar_atendimentos(
        db, barbearia_id, inicio, fim
    )
    servicos_periodo = _quantidade_servicos(
        db, barbearia_id, inicio, fim
    )
    financeiro = dashboard_financeiro_service(
        db=db,
        usuario_logado=usuario_logado,
        data_inicio=inicio,
        data_fim=fim,
    )
    estoque = _resumo_estoque(db, barbearia_id)
    operacao = _operacao(db, barbearia_id)

    resposta = {
        "periodo": {
            "tipo": periodo,
            "data_inicio": inicio,
            "data_fim": fim,
            "granularidade": granularidade,
        },
        "atendimentos": {
            **contagens,
            "periodo": atendimentos_periodo,
        },
        "indicadores": {
            "receitas": float(financeiro["entradas"]),
            "despesas": float(financeiro["saidas"]),
            "resultado": float(financeiro["saldo"]),
            "servicos_realizados": servicos_periodo,
            "servicos_por_atendimento": round(
                servicos_periodo / atendimentos_periodo
                if atendimentos_periodo else 0,
                2,
            ),
            "comandas_abertas": operacao["comandas_abertas"],
        },
        "operacao": operacao,
        "estoque": estoque,
        "alertas_financeiros": {
            "contas_receber_vencidas": int(
                financeiro["contas_receber_vencidas"]
            ),
            "contas_pagar_vencidas": int(
                financeiro["contas_pagar_vencidas"]
            ),
        },
        "graficos": None,
    }

    if incluir_graficos:
        resposta["graficos"] = {
            "atendimentos_evolucao": _evolucao_atendimentos(
                db, barbearia_id, inicio, fim, granularidade
            ),
            "financeiro_evolucao": _evolucao_financeira(
                db, barbearia_id, inicio, fim, granularidade
            ),
            "servicos_top": _ranking_itens(
                db, barbearia_id, inicio, fim, "servico",
                models.ItemComanda.servico_id,
            ),
            "produtos_top": _ranking_itens(
                db, barbearia_id, inicio, fim, "produto",
                models.ItemComanda.produto_id,
            ),
            "barbeiros_top": _ranking_barbeiros(
                db, barbearia_id, inicio, fim
            ),
            "planos": _dados_planos(
                db, barbearia_id, inicio, fim
            ),
            "formas_pagamento": _formas_pagamento(
                db, barbearia_id, inicio, fim
            ),
            "origens_agendamento": _origens_agendamento(
                db, barbearia_id, inicio, fim
            ),
            "agenda_status": _status_agenda(
                db, barbearia_id, inicio, fim
            ),
            "receitas_por_origem": list(
                financeiro.get("receitas_por_origem", [])
            ),
        }

    return resposta
