from sqlalchemy.orm import Session
from models import ConfiguracaoFuncionamento
from schemas import (
    ConfiguracaoFuncionamentoCreate,
    ConfiguracaoFuncionamentoUpdate,
)


def criar_configuracao_padrao(db: Session):
    existentes = db.query(ConfiguracaoFuncionamento).count()

    if existentes > 0:
        return db.query(ConfiguracaoFuncionamento).order_by(
            ConfiguracaoFuncionamento.dia_semana
        ).all()

    configuracoes = []

    for dia in range(7):
        trabalha = dia != 6  # domingo fechado por padrão

        config = ConfiguracaoFuncionamento(
            dia_semana=dia,
            trabalha=trabalha,
            hora_inicio="08:00",
            hora_fim="20:00" if dia != 5 else "18:00",
        )

        db.add(config)
        configuracoes.append(config)

    db.commit()

    for config in configuracoes:
        db.refresh(config)

    return configuracoes


def listar_configuracoes(db: Session):
    criar_configuracao_padrao(db)

    return db.query(ConfiguracaoFuncionamento).order_by(
        ConfiguracaoFuncionamento.dia_semana
    ).all()


def buscar_configuracao_por_dia(db: Session, dia_semana: int):
    criar_configuracao_padrao(db)

    return db.query(ConfiguracaoFuncionamento).filter(
        ConfiguracaoFuncionamento.dia_semana == dia_semana
    ).first()


def atualizar_configuracao(
    db: Session,
    configuracao_id: int,
    dados: ConfiguracaoFuncionamentoUpdate,
):
    config = db.query(ConfiguracaoFuncionamento).filter(
        ConfiguracaoFuncionamento.id == configuracao_id
    ).first()

    if not config:
        return None

    if dados.trabalha is not None:
        config.trabalha = dados.trabalha

    if dados.hora_inicio is not None:
        config.hora_inicio = dados.hora_inicio

    if dados.hora_fim is not None:
        config.hora_fim = dados.hora_fim

    db.commit()
    db.refresh(config)

    return config