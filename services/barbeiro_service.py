import re

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

import models

from auth.tenant import obter_barbearia_id
from services.adequacao_plano_saas_service import reconciliar_adequacao_plano_saas

from services.crud_service import (
    criar_registro_com_codigo,
    consultar_registros,
    buscar_registro,
    salvar_alteracoes,
    inativar_registro,
    reativar_registro,
)


def validar_limite_barbeiros_saas(
    db: Session,
    usuario_logado: models.Usuario,
):
    """Compatibilidade V4.7.2A: cadastro nao e mais bloqueado por capacidade."""
    return

def normalizar_texto(
    valor: str | None,
    *,
    maiusculo: bool = True
) -> str | None:
    if valor is None:
        return None

    valor_normalizado = " ".join(
        valor.strip().split()
    )

    if not valor_normalizado:
        return None

    if maiusculo:
        return valor_normalizado.upper()

    return valor_normalizado


def normalizar_email(
    valor: str | None
) -> str | None:
    if valor is None:
        return None

    email = valor.strip().lower()

    if not email:
        return None

    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe um e-mail válido."
        )

    return email


def limpar_telefone(
    valor: str | None
) -> str | None:
    if valor is None:
        return None

    telefone = re.sub(
        r"\D",
        "",
        valor
    )

    if not telefone:
        return None

    if len(telefone) not in (10, 11):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Informe um telefone válido com DDD, "
                "contendo 10 ou 11 dígitos."
            )
        )

    return telefone


def validar_nome(
    nome: str | None
) -> str:
    nome_normalizado = normalizar_texto(
        nome
    )

    if not nome_normalizado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe o nome do barbeiro."
        )

    if len(nome_normalizado) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "O nome do barbeiro deve possuir "
                "pelo menos 2 caracteres."
            )
        )

    return nome_normalizado


def validar_percentual(
    percentual: float | None
) -> float:
    if percentual is None:
        return 50.0

    try:
        percentual_validado = float(
            percentual
        )
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "O percentual de comissão é inválido."
            )
        )

    if percentual_validado < 0 or percentual_validado > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "O percentual de comissão deve estar "
                "entre 0 e 100."
            )
        )

    return round(
        percentual_validado,
        2
    )


def validar_tipo(
    tipo: str | None
) -> str:
    tipo_normalizado = normalizar_texto(
        tipo
    ) or "ASSOCIADO"

    tipos_validos = {
        "ASSOCIADO",
        "FUNCIONARIO",
        "AUTONOMO",
        "PROPRIETARIO",
        "PARCEIRO",
        "COMISSIONADO",
        "ALUGUEL DE CADEIRA",
        "DIARISTA",
        "ALUNO",
        "TESTE",
    }

    if tipo_normalizado not in tipos_validos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Tipo de vínculo inválido. Utilize "
                "ASSOCIADO, FUNCIONARIO, AUTONOMO "
                "ou PROPRIETARIO."
            )
        )

    return tipo_normalizado


def validar_dados_financeiros_vinculo(tipo, percentual, aluguel, periodicidade, vencimento, diaria):
    percentual = validar_percentual(percentual)
    if tipo == "ALUGUEL DE CADEIRA":
        try: aluguel = float(aluguel)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Informe um valor de aluguel valido.")
        if aluguel <= 0:
            raise HTTPException(status_code=400, detail="O valor do aluguel deve ser maior que zero.")
        periodicidade = normalizar_texto(periodicidade)
        if periodicidade not in {"SEMANAL", "QUINZENAL", "MENSAL"}:
            raise HTTPException(status_code=400, detail="Periodicidade invalida.")
        venc = None
        if periodicidade == "MENSAL":
            try: venc = int(vencimento)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="Informe vencimento entre 1 e 31.")
            if not 1 <= venc <= 31:
                raise HTTPException(status_code=400, detail="Informe vencimento entre 1 e 31.")
        return percentual, aluguel, periodicidade, venc, None
    if tipo == "DIARISTA":
        try: diaria = float(diaria)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Informe um valor de diaria valido.")
        if diaria <= 0:
            raise HTTPException(status_code=400, detail="O valor da diaria deve ser maior que zero.")
        return percentual, None, None, None, diaria
    return percentual, None, None, None, None

