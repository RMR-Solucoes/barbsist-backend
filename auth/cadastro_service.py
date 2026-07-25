from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models

from auth.security import criar_hash_senha
from auth.usuario_service import (
    normalizar_email,
    validar_senha,
)
from services.barbearia_service import (
    gerar_proximo_codigo,
    gerar_slug_unico,
    normalizar_texto,
    validar_nome_barbearia,
)
from services.configuracao_funcionamento_service import (
    criar_configuracao_padrao_por_barbearia,
)
from services.sequencia_service import PREFIXOS_CODIGO


def validar_dados_cadastro(dados):
    nome_barbearia = validar_nome_barbearia(
        dados.nome_barbearia
    )

    responsavel = normalizar_texto(
        dados.responsavel
    )

    if not responsavel:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O nome do responsável é obrigatório."
        )

    email = normalizar_email(
        dados.email
    )

    if not email or "@" not in email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe um e-mail válido."
        )

    telefone_whatsapp = normalizar_texto(
        dados.telefone_whatsapp
    )

    if not telefone_whatsapp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O telefone ou WhatsApp é obrigatório."
        )

    cidade = normalizar_texto(
        dados.cidade
    )

    if not cidade:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A cidade é obrigatória."
        )

    estado = normalizar_texto(
        dados.estado
    )

    if not estado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O estado é obrigatório."
        )

    validar_senha(
        dados.senha
    )

    if dados.senha != dados.confirmar_senha:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A confirmação da senha não confere."
        )

    if not dados.aceite_termos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "É necessário aceitar os termos "
                "para realizar o cadastro."
            )
        )

    return {
        "nome_barbearia": nome_barbearia,
        "responsavel": responsavel,
        "email": email,
        "telefone_whatsapp": telefone_whatsapp,
        "cidade": cidade,
        "estado": estado.upper(),
    }


def criar_sequencias_iniciais(
    db: Session,
    barbearia_id: int,
):
    for tipo in PREFIXOS_CODIGO:
        sequencia = models.SequenciaBarbearia(
            barbearia_id=barbearia_id,
            tipo=tipo,
            ultimo_numero=0,
        )

        db.add(sequencia)

    db.flush()


def cadastrar_barbearia_service(
    db: Session,
    dados,
):
    dados_validados = validar_dados_cadastro(
        dados
    )

    try:
        codigo = gerar_proximo_codigo(
            db
        )

        slug = gerar_slug_unico(
            db=db,
            nome=dados_validados["nome_barbearia"],
        )

        barbearia = models.Barbearia(
            codigo=codigo,
            slug=slug,
            nome=dados_validados["nome_barbearia"],
            responsavel=dados_validados["responsavel"],
            email=dados_validados["email"],
            telefone=dados_validados["telefone_whatsapp"],
            telefone_whatsapp=(
                dados_validados["telefone_whatsapp"]
            ),
            cidade=dados_validados["cidade"],
            estado=dados_validados["estado"],
            ativa=True,
        )

        db.add(barbearia)
        db.flush()

        administrador = models.Usuario(
            nome=dados_validados["responsavel"],
            email=dados_validados["email"],
            senha_hash=criar_hash_senha(
                dados.senha
            ),
            perfil="admin",
            barbeiro_id=None,
            barbearia_id=barbearia.id,
            ativo=True,
        )

        db.add(administrador)
        db.flush()

        criar_configuracao_padrao_por_barbearia(
            db=db,
            barbearia_id=barbearia.id,
            realizar_commit=False,
        )

        criar_sequencias_iniciais(
            db=db,
            barbearia_id=barbearia.id,
        )

        db.commit()

        db.refresh(barbearia)
        db.refresh(administrador)

        return {
    "sucesso": True,
    "mensagem": (
        "Cadastro realizado com sucesso! "
        "Sua barbearia já está pronta para uso."
    ),
    "barbearia": {
        "id": barbearia.id,
        "codigo": barbearia.codigo,
        "nome": barbearia.nome,
        "slug": barbearia.slug,
    },
    "administrador": {
        "email": administrador.email,
    },
    "login": {
        "slug": barbearia.slug,
        "email": administrador.email,
    },
    "proximo_passo": (
        "Faça login utilizando o slug, "
        "o e-mail e a senha cadastrada."
    ),
}

    except HTTPException:
        db.rollback()
        raise

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Não foi possível concluir o cadastro. "
                "Verifique se os dados já estão sendo utilizados."
            ),
        )

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Não foi possível concluir o cadastro "
                "da barbearia."
            ),
        )