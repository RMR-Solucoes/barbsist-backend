from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

import models

from auth.tenant import (
    buscar_da_barbearia,
    consultar_da_barbearia,
    obter_barbearia_id,
    obter_barbearia_usuario
)

from services.plano_service import (
    atualizar_status_assinatura
)

from services.sequencia_service import (
    gerar_codigo_comercial
)

from services.crud_service import (
    criar_registro_com_codigo,
    consultar_registros,
    buscar_registro,
    salvar_alteracoes,
    inativar_registro,
    reativar_registro
)


def normalizar_texto(
    valor: str | None
) -> str | None:
    """
    Remove espaços extras.

    Retorna None quando o valor estiver vazio.
    """

    if valor is None:
        return None

    valor_normalizado = valor.strip()

    return valor_normalizado or None


def normalizar_email(
    email: str | None
) -> str | None:
    """
    Padroniza o e-mail em letras minúsculas.
    """

    email_normalizado = normalizar_texto(email)

    if email_normalizado is None:
        return None

    return email_normalizado.lower()


def normalizar_telefone(
    telefone: str | None
) -> str | None:
    """
    Mantém somente os números do telefone.

    Exemplo:
        (11) 99999-9999 -> 11999999999
    """

    telefone_normalizado = normalizar_texto(
        telefone
    )

    if telefone_normalizado is None:
        return None

    somente_numeros = "".join(
        caractere
        for caractere in telefone_normalizado
        if caractere.isdigit()
    )

    return somente_numeros or None


def validar_nome_cliente(
    nome: str
) -> str:
    """
    Valida e normaliza o nome do cliente.
    """

    nome_normalizado = normalizar_texto(nome)

    if not nome_normalizado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O nome do cliente é obrigatório."
        )

    if len(nome_normalizado) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "O nome do cliente deve possuir "
                "pelo menos 2 caracteres."
            )
        )

    return nome_normalizado


def validar_duplicidade_cliente(
    db: Session,
    usuario_logado: models.Usuario,
    telefone: str | None,
    email: str | None,
    cliente_id_ignorado: int | None = None
):
    """
    Verifica duplicidade de telefone ou e-mail somente
    dentro da barbearia atual.

    Clientes de barbearias diferentes podem possuir
    o mesmo telefone ou e-mail.
    """

    barbearia_id = obter_barbearia_id(
        usuario_logado
    )

    criterios = []

    if telefone:
        criterios.append(
            models.Cliente.telefone == telefone
        )

    if email:
        criterios.append(
            models.Cliente.email == email
        )

    if not criterios:
        return

    query = db.query(
        models.Cliente
    ).filter(
        models.Cliente.barbearia_id == barbearia_id,
        or_(*criterios)
    )

    if cliente_id_ignorado is not None:
        query = query.filter(
            models.Cliente.id != cliente_id_ignorado
        )

    cliente_existente = query.first()

    if not cliente_existente:
        return

    if (
        telefone
        and cliente_existente.telefone == telefone
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Já existe um cliente com este telefone "
                "nesta barbearia."
            )
        )

    if (
        email
        and cliente_existente.email == email
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Já existe um cliente com este e-mail "
                "nesta barbearia."
            )
        )


def criar_cliente_service(
    dados,
    db: Session,
    usuario_logado: models.Usuario
):
    """
    Cria um cliente vinculado automaticamente à
    barbearia do usuário autenticado.
    """

    nome = validar_nome_cliente(
        dados.nome
    )

    telefone = normalizar_telefone(
        dados.telefone
    )

    email = normalizar_email(
        dados.email
    )

    observacoes = normalizar_texto(
        dados.observacoes
    )

    validar_duplicidade_cliente(
        db=db,
        usuario_logado=usuario_logado,
        telefone=telefone,
        email=email
    )

    return criar_registro_com_codigo(
        db=db,
        model=models.Cliente,
        tipo_sequencia="CLIENTE",
        usuario_logado=usuario_logado,
        dados={
            "nome": nome,
            "telefone": telefone,
            "email": email,
            "observacoes": observacoes,
            "ativo": True
        }
    )


