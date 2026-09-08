from datetime import datetime, timedelta
import hashlib
import secrets
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

import models
from auth.permissions import admin_gerente_ou_recepcao, admin_ou_gerente
from auth.security import criar_hash_senha, criar_token_acesso, verificar_senha
from auth.tenant import obter_barbearia_id
from database import get_db
from portal_cliente.models import ClienteAcesso, ClienteConfirmacaoEmail, PortalClienteConfiguracao
from portal_cliente.schemas import (
    AcessoResponse, AlterarSenhaRequest, AtivarAcessoRequest, ConfiguracaoPortalResponse,
    ConfiguracaoPortalUpdate, ConfirmarEmailRequest, PortalLoginRequest, PortalMeResponse,
    PrimeiroAcessoRequest, PrimeiroAcessoResponse, ReenviarCodigoRequest, TokenResponse,
)
from portal_cliente.security import obter_acesso_cliente
from services.sequencia_service import gerar_codigo_comercial

router = APIRouter(prefix="/portal-cliente", tags=["Portal do Cliente"])


def _email(valor: str) -> str:
    return valor.strip().lower()


def _telefone(valor: str) -> str:
    telefone = re.sub(r"\D", "", valor or "")
    if len(telefone) not in (10, 11):
        raise HTTPException(status_code=400, detail="Telefone inválido. Informe DDD + número.")
    return telefone


