import os

from database import SessionLocal
from auth.security import criar_hash_senha
import models


EMAIL = os.getenv(
    "BOOTSTRAP_SUPERADMIN_EMAIL",
    "",
).strip().lower()

SENHA = os.getenv(
    "BOOTSTRAP_SUPERADMIN_PASSWORD",
    "",
)

NOME = os.getenv(
    "BOOTSTRAP_SUPERADMIN_NAME",
    "MaxBarbSist",
).strip()

BARBEARIA_NOME = os.getenv(
    "BOOTSTRAP_BARBEARIA_NOME",
    "Barbearia do Mario",
).strip()

BARBEARIA_SLUG = os.getenv(
    "BOOTSTRAP_BARBEARIA_SLUG",
    "barbearia-do-mario",
).strip().lower()


def validar_variaveis():
    if not EMAIL:
        raise RuntimeError(
            "BOOTSTRAP_SUPERADMIN_EMAIL não configurado."
        )

    if len(SENHA) < 12:
        raise RuntimeError(
            "BOOTSTRAP_SUPERADMIN_PASSWORD deve ter "
            "pelo menos 12 caracteres."
        )

    if not NOME:
        raise RuntimeError(
            "BOOTSTRAP_SUPERADMIN_NAME não configurado."
        )

    if not BARBEARIA_NOME or not BARBEARIA_SLUG:
        raise RuntimeError(
            "Nome ou slug da barbearia não configurado."
        )


def executar():
    validar_variaveis()

    db = SessionLocal()

    try:
        barbearia = (
            db.query(models.Barbearia)
            .filter(
                models.Barbearia.slug
                == BARBEARIA_SLUG
            )
            .first()
        )

        if not barbearia:
            barbearia = models.Barbearia(
                nome=BARBEARIA_NOME,
                slug=BARBEARIA_SLUG,
                responsavel="Administrador BarbSist",
                email=EMAIL,
                ativa=True,
            )

            db.add(barbearia)
            db.flush()

            print(
                "[OK] Barbearia inicial criada."
            )

        usuario = (
            db.query(models.Usuario)
            .filter(
                models.Usuario.email == EMAIL
            )
            .first()
        )

        if usuario:
            usuario.nome = NOME
            usuario.senha_hash = (
                criar_hash_senha(SENHA)
            )
            usuario.perfil = "superadmin"
            usuario.barbeiro_id = None
            usuario.ativo = True
            usuario.barbearia_id = barbearia.id

            print(
                "[OK] Superadmin atualizado."
            )

        else:
            usuario = models.Usuario(
                nome=NOME,
                email=EMAIL,
                senha_hash=(
                    criar_hash_senha(SENHA)
                ),
                perfil="superadmin",
                barbeiro_id=None,
                ativo=True,
                barbearia_id=barbearia.id,
            )

            db.add(usuario)

            print(
                "[OK] Superadmin criado."
            )

        db.commit()
        db.refresh(usuario)

        print(
            f"[OK] ID do superadmin: {usuario.id}"
        )
        print(
            f"[OK] Barbearia: {barbearia.slug}"
        )
        print(
            f"[OK] E-mail: {usuario.email}"
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    executar()