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


class PortalPlanoResumo(BaseModel):
    id: int
    nome: str
    descricao: str | None = None
    quantidade_servicos: int
    validade_dias: int


class PortalPlanoDisponivelResponse(PortalPlanoResumo):
    valor: float
    valor_pix: float
    valor_cartao: float
    max_parcelas_cartao: int


class PortalAssinarPixRequest(BaseModel):
    dia_vencimento: int = Field(ge=1, le=28)


class PortalComandaPixRequest(BaseModel):
    payer_email: str | None = Field(default=None, max_length=255)


class PortalPixResponse(BaseModel):
    cobranca_id: int
    assinatura_id: int | None = None
    order_id: str | None = None
    payment_id: str | None = None
    status: str
    external_reference: str
    valor: float
    tipo_pagamento: str = "PIX"
    qr_code: str | None = None
    qr_code_base64: str | None = None
    ticket_url: str | None = None


class PortalAssinaturaResponse(BaseModel):
    id: int
    plano: PortalPlanoResumo
    plano_programado: PortalPlanoResumo | None = None
    data_inicio: datetime
    data_fim: datetime
    data_ultimo_pagamento: datetime | None = None
    data_proximo_vencimento: datetime | None = None
    dia_vencimento: int | None = None
    valor_mensal: float
    valor_proxima_cobranca: float | None = None
    usos_disponiveis: int
    usos_proximo_ciclo: int | None = None
    status: str
    status_pagamento: str


class PortalPagamentoResponse(BaseModel):
    id: int
    assinatura_id: int
    plano_id: int
    plano_nome: str
    valor: float
    forma_pagamento: str
    status: str
    referencia_mes: str | None = None
    observacoes: str | None = None
    data_pagamento: datetime


class AcessoResponse(BaseModel):
    cliente_id: int
    email: str
    ativo: bool
    deve_trocar_senha: bool


class ConfiguracaoPortalResponse(BaseModel):
    permitir_agendamento_portal: bool


class PortalComandaItemResponse(BaseModel):
    descricao: str
    quantidade: int
    valor_unitario: float
    subtotal: float


class PortalComandaResponse(BaseModel):
    id: int
    status: str
    total: float
    data_abertura: datetime
    barbeiro_nome: str | None = None
    itens: list[PortalComandaItemResponse] = Field(default_factory=list)