def validar_duplicidade_barbeiro(
    db: Session,
    usuario_logado: models.Usuario,
    telefone: str | None,
    email: str | None,
    barbeiro_id_ignorado: int | None = None
):
    barbearia_id = obter_barbearia_id(
        usuario_logado
    )

    if telefone:
        query = db.query(
            models.Barbeiro
        ).filter(
            models.Barbeiro.barbearia_id
            == barbearia_id,

            models.Barbeiro.telefone
            == telefone
        )

        if barbeiro_id_ignorado is not None:
            query = query.filter(
                models.Barbeiro.id
                != barbeiro_id_ignorado
            )

        if query.first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Já existe um barbeiro com este "
                    "telefone nesta barbearia."
                )
            )

    if email:
        query = db.query(
            models.Barbeiro
        ).filter(
            models.Barbeiro.barbearia_id
            == barbearia_id,

            models.Barbeiro.email
            == email
        )

        if barbeiro_id_ignorado is not None:
            query = query.filter(
                models.Barbeiro.id
                != barbeiro_id_ignorado
            )

        if query.first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Já existe um barbeiro com este "
                    "e-mail nesta barbearia."
                )
            )


def criar_barbeiro_service(
    dados,
    db: Session,
    usuario_logado: models.Usuario
):
    nome = validar_nome(
        dados.nome
    )

    telefone = limpar_telefone(
        dados.telefone
    )

    if not telefone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe o telefone do barbeiro."
        )

    email = normalizar_email(
        dados.email
    )

    tipo = validar_tipo(
        dados.tipo
    )

    (percentual_comissao, valor_aluguel_cadeira, periodicidade_aluguel,
     dia_vencimento_aluguel, valor_diaria) = validar_dados_financeiros_vinculo(
        tipo, dados.percentual_comissao, dados.valor_aluguel_cadeira,
        dados.periodicidade_aluguel, dados.dia_vencimento_aluguel, dados.valor_diaria
    )

    especialidades = normalizar_texto(
        dados.especialidades
    )

    observacoes = normalizar_texto(
        dados.observacoes,
        maiusculo=False
    )

    validar_duplicidade_barbeiro(
        db=db,
        usuario_logado=usuario_logado,
        telefone=telefone,
        email=email
    )

    barbeiro = criar_registro_com_codigo(
        db=db,
        model=models.Barbeiro,
        tipo_sequencia="BARBEIRO",
        usuario_logado=usuario_logado,
        dados={
            "nome": nome,
            "telefone": telefone,
            "email": email,
            "tipo": tipo,
            "percentual_comissao": percentual_comissao,
            "valor_aluguel_cadeira": valor_aluguel_cadeira,
            "periodicidade_aluguel": periodicidade_aluguel,
            "dia_vencimento_aluguel": dia_vencimento_aluguel,
            "valor_diaria": valor_diaria,
            "especialidades": especialidades,
            "observacoes": observacoes,
            "ativo": True,
        }
    )

    reconciliar_adequacao_plano_saas(
        db=db,
        barbearia_id=barbeiro.barbearia_id,
        barbeiro_evento_id=barbeiro.id,
    )
    return barbeiro


def listar_barbeiros_service(
    db: Session,
    usuario_logado: models.Usuario,
    apenas_ativos: bool = True
):
    query = consultar_registros(
        db=db,
        model=models.Barbeiro,
        usuario_logado=usuario_logado,
        apenas_ativos=apenas_ativos
    )

    return (
        query
        .order_by(
            models.Barbeiro.ativo.desc(),
            models.Barbeiro.nome.asc()
        )
        .all()
    )


def buscar_barbeiro_service(
    barbeiro_id: int,
    db: Session,
    usuario_logado: models.Usuario,
    exigir_ativo: bool = False
):
    return buscar_registro(
        db=db,
        model=models.Barbeiro,
        registro_id=barbeiro_id,
        usuario_logado=usuario_logado,
        mensagem_nao_encontrado=(
            "Barbeiro não encontrado."
        ),
        exigir_ativo=exigir_ativo
    )


def atualizar_barbeiro_service(
    barbeiro_id: int,
    dados,
    db: Session,
    usuario_logado: models.Usuario
):
    barbeiro = buscar_barbeiro_service(
        barbeiro_id=barbeiro_id,
        db=db,
        usuario_logado=usuario_logado,
        exigir_ativo=True
    )

    nome = validar_nome(
        dados.nome
    )

    telefone = limpar_telefone(
        dados.telefone
    )

    if not telefone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe o telefone do barbeiro."
        )

    email = normalizar_email(
        dados.email
    )

    tipo = validar_tipo(
        dados.tipo
    )

    (percentual_comissao, valor_aluguel_cadeira, periodicidade_aluguel,
     dia_vencimento_aluguel, valor_diaria) = validar_dados_financeiros_vinculo(
        tipo, dados.percentual_comissao, dados.valor_aluguel_cadeira,
        dados.periodicidade_aluguel, dados.dia_vencimento_aluguel, dados.valor_diaria
    )

    especialidades = normalizar_texto(
        dados.especialidades
    )

    observacoes = normalizar_texto(
        dados.observacoes,
        maiusculo=False
    )

    validar_duplicidade_barbeiro(
        db=db,
        usuario_logado=usuario_logado,
        telefone=telefone,
        email=email,
        barbeiro_id_ignorado=barbeiro.id
    )

    barbeiro.nome = nome
    barbeiro.telefone = telefone
    barbeiro.email = email
    barbeiro.tipo = tipo
    barbeiro.percentual_comissao = (
        percentual_comissao
    )
    barbeiro.valor_aluguel_cadeira = valor_aluguel_cadeira
    barbeiro.periodicidade_aluguel = periodicidade_aluguel
    barbeiro.dia_vencimento_aluguel = dia_vencimento_aluguel
    barbeiro.valor_diaria = valor_diaria
    barbeiro.especialidades = especialidades
    barbeiro.observacoes = observacoes

    return salvar_alteracoes(
        db=db,
        registro=barbeiro,
        mensagem_erro=(
            "Não foi possível atualizar o barbeiro. "
            "Verifique os dados informados."
        )
    )


