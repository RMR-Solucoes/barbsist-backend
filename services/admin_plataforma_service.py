from sqlalchemy import func

import models


def resumo_plataforma_service(db):
    total_barbearias = db.query(func.count(models.Barbearia.id)).scalar() or 0
    barbearias_ativas = db.query(func.count(models.Barbearia.id)).filter(models.Barbearia.ativa.is_(True)).scalar() or 0
    barbearias_inativas = total_barbearias - barbearias_ativas

    total_assinaturas = db.query(func.count(models.AssinaturaSaaS.id)).scalar() or 0
    assinaturas_ativas = db.query(func.count(models.AssinaturaSaaS.id)).filter(models.AssinaturaSaaS.status == "ATIVA").scalar() or 0
    assinaturas_pendentes = db.query(func.count(models.AssinaturaSaaS.id)).filter(models.AssinaturaSaaS.status == "PENDENTE").scalar() or 0
    assinaturas_bloqueadas = db.query(func.count(models.AssinaturaSaaS.id)).filter(models.AssinaturaSaaS.status == "BLOQUEADA").scalar() or 0

    pagamentos_aprovados = db.query(func.count(models.PagamentoSaaS.id)).filter(models.PagamentoSaaS.status == "approved").scalar() or 0
    pagamentos_pendentes = db.query(func.count(models.PagamentoSaaS.id)).filter(models.PagamentoSaaS.status.in_(["pending", "in_process"])).scalar() or 0
    receita_aprovada = db.query(func.coalesce(func.sum(models.PagamentoSaaS.valor), 0.0)).filter(models.PagamentoSaaS.status == "approved").scalar() or 0.0

    return {
        "barbearias": {
            "total": int(total_barbearias),
            "ativas": int(barbearias_ativas),
            "inativas": int(barbearias_inativas),
        },
        "assinaturas_saas": {
            "total": int(total_assinaturas),
            "ativas": int(assinaturas_ativas),
            "pendentes": int(assinaturas_pendentes),
            "bloqueadas": int(assinaturas_bloqueadas),
        },
        "pagamentos_saas": {
            "aprovados": int(pagamentos_aprovados),
            "pendentes": int(pagamentos_pendentes),
            "receita_aprovada": float(receita_aprovada),
        },
    }
