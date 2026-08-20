"""
Migração consolidada da fundação Superadmin + Assinaturas SaaS BarbSist.

1. Permite Usuario.barbearia_id = NULL para o superadmin global.
2. Move usuários com perfil superadmin para barbearia_id = NULL.
3. Cria tabelas PlanoSaaS, AssinaturaSaaS e PagamentoSaaS.
4. Cria planos iniciais de homologação, somente se ainda não existirem.

Faça backup do banco antes de executar.
"""

from sqlalchemy import inspect, text

from database import Base, SessionLocal, engine
import models


def _sqlite_tornar_usuario_global_compativel():
    insp = inspect(engine)
    cols = {c["name"]: c for c in insp.get_columns("usuarios")}
    col = cols.get("barbearia_id")
    if not col or col.get("nullable", True):
        print("[OK] usuarios.barbearia_id já aceita NULL.")
        return

    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.execute(text("""
            CREATE TABLE usuarios_new (
                id INTEGER PRIMARY KEY,
                barbearia_id INTEGER NULL REFERENCES barbearias(id) ON DELETE RESTRICT,
                nome VARCHAR NOT NULL,
                email VARCHAR NOT NULL,
                senha_hash VARCHAR NOT NULL,
                perfil VARCHAR NOT NULL DEFAULT 'admin',
                barbeiro_id INTEGER NULL REFERENCES barbeiros(id),
                ativo BOOLEAN NOT NULL DEFAULT 1,
                data_criacao DATETIME NOT NULL,
                CONSTRAINT uq_usuario_barbearia_email UNIQUE (barbearia_id, email)
            )
        """))
        conn.execute(text("""
            INSERT INTO usuarios_new
                (id, barbearia_id, nome, email, senha_hash, perfil, barbeiro_id, ativo, data_criacao)
            SELECT
                id, barbearia_id, nome, email, senha_hash, perfil, barbeiro_id, ativo, data_criacao
            FROM usuarios
        """))
        conn.execute(text("DROP TABLE usuarios"))
        conn.execute(text("ALTER TABLE usuarios_new RENAME TO usuarios"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_usuarios_id ON usuarios (id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_usuarios_barbearia_id ON usuarios (barbearia_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_usuarios_email ON usuarios (email)"))
        conn.execute(text("PRAGMA foreign_keys=ON"))
    print("[OK] SQLite: usuarios.barbearia_id agora aceita NULL.")


def _sqlite_tornar_token_recuperacao_global_compativel():
    insp = inspect(engine)
    if "tokens_recuperacao_senha" not in insp.get_table_names():
        return
    cols = {c["name"]: c for c in insp.get_columns("tokens_recuperacao_senha")}
    col = cols.get("barbearia_id")
    if not col or col.get("nullable", True):
        print("[OK] tokens_recuperacao_senha.barbearia_id já aceita NULL.")
        return

    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.execute(text("""
            CREATE TABLE tokens_recuperacao_senha_new (
                id INTEGER PRIMARY KEY,
                usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
                barbearia_id INTEGER NULL REFERENCES barbearias(id),
                token_hash VARCHAR NOT NULL UNIQUE,
                criado_em DATETIME NOT NULL,
                expira_em DATETIME NOT NULL,
                utilizado BOOLEAN NOT NULL DEFAULT 0,
                utilizado_em DATETIME NULL
            )
        """))
        conn.execute(text("""
            INSERT INTO tokens_recuperacao_senha_new
                (id, usuario_id, barbearia_id, token_hash, criado_em, expira_em, utilizado, utilizado_em)
            SELECT id, usuario_id, barbearia_id, token_hash, criado_em, expira_em, utilizado, utilizado_em
            FROM tokens_recuperacao_senha
        """))
        conn.execute(text("DROP TABLE tokens_recuperacao_senha"))
        conn.execute(text("ALTER TABLE tokens_recuperacao_senha_new RENAME TO tokens_recuperacao_senha"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tokens_recuperacao_senha_id ON tokens_recuperacao_senha (id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tokens_recuperacao_senha_usuario_id ON tokens_recuperacao_senha (usuario_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tokens_recuperacao_senha_barbearia_id ON tokens_recuperacao_senha (barbearia_id)"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_tokens_recuperacao_senha_token_hash ON tokens_recuperacao_senha (token_hash)"))
        conn.execute(text("PRAGMA foreign_keys=ON"))
    print("[OK] SQLite: recuperação de senha agora aceita superadmin global.")


def _postgres_tornar_usuario_global_compativel():
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE usuarios ALTER COLUMN barbearia_id DROP NOT NULL"))
    print("[OK] PostgreSQL: usuarios.barbearia_id agora aceita NULL.")


def migrar_usuario_superadmin():
    dialect = engine.dialect.name
    if dialect == "sqlite":
        _sqlite_tornar_usuario_global_compativel()
        _sqlite_tornar_token_recuperacao_global_compativel()
    elif dialect in {"postgresql", "postgres"}:
        _postgres_tornar_usuario_global_compativel()
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE tokens_recuperacao_senha ALTER COLUMN barbearia_id DROP NOT NULL"))
        print("[OK] PostgreSQL: recuperação de senha aceita superadmin global.")
    else:
        raise RuntimeError(f"Banco não suportado automaticamente por esta migração: {dialect}")

    with engine.begin() as conn:
        conn.execute(text("UPDATE usuarios SET barbearia_id = NULL, barbeiro_id = NULL WHERE perfil = 'superadmin'"))
    print("[OK] Superadmin(s) convertido(s) para usuário(s) global(is).")


def criar_saas():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(models.PlanoSaaS).count() == 0:
            db.add_all([
                models.PlanoSaaS(
                    nome="Mensal", descricao="Plano mensal BarbSist",
                    periodo_meses=1, valor_pix=0.01, valor_cartao=0.01,
                    max_parcelas_cartao=1, ativo=True,
                ),
                models.PlanoSaaS(
                    nome="Semestral", descricao="Plano semestral BarbSist",
                    periodo_meses=6, valor_pix=0.01, valor_cartao=0.01,
                    max_parcelas_cartao=6, ativo=True,
                ),
                models.PlanoSaaS(
                    nome="Anual", descricao="Plano anual BarbSist",
                    periodo_meses=12, valor_pix=0.01, valor_cartao=0.01,
                    max_parcelas_cartao=12, ativo=True,
                ),
            ])
            db.commit()
            print("[OK] Planos SaaS de homologação criados a R$ 0,01.")
        else:
            print("[OK] Planos SaaS já existem; nada duplicado.")
    finally:
        db.close()


if __name__ == "__main__":
    migrar_usuario_superadmin()
    criar_saas()
    print("[OK] Migração Superadmin + SaaS concluída.")
