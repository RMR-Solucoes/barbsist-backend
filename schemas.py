from pydantic import BaseModel, Field, model_validator
from typing import Optional, Literal
from datetime import datetime, date


# =========================
# BARBEARIA
# =========================

class BarbeariaBase(BaseModel):
    # Dados cadastrais
    nome: str
    responsavel: str | None = None
    email: str | None = None
    telefone: str | None = None
    telefone_whatsapp: str | None = None
    cnpj: str | None = None

    # Endereço
    endereco: str | None = None
    cidade: str | None = None
    estado: str | None = None
    cep: str | None = None

    # Identidade visual
    instagram: str | None = None
    logo_url: str | None = None
    slogan: str | None = None
    imagem_capa_url: str | None = None

    # Tema visual
    cor_primaria: str = "#111827"
    cor_secundaria: str = "#2563EB"
    cor_fundo: str = "#F3F4F6"
    cor_sidebar: str = "#111827"
    cor_texto_sidebar: str = "#FFFFFF"
    cor_destaque: str = "#2563EB"


class BarbeariaCreate(BarbeariaBase):
    """
    O código e o slug serão gerados pelo backend.

    O frontend não deverá controlar esses identificadores.
    """

    pass


class BarbeariaUpdate(BaseModel):
    nome: str | None = None
    responsavel: str | None = None
    email: str | None = None
    telefone: str | None = None
    telefone_whatsapp: str | None = None
    cnpj: str | None = None

    endereco: str | None = None
    cidade: str | None = None
    estado: str | None = None
    cep: str | None = None

    instagram: str | None = None
    logo_url: str | None = None
    slogan: str | None = None
    imagem_capa_url: str | None = None

    cor_primaria: str | None = None
    cor_secundaria: str | None = None
    cor_fundo: str | None = None
    cor_sidebar: str | None = None
    cor_texto_sidebar: str | None = None
    cor_destaque: str | None = None

    ativa: bool | None = None


class BarbeariaResponse(BarbeariaBase):
    id: int
    codigo: int
    slug: str
    ativa: bool
    created_at: datetime | None = None

    class Config:
        from_attributes = True

# =========================
# CLIENTES
# =========================

class ClienteBase(BaseModel):
    nome: str
    telefone: Optional[str] = None
    email: Optional[str] = None
    observacoes: Optional[str] = None


class ClienteCreate(ClienteBase):
    pass


class ClienteUpdate(BaseModel):
    nome: Optional[str] = None
    telefone: Optional[str] = None
    email: Optional[str] = None
    observacoes: Optional[str] = None


class ClienteResponse(ClienteBase):
    id: int
    numero_sequencial: int
    codigo: str
    ativo: bool

    class Config:
        from_attributes = True


class ClienteComAssinaturaResponse(
    ClienteResponse
):
    possui_assinatura: bool = False

    assinatura_id: Optional[int] = None
    assinatura_status: Optional[str] = None
    status_pagamento: Optional[str] = None

    plano_id: Optional[int] = None
    plano_nome: Optional[str] = None

    data_proximo_vencimento: Optional[
        datetime
    ] = None

    usos_disponiveis: Optional[int] = None

    quantidade_servicos_plano: Optional[
        int
    ] = None

    class Config:
        from_attributes = True

# =========================
# BARBEIROS
# =========================

class BarbeiroBase(BaseModel):
    nome: str
    telefone: Optional[str] = None
    email: Optional[str] = None
    tipo: Optional[str] = "associado"
    percentual_comissao: Optional[float] = 50.0
    especialidades: Optional[str] = None
    observacoes: Optional[str] = None


class BarbeiroCreate(BarbeiroBase):
    pass


class BarbeiroResponse(BarbeiroBase):
    id: int
    numero_sequencial: int
    codigo: str
    barbearia_id: int
    ativo: bool

    class Config:
        from_attributes = True

# =========================
# SERVIÇOS
# =========================

class ServicoBase(BaseModel):
    nome: str
    preco: float
    tempo_medio_minutos: int = 30


class ServicoCreate(ServicoBase):
    pass


class ServicoResponse(ServicoBase):
    id: int
    numero_sequencial: int
    codigo: str
    barbearia_id: int
    ativo: bool

    class Config:
        from_attributes = True