def validar_barbeiro_sem_usuario_ativo(
    barbeiro: models.Barbeiro,
    db: Session
):
    usuario_vinculado = (
        db.query(models.Usuario)
        .filter(
            models.Usuario.barbearia_id
            == barbeiro.barbearia_id,

            models.Usuario.barbeiro_id
            == barbeiro.id,

            models.Usuario.ativo.is_(True)
        )
        .first()
    )

    if usuario_vinculado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Não é possível inativar este barbeiro "
                "enquanto houver um usuário ativo "
                "vinculado a ele."
            )
        )


def inativar_barbeiro_service(
    barbeiro_id: int,
    db: Session,
    usuario_logado: models.Usuario
):
    barbeiro = buscar_barbeiro_service(
        barbeiro_id=barbeiro_id,
        db=db,
        usuario_logado=usuario_logado,
        exigir_ativo=False
    )

    if not barbeiro.ativo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O barbeiro já está inativo."
        )

    validar_barbeiro_sem_usuario_ativo(
        barbeiro=barbeiro,
        db=db
    )

    barbeiro = inativar_registro(
        db=db,
        registro=barbeiro
    )

    reconciliar_adequacao_plano_saas(
        db=db,
        barbearia_id=barbeiro.barbearia_id,
    )
    return barbeiro


def reativar_barbeiro_service(
    barbeiro_id: int,
    db: Session,
    usuario_logado: models.Usuario
):
    barbeiro = buscar_barbeiro_service(
        barbeiro_id=barbeiro_id,
        db=db,
        usuario_logado=usuario_logado,
        exigir_ativo=False
    )

    if barbeiro.ativo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O barbeiro já está ativo."
        )

    validar_duplicidade_barbeiro(
        db=db,
        usuario_logado=usuario_logado,
        telefone=barbeiro.telefone,
        email=barbeiro.email,
        barbeiro_id_ignorado=barbeiro.id
    )

    barbeiro = reativar_registro(
        db=db,
        registro=barbeiro
    )



    reconciliar_adequacao_plano_saas(
        db=db,
        barbearia_id=barbeiro.barbearia_id,
        barbeiro_evento_id=barbeiro.id,
    )
    return barbeiro


def excluir_barbeiro_definitivamente_service(
    barbeiro_id: int,
    db: Session,
    usuario_logado: models.Usuario
):
    barbeiro = buscar_barbeiro_service(
        barbeiro_id=barbeiro_id, db=db,
        usuario_logado=usuario_logado, exigir_ativo=False
    )

    referencias = []
    for tabela in models.Base.metadata.sorted_tables:
        if tabela.name == models.Barbeiro.__table__.name:
            continue
        for coluna in tabela.columns:
            aponta = any(
                fk.column.table.name == models.Barbeiro.__table__.name
                and fk.column.name == "id"
                for fk in coluna.foreign_keys
            )
            if aponta and db.query(tabela).filter(coluna == barbeiro.id).first() is not None:
                referencias.append(tabela.name)
                break

    if referencias:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Este barbeiro possui historico vinculado e nao pode ser "
                "excluido definitivamente. Utilize Inativar para preservar "
                "os registros. Vinculos encontrados: "
                + ", ".join(sorted(set(referencias))) + "."
            )
        )

    barbearia_id = barbeiro.barbearia_id
    try:
        db.delete(barbeiro)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Nao foi possivel excluir este barbeiro porque existem registros vinculados. Utilize Inativar."
        )

    reconciliar_adequacao_plano_saas(db=db, barbearia_id=barbearia_id)
    return {"mensagem": "Barbeiro excluido definitivamente.", "barbeiro_id": barbeiro_id}

