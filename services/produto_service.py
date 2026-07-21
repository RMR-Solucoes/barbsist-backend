from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

import models

from auth.tenant import obter_barbearia_id

from services.crud_service import (
    criar_registro_com_codigo,
    consultar_registros,
    buscar_registro,
    salvar_alteracoes,
    inativar_registro,
    reativar_registro,
)


def normalizar_texto(
    valor: str | None,
) -> str | None:
    """
    Remove espaços extras e retorna None quando o texto
    estiver vazio.
    """

    if valor is None:
        return None

    valor_normalizado = valor.strip()

    return valor_normalizado or None


def validar_nome_produto(
    nome: str | None,
) -> str:
    """
    Valida e normaliza o nome do produto.
    """

    nome_normalizado = normalizar_texto(nome)

    if not nome_normalizado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O nome do produto é obrigatório.",
        )

    if len(nome_normalizado) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "O nome do produto deve possuir "
                "pelo menos 2 caracteres."
            ),
        )

    return nome_normalizado


def validar_valores_produto(
    preco_custo: float,
    preco_venda: float,
    estoque: int,
):
    """
    Impede preços ou estoque negativos.
    """

    if preco_custo < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "O preço de custo não pode ser negativo."
            ),
        )

    if preco_venda < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "O preço de venda não pode ser negativo."
            ),
        )

    if estoque < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O estoque não pode ser negativo.",
        )


def validar_duplicidade_produto(
    db: Session,
    usuario_logado: models.Usuario,
    nome: str,
    codigo_qr: str | None,
    produto_id_ignorado: int | None = None,
):
    """
    Verifica duplicidade de nome ou código QR apenas
    dentro da barbearia atual.

    Barbearias diferentes podem cadastrar produtos
    com o mesmo nome ou código QR.
    """

    barbearia_id = obter_barbearia_id(
        usuario_logado
    )

    query_nome = db.query(
        models.Produto
    ).filter(
        models.Produto.barbearia_id == barbearia_id,
        func.lower(models.Produto.nome) == nome.lower(),
    )

    if produto_id_ignorado is not None:
        query_nome = query_nome.filter(
            models.Produto.id != produto_id_ignorado
        )

    produto_mesmo_nome = query_nome.first()

    if produto_mesmo_nome:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Já existe um produto com este nome "
                "nesta barbearia."
            ),
        )

    if codigo_qr:
        query_codigo_qr = db.query(
            models.Produto
        ).filter(
            models.Produto.barbearia_id == barbearia_id,
            models.Produto.codigo_qr == codigo_qr,
        )

        if produto_id_ignorado is not None:
            query_codigo_qr = query_codigo_qr.filter(
                models.Produto.id != produto_id_ignorado
            )

        produto_mesmo_codigo_qr = (
            query_codigo_qr.first()
        )

        if produto_mesmo_codigo_qr:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Já existe um produto com este código "
                    "QR nesta barbearia."
                ),
            )


def criar_produto_service(
    dados,
    db: Session,
    usuario_logado: models.Usuario,
):
    """
    Cria um produto vinculado automaticamente à
    barbearia do usuário autenticado.
    """

    nome = validar_nome_produto(
        dados.nome
    )

    categoria = normalizar_texto(
        dados.categoria
    )

    codigo_qr = normalizar_texto(
        dados.codigo_qr
    )

    validar_valores_produto(
        preco_custo=dados.preco_custo,
        preco_venda=dados.preco_venda,
        estoque=dados.estoque,
    )

    validar_duplicidade_produto(
        db=db,
        usuario_logado=usuario_logado,
        nome=nome,
        codigo_qr=codigo_qr,
    )

    return criar_registro_com_codigo(
        db=db,
        model=models.Produto,
        tipo_sequencia="PRODUTO",
        usuario_logado=usuario_logado,
        dados={
            "nome": nome,
            "categoria": categoria,
            "preco_custo": dados.preco_custo,
            "preco_venda": dados.preco_venda,
            "estoque": dados.estoque,
            "codigo_qr": codigo_qr,
            "ativo": True,
        },
    )