# =========================
# PRODUTOS
# =========================

class ProdutoBase(BaseModel):
    nome: str
    categoria: Optional[str] = None
    preco_custo: float = 0
    preco_venda: float
    estoque: int = 0
    codigo_qr: Optional[str] = None


class ProdutoCreate(ProdutoBase):
    pass


class ProdutoUpdate(BaseModel):
    nome: Optional[str] = None
    categoria: Optional[str] = None
    preco_custo: Optional[float] = None
    preco_venda: Optional[float] = None
    estoque: Optional[int] = None
    codigo_qr: Optional[str] = None


class ProdutoResponse(ProdutoBase):
    id: int
    numero_sequencial: int
    codigo: str
    barbearia_id: int
    ativo: bool

    class Config:
        from_attributes = True
# =========================
# ITENS DA COMANDA
# =========================

class ItemComandaBase(BaseModel):
    quantidade: int = 1


class AdicionarServicoComanda(ItemComandaBase):
    servico_id: int


class AdicionarProdutoComanda(ItemComandaBase):
    produto_id: int


class ItemComandaResponse(BaseModel):
    id: int

    tipo: str
    descricao: str

    quantidade: int

    valor_unitario: float
    subtotal: float

    servico_id: Optional[int] = None
    produto_id: Optional[int] = None

    pago_com_plano: bool = False
    uso_plano_id: Optional[int] = None

    class Config:
        from_attributes = True


# =========================
# COMANDAS
# =========================

class ComandaBase(BaseModel):
    cliente_id: Optional[int] = None
    barbeiro_id: Optional[int] = None


class ComandaCreate(ComandaBase):
    pass


class ComandaResponse(ComandaBase):
    id: int

    status: str
    total: float

    forma_pagamento: Optional[str] = None

    data_abertura: Optional[datetime] = None
    data_fechamento: Optional[datetime] = None

    cliente_nome: Optional[str] = None
    barbeiro_nome: Optional[str] = None

    itens: list[ItemComandaResponse] = Field(
        default_factory=list
    )

    class Config:
        from_attributes = True

# =========================
# FECHAMENTO DE COMANDA
# =========================

class FecharComanda(BaseModel):
    forma_pagamento: str



# =========================
# VENDAS AVULSAS
# =========================

class VendaCreate(BaseModel):
    cliente_id: Optional[int] = None
    barbeiro_id: Optional[int] = None


class AdicionarProdutoVenda(BaseModel):
    produto_id: int
    quantidade: int = 1


class ItemVendaResponse(BaseModel):
    id: int
    venda_id: int
    produto_id: int
    descricao: str
    quantidade: int
    valor_unitario: float
    subtotal: float

    class Config:
        from_attributes = True


class VendaResponse(BaseModel):
    id: int

    cliente_id: Optional[int] = None
    barbeiro_id: Optional[int] = None

    status: str
    total: float

    forma_pagamento: Optional[str] = None

    data_abertura: Optional[datetime] = None
    data_fechamento: Optional[datetime] = None

    cliente_nome: Optional[str] = None
    barbeiro_nome: Optional[str] = None

    itens: list[ItemVendaResponse] = Field(
        default_factory=list
    )

    class Config:
        from_attributes = True


class FecharVenda(BaseModel):
    forma_pagamento: str


# =========================
# CAIXA
# =========================

# =========================
# CAIXA
# =========================

class CaixaBase(BaseModel):
    tipo: str
    descricao: str
    valor: float
    forma_pagamento: Optional[str] = None
    observacoes: Optional[str] = None


class CaixaCreate(CaixaBase):
    pass


class CaixaResponse(CaixaBase):
    id: int

    barbearia_id: int

    origem: str
    referencia_id: Optional[int] = None

    status: str

    usuario_id: Optional[int] = None
    movimentacao_origem_id: Optional[int] = None

    data: datetime

    class Config:
        from_attributes = True



class CaixaResumoResponse(BaseModel):
    entradas: float
    saidas: float
    saldo: float
    quantidade_movimentacoes: int


class CaixaResumoFiltro(BaseModel):
    data_inicio: date | None = None
    data_fim: date | None = None
