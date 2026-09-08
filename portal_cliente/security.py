from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from auth.security import ALGORITHM, SECRET_KEY
from database import get_db
from portal_cliente.models import ClienteAcesso

bearer_cliente = HTTPBearer(auto_error=False)


def obter_acesso_cliente(
    credenciais: HTTPAuthorizationCredentials | None = Depends(bearer_cliente),
    db: Session = Depends(get_db),
) -> ClienteAcesso:
    if not credenciais:
        raise HTTPException(status_code=401, detail="Token do cliente não informado.")
    try:
        payload = jwt.decode(credenciais.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("tipo_acesso") != "cliente":
            raise ValueError
        acesso_id = int(payload["acesso_id"])
        cliente_id = int(payload["cliente_id"])
        barbearia_id = int(payload["barbearia_id"])
    except (JWTError, KeyError, TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token do cliente inválido ou expirado.")

    acesso = db.query(ClienteAcesso).filter(ClienteAcesso.id == acesso_id).first()
    if not acesso or not acesso.ativo or not acesso.email_confirmado:
        raise HTTPException(status_code=403, detail="Acesso do cliente ainda não está confirmado.")
    if acesso.cliente_id != cliente_id or acesso.barbearia_id != barbearia_id:
        raise HTTPException(status_code=401, detail="Vínculo do cliente foi alterado. Entre novamente.")
    if not acesso.cliente or not acesso.cliente.ativo or not acesso.barbearia or not acesso.barbearia.ativa:
        raise HTTPException(status_code=403, detail="Cliente ou barbearia inativo.")
    return acesso