def listar_clientes_service(
    db: Session,
    usuario_logado: models.Usuario,
    apenas_ativos: bool = True
):
    """
    Lista somente os clientes da barbearia atual.
    """

    query = consultar_registros(
        db=db,
        model=models.Cliente,
        usuario_logado=usuario_logado,
        apenas_ativos=apenas_ativos
    )

    return query.order_by(
        models.Cliente.nome.asc()
    ).all()


def buscar_cliente_service(
    cliente_id: int,
    db: Session,
    usuario_logado: models.Usuario,
    exigir_ativo: bool = True
):
    """
    Busca um cliente dentro da barbearia atual.

    Clientes pertencentes a outras barbearias são tratados
    como registros inexistentes.
    """

    return buscar_registro(
        db=db,
        model=models.Cliente,
        registro_id=cliente_id,
        usuario_logado=usuario_logado,
        mensagem_nao_encontrado=(
            "Cliente não encontrado."
        ),
        exigir_ativo=exigir_ativo
    )


def atualizar_cliente_service(
    cliente_id: int,
    dados,
    db: Session,
    usuario_logado: models.Usuario
):
    """
    Atualiza somente os campos enviados pelo frontend.
    """

    cliente = buscar_cliente_service(
        cliente_id=cliente_id,
        db=db,
        usuario_logado=usuario_logado,
        exigir_ativo=True
    )

    dados_enviados = dados.model_dump(
        exclude_unset=True
    )

    if not dados_enviados:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Nenhum dado foi informado "
                "para atualização."
            )
        )

    nome = cliente.nome
    telefone = cliente.telefone
    email = cliente.email
    observacoes = cliente.observacoes

    if "nome" in dados_enviados:
        nome = validar_nome_cliente(
            dados_enviados["nome"]
        )

    if "telefone" in dados_enviados:
        telefone = normalizar_telefone(
            dados_enviados["telefone"]
        )

    if "email" in dados_enviados:
        email = normalizar_email(
            dados_enviados["email"]
        )

    if "observacoes" in dados_enviados:
        observacoes = normalizar_texto(
            dados_enviados["observacoes"]
        )

    validar_duplicidade_cliente(
        db=db,
        usuario_logado=usuario_logado,
        telefone=telefone,
        email=email,
        cliente_id_ignorado=cliente.id
    )

    cliente.nome = nome
    cliente.telefone = telefone
    cliente.email = email
    cliente.observacoes = observacoes

    return salvar_alteracoes(
        db=db,
        registro=cliente,
        mensagem_erro=(
            "Não foi possível atualizar o cliente. "
            "Verifique os dados informados."
        )
    )


def inativar_cliente_service(
    cliente_id: int,
    db: Session,
    usuario_logado: models.Usuario
):
    """
    Realiza a exclusão lógica do cliente.
    """

    cliente = buscar_cliente_service(
        cliente_id=cliente_id,
        db=db,
        usuario_logado=usuario_logado,
        exigir_ativo=False
    )

    if not cliente.ativo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cliente já está inativo."
        )

    return inativar_registro(
        db=db,
        registro=cliente
    )


def reativar_cliente_service(
    cliente_id: int,
    db: Session,
    usuario_logado: models.Usuario
):
    """
    Reativa um cliente da própria barbearia.
    """

    cliente = buscar_cliente_service(
        cliente_id=cliente_id,
        db=db,
        usuario_logado=usuario_logado,
        exigir_ativo=False
    )

    if cliente.ativo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cliente já está ativo."
        )

    validar_duplicidade_cliente(
        db=db,
        usuario_logado=usuario_logado,
        telefone=cliente.telefone,
        email=cliente.email,
        cliente_id_ignorado=cliente.id
    )

    return reativar_registro(
        db=db,
        registro=cliente
    )