# =========================
# COMISSÕES
# =========================

class ComissaoResponse(BaseModel):
    id: int
    barbeiro_id: int
    comanda_id: int
    valor_servico: float
    percentual: float
    valor_comissao: float

    class Config:
        from_attributes = True


# =========================
# USUÁRIOS / AUTENTICAÇÃO
# =========================

PERFIS_USUARIO_VALIDOS = {
    "admin",
    "gerente",
    "recepcao",
    "barbeiro"
}


class UsuarioCreate(BaseModel):
    nome: str
    email: str
    senha: str
    perfil: str = "admin"
    barbearia_id: int | None = None
    barbeiro_id: int | None = None

class UsuarioResponse(BaseModel):
    id: int
    nome: str
    email: str
    perfil: str

    barbearia_id: int | None = None
    barbeiro_id: int | None = None

    contexto_barbearia_id: int | None = None
    contexto_barbearia_slug: str | None = None

    ativo: bool

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    # Obrigat?rio para usu?rios de barbearia; opcional para o superadmin global.
    barbearia_slug: str | None = None
    email: str
    senha: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SuperadminContextoInfo(BaseModel):
    barbearia_id: int
    barbearia_nome: str
    barbearia_slug: str


class SuperadminContextoTokenResponse(TokenResponse):
    contexto: SuperadminContextoInfo | None = None

class CadastroBarbeariaRequest(BaseModel):
    nome_barbearia: str
    responsavel: str
    email: str
    telefone_whatsapp: str
    cidade: str
    estado: str
    senha: str
    confirmar_senha: str
    aceite_termos: bool


class CadastroBarbeariaLoginResponse(BaseModel):
    slug: str
    email: str


class CadastroBarbeariaInfoResponse(BaseModel):
    id: int
    codigo: int
    nome: str
    slug: str


class CadastroAdministradorResponse(BaseModel):
    email: str


class CadastroBarbeariaResponse(BaseModel):
    sucesso: bool
    mensagem: str
    barbearia: CadastroBarbeariaInfoResponse
    administrador: CadastroAdministradorResponse
    login: CadastroBarbeariaLoginResponse
    proximo_passo: str
# =========================
# ESTILOS DE CORTE / BARBA
# =========================

class EstiloBase(BaseModel):
    nome: str
    categoria: str
    tipo_cabelo: Optional[str] = "geral"
    descricao: Optional[str] = None
    imagem_url: Optional[str] = None


class EstiloCreate(EstiloBase):
    pass


class EstiloResponse(EstiloBase):
    id: int
    ativo: bool

    class Config:
        from_attributes = True

# =========================
# AGENDAMENTOS
# =========================

class AgendamentoBase(BaseModel):
    cliente_id: Optional[int] = None
    barbeiro_id: int
    servico_id: int

    estilo_corte_id: Optional[int] = None
    estilo_barba_id: Optional[int] = None

    data_hora_inicio: datetime
    data_hora_fim: Optional[datetime] = None

    tipo_atendimento: Optional[str] = "avulso"

    observacoes: Optional[str] = None

    # INTERNO | ONLINE
    origem: Optional[str] = "INTERNO"


class AgendamentoCreate(AgendamentoBase):
    pass


class AgendamentoResponse(AgendamentoBase):
    id: int

    data_hora_fim: Optional[datetime] = None

    status: str

    class Config:
        from_attributes = True
# =========================
# PLANOS
# =========================

class PlanoBase(BaseModel):
    nome: str
    descricao: Optional[str] = None
    valor: float
    valor_pix: Optional[float] = None
    valor_cartao: Optional[float] = None
    max_parcelas_cartao: int = 1
    quantidade_servicos: int = 0
    validade_dias: int = 30
    servicos_ids: list[int] = Field(
        default_factory=list
    )


class PlanoCreate(PlanoBase):
    pass


class PlanoResponse(PlanoBase):
    id: int
    ativo: bool

    class Config:
        from_attributes = True


class PlanoUpdate(BaseModel):
    nome: str
    descricao: Optional[str] = None
    valor: float
    valor_pix: Optional[float] = None
    valor_cartao: Optional[float] = None
    max_parcelas_cartao: int = 1
    quantidade_servicos: int
    validade_dias: int
    servicos_ids: list[int] = Field(
        default_factory=list
    )

