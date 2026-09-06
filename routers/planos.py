from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db

from schemas import (
    PlanoCreate,
    PlanoUpdate,
    PlanoResponse,
    AssinaturaClienteCreate,
    AssinaturaClienteUpdate,
    AssinaturaClienteResponse,
    UsarPlanoRequest,
    UsoPlanoResponse,
    RegistrarPagamentoPlanoRequest,
    PagamentoPlanoResponse,
    RenovarAssinaturaRequest,
    SuspenderAssinaturaRequest,
    ReativarAssinaturaRequest,
    TrocarPlanoAssinaturaRequest,
    AssinaturaClienteTrocaPlanoResponse,
)

from services.plano_service import (
    criar_plano_service,
    listar_planos_service,
    buscar_plano_service,
    atualizar_plano_service,
    criar_assinatura_service,
    listar_assinaturas_service,
    buscar_assinaturas_cliente_service,
    atualizar_assinatura_service,
    usar_plano_service,
    registrar_pagamento_plano_service,
    listar_pagamentos_planos_service,
    listar_pagamentos_assinatura_service,
    listar_pagamentos_cliente_service,
    renovar_assinatura_service,
    suspender_assinatura_service,
    reativar_assinatura_service,
    cancelar_assinatura_service,
    verificar_inadimplencia_service,
    solicitar_troca_plano_service,
    cancelar_troca_plano_service,
    listar_historico_troca_plano_service,
)

from auth.permissions import (
    admin_ou_gerente,
    admin_gerente_ou_recepcao,
)


router = APIRouter(
    prefix="/planos",
    tags=["Planos"],
)


# ============================================================
# PLANOS — ROTAS GERAIS
# ============================================================

@router.post(
    "",
    response_model=PlanoResponse,
)
def criar_plano(
    dados: PlanoCreate,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_ou_recepcao
    ),
):
    return criar_plano_service(
        db=db,
        dados=dados,
        usuario_logado=usuario_logado,
    )


@router.get(
    "",
    response_model=list[PlanoResponse],
)
def listar_planos(
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_ou_recepcao
    ),
):
    return listar_planos_service(
        db=db,
        usuario_logado=usuario_logado,
    )


# ============================================================
# ASSINATURAS — ROTAS ESTÁTICAS
# Devem ficar antes das rotas com {assinatura_id}.
# ============================================================

@router.post(
    "/assinaturas",
    response_model=AssinaturaClienteResponse,
)
def criar_assinatura(
    dados: AssinaturaClienteCreate,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_ou_recepcao
    ),
):
    return criar_assinatura_service(
        db=db,
        dados=dados,
        usuario_logado=usuario_logado,
    )


@router.get(
    "/assinaturas",
    response_model=list[
        AssinaturaClienteResponse
    ],
)
def listar_assinaturas(
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_ou_recepcao
    ),
):
    return listar_assinaturas_service(
        db=db,
        usuario_logado=usuario_logado,
    )


@router.put(
    "/assinaturas/verificar-inadimplencia",
    response_model=list[
        AssinaturaClienteResponse
    ],
)
def verificar_inadimplencia(
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_ou_gerente
    ),
):
    return verificar_inadimplencia_service(
        db=db,
        usuario_logado=usuario_logado,
    )


# ============================================================
# ASSINATURAS — CONSULTA POR CLIENTE
# ============================================================

@router.get(
    "/cliente/{cliente_id}",
    response_model=list[
        AssinaturaClienteResponse
    ],
)
def buscar_assinaturas_cliente(
    cliente_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_ou_recepcao
    ),
):
    return buscar_assinaturas_cliente_service(
        db=db,
        cliente_id=cliente_id,
        usuario_logado=usuario_logado,
    )


# ============================================================
# ASSINATURAS — AÇÕES ESPECÍFICAS
# Devem ficar antes de /assinaturas/{assinatura_id}.
# ============================================================

@router.put(
    "/assinaturas/{assinatura_id}/renovar",
    response_model=AssinaturaClienteResponse,
)
def renovar_assinatura(
    assinatura_id: int,
    dados: RenovarAssinaturaRequest,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_ou_recepcao
    ),
):
    return renovar_assinatura_service(
        db=db,
        assinatura_id=assinatura_id,
        dados=dados,
        usuario_logado=usuario_logado,
    )


@router.put(
    "/assinaturas/{assinatura_id}/suspender",
    response_model=AssinaturaClienteResponse,
)
def suspender_assinatura(
    assinatura_id: int,
    dados: SuspenderAssinaturaRequest,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_ou_gerente
    ),
):
    return suspender_assinatura_service(
        db=db,
        assinatura_id=assinatura_id,
        dados=dados,
        usuario_logado=usuario_logado,
    )


@router.put(
    "/assinaturas/{assinatura_id}/reativar",
    response_model=AssinaturaClienteResponse,
)
def reativar_assinatura(
    assinatura_id: int,
    dados: ReativarAssinaturaRequest,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_ou_gerente
    ),
):
    return reativar_assinatura_service(
        db=db,
        assinatura_id=assinatura_id,
        dados=dados,
        usuario_logado=usuario_logado,
    )


# ============================================================
# ASSINATURAS — ATUALIZAÇÃO GENÉRICA
# Deve ficar após as rotas específicas.
# ============================================================



@router.put(
    "/assinaturas/{assinatura_id}/trocar-plano",
    response_model=AssinaturaClienteResponse,
)
def solicitar_troca_plano(
    assinatura_id: int,
    dados: TrocarPlanoAssinaturaRequest,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_ou_gerente),
):
    return solicitar_troca_plano_service(
        db=db,
        assinatura_id=assinatura_id,
        dados=dados,
        usuario_logado=usuario_logado,
    )