def listar_clientes_com_assinaturas_service(
    db: Session,
    usuario_logado: models.Usuario
):
    """
    Lista os clientes ativos da barbearia atual juntamente
    com os dados de suas assinaturas.
    """

    barbearia_id = obter_barbearia_id(
        usuario_logado
    )

    clientes = listar_clientes_service(
        db=db,
        usuario_logado=usuario_logado,
        apenas_ativos=True
    )

    resultado = []
    houve_alteracao = False

    for cliente in clientes:
        assinaturas = (
            db.query(models.AssinaturaCliente)
            .filter(
                models.AssinaturaCliente.barbearia_id
                == barbearia_id,

                models.AssinaturaCliente.cliente_id
                == cliente.id
            )
            .order_by(
                models.AssinaturaCliente.id.desc()
            )
            .all()
        )

        for assinatura in assinaturas:
            status_anterior = assinatura.status
            pagamento_anterior = (
                assinatura.status_pagamento
            )

            atualizar_status_assinatura(
                assinatura
            )

            if (
                assinatura.status != status_anterior
                or assinatura.status_pagamento
                != pagamento_anterior
            ):
                houve_alteracao = True

        assinatura_atual = next(
            (
                assinatura
                for assinatura in assinaturas
                if assinatura.status in {
                    "ATIVO",
                    "VENCIDO",
                    "SUSPENSO"
                }
            ),
            None
        )

        if (
            assinatura_atual is None
            and assinaturas
        ):
            assinatura_atual = assinaturas[0]

        plano = None

        if assinatura_atual:
            plano = (
                db.query(models.Plano)
                .filter(
                    models.Plano.id
                    == assinatura_atual.plano_id,

                    models.Plano.barbearia_id
                    == barbearia_id
                )
                .first()
)

        resultado.append({
            "id": cliente.id,
            "numero_sequencial": (
                cliente.numero_sequencial
            ),
            "codigo": cliente.codigo,
            "nome": cliente.nome,
            "telefone": cliente.telefone,
            "email": cliente.email,
            "observacoes": cliente.observacoes,
            "ativo": cliente.ativo,

            "possui_assinatura": (
                assinatura_atual is not None
            ),

            "assinatura_id": (
                assinatura_atual.id
                if assinatura_atual
                else None
            ),

            "assinatura_status": (
                assinatura_atual.status
                if assinatura_atual
                else None
            ),

            "status_pagamento": (
                assinatura_atual.status_pagamento
                if assinatura_atual
                else None
            ),

            "plano_id": (
                assinatura_atual.plano_id
                if assinatura_atual
                else None
            ),

            "plano_nome": (
                plano.nome
                if plano
                else None
            ),

            "data_proximo_vencimento": (
                assinatura_atual.data_proximo_vencimento
                if assinatura_atual
                else None
            ),

            "usos_disponiveis": (
                assinatura_atual.usos_disponiveis
                if assinatura_atual
                else None
            ),

            "quantidade_servicos_plano": (
                plano.quantidade_servicos
                if plano
                else None
            )
        })

    if houve_alteracao:
        db.commit()

    return resultado


def listar_clientes_do_barbeiro_service(
    barbeiro_id: int,
    db: Session,
    usuario_logado: models.Usuario
):
    """
    Lista os clientes atendidos pelo barbeiro autenticado,
    sempre dentro da mesma barbearia.
    """

    barbearia_id = obter_barbearia_id(
        usuario_logado
    )

    return (
        db.query(models.Cliente)
        .join(
            models.Comanda,
            models.Comanda.cliente_id
            == models.Cliente.id
        )
        .filter(
            models.Cliente.barbearia_id
            == barbearia_id,

            models.Cliente.ativo.is_(True),

            models.Comanda.barbeiro_id
            == barbeiro_id
        )
        .distinct()
        .order_by(
            models.Cliente.nome.asc()
        )
        .all()
    )