import re
import unicodedata

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models


def normalizar_texto(
    valor: str | None
) -> str | None:
    if valor is None:
        return None

    valor_normalizado = valor.strip()

    return valor_normalizado or None


def validar_nome_barbearia(
    nome: str
) -> str:
    nome_normalizado = normalizar_texto(
        nome
    )

    if not nome_normalizado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "O nome da barbearia é obrigatório."
            )
        )

    if len(nome_normalizado) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "O nome da barbearia deve possuir "
                "pelo menos 2 caracteres."
            )
        )

    return nome_normalizado


def gerar_slug_base(
    texto: str
) -> str:
    texto_normalizado = unicodedata.normalize(
        "NFKD",
        texto
    )

    texto_sem_acentos = "".join(
        caractere
        for caractere in texto_normalizado
        if not unicodedata.combining(
            caractere
        )
    )

    texto_sem_acentos = (
        texto_sem_acentos
        .lower()
        .strip()
    )

    slug = re.sub(
        r"[^a-z0-9]+",
        "-",
        texto_sem_acentos
    )

    return slug.strip("-") or "barbearia"


def gerar_slug_unico(
    db: Session,
    nome: str
) -> str:
    slug_base = gerar_slug_base(
        nome
    )

    slug = slug_base
    contador = 2

    while (
        db.query(models.Barbearia)
        .filter(
            models.Barbearia.slug == slug
        )
        .first()
        is not None
    ):
        slug = (
            f"{slug_base}-{contador}"
        )
        contador += 1

    return slug


def gerar_proximo_codigo(
    db: Session
) -> int:
    maior_codigo = (
        db.query(
            func.max(
                models.Barbearia.codigo
            )
        )
        .scalar()
    )

    return int(
        maior_codigo or 0
    ) + 1


def criar_barbearia_service(
    db: Session,
    dados
):
    nome = validar_nome_barbearia(
        dados.nome
    )

    codigo = gerar_proximo_codigo(
        db
    )

    slug = gerar_slug_unico(
        db=db,
        nome=nome
    )

    barbearia = models.Barbearia(
        codigo=codigo,
        slug=slug,
        nome=nome,
        responsavel=normalizar_texto(
            dados.responsavel
        ),
        email=normalizar_texto(
            dados.email
        ),
        telefone=normalizar_texto(
            dados.telefone
        ),
        telefone_whatsapp=normalizar_texto(
            dados.telefone_whatsapp
        ),
        cnpj=normalizar_texto(
            dados.cnpj
        ),
        endereco=normalizar_texto(
            dados.endereco
        ),
        cidade=normalizar_texto(
            dados.cidade
        ),
        estado=normalizar_texto(
            dados.estado
        ),
        cep=normalizar_texto(
            dados.cep
        ),
        instagram=normalizar_texto(
            dados.instagram
        ),
        logo_url=normalizar_texto(
            dados.logo_url
        ),
        slogan=normalizar_texto(
            dados.slogan
        ),
        imagem_capa_url=normalizar_texto(
            dados.imagem_capa_url
        ),
        cor_primaria=dados.cor_primaria,
        cor_secundaria=dados.cor_secundaria,
        cor_fundo=dados.cor_fundo,
        cor_sidebar=dados.cor_sidebar,
        cor_texto_sidebar=(
            dados.cor_texto_sidebar
        ),
        cor_destaque=dados.cor_destaque,
        ativa=True
    )

    try:
        db.add(barbearia)
        db.commit()
        db.refresh(barbearia)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Não foi possível cadastrar a barbearia. "
                "Verifique código, slug ou dados duplicados."
            )
        )

    return barbearia


def listar_barbearias_service(
    db: Session
):
    return (
        db.query(models.Barbearia)
        .order_by(
            models.Barbearia.codigo.asc()
        )
        .all()
    )


def buscar_barbearia_por_id_service(
    db: Session,
    barbearia_id: int
):
    barbearia = (
        db.query(models.Barbearia)
        .filter(
            models.Barbearia.id
            == barbearia_id
        )
        .first()
    )

    if not barbearia:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Barbearia não encontrada."
        )

    return barbearia


def obter_minha_barbearia_service(
    db: Session,
    usuario_logado: models.Usuario
):
    if usuario_logado.barbearia_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Usuário sem barbearia vinculada."
            )
        )

    return buscar_barbearia_por_id_service(
        db=db,
        barbearia_id=(
            usuario_logado.barbearia_id
        )
    )


def atualizar_minha_barbearia_service(
    db: Session,
    dados,
    usuario_logado: models.Usuario
):
    barbearia = obter_minha_barbearia_service(
        db=db,
        usuario_logado=usuario_logado
    )

    campos = dados.model_dump(
        exclude_unset=True
    )

    campos_proibidos = {
        "id",
        "codigo",
        "slug",
        "ativa",
        "created_at"
    }

    for campo in campos_proibidos:
        campos.pop(
            campo,
            None
        )

    if "nome" in campos:
        campos["nome"] = validar_nome_barbearia(
            campos["nome"]
        )

    campos_texto = {
        "responsavel",
        "email",
        "telefone",
        "telefone_whatsapp",
        "cnpj",
        "endereco",
        "cidade",
        "estado",
        "cep",
        "instagram",
        "logo_url",
        "slogan",
        "imagem_capa_url"
    }

    for campo in campos_texto:
        if campo in campos:
            campos[campo] = normalizar_texto(
                campos[campo]
            )

    for campo, valor in campos.items():
        setattr(
            barbearia,
            campo,
            valor
        )

    try:
        db.commit()
        db.refresh(barbearia)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Não foi possível atualizar "
                "a barbearia."
            )
        )

    return barbearia


def alterar_status_barbearia_service(
    db: Session,
    barbearia_id: int,
    ativa: bool
):
    barbearia = (
        buscar_barbearia_por_id_service(
            db=db,
            barbearia_id=barbearia_id
        )
    )

    barbearia.ativa = ativa

    db.commit()
    db.refresh(barbearia)

    return barbearia