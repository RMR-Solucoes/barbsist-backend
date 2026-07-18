from fastapi import Depends, HTTPException

from auth.security import obter_usuario_logado, SEGURANCA_ATIVA


def permitir_perfis(perfis_permitidos: list[str]):
    def verificar(usuario=Depends(obter_usuario_logado)):

        if not SEGURANCA_ATIVA:
            return usuario

        if usuario is None:
            raise HTTPException(
                status_code=401,
                detail="Usuário não autenticado"
            )

        if usuario.perfil not in perfis_permitidos:
            raise HTTPException(
                status_code=403,
                detail="Acesso não autorizado para este perfil"
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