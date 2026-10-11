from __future__ import annotations

from collections import Counter

from database import SessionLocal, engine
import models


def main():
    dialect = engine.dialect.name
    print(f"DIALECTO={dialect}")

    tabela = models.AgendamentoServico.__table__

    # Cria a tabela conforme o ORM em qualquer banco suportado
    # (SQLite local ou PostgreSQL/Railway).
    tabela.create(bind=engine, checkfirst=True)

    # Garante indices declarados no modelo quando a tabela ja existia.
    for indice in tabela.indexes:
        indice.create(bind=engine, checkfirst=True)

    db = SessionLocal()
    try:
        agendamentos = (
            db.query(models.Agendamento)
            .order_by(models.Agendamento.id.asc())
            .all()
        )

        existentes = {
            agendamento_id
            for (agendamento_id,) in (
                db.query(models.AgendamentoServico.agendamento_id)
                .distinct()
                .all()
            )
        }

        criados = 0
        sem_servico = []

        for agendamento in agendamentos:
            if agendamento.id in existentes:
                continue

            servico = (
                db.query(models.Servico)
                .filter(models.Servico.id == agendamento.servico_id)
                .first()
            )

            if servico is None:
                sem_servico.append(agendamento.id)
                continue

            db.add(
                models.AgendamentoServico(
                    agendamento_id=agendamento.id,
                    servico_id=servico.id,
                    ordem=1,
                    preco_snapshot=servico.preco,
                    duracao_minutos_snapshot=(
                        servico.tempo_medio_minutos or 30
                    ),
                )
            )
            criados += 1

        db.commit()

        vinculos = (
            db.query(models.AgendamentoServico)
            .order_by(
                models.AgendamentoServico.agendamento_id.asc(),
                models.AgendamentoServico.ordem.asc(),
                models.AgendamentoServico.id.asc(),
            )
            .all()
        )

        agendamentos_com_vinculo = {
            v.agendamento_id for v in vinculos
        }

        faltantes = [
            a.id
            for a in agendamentos
            if a.id not in agendamentos_com_vinculo
        ]

        pares = Counter(
            (v.agendamento_id, v.servico_id)
            for v in vinculos
        )
        duplicados = [
            chave for chave, quantidade in pares.items()
            if quantidade > 1
        ]

        snapshots_invalidos = [
            v.id
            for v in vinculos
            if (
                v.preco_snapshot is None
                or v.duracao_minutos_snapshot is None
                or v.duracao_minutos_snapshot <= 0
            )
        ]

        print(f"AGENDAMENTOS={len(agendamentos)}")
        print(f"VINCULOS={len(vinculos)}")
        print(f"BACKFILL_CRIADOS={criados}")
        print(f"FALTANTES={len(faltantes)}")
        print(f"DUPLICADOS={len(duplicados)}")
        print(f"SNAPSHOTS_INVALIDOS={len(snapshots_invalidos)}")
        print(f"AGENDAMENTOS_SEM_SERVICO={len(sem_servico)}")

        if sem_servico:
            print(
                "IDS_SEM_SERVICO="
                + ",".join(map(str, sem_servico))
            )

        if faltantes or duplicados or snapshots_invalidos:
            raise RuntimeError(
                "Migracao terminou com inconsistencias."
            )

        print("MIGRACAO_MULTISSERVICO_PRODUCAO=OK")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
