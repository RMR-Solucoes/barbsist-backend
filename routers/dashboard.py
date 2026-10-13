from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.permissions import admin_gerente_ou_recepcao
from database import get_db
from services.dashboard_service import dashboard_gerencial_service


router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)


@router.get("")
def dashboard_gerencial(
    periodo: str = "mes",
    incluir_graficos: bool = False,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    db: Session = Depends(get_db),
    usuario_logado=Depends(admin_gerente_ou_recepcao),
):
    return dashboard_gerencial_service(
        db=db,
        usuario_logado=usuario_logado,
        periodo=periodo,
        incluir_graficos=incluir_graficos,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )
