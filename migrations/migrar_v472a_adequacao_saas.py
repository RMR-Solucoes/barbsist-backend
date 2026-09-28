"""V4.7.2A R1 - cria apenas as tabelas de adequacao SaaS, de forma idempotente."""
from pathlib import Path
import sys

# Ao executar este arquivo diretamente, Python usa backend/migrations como
# sys.path[0]. Inclui backend explicitamente para importar database/models.
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import engine
from sqlalchemy import inspect
import models


def main():
    antes = set(inspect(engine).get_table_names())
    criadas = []
    try:
        for tabela in (
            models.AdequacaoPlanoSaaS.__table__,
            models.AdequacaoPlanoSaaSBarbeiro.__table__,
        ):
            if tabela.name not in antes:
                tabela.create(bind=engine, checkfirst=True)
                criadas.append(tabela)
        print("V4.7.2A_MIGRACAO_OK")
    except Exception:
        # Remove somente tabelas que esta execucao criou.
        for tabela in reversed(criadas):
            try:
                tabela.drop(bind=engine, checkfirst=True)
            except Exception:
                pass
        raise


if __name__ == "__main__":
    main()