@router.delete(
    "/assinaturas/{assinatura_id}/troca-plano",
    response_model=AssinaturaClienteResponse,
)
def cancelar_troca_plano(
    assinatura_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_ou_gerente),
):
    return cancelar_troca_plano_service(
        db=db,
        assinatura_id=assinatura_id,
        usuario_logado=usuario_logado,
    )


@router.get(
    "/assinaturas/{assinatura_id}/trocas-plano",
    response_model=list[AssinaturaClienteTrocaPlanoResponse],
)
def listar_historico_troca_plano(
    assinatura_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_ou_gerente),
):
    return listar_historico_troca_plano_service(
        db=db,
        assinatura_id=assinatura_id,
        usuario_logado=usuario_logado,
    )


@router.put(
    "/assinaturas/{assinatura_id}/cancelar",
    response_model=AssinaturaClienteResponse,
)
def cancelar_assinatura(
    assinatura_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_ou_gerente
    ),
):
    return cancelar_assinatura_service(
        db=db,
        assinatura_id=assinatura_id,
        usuario_logado=usuario_logado,
    )


@router.put(
    "/assinaturas/{assinatura_id}",
    response_model=AssinaturaClienteResponse,
)
def atualizar_assinatura(
    assinatura_id: int,
    dados: AssinaturaClienteUpdate,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_ou_gerente
    ),
):
    return atualizar_assinatura_service(
        db=db,
        assinatura_id=assinatura_id,
        dados=dados,
        usuario_logado=usuario_logado,
    )


# ============================================================
# USO DO PLANO
# ============================================================

@router.post(
    "/usar",
    response_model=UsoPlanoResponse,
)
def usar_plano(
    dados: UsarPlanoRequest,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_ou_recepcao
    ),
):
    return usar_plano_service(
        db=db,
        dados=dados,
        usuario_logado=usuario_logado,
    )


# ============================================================
# PAGAMENTOS DE PLANOS
# ============================================================

@router.post(
    "/pagamento",
    response_model=AssinaturaClienteResponse,
)
def registrar_pagamento_plano(
    dados: RegistrarPagamentoPlanoRequest,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_ou_recepcao
    ),
):
    return registrar_pagamento_plano_service(
        db=db,
        dados=dados,
        usuario_logado=usuario_logado,
    )


@router.get(
    "/pagamentos",
    response_model=list[
        PagamentoPlanoResponse
    ],
)
def listar_pagamentos_planos(
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_ou_recepcao
    ),
):
    return listar_pagamentos_planos_service(
        db=db,
        usuario_logado=usuario_logado,
    )


@router.get(
    "/assinaturas/{assinatura_id}/pagamentos",
    response_model=list[
        PagamentoPlanoResponse
    ],
)
def listar_pagamentos_assinatura(
    assinatura_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_ou_recepcao
    ),
):
    return listar_pagamentos_assinatura_service(
        db=db,
        assinatura_id=assinatura_id,
        usuario_logado=usuario_logado,
    )


@router.get(
    "/cliente/{cliente_id}/pagamentos",
    response_model=list[
        PagamentoPlanoResponse
    ],
)
def listar_pagamentos_cliente(
    cliente_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_ou_recepcao
    ),
):
    return listar_pagamentos_cliente_service(
        db=db,
        cliente_id=cliente_id,
        usuario_logado=usuario_logado,
    )


# ============================================================
# PLANOS — AÇÕES ESPECÍFICAS
# Devem ficar antes das rotas genéricas /{plano_id}.
# ============================================================

@router.put(
    "/{plano_id}/inativar",
    response_model=PlanoResponse,
)
def inativar_plano(
    plano_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_ou_gerente
    ),
):
    plano = buscar_plano_service(
        db=db,
        plano_id=plano_id,
        usuario_logado=usuario_logado,
        exigir_ativo=False,
    )

    if not plano.ativo:
        raise HTTPException(
            status_code=400,
            detail="Plano já está inativo.",
        )

    plano.ativo = False

    db.commit()
    db.refresh(plano)

    return plano


@router.put(
    "/{plano_id}/reativar",
    response_model=PlanoResponse,
)
def reativar_plano(
    plano_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_ou_gerente
    ),
):
    plano = buscar_plano_service(
        db=db,
        plano_id=plano_id,
        usuario_logado=usuario_logado,
        exigir_ativo=False,
    )

    if plano.ativo:
        raise HTTPException(
            status_code=400,
            detail="Plano já está ativo.",
        )

    plano.ativo = True

    db.commit()
    db.refresh(plano)

    return plano


# ============================================================
# PLANOS — ROTAS GENÉRICAS POR ID
# Devem permanecer no final do arquivo.
# ============================================================

@router.put(
    "/{plano_id}",
    response_model=PlanoResponse,
)
def atualizar_plano(
    plano_id: int,
    dados: PlanoUpdate,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_ou_gerente
    ),
):
    return atualizar_plano_service(
        db=db,
        plano_id=plano_id,
        dados=dados,
        usuario_logado=usuario_logado,
    )


@router.get(
    "/{plano_id}",
    response_model=PlanoResponse,
)
def buscar_plano(
    plano_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_ou_recepcao
    ),
):
    return buscar_plano_service(
        db=db,
        plano_id=plano_id,
        usuario_logado=usuario_logado,
        exigir_ativo=True,
    )