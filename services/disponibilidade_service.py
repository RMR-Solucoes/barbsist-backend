from datetime import datetime

from fastapi import HTTPException

import models


def converter_hora(valor):
    if valor is None:
        return None
    if hasattr(valor, "hour") and hasattr(valor, "minute"):
        return valor
    texto = str(valor).strip()
    for formato in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(texto, formato).time()
        except ValueError:
            pass
    raise HTTPException(status_code=400, detail="Horário inválido. Use HH:MM.")


def validar_intervalo_horario(hora_inicio, hora_fim):
    inicio = converter_hora(hora_inicio)
    fim = converter_hora(hora_fim)
    if inicio is None or fim is None:
        raise HTTPException(status_code=400, detail="Horário inicial e final são obrigatórios.")
    if inicio >= fim:
        raise HTTPException(status_code=400, detail="O horário inicial deve ser anterior ao horário final.")
    return inicio, fim


def obter_horario_trabalho(
    db,
    barbearia_id: int,
    barbeiro_id: int,
    data_agenda,
):
    dia_semana = data_agenda.weekday()

    config = (
        db.query(models.ConfiguracaoFuncionamento)
        .filter(
            models.ConfiguracaoFuncionamento.barbearia_id == barbearia_id,
            models.ConfiguracaoFuncionamento.dia_semana == dia_semana,
        )
        .first()
    )

    disponibilidade = (
        db.query(models.BarbeiroDisponibilidade)
        .filter(
            models.BarbeiroDisponibilidade.barbearia_id == barbearia_id,
            models.BarbeiroDisponibilidade.barbeiro_id == barbeiro_id,
            models.BarbeiroDisponibilidade.dia_semana == dia_semana,
        )
        .first()
    )

    # Regra oficial: usa_padrao=True significa usar a configuração da barbearia.
    if disponibilidade is not None and disponibilidade.usa_padrao is False:
        if disponibilidade.trabalha is False:
            return None
        inicio, fim = validar_intervalo_horario(
            disponibilidade.hora_inicio,
            disponibilidade.hora_fim,
        )
        return inicio, fim

    if config is None or config.trabalha is False:
        return None

    inicio, fim = validar_intervalo_horario(config.hora_inicio, config.hora_fim)
    return inicio, fim


def validar_agendamento_no_expediente(
    db,
    barbearia_id: int,
    barbeiro_id: int,
    inicio,
    fim,
):
    horario = obter_horario_trabalho(
        db=db,
        barbearia_id=barbearia_id,
        barbeiro_id=barbeiro_id,
        data_agenda=inicio.date(),
    )

    if horario is None:
        raise HTTPException(
            status_code=400,
            detail="O barbeiro não trabalha nesta data.",
        )

    hora_inicio, hora_fim = horario
    limite_inicio = datetime.combine(inicio.date(), hora_inicio)
    limite_fim = datetime.combine(inicio.date(), hora_fim)

    if inicio < limite_inicio or fim > limite_fim:
        raise HTTPException(
            status_code=400,
            detail="O horário solicitado está fora do expediente/disponibilidade do barbeiro.",
        )

    return True
