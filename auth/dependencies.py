from fastapi import Depends, HTTPException, status

from auth.security import obter_usuario_logado


def get_usuario_logado(
    usuario=Depends(obter_usuario_logado)
):
    """
    Mantém compatibilidade com os routers que ainda importam
    get_usuario_logado de auth.dependencies.

    A validação real do token fica centralizada em auth.security.
    """

    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não autenticado."
        )

    return usuario


def get_barbeiro_logado(
    usuario=Depends(get_usuario_logado)
):
    """
    Retorna o barbeiro_id do usuário autenticado quando ele possui
    perfil de barbeiro e está corretamente vinculado.
    """

    if usuario.perfil != "barbeiro":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso permitido apenas para barbeiros."
        )

    if usuario.barbeiro_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Usuário barbeiro não está vinculado "
                "a um barbeiro."
            )
        )

    return usuario.barbeiro_id