# =========================
# ASSINATURAS DE CLIENTES
# =========================

class AssinaturaClienteCreate(BaseModel):
    cliente_id: int
    plano_id: int


class AssinaturaClienteResponse(BaseModel):
    id: int

    cliente_id: int
    plano_id: int

    data_inicio: datetime
    data_fim: datetime

    data_ultimo_pagamento: Optional[datetime] = None
    data_proximo_vencimento: Optional[datetime] = None

    dias_tolerancia: int = 5
    valor_mensal: float = 0

    usos_disponiveis: int

    status: str
    status_pagamento: Optional[str] = "pendente_pagamento"

    class Config:
        from_attributes = True

class AssinaturaClienteUpdate(BaseModel):
    plano_id: int | None = None
    data_inicio: datetime | None = None
    data_fim: datetime | None = None
    data_proximo_vencimento: datetime | None = None
    dias_tolerancia: int | None = None
    usos_disponiveis: int | None = None
    valor_mensal: float | None = None
    status: str | None = None
    status_pagamento: str | None = None 

# =========================
# USO DE PLANO
# =========================

class UsarPlanoRequest(BaseModel):
    assinatura_id: int
    comanda_id: int
    servico_id: int

class UsarPlanoItemComandaRequest(BaseModel):
    assinatura_id: int


class UsoPlanoResponse(BaseModel):
    id: int

    assinatura_id: int
    comanda_id: Optional[int] = None
    servico_id: Optional[int] = None

    data_uso: datetime

    class Config:
        from_attributes = True

class AtualizarStatusAgendamento(BaseModel):
    status: str

class RegistrarPagamentoPlanoRequest(BaseModel):
    assinatura_id: int
    forma_pagamento: str    


# =========================
# HISTÓRICO DE PAGAMENTOS DOS PLANOS
# =========================

class PagamentoPlanoResponse(BaseModel):
    id: int

    assinatura_id: int
    cliente_id: int
    plano_id: int

    valor: float
    forma_pagamento: str
    status: str

    referencia_mes: Optional[str] = None
    observacoes: Optional[str] = None

    data_pagamento: datetime

    class Config:
        from_attributes = True

class RenovarAssinaturaRequest(BaseModel):
    forma_pagamento: str
    observacoes: Optional[str] = None


class SuspenderAssinaturaRequest(BaseModel):
    motivo: Optional[str] = None


class ReativarAssinaturaRequest(BaseModel):
    forma_pagamento: Optional[str] = None
    observacoes: Optional[str] = None

# =========================
# REAGENDAMENTO
# =========================

class ReagendarAgendamentoRequest(BaseModel):
    nova_data_hora_inicio: datetime   




class ConfiguracaoFuncionamentoBase(BaseModel):
    dia_semana: int
    trabalha: bool = True
    hora_inicio: str = "08:00"
    hora_fim: str = "20:00"


class ConfiguracaoFuncionamentoCreate(ConfiguracaoFuncionamentoBase):
    pass


class ConfiguracaoFuncionamentoUpdate(BaseModel):
    trabalha: bool | None = None
    hora_inicio: str | None = None
    hora_fim: str | None = None


class ConfiguracaoFuncionamentoResponse(ConfiguracaoFuncionamentoBase):
    id: int

    class Config:
        from_attributes = True     


class BarbeiroDisponibilidadeBase(BaseModel):
    barbeiro_id: int
    usa_padrao: bool = True
    dia_semana: int
    trabalha: bool = True
    hora_inicio: str = "08:00"
    hora_fim: str = "20:00"


class BarbeiroDisponibilidadeCreate(BarbeiroDisponibilidadeBase):
    pass


class BarbeiroDisponibilidadeUpdate(BaseModel):
    usa_padrao: bool | None = None
    trabalha: bool | None = None
    hora_inicio: str | None = None
    hora_fim: str | None = None


class BarbeiroDisponibilidadeResponse(BarbeiroDisponibilidadeBase):
    id: int

    class Config:
        from_attributes = True




class ContaReceberBase(BaseModel):
    descricao: str
    cliente_id: Optional[int] = None
    valor: float
    vencimento: date
    forma_pagamento: Optional[str] = None
    observacoes: Optional[str] = None


class ContaReceberCreate(ContaReceberBase):
    pass


class ContaReceberResponse(ContaReceberBase):
    id: int
    data_pagamento: Optional[date] = None
    status: str

    class Config:
        from_attributes = True


class ContaPagarBase(BaseModel):
    descricao: str
    fornecedor: Optional[str] = None
    valor: float
    vencimento: date
    forma_pagamento: Optional[str] = None
    observacoes: Optional[str] = None


class ContaPagarCreate(ContaPagarBase):
    pass


class ContaPagarResponse(ContaPagarBase):
    id: int
    data_pagamento: Optional[date] = None
    status: str

    class Config:
        from_attributes = True



class UsuarioUpdate(BaseModel):
    nome: str
    email: str
    perfil: str
    barbeiro_id: int | None = None
    ativo: bool = True


class AlterarSenhaUsuarioRequest(BaseModel):
    nova_senha: str


class AlterarMinhaSenhaRequest(BaseModel):
    senha_atual: str
    nova_senha: str
    confirmar_nova_senha: str


class EsqueciSenhaRequest(BaseModel):
    barbearia_slug: str | None = None
    email: str


class RedefinirSenhaRequest(BaseModel):
    token: str
    nova_senha: str
    confirmar_nova_senha: str


class MensagemResponse(BaseModel):
    mensagem: str


class MercadoPagoConfiguracaoUpdate(BaseModel):
    access_token: Optional[str] = None
    webhook_secret: Optional[str] = None
    public_key: Optional[str] = None
    ambiente: str = "producao"
    ativo: bool = True


class MercadoPagoConfiguracaoResponse(BaseModel):
    configurado: bool
    conectado: bool = False
    access_token_configurado: bool
    webhook_secret_configurado: bool
    public_key: Optional[str] = None
    mercado_pago_user_id: Optional[str] = None
    oauth_status: str = "NAO_CONECTADO"
    token_expires_at: Optional[datetime] = None
    conectado_em: Optional[datetime] = None
    ambiente: str = "producao"
    ativo: bool = False
    webhook_url: Optional[str] = None


class MercadoPagoOAuthConectarResponse(BaseModel):
    authorization_url: str
    expires_in_seconds: int = 600


class MercadoPagoOAuthDesconectarResponse(BaseModel):
    desconectado: bool
    mensagem: str


class MercadoPagoPixRequest(BaseModel):
    payer_email: Optional[str] = None


class MercadoPagoCobrancaPixRequest(BaseModel):
    origem_negocio: str
    origem_id: int
    payer_email: Optional[str] = None


class MercadoPagoCartaoRequest(BaseModel):
    token: str
    installments: int = 1
    payment_method_id: str
    issuer_id: Optional[int] = None
    payer_email: str
    identification_type: Optional[str] = None
    identification_number: Optional[str] = None


class MercadoPagoCobrancaCartaoRequest(MercadoPagoCartaoRequest):
    origem_negocio: str
    origem_id: int


class MercadoPagoPixResponse(BaseModel):
    cobranca_id: int
    order_id: Optional[str] = None
    payment_id: Optional[str] = None
    status: str
    external_reference: str
    valor: float
    tipo_pagamento: str = "PIX"
    installments: int = 1
    valor_parcela: Optional[float] = None
    payment_method_id: Optional[str] = None
    payment_type_id: Optional[str] = None
    status_detail: Optional[str] = None
    qr_code: Optional[str] = None
    qr_code_base64: Optional[str] = None
    ticket_url: Optional[str] = None


class MercadoPagoCobrancaResponse(MercadoPagoPixResponse):
    assinatura_id: Optional[int] = None
    origem_negocio: str = "PLANO_CLIENTE"
    origem_id: Optional[int] = None
    payer_email: Optional[str] = None
    processado: bool = False
    data_criacao: datetime


class PlanoSaaSBase(BaseModel):
    nome: str
    descricao: Optional[str] = None
    periodo_meses: int = 1
    valor_pix: float
    valor_cartao: float
    max_parcelas_cartao: int = 1
    limite_barbeiros: int = 1


class PlanoSaaSCreate(PlanoSaaSBase):
    ativo: bool = True


class PlanoSaaSUpdate(BaseModel):
    nome: Optional[str] = None
    descricao: Optional[str] = None
    periodo_meses: Optional[int] = None
    valor_pix: Optional[float] = None
    valor_cartao: Optional[float] = None
    max_parcelas_cartao: Optional[int] = None
    limite_barbeiros: Optional[int] = None
    ativo: Optional[bool] = None


class PlanoSaaSResponse(PlanoSaaSBase):
    id: int
    ativo: bool
    class Config:
        from_attributes = True


class AssinaturaSaaSResponse(BaseModel):
    id: int
    barbearia_id: int
    plano_id: int
    status: str
    status_pagamento: str
    forma_pagamento: Optional[str] = None
    data_inicio: Optional[datetime] = None
    data_fim: Optional[datetime] = None
    data_proximo_vencimento: Optional[datetime] = None
    liberado_manual: bool = False
    motivo_bloqueio: Optional[str] = None
    promocao_codigo: Optional[str] = None
    promocao_inicio: Optional[datetime] = None
    promocao_fim: Optional[datetime] = None
    fundador_posicao: Optional[int] = None
    criado_em: datetime
    class Config:
        from_attributes = True


class CheckoutSaaSPixRequest(BaseModel):
    plano_id: int
    payer_email: str


class CheckoutSaaSCartaoRequest(BaseModel):
    plano_id: int
    token: str
    installments: int = 1
    payment_method_id: str
    issuer_id: Optional[int] = None
    payer_email: str
    identification_type: Optional[str] = None
    identification_number: Optional[str] = None


class PagamentoSaaSResponse(BaseModel):
    id: int
    assinatura_id: int
    barbearia_id: int
    plano_id: int
    payment_id: Optional[str] = None
    external_reference: str
    tipo_pagamento: str
    payment_method_id: Optional[str] = None
    payment_type_id: Optional[str] = None
    installments: int = 1
    valor: float
    valor_parcela: Optional[float] = None
    payer_email: Optional[str] = None
    status: str
    status_detail: Optional[str] = None
    qr_code: Optional[str] = None
    qr_code_base64: Optional[str] = None
    ticket_url: Optional[str] = None
    processado: bool
    data_criacao: datetime
    class Config:
        from_attributes = True


class LiberarAssinaturaSaaSRequest(BaseModel):
    dias: int = 30
    observacao: Optional[str] = None


class BloquearAssinaturaSaaSRequest(BaseModel):
    motivo: str


class ContaReceberUpdate(BaseModel):
    descricao: Optional[str] = None
    cliente_id: Optional[int] = None
    valor: Optional[float] = None
    vencimento: Optional[date] = None
    forma_pagamento: Optional[str] = None
    observacoes: Optional[str] = None


class ContaPagarUpdate(BaseModel):
    descricao: Optional[str] = None
    fornecedor: Optional[str] = None
    valor: Optional[float] = None
    vencimento: Optional[date] = None
    forma_pagamento: Optional[str] = None
    observacoes: Optional[str] = None


class FinanceiroOrigemResumo(BaseModel):
    origem: str
    valor: float


class FinanceiroMovimentacaoRecente(BaseModel):
    id: int
    tipo: str
    descricao: str
    valor: float
    origem: str
    forma_pagamento: Optional[str] = None
    data: datetime


class FinanceiroDashboardResponse(BaseModel):
    data_inicio: date
    data_fim: date
    entradas: float
    saidas: float
    saldo: float
    contas_receber_pendentes: float
    contas_pagar_pendentes: float
    contas_receber_vencidas: int
    contas_pagar_vencidas: int
    quantidade_movimentacoes: int
    receitas_por_origem: list[FinanceiroOrigemResumo]
    despesas_por_origem: list[FinanceiroOrigemResumo]
    movimentacoes_recentes: list[FinanceiroMovimentacaoRecente]


class FluxoCaixaDia(BaseModel):
    data: date
    entradas: float
    saidas: float
    saldo_dia: float
    saldo_acumulado: float


