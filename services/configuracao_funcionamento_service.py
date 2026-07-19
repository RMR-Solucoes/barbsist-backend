from sqlalchemy.orm import Session

import models

from auth.tenant import (
    buscar_da_barbearia,
    obter_barbearia_id,
)
from schemas import ConfiguracaoFuncionamentoUpdate


def criar_configuracao_padrao_por_barbearia(
    db: Session,
    barbearia_id: int,
):
    existentes = (
        db.query(models.ConfiguracaoFuncionamento)
        .filter(
            models.ConfiguracaoFuncionamento.barbearia_id
            == barbearia_id
        )
        .order_by(models.ConfiguracaoFuncionamento.dia_semana)
        .all()
    )

    dias_existentes = {item.dia_semana for item in existentes}
    novos = []

    for dia in range(7):
        if dia in dias_existentes:
            continue

        trabalha = dia != 6
        config = models.ConfiguracaoFuncionamento(
            barbearia_id=barbearia_id,
            dia_semana=dia,
            trabalha=trabalha,
            hora_inicio="08:00",
            hora_fim="18:00" if dia == 5 else "20:00",
        )
        db.add(config)
        novos.append(config)

    if novos:
        db.commit()

    return (
        db.query(models.ConfiguracaoFuncionamento)
        .filter(
            models.ConfiguracaoFuncionamento.barbearia_id
            == barbearia_id
        )
        .order_by(models.ConfiguracaoFuncionamento.dia_semana)
        .all()
    )


def criar_configuracao_padrao(db: Session, usuario_logado):
    return criar_configuracao_padrao_por_barbearia(
        db=db,
        barbearia_id=obter_barbearia_id(usuario_logado),
    )


def listar_configuracoes(db: Session, usuario_logado):
    return criar_configuracao_padrao(db, usuario_logado)


def buscar_configuracao_por_dia(
    db: Session,
    dia_semana: int,
    usuario_logado,
):
    criar_configuracao_padrao(db, usuario_logado)
    barbearia_id = obter_barbearia_id(usuario_logado)

    return (
        db.query(models.ConfiguracaoFuncionamento)
        .filter(
            models.ConfiguracaoFuncionamento.barbearia_id
            == barbearia_id,
            models.ConfiguracaoFuncionamento.dia_semana
            == dia_semana,
        )
        .first()
    )


def buscar_configuracao_publica_por_dia(
    db: Session,
    barbearia_id: int,
    dia_semana: int,
):
    criar_configuracao_padrao_por_barbearia(db, barbearia_id)

    return (
        db.query(models.ConfiguracaoFuncionamento)
        .filter(
            models.ConfiguracaoFuncionamento.barbearia_id
            == barbearia_id,
            models.ConfiguracaoFuncionamento.dia_semana
            == dia_semana,
        )
        .first()
    )


def atualizar_configuracao(
    db: Session,
    configuracao_id: int,
    dados: ConfiguracaoFuncionamentoUpdate,
    usuario_logado,
):
    config = buscar_da_barbearia(
        db=db,
        model=models.ConfiguracaoFuncionamento,
        registro_id=configuracao_id,
        usuario=usuario_logado,
        mensagem_nao_encontrado="Configuração não encontrada.",
    )

    if dados.trabalha is not None:
        config.trabalha = dados.trabalha
    if dados.hora_inicio is not None:
        config.hora_inicio = dados.hora_inicio
    if dados.hora_fim is not None:
        config.hora_fim = dados.hora_fim

    db.commit()
    db.refresh(config)
    return config