def listar_produtos_service(
    db: Session,
    usuario_logado: models.Usuario,
    apenas_ativos: bool = True,
):
    """
    Lista somente os produtos da barbearia atual.
    """

    query = consultar_registros(
        db=db,
        model=models.Produto,
        usuario_logado=usuario_logado,
        apenas_ativos=apenas_ativos,
    )

    return query.order_by(
        models.Produto.nome.asc()
    ).all()


def buscar_produto_service(
    produto_id: int,
    db: Session,
    usuario_logado: models.Usuario,
    exigir_ativo: bool = True,
):
    """
    Busca um produto pelo ID dentro da barbearia atual.
    """

    return buscar_registro(
        db=db,
        model=models.Produto,
        registro_id=produto_id,
        usuario_logado=usuario_logado,
        mensagem_nao_encontrado=(
            "Produto não encontrado ou indisponível."
        ),
        exigir_ativo=exigir_ativo,
    )


def atualizar_produto_service(
    produto_id: int,
    dados,
    db: Session,
    usuario_logado: models.Usuario,
):
    """
    Atualiza um produto pertencente à barbearia atual.
    """

    produto = buscar_produto_service(
        produto_id=produto_id,
        db=db,
        usuario_logado=usuario_logado,
        exigir_ativo=True,
    )

    dados_atualizacao = dados.model_dump(
        exclude_unset=True
    )

    novo_nome = produto.nome
    novo_codigo_qr = produto.codigo_qr

    if "nome" in dados_atualizacao:
        novo_nome = validar_nome_produto(
            dados_atualizacao["nome"]
        )

    if "categoria" in dados_atualizacao:
        dados_atualizacao["categoria"] = (
            normalizar_texto(
                dados_atualizacao["categoria"]
            )
        )

    if "codigo_qr" in dados_atualizacao:
        novo_codigo_qr = normalizar_texto(
            dados_atualizacao["codigo_qr"]
        )

        dados_atualizacao["codigo_qr"] = (
            novo_codigo_qr
        )

    novo_preco_custo = dados_atualizacao.get(
        "preco_custo",
        produto.preco_custo,
    )

    novo_preco_venda = dados_atualizacao.get(
        "preco_venda",
        produto.preco_venda,
    )

    novo_estoque = dados_atualizacao.get(
        "estoque",
        produto.estoque,
    )

    validar_valores_produto(
        preco_custo=novo_preco_custo,
        preco_venda=novo_preco_venda,
        estoque=novo_estoque,
    )

    validar_duplicidade_produto(
        db=db,
        usuario_logado=usuario_logado,
        nome=novo_nome,
        codigo_qr=novo_codigo_qr,
        produto_id_ignorado=produto.id,
    )

    if "nome" in dados_atualizacao:
        dados_atualizacao["nome"] = novo_nome

    for campo, valor in dados_atualizacao.items():
        setattr(
            produto,
            campo,
            valor,
        )

    return salvar_alteracoes(
        db=db,
        registro=produto,
        mensagem_erro=(
            "Não foi possível atualizar o produto."
        ),
    )


def inativar_produto_service(
    produto_id: int,
    db: Session,
    usuario_logado: models.Usuario,
):
    """
    Realiza a exclusão lógica do produto.
    """

    produto = buscar_produto_service(
        produto_id=produto_id,
        db=db,
        usuario_logado=usuario_logado,
        exigir_ativo=True,
    )

    return inativar_registro(
        db=db,
        registro=produto,
    )


def reativar_produto_service(
    produto_id: int,
    db: Session,
    usuario_logado: models.Usuario,
):
    """
    Reativa um produto da barbearia atual.
    """

    produto = buscar_produto_service(
        produto_id=produto_id,
        db=db,
        usuario_logado=usuario_logado,
        exigir_ativo=False,
    )

    return reativar_registro(
        db=db,
        registro=produto,
    )