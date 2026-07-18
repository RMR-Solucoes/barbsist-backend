from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from sqlalchemy.orm import (
    Session,
    joinedload
)

import models

from database import get_db

from schemas import (
    ComandaCreate,
    ComandaResponse,
    AdicionarServicoComanda,
    AdicionarProdutoComanda,
    ItemComandaResponse,
    FecharComanda,
    UsarPlanoItemComandaRequest
)

from services.comanda_service import (
    fechar_comanda_service,
    obter_assinatura_disponivel_comanda_service,
    usar_plano_em_item_comanda_service
)

from services.estoque_service import (
    validar_estoque,
    baixar_estoque
)

from auth.permissions import (
    admin_gerente_recepcao_ou_barbeiro
)

from auth.dependencies import (
    get_barbeiro_logado
)

from auth.tenant import (
    buscar_da_barbearia,
    consultar_da_barbearia,
    obter_barbearia_id
)


router = APIRouter(
    prefix="/comandas",
    tags=["Comandas"]
)

@router.post(
    "",
    response_model=ComandaResponse
)
def abrir_comanda(
    comanda: ComandaCreate,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_recepcao_ou_barbeiro
    )
):
    barbearia_id = obter_barbearia_id(
        usuario_logado
    )

    barbeiro = buscar_da_barbearia(
        db=db,
        model=models.Barbeiro,
        registro_id=comanda.barbeiro_id,
        usuario=usuario_logado,
        mensagem_nao_encontrado=(
            "Barbeiro não encontrado ou inativo."
        )
    )

    if not barbeiro.ativo:
        raise HTTPException(
            status_code=404,
            detail="Barbeiro não encontrado ou inativo."
        )

    cliente_id = None

    if comanda.cliente_id is not None:
        cliente = buscar_da_barbearia(
            db=db,
            model=models.Cliente,
            registro_id=comanda.cliente_id,
            usuario=usuario_logado,
            mensagem_nao_encontrado=(
                "Cliente não encontrado ou inativo."
            )
        )

        if not cliente.ativo:
            raise HTTPException(
                status_code=404,
                detail="Cliente não encontrado ou inativo."
            )

        cliente_id = cliente.id

    nova_comanda = models.Comanda(
        cliente_id=cliente_id,
        barbeiro_id=barbeiro.id,
        status="aberta",
        total=0,
        barbearia_id=barbearia_id
    )

    db.add(nova_comanda)
    db.commit()
    db.refresh(nova_comanda)

    return nova_comanda


@router.get(
    "",
    response_model=list[ComandaResponse]
)
def listar_comandas(
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_recepcao_ou_barbeiro
    )
):
    return (
        consultar_da_barbearia(
            db=db,
            model=models.Comanda,
            usuario=usuario_logado
        )
        .options(
            joinedload(models.Comanda.cliente),
            joinedload(models.Comanda.barbeiro),
            joinedload(models.Comanda.itens)
        )
        .order_by(
            models.Comanda.id.desc()
        )
        .all()
    )


@router.get(
    "/minhas",
    response_model=list[ComandaResponse]
)
def minhas_comandas(
    barbeiro_id: int = Depends(
        get_barbeiro_logado
    ),
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_recepcao_ou_barbeiro
    )
):
    return (
        consultar_da_barbearia(
            db=db,
            model=models.Comanda,
            usuario=usuario_logado
        )
        .options(
            joinedload(models.Comanda.cliente),
            joinedload(models.Comanda.barbeiro),
            joinedload(models.Comanda.itens)
        )
        .filter(
            models.Comanda.barbeiro_id
            == barbeiro_id
        )
        .order_by(
            models.Comanda.id.desc()
        )
        .all()
    )


@router.get(
    "/{comanda_id}",
    response_model=ComandaResponse
)
def buscar_comanda(
    comanda_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_recepcao_ou_barbeiro
    )
):
    comanda = (
        consultar_da_barbearia(
            db=db,
            model=models.Comanda,
            usuario=usuario_logado
        )
        .options(
            joinedload(models.Comanda.cliente),
            joinedload(models.Comanda.barbeiro),
            joinedload(models.Comanda.itens)
        )
        .filter(
            models.Comanda.id == comanda_id
        )
        .first()
    )

    if not comanda:
        raise HTTPException(
            status_code=404,
            detail="Comanda não encontrada."
        )

    return comanda


@router.get(
    "/{comanda_id}/assinatura"
)
def consultar_assinatura_da_comanda(
    comanda_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_recepcao_ou_barbeiro
    )
):
    return obter_assinatura_disponivel_comanda_service(
        db=db,
        comanda_id=comanda_id,
        usuario_logado=usuario_logado
    )


@router.post(
    "/{comanda_id}/servicos",
    response_model=ItemComandaResponse
)
def adicionar_servico_na_comanda(
    comanda_id: int,
    item: AdicionarServicoComanda,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_recepcao_ou_barbeiro
    )
):
    if item.quantidade <= 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "A quantidade do serviço deve ser "
                "maior que zero."
            )
        )

    comanda = buscar_da_barbearia(
        db=db,
        model=models.Comanda,
        registro_id=comanda_id,
        usuario=usuario_logado,
        mensagem_nao_encontrado=(
            "Comanda não encontrada ou já fechada."
        )
    )

    if comanda.status != "aberta":
        raise HTTPException(
            status_code=404,
            detail=(
                "Comanda não encontrada ou já fechada."
            )
        )

    servico = buscar_da_barbearia(
        db=db,
        model=models.Servico,
        registro_id=item.servico_id,
        usuario=usuario_logado,
        mensagem_nao_encontrado=(
            "Serviço não encontrado ou inativo."
        )
    )

    if not servico.ativo:
        raise HTTPException(
            status_code=404,
            detail="Serviço não encontrado ou inativo."
        )

    subtotal = (
        servico.preco * item.quantidade
    )

    novo_item = models.ItemComanda(
        comanda_id=comanda.id,
        tipo="servico",
        descricao=servico.nome,
        quantidade=item.quantidade,
        valor_unitario=servico.preco,
        subtotal=subtotal,
        servico_id=servico.id,
        pago_com_plano=False,
        uso_plano_id=None
    )

    comanda.total = (
        (comanda.total or 0) + subtotal
    )

    db.add(novo_item)
    db.commit()
    db.refresh(novo_item)

    return novo_item


@router.post(
    "/{comanda_id}/produtos",
    response_model=ItemComandaResponse
)
def adicionar_produto_na_comanda(
    comanda_id: int,
    item: AdicionarProdutoComanda,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_recepcao_ou_barbeiro
    )
):
    if item.quantidade <= 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "A quantidade do produto deve ser "
                "maior que zero."
            )
        )

    comanda = buscar_da_barbearia(
        db=db,
        model=models.Comanda,
        registro_id=comanda_id,
        usuario=usuario_logado,
        mensagem_nao_encontrado=(
            "Comanda não encontrada ou já fechada."
        )
    )

    if comanda.status != "aberta":
        raise HTTPException(
            status_code=404,
            detail=(
                "Comanda não encontrada ou já fechada."
            )
        )

    produto = buscar_da_barbearia(
        db=db,
        model=models.Produto,
        registro_id=item.produto_id,
        usuario=usuario_logado,
        mensagem_nao_encontrado=(
            "Produto não encontrado ou inativo."
        )
    )

    if not produto.ativo:
        raise HTTPException(
            status_code=404,
            detail="Produto não encontrado ou inativo."
        )

    validar_estoque(
        produto=produto,
        quantidade=item.quantidade
    )

    subtotal = (
        produto.preco_venda
        * item.quantidade
    )

    novo_item = models.ItemComanda(
        comanda_id=comanda.id,
        tipo="produto",
        descricao=produto.nome,
        quantidade=item.quantidade,
        valor_unitario=produto.preco_venda,
        subtotal=subtotal,
        produto_id=produto.id,
        pago_com_plano=False,
        uso_plano_id=None
    )

    baixar_estoque(
        produto=produto,
        quantidade=item.quantidade
    )

    comanda.total = (
        (comanda.total or 0) + subtotal
    )

    db.add(novo_item)
    db.commit()
    db.refresh(novo_item)

    return novo_item


@router.get(
    "/{comanda_id}/itens",
    response_model=list[ItemComandaResponse]
)
def listar_itens_da_comanda(
    comanda_id: int,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_recepcao_ou_barbeiro
    )
):
    comanda = buscar_da_barbearia(
        db=db,
        model=models.Comanda,
        registro_id=comanda_id,
        usuario=usuario_logado,
        mensagem_nao_encontrado=(
            "Comanda não encontrada."
        )
    )

    return (
        db.query(models.ItemComanda)
        .filter(
            models.ItemComanda.comanda_id
            == comanda.id
        )
        .order_by(
            models.ItemComanda.id.asc()
        )
        .all()
    )


@router.post(
    "/{comanda_id}/itens/{item_id}/usar-plano"
)
def usar_plano_no_item(
    comanda_id: int,
    item_id: int,
    dados: UsarPlanoItemComandaRequest,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_recepcao_ou_barbeiro
    )
):
    return usar_plano_em_item_comanda_service(
        db=db,
        comanda_id=comanda_id,
        item_id=item_id,
        assinatura_id=dados.assinatura_id,
        usuario_logado=usuario_logado
    )


@router.put(
    "/{comanda_id}/fechar"
)
def fechar_comanda(
    comanda_id: int,
    dados: FecharComanda,
    db: Session = Depends(get_db),
    usuario_logado=Depends(
        admin_gerente_recepcao_ou_barbeiro
    )
):
    return fechar_comanda_service(
        db=db,
        comanda_id=comanda_id,
        forma_pagamento=dados.forma_pagamento,
        usuario_logado=usuario_logado
    )
