from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.permissions import superadmin
from database import get_db
from services.admin_plataforma_service import resumo_plataforma_service

router = APIRouter(prefix="/admin/plataforma", tags=["Admin - Plataforma BarbSist"])


@router.get("/resumo")
def resumo(db: Session = Depends(get_db), usuario_logado=Depends(superadmin)):
    return resumo_plataforma_service(db)
