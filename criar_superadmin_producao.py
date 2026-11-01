import os

from database import SessionLocal
from auth.security import criar_hash_senha
import models

EMAIL = os.getenv("BOOTSTRAP_SUPERADMIN_EMAIL", "").strip().lower()
SENHA = os.getenv("BOOTSTRAP_SUPERADMIN_PASSWORD", "")
NOME = os.getenv("BOOTSTRAP_SUPERADMIN_NAME", "MaxBarbSist").strip()


def validar_variaveis():
    if not EMAIL:
        raise RuntimeError("BOOTSTRAP_SUPERADMIN_EMAIL não configurado.")
    if len(SENHA) < 12:
        raise RuntimeError("BOOTSTRAP_SUPERADMIN_PASSWORD deve ter pelo menos 12 caracteres.")
    if not NOME:
        raise RuntimeError("BOOTSTRAP_SUPERADMIN_NAME não configurado.")


def executar():
    validar_variaveis()
    db = SessionLocal()
    try:
        usuario = (
            db.query(models.Usuario)
            .filter(models.Usuario.email == EMAIL)
            .first()
        )

        if usuario:
            # Protege contas existentes: inclusive senha e perfil.
            # Bootstrap recorrente NUNCA deve alterar credenciais.
            print("SUPERADMIN_EXISTENTE_PRESERVADO=SIM")
            return

        usuario = models.Usuario(
            nome=NOME,
            email=EMAIL,
            senha_hash=criar_hash_senha(SENHA),
            perfil="superadmin",
            barbeiro_id=None,
            ativo=True,
            barbearia_id=None,
        )
        db.add(usuario)
        db.commit()
        print("SUPERADMIN_INICIAL_CRIADO=SIM")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    executar()