def _barbearia(db: Session, slug: str):
    item = db.query(models.Barbearia).filter(
        models.Barbearia.slug == slug.strip().lower(), models.Barbearia.ativa.is_(True)
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Barbearia não encontrada ou indisponível.")
    return item


def _config(db: Session, barbearia_id: int):
    item = db.query(PortalClienteConfiguracao).filter_by(barbearia_id=barbearia_id).first()
    if item is None:
        item = PortalClienteConfiguracao(barbearia_id=barbearia_id, permitir_agendamento_portal=False)
        db.add(item); db.flush()
    return item


def _hash_codigo(codigo: str) -> str:
    return hashlib.sha256(codigo.encode("utf-8")).hexdigest()


def _enviar_codigo(db: Session, acesso: ClienteAcesso):
    codigo = f"{secrets.randbelow(1_000_000):06d}"
    db.query(ClienteConfirmacaoEmail).filter(
        ClienteConfirmacaoEmail.acesso_id == acesso.id,
        ClienteConfirmacaoEmail.utilizado_em.is_(None),
    ).update({"utilizado_em": datetime.utcnow()}, synchronize_session=False)
    db.add(ClienteConfirmacaoEmail(
        acesso_id=acesso.id, codigo_hash=_hash_codigo(codigo),
        expira_em=datetime.utcnow() + timedelta(minutes=15),
    ))
    from portal_cliente.email_service import enviar_email_confirmacao_portal_cliente
    enviar_email_confirmacao_portal_cliente(acesso.email, acesso.cliente.nome, codigo, 15)


@router.post("/primeiro-acesso", response_model=PrimeiroAcessoResponse, status_code=201)
def primeiro_acesso(dados: PrimeiroAcessoRequest, db: Session = Depends(get_db)):
    barbearia = _barbearia(db, dados.barbearia_slug)
    email, telefone = _email(dados.email), _telefone(dados.telefone)
    nome = dados.nome.strip()
    acesso_email = db.query(ClienteAcesso).filter_by(barbearia_id=barbearia.id, email=email).first()
    if acesso_email and acesso_email.email_confirmado:
        raise HTTPException(status_code=409, detail="Já existe uma conta com este e-mail nesta barbearia.")

    clientes = db.query(models.Cliente).filter(models.Cliente.barbearia_id == barbearia.id).all()
    por_telefone = next((c for c in clientes if re.sub(r"\D", "", c.telefone or "") == telefone), None)
    por_email = db.query(models.Cliente).filter(
        models.Cliente.barbearia_id == barbearia.id,
        models.Cliente.email.isnot(None),
        models.Cliente.email == email,
    ).first()
    if por_telefone and por_email and por_telefone.id != por_email.id:
        raise HTTPException(status_code=409, detail="Telefone e e-mail pertencem a cadastros diferentes. Procure a barbearia.")
    cliente = por_telefone or por_email
    if cliente:
        acesso_cliente = db.query(ClienteAcesso).filter_by(cliente_id=cliente.id).first()
        if acesso_cliente and acesso_cliente.email_confirmado:
            raise HTTPException(status_code=409, detail="Este cliente já possui uma conta de acesso.")
        cliente.telefone = telefone
        cliente.email = email
        cliente.ativo = True
    else:
        numero, codigo = gerar_codigo_comercial(db=db, barbearia=barbearia, tipo="CLIENTE")
        cliente = models.Cliente(
            barbearia_id=barbearia.id, numero_sequencial=numero, codigo=codigo,
            nome=nome, telefone=telefone, email=email,
            observacoes="Cliente cadastrado pelo Portal do Cliente.", ativo=True,
        )
        db.add(cliente); db.flush()

    acesso = db.query(ClienteAcesso).filter_by(cliente_id=cliente.id).first()
    if acesso is None:
        acesso = ClienteAcesso(barbearia_id=barbearia.id, cliente_id=cliente.id, email=email, senha_hash=criar_hash_senha(dados.senha))
        db.add(acesso); db.flush()
    else:
        acesso.email, acesso.senha_hash = email, criar_hash_senha(dados.senha)
    acesso.ativo = False; acesso.email_confirmado = False; acesso.deve_trocar_senha = False
    _enviar_codigo(db, acesso)
    db.commit()
    return {"mensagem": "Enviamos um código de confirmação para o e-mail informado.", "requer_confirmacao_email": True}


@router.post("/confirmar-email")
def confirmar_email(dados: ConfirmarEmailRequest, db: Session = Depends(get_db)):
    barbearia = _barbearia(db, dados.barbearia_slug)
    acesso = db.query(ClienteAcesso).filter_by(barbearia_id=barbearia.id, email=_email(dados.email)).first()
    if not acesso:
        raise HTTPException(status_code=400, detail="Código inválido ou expirado.")
    confirmacao = db.query(ClienteConfirmacaoEmail).filter(
        ClienteConfirmacaoEmail.acesso_id == acesso.id,
        ClienteConfirmacaoEmail.utilizado_em.is_(None),
        ClienteConfirmacaoEmail.expira_em >= datetime.utcnow(),
    ).order_by(ClienteConfirmacaoEmail.id.desc()).first()
    if not confirmacao or not secrets.compare_digest(confirmacao.codigo_hash, _hash_codigo(dados.codigo)):
        raise HTTPException(status_code=400, detail="Código inválido ou expirado.")
    confirmacao.utilizado_em = datetime.utcnow(); acesso.email_confirmado = True; acesso.ativo = True
    db.commit()
    return {"mensagem": "E-mail confirmado. Sua conta está liberada."}


@router.post("/reenviar-codigo")
def reenviar_codigo(dados: ReenviarCodigoRequest, db: Session = Depends(get_db)):
    barbearia = _barbearia(db, dados.barbearia_slug)
    acesso = db.query(ClienteAcesso).filter_by(barbearia_id=barbearia.id, email=_email(dados.email)).first()
    if acesso and not acesso.email_confirmado:
        _enviar_codigo(db, acesso); db.commit()
    return {"mensagem": "Se houver uma conta pendente, um novo código será enviado."}


@router.post("/login", response_model=TokenResponse)
def login(dados: PortalLoginRequest, db: Session = Depends(get_db)):
    barbearia = _barbearia(db, dados.barbearia_slug)
    acesso = db.query(ClienteAcesso).filter_by(barbearia_id=barbearia.id, email=_email(dados.email)).first()
    if not acesso or not acesso.ativo or not acesso.email_confirmado or not verificar_senha(dados.senha, acesso.senha_hash):
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos, ou conta ainda não confirmada.")
    acesso.ultimo_acesso_em = datetime.utcnow(); db.commit()
    return {"access_token": criar_token_acesso({
        "sub": f"cliente:{acesso.cliente_id}", "tipo_acesso": "cliente", "acesso_id": acesso.id,
        "cliente_id": acesso.cliente_id, "barbearia_id": acesso.barbearia_id, "barbearia_slug": barbearia.slug,
    }), "token_type": "bearer"}


@router.get("/me", response_model=PortalMeResponse)
def me(acesso: ClienteAcesso = Depends(obter_acesso_cliente), db: Session = Depends(get_db)):
    config = _config(db, acesso.barbearia_id); db.commit()
    return {"cliente_id": acesso.cliente_id, "nome": acesso.cliente.nome, "email": acesso.email,
            "telefone": acesso.cliente.telefone, "barbearia_id": acesso.barbearia_id,
            "barbearia_nome": acesso.barbearia.nome, "barbearia_slug": acesso.barbearia.slug,
            "permitir_agendamento_portal": config.permitir_agendamento_portal,
            "deve_trocar_senha": acesso.deve_trocar_senha, "ultimo_acesso_em": acesso.ultimo_acesso_em}


@router.put("/minha-senha")
def alterar_senha(dados: AlterarSenhaRequest, acesso: ClienteAcesso = Depends(obter_acesso_cliente), db: Session = Depends(get_db)):
    if not verificar_senha(dados.senha_atual, acesso.senha_hash):
        raise HTTPException(status_code=400, detail="Senha atual incorreta.")
    acesso.senha_hash = criar_hash_senha(dados.nova_senha); acesso.deve_trocar_senha = False; db.commit()
    return {"mensagem": "Senha alterada com sucesso."}


@router.put("/admin/clientes/{cliente_id}/acesso", response_model=AcessoResponse)
def ativar_acesso(cliente_id: int, dados: AtivarAcessoRequest, db: Session = Depends(get_db), usuario=Depends(admin_gerente_ou_recepcao)):
    barbearia_id = obter_barbearia_id(usuario)
    cliente = db.query(models.Cliente).filter_by(id=cliente_id, barbearia_id=barbearia_id).first()
    if not cliente: raise HTTPException(status_code=404, detail="Cliente não encontrado nesta barbearia.")
    email = _email(dados.email)
    conflito = db.query(ClienteAcesso).filter(ClienteAcesso.barbearia_id == barbearia_id, ClienteAcesso.email == email, ClienteAcesso.cliente_id != cliente_id).first()
    if conflito: raise HTTPException(status_code=409, detail="E-mail já vinculado a outro cliente desta barbearia.")
    acesso = db.query(ClienteAcesso).filter_by(cliente_id=cliente_id).first()
    if acesso is None:
        acesso = ClienteAcesso(barbearia_id=barbearia_id, cliente_id=cliente_id, email=email, senha_hash=criar_hash_senha(dados.senha_inicial))
        db.add(acesso)
    else: acesso.email, acesso.senha_hash = email, criar_hash_senha(dados.senha_inicial)
    acesso.ativo = True; acesso.email_confirmado = True; acesso.deve_trocar_senha = True; cliente.email = email
    db.commit(); db.refresh(acesso); return acesso


@router.delete("/admin/clientes/{cliente_id}/acesso")
def desativar_acesso(cliente_id: int, db: Session = Depends(get_db), usuario=Depends(admin_gerente_ou_recepcao)):
    acesso = db.query(ClienteAcesso).filter_by(cliente_id=cliente_id, barbearia_id=obter_barbearia_id(usuario)).first()
    if not acesso: raise HTTPException(status_code=404, detail="Acesso não encontrado.")
    acesso.ativo = False; db.commit(); return {"mensagem": "Acesso do cliente desativado."}


@router.get("/admin/configuracao", response_model=ConfiguracaoPortalResponse)
def obter_configuracao(db: Session = Depends(get_db), usuario=Depends(admin_ou_gerente)):
    item = _config(db, obter_barbearia_id(usuario)); db.commit(); return item


@router.put("/admin/configuracao", response_model=ConfiguracaoPortalResponse)
def atualizar_configuracao(dados: ConfiguracaoPortalUpdate, db: Session = Depends(get_db), usuario=Depends(admin_ou_gerente)):
    item = _config(db, obter_barbearia_id(usuario)); item.permitir_agendamento_portal = dados.permitir_agendamento_portal
    db.commit(); db.refresh(item); return item
