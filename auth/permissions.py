from fastapi import Depends, HTTPException, Request

from auth.security import obter_usuario_logado
from auth.tenant import (
    obter_barbearia_id,
    superadmin_possui_contexto,
)
from database import get_db
from services.autorizacao_operacional_saas_service import (
    validar_operacao_interna_saas,
)


def permitir_perfis(perfis_permitidos: list[str]):
    def verificar(
        request: Request,
        db=Depends(get_db),
        usuario=Depends(obter_usuario_logado),
    ):
        if usuario is None:
            raise HTTPException(
                status_code=401,
                detail="Usu\u00e1rio n\u00e3o autenticado",
            )

        autorizado = (
            usuario.perfil
            in perfis_permitidos
        )

        # O superadmin somente assume permissoes
        # administrativas de uma barbearia quando
        # existe contexto explicito e a rota ja
        # permite o perfil admin.
        if (
            not autorizado
            and usuario.perfil == "superadmin"
            and "admin" in perfis_permitidos
            and superadmin_possui_contexto(
                usuario
            )
        ):
            autorizado = True

        if not autorizado:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Acesso n\u00e3o autorizado "
                    "para este perfil"
                ),
            )

        # Superadmin permanece livre para suporte,
        # administracao e regularizacao.
        if usuario.perfil != "superadmin":
            barbearia_id = (
                obter_barbearia_id(
                    usuario
                )
            )

            validar_operacao_interna_saas(
                db=db,
                barbearia_id=barbearia_id,
                request=request,
            )

        return usuario

    return verificar
# =========================
# ADMINISTRAÇÃO DA PLATAFORMA
# =========================

superadmin = permitir_perfis([
    "superadmin"
])

superadmin_ou_admin = permitir_perfis([
    "superadmin",
    "admin"
])
# =========================
# PERMISSÕES BASE
# =========================

admin = permitir_perfis([
    "admin"
])

admin_ou_gerente = permitir_perfis([
    "admin",
    "gerente"
])

admin_gerente_ou_recepcao = permitir_perfis([
    "admin",
    "gerente",
    "recepcao"
])

admin_gerente_ou_barbeiro = permitir_perfis([
    "admin",
    "gerente",
    "barbeiro"
])

admin_gerente_recepcao_ou_barbeiro = permitir_perfis([
    "admin",
    "gerente",
    "recepcao",
    "barbeiro"
])

todos_logados = permitir_perfis([
    "admin",
    "gerente",
    "recepcao",
    "barbeiro"
])

admin_ou_recepcao = permitir_perfis([
    "admin",
    "recepcao"
])


# =========================
# APELIDOS PARA COMPATIBILIDADE
# =========================

admin_gerente_recepcao = admin_gerente_ou_recepcao

admin_gerente_barbeiro = admin_gerente_ou_barbeiro