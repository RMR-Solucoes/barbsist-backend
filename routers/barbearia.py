from fastapi import (
    APIRouter,
    Depends
)

from sqlalchemy.orm import Session

from database import get_db

from schemas import (
    BarbeariaCreate,
    BarbeariaUpdate,
    BarbeariaResponse
)

from services.barbearia_service import (
    criar_barbearia_service,
    listar_barbearias_service,
    buscar_barbearia_por_id_service,
    obter_minha_barbearia_service,
    atualizar_minha_barbearia_service,
    alterar_status_barbearia_service
)

from auth.permissions import (
    superadmin,
    admin_ou_gerente,
    todos_logados
)


router = APIRouter(
    prefix="/barbearia",
    tags=["Barbearia"]
)


# =========================
# ADMINISTRAÇÃO DA PLATAFORMA
# =========================

@router.post(
    "",
    response_model=BarbeariaResponse
)
def criar_barbearia(
    dados: BarbeariaCreate,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        superadmin
    )
):
    return criar_barbearia_service(
        db=db,
        dados=dados
    )


@router.get(
    "/todas",
    response_model=list[BarbeariaResponse]
)
def listar_barbearias(
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        superadmin
    )
):
    return listar_barbearias_service(
        db=db
    )


@router.get(
    "/administracao/{barbearia_id}",
    response_model=BarbeariaResponse
)
def buscar_barbearia_por_id(
    barbearia_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        superadmin
    )
):
    return buscar_barbearia_por_id_service(
        db=db,
        barbearia_id=barbearia_id
    )


@router.put(
    "/administracao/{barbearia_id}/ativar",
    response_model=BarbeariaResponse
)
def ativar_barbearia(
    barbearia_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        superadmin
    )
):
    return alterar_status_barbearia_service(
        db=db,
        barbearia_id=barbearia_id,
        ativa=True
    )


@router.put(
    "/administracao/{barbearia_id}/desativar",
    response_model=BarbeariaResponse
)
def desativar_barbearia(
    barbearia_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        superadmin
    )
):
    return alterar_status_barbearia_service(
        db=db,
        barbearia_id=barbearia_id,
        ativa=False
    )


# =========================
# BARBEARIA DO USUÁRIO
# =========================

@router.get(
    "/minha",
    response_model=BarbeariaResponse
)
def obter_minha_barbearia(
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        todos_logados
    )
):
    return obter_minha_barbearia_service(
        db=db,
        usuario_logado=usuario_logado
    )


@router.put(
    "/minha",
    response_model=BarbeariaResponse
)
def atualizar_minha_barbearia(
    dados: BarbeariaUpdate,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_ou_gerente
    )
):
    return atualizar_minha_barbearia_service(
        db=db,
        dados=dados,
        usuario_logado=usuario_logado
    )