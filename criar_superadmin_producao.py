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
            usuario.nome = NOME
            usuario.senha_hash = criar_hash_senha(SENHA)
            usuario.perfil = "superadmin"
            usuario.barbeiro_id = None
            usuario.ativo = True
            usuario.barbearia_id = None
            print("[OK] Superadmin global atualizado.")
        else:
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
            print("[OK] Superadmin global criado.")

        db.commit()
        db.refresh(usuario)
        print(f"[OK] ID do superadmin: {usuario.id}")
        print(f"[OK] E-mail: {usuario.email}")
        print("[OK] barbearia_id: NULL (controle global do BarbSist)")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    executar()
