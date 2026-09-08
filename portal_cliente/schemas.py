from datetime import datetime
from pydantic import BaseModel, Field


class PortalLoginRequest(BaseModel):
    barbearia_slug: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=255)
    senha: str = Field(min_length=8, max_length=128)


class PrimeiroAcessoRequest(BaseModel):
    barbearia_slug: str = Field(min_length=1, max_length=120)
    nome: str = Field(min_length=2, max_length=150)
    telefone: str = Field(min_length=10, max_length=30)
    email: str = Field(min_length=3, max_length=255)
    senha: str = Field(min_length=8, max_length=128)


class ConfirmarEmailRequest(BaseModel):
    barbearia_slug: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=255)
    codigo: str = Field(min_length=6, max_length=6)


class ReenviarCodigoRequest(BaseModel):
    barbearia_slug: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=255)


class AtivarAcessoRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    senha_inicial: str = Field(min_length=8, max_length=128)


class AlterarSenhaRequest(BaseModel):
    senha_atual: str = Field(min_length=8, max_length=128)
    nova_senha: str = Field(min_length=8, max_length=128)


class ConfiguracaoPortalUpdate(BaseModel):
    permitir_agendamento_portal: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PrimeiroAcessoResponse(BaseModel):
    mensagem: str
    requer_confirmacao_email: bool = True


class PortalMeResponse(BaseModel):
    cliente_id: int
    nome: str
    email: str
    telefone: str | None = None
    barbearia_id: int
    barbearia_nome: str
    barbearia_slug: str
    permitir_agendamento_portal: bool
    deve_trocar_senha: bool
    ultimo_acesso_em: datetime | None = None


class AcessoResponse(BaseModel):
    cliente_id: int
    email: str
    ativo: bool
    deve_trocar_senha: bool


class ConfiguracaoPortalResponse(BaseModel):
    permitir_agendamento_portal: bool