class FluxoCaixaResponse(BaseModel):
    data_inicio: date
    data_fim: date
    saldo_inicial: float
    saldo_final: float
    dias: list[FluxoCaixaDia]


class DRESimplificadaResponse(BaseModel):
    data_inicio: date
    data_fim: date
    receita_operacional: float
    outras_entradas: float
    receitas_totais: float
    despesas_operacionais: float
    outras_saidas: float
    despesas_totais: float
    resultado: float


class AssinaturaSaaSAuditoriaResponse(BaseModel):
    id: int
    assinatura_id: int
    barbearia_id: int
    usuario_id: int
    acao: str
    observacao: Optional[str] = None
    status_anterior: Optional[str] = None
    status_novo: Optional[str] = None
    criado_em: datetime

    class Config:
        from_attributes = True


# ==================================
# FINANCEIRO GLOBAL DA PLATAFORMA
# ==================================

class FinanceiroPlataformaMovimentacaoCreate(BaseModel):
    tipo: Literal["ENTRADA", "SAIDA"]

    categoria: str = Field(
        min_length=2,
        max_length=80,
    )

    descricao: str = Field(
        min_length=2,
        max_length=255,
    )

    valor: float = Field(gt=0)

    data_competencia: datetime

    data_realizacao: datetime | None = None

    forma_pagamento: str | None = Field(
        default=None,
        max_length=80,
    )

    observacao: str | None = None

    status: Literal[
        "PENDENTE",
        "REALIZADO",
        "CANCELADO",
    ] = "REALIZADO"

    @model_validator(mode="after")
    def validar_realizacao(self):
        if (
            self.status == "REALIZADO"
            and self.data_realizacao is None
        ):
            raise ValueError(
                "data_realizacao e obrigatoria quando status=REALIZADO."
            )

        if (
            self.status != "REALIZADO"
            and self.data_realizacao is not None
        ):
            raise ValueError(
                "data_realizacao deve ser nula quando status nao for REALIZADO."
            )

        return self


class FinanceiroPlataformaMovimentacaoUpdate(BaseModel):
    categoria: str | None = Field(
        default=None,
        min_length=2,
        max_length=80,
    )

    descricao: str | None = Field(
        default=None,
        min_length=2,
        max_length=255,
    )

    valor: float | None = Field(
        default=None,
        gt=0,
    )

    data_competencia: datetime | None = None

    data_realizacao: datetime | None = None

    forma_pagamento: str | None = Field(
        default=None,
        max_length=80,
    )

    observacao: str | None = None

    status: Literal[
        "PENDENTE",
        "REALIZADO",
        "CANCELADO",
    ] | None = None


class FinanceiroPlataformaMovimentacaoOut(BaseModel):
    id: int
    tipo: str
    categoria: str
    descricao: str
    valor: float
    data_competencia: datetime
    data_realizacao: datetime | None
    forma_pagamento: str | None
    observacao: str | None
    status: str
    usuario_id: int
    criado_em: datetime
    atualizado_em: datetime

    class Config:
        from_attributes = True


class FinanceiroPlataformaCategoriaResumo(BaseModel):
    categoria: str
    valor: float


class FinanceiroPlataformaResumo(BaseModel):
    data_inicio: date
    data_fim: date

    receita_saas: float
    outras_entradas: float
    entradas_totais: float

    despesas_totais: float
    taxas_pagamento: float
    comissoes_parceiros: float
    impostos: float
    outras_despesas: float

    resultado_liquido: float

    pendentes_entrada: float
    pendentes_saida: float

    quantidade_movimentacoes: int

    entradas_por_categoria: list[
        FinanceiroPlataformaCategoriaResumo
    ]

    saidas_por_categoria: list[
        FinanceiroPlataformaCategoriaResumo
    ]


class FinanceiroPlataformaFluxoDia(BaseModel):
    data: date
    entradas: float
    saidas: float
    resultado_dia: float
    saldo_acumulado: float


class FinanceiroPlataformaFluxoResponse(BaseModel):
    data_inicio: date
    data_fim: date
    saldo_inicial: float
    saldo_final: float
    dias: list[FinanceiroPlataformaFluxoDia]

