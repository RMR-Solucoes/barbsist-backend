from pydantic import BaseModel, Field
from typing import Optional
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
    barbeiro_id: int


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
# CAIXA
# =========================

class CaixaBase(BaseModel):
    tipo: str  # entrada ou saida
    descricao: str
    valor: float
    forma_pagamento: Optional[str] = None


class CaixaCreate(CaixaBase):
    pass


class CaixaResponse(CaixaBase):
    id: int
    data: datetime

    class Config:
        from_attributes = True


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

    barbearia_id: int
    barbeiro_id: int | None = None

    ativo: bool

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    barbearia_slug: str
    email: str
    senha: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


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
    quantidade_servicos: int
    validade_dias: int
    ativo: bool = True
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