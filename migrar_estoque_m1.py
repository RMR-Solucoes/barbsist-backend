from sqlalchemy import inspect, text

from database import SessionLocal, engine
import models


def main():
    print("DIALECT=", engine.dialect.name)

    inspector = inspect(engine)
    tabelas = set(inspector.get_table_names())

    if "produtos" not in tabelas:
        raise RuntimeError("Tabela produtos não encontrada.")

    colunas = {
        coluna["name"]
        for coluna in inspector.get_columns("produtos")
    }

    if "estoque_minimo" not in colunas:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE produtos "
                    "ADD COLUMN estoque_minimo INTEGER NOT NULL DEFAULT 2"
                )
            )
        print("COLUNA_ESTOQUE_MINIMO=CRIADA")
    else:
        print("COLUNA_ESTOQUE_MINIMO=JA_EXISTE")

    models.MovimentacaoEstoque.__table__.create(
        bind=engine,
        checkfirst=True,
    )
    print("TABELA_MOVIMENTACOES_ESTOQUE=OK")

    db = SessionLocal()

    try:
        produtos = db.query(models.Produto).order_by(models.Produto.id).all()
        criados = 0

        for produto in produtos:
            if produto.estoque_minimo is None:
                produto.estoque_minimo = 2

            existe = (
                db.query(models.MovimentacaoEstoque)
                .filter(
                    models.MovimentacaoEstoque.barbearia_id
                    == produto.barbearia_id,
                    models.MovimentacaoEstoque.produto_id
                    == produto.id,
                    models.MovimentacaoEstoque.origem
                    == "MIGRACAO_M1",
                )
                .first()
            )

            if existe:
                continue

            saldo = int(produto.estoque or 0)

            db.add(
                models.MovimentacaoEstoque(
                    barbearia_id=produto.barbearia_id,
                    produto_id=produto.id,
                    tipo="SALDO",
                    origem="MIGRACAO_M1",
                    quantidade=0,
                    saldo_anterior=saldo,
                    saldo_posterior=saldo,
                    referencia_id=None,
                    usuario_id=None,
                    observacao="Fotografia do saldo existente na implantação do Estoque M1.",
                )
            )
            criados += 1

        db.commit()

        total_movimentos = db.query(
            models.MovimentacaoEstoque
        ).count()

        print("PRODUTOS_EXISTENTES=", len(produtos))
        print("BACKFILL_MIGRACAO_CRIADOS=", criados)
        print("MOVIMENTACOES_TOTAL=", total_movimentos)
        print("MIGRACAO_ESTOQUE_M1=OK")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
