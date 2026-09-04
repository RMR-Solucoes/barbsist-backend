from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from auth.permissions import superadmin

from parceiros.models_parceiros import ResgateCreditoBarbearia

from parceiros.schemas_parceiros import (
    ParceiroCreate,
    ParceiroOut,
    IndicacaoOut,
    ComissaoParceiroOut,
    CreditoBarbeariaOut,
)

from parceiros.service_parceiros import (
    criar_parceiro_service,
    listar_parceiros_service,
    obter_parceiro_service,
    registrar_indicacao_service,
    processar_beneficio_pagamento_service,
    listar_indicacoes_parceiro_service,
    listar_comissoes_parceiro_service,
    listar_creditos_parceiro_service,
    aprovar_resgate_creditos_service,
    aplicar_resgate_creditos_service,
)


router = APIRouter(
    prefix="/admin/parceiros",
    tags=["Admin - Parceiros BarbSist"],
)


@router.post(
    "",
    response_model=ParceiroOut,
    status_code=201,
)
def criar_parceiro(
    dados: ParceiroCreate,
    db: Session = Depends(get_db),
    usuario_logado=Depends(superadmin),
):
    return criar_parceiro_service(db, dados)


@router.get(
    "",
    response_model=list[ParceiroOut],
)
def listar_parceiros(
    incluir_inativos: bool = Query(default=True),
    db: Session = Depends(get_db),
    usuario_logado=Depends(superadmin),
):
    return listar_parceiros_service(
        db,
        incluir_inativos=incluir_inativos,
    )


@router.get("/resgates")
def listar_resgates(
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    usuario_logado=Depends(superadmin),
):
    query = db.query(ResgateCreditoBarbearia)

    if status:
        query = query.filter(
            ResgateCreditoBarbearia.status
            == status.strip().upper()
        )

    return (
        query
        .order_by(ResgateCreditoBarbearia.id.desc())
        .all()
    )


@router.get(
    "/{parceiro_id}",
    response_model=ParceiroOut,
)
def obter_parceiro(
    parceiro_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(superadmin),
):
    return obter_parceiro_service(db, parceiro_id)


@router.post(
    "/{parceiro_id}/indicacoes",
    response_model=IndicacaoOut,
    status_code=201,
)
def registrar_indicacao_manual(
    parceiro_id: int,
    barbearia_indicada_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(superadmin),
):
    parceiro = obter_parceiro_service(db, parceiro_id)

    return registrar_indicacao_service(
        db=db,
        codigo_ref=parceiro.codigo_ref,
        barbearia_indicada_id=barbearia_indicada_id,
    )


@router.get(
    "/{parceiro_id}/indicacoes",
    response_model=list[IndicacaoOut],
)
def listar_indicacoes(
    parceiro_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(superadmin),
):
    return listar_indicacoes_parceiro_service(
        db,
        parceiro_id,
    )


@router.get(
    "/{parceiro_id}/comissoes",
    response_model=list[ComissaoParceiroOut],
)
def listar_comissoes(
    parceiro_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(superadmin),
):
    return listar_comissoes_parceiro_service(
        db,
        parceiro_id,
    )


@router.get(
    "/{parceiro_id}/creditos",
    response_model=list[CreditoBarbeariaOut],
)
def listar_creditos(
    parceiro_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(superadmin),
):
    return listar_creditos_parceiro_service(
        db,
        parceiro_id,
    )


@router.post(
    "/processar-pagamento/{pagamento_saas_id}",
)
def processar_pagamento(
    pagamento_saas_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(superadmin),
):
    return processar_beneficio_pagamento_service(
        db,
        pagamento_saas_id,
    )




@router.post("/resgates/{resgate_id}/aprovar")
def aprovar_resgate(
    resgate_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(superadmin),
):
    return aprovar_resgate_creditos_service(
        db,
        resgate_id,
    )


@router.post("/resgates/{resgate_id}/aplicar")
def aplicar_resgate(
    resgate_id: int,
    assinatura_saas_id: int | None = Query(default=None),
    pagamento_saas_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    usuario_logado=Depends(superadmin),
):
    return aplicar_resgate_creditos_service(
        db=db,
        resgate_id=resgate_id,
        assinatura_saas_id=assinatura_saas_id,
        pagamento_saas_id=pagamento_saas_id,
    )

