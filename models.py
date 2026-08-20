from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    UniqueConstraint
)
from sqlalchemy.orm import relationship
from datetime import datetime

from database import Base
from models_mixins import BarbeariaMixin

class Barbearia(Base):
    __tablename__ = "barbearias"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    codigo = Column(
        Integer,
        unique=True,
        nullable=False,
        index=True
    )

    slug = Column(
        String,
        unique=True,
        nullable=False,
        index=True
    )

    # Dados cadastrais
    nome = Column(
        String,
        nullable=False
    )

    responsavel = Column(
        String,
        nullable=True
    )

    email = Column(
        String,
        nullable=True
    )

    telefone = Column(
        String,
        nullable=True
    )

    telefone_whatsapp = Column(
        String,
        nullable=True
    )

    cnpj = Column(
        String,
        nullable=True
    )

    # Endereço
    endereco = Column(
        String,
        nullable=True
    )

    cidade = Column(
        String,
        nullable=True
    )

    estado = Column(
        String,
        nullable=True
    )

    cep = Column(
        String,
        nullable=True
    )

    # Identidade visual
    instagram = Column(
        String,
        nullable=True
    )

    logo_url = Column(
        String,
        nullable=True
    )

    slogan = Column(
        String,
        nullable=True
    )

    imagem_capa_url = Column(
        String,
        nullable=True
    )

    # Preparação para personalização visual
    cor_primaria = Column(
        String,
        default="#111827",
        nullable=False
    )

    cor_secundaria = Column(
        String,
        default="#2563EB",
        nullable=False
    )

    cor_fundo = Column(
        String,
        default="#F3F4F6",
        nullable=False
    )

    cor_sidebar = Column(
        String,
        default="#111827",
        nullable=False
    )

    cor_texto_sidebar = Column(
        String,
        default="#FFFFFF",
        nullable=False
    )

    cor_destaque = Column(
        String,
        default="#2563EB",
        nullable=False
    )

    # Controle
    ativa = Column(
        Boolean,
        default=True,
        nullable=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

class SequenciaBarbearia(Base):
    __tablename__ = "sequencias_barbearia"

    __table_args__ = (
        UniqueConstraint(
            "barbearia_id",
            "tipo",
            name="uq_sequencia_barbearia_tipo"
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    barbearia_id = Column(
        Integer,
        ForeignKey(
            "barbearias.id",
            ondelete="RESTRICT"
        ),
        nullable=False,
        index=True
    )

    tipo = Column(
        String,
        nullable=False
    )

    ultimo_numero = Column(
        Integer,
        default=0,
        nullable=False
    )

    data_atualizacao = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        nullable=False
    )

    barbearia = relationship(
        "Barbearia"
    )

class Cliente(BarbeariaMixin, Base):
    __tablename__ = "clientes"

    __table_args__ = (
        UniqueConstraint(
            "barbearia_id",
            "codigo",
            name="uq_cliente_barbearia_codigo"
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    numero_sequencial = Column(
        Integer,
        nullable=False,
        index=True
    )

    codigo = Column(
        String,
        nullable=False,
        index=True
    )

    nome = Column(
        String,
        nullable=False
    )

    telefone = Column(
        String,
        nullable=True
    )

    email = Column(
        String,
        nullable=True
    )

    observacoes = Column(
        String,
        nullable=True
    )

    ativo = Column(
        Boolean,
        default=True,
        nullable=False
    )

    comandas = relationship(
        "Comanda",
        back_populates="cliente"
    )

class Barbeiro(BarbeariaMixin, Base):
    __tablename__ = "barbeiros"

    __table_args__ = (
        UniqueConstraint(
            "barbearia_id",
            "codigo",
            name="uq_barbeiro_barbearia_codigo"
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    numero_sequencial = Column(
        Integer,
        nullable=False,
        index=True
    )

    codigo = Column(
        String,
        nullable=False,
        index=True
    )

    nome = Column(
        String,
        nullable=False
    )

    telefone = Column(
        String,
        nullable=True
    )

    email = Column(
        String,
        nullable=True
    )

    tipo = Column(
        String,
        default="associado",
        nullable=False
    )

    percentual_comissao = Column(
        Float,
        default=50.0,
        nullable=False
    )

    especialidades = Column(
        String,
        nullable=True
    )

    observacoes = Column(
        String,
        nullable=True
    )

    ativo = Column(
        Boolean,
        default=True,
        nullable=False
    )

    comandas = relationship(
        "Comanda",
        back_populates="barbeiro"
    )


class Servico(BarbeariaMixin, Base):
    __tablename__ = "servicos"

    __table_args__ = (
        UniqueConstraint(
            "barbearia_id",
            "codigo",
            name="uq_servico_barbearia_codigo"
        ),
        UniqueConstraint(
            "barbearia_id",
            "nome",
            name="uq_servico_barbearia_nome"
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    numero_sequencial = Column(
        Integer,
        nullable=False,
        index=True
    )

    codigo = Column(
        String,
        nullable=False,
        index=True
    )

    nome = Column(
        String,
        nullable=False
    )

    preco = Column(
        Float,
        nullable=False
    )

    tempo_medio_minutos = Column(
        Integer,
        default=30,
        nullable=False
    )

    ativo = Column(
        Boolean,
        default=True,
        nullable=False
    )


class Produto(BarbeariaMixin, Base):
    __tablename__ = "produtos"

    __table_args__ = (
        UniqueConstraint(
            "barbearia_id",
            "codigo",
            name="uq_produto_barbearia_codigo"
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    numero_sequencial = Column(
        Integer,
        nullable=False,
        index=True
    )

    codigo = Column(
        String,
        nullable=False,
        index=True
    )

    nome = Column(
        String,
        nullable=False
    )

    categoria = Column(
        String,
        nullable=True
    )

    preco_custo = Column(
        Float,
        default=0,
        nullable=False
    )

    preco_venda = Column(
        Float,
        nullable=False
    )

    estoque = Column(
        Integer,
        default=0,
        nullable=False
    )

    codigo_qr = Column(
        String,
        nullable=True
    )

    ativo = Column(
        Boolean,
        default=True,
        nullable=False
    )


class Comanda(BarbeariaMixin, Base):
    __tablename__ = "comandas"

    id = Column(Integer, primary_key=True, index=True)

    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=True)
    barbeiro_id = Column(Integer, ForeignKey("barbeiros.id"), nullable=False)

    status = Column(String, default="aberta")
    total = Column(Float, default=0)
    forma_pagamento = Column(String, nullable=True)

    data_abertura = Column(DateTime, default=datetime.now)
    data_fechamento = Column(DateTime, nullable=True)

    cliente = relationship("Cliente", back_populates="comandas")
    barbeiro = relationship("Barbeiro", back_populates="comandas")
    itens = relationship("ItemComanda", back_populates="comanda")

    @property
    def cliente_nome(self):
        return self.cliente.nome if self.cliente else "CLIENTE AVULSO"

    @property
    def barbeiro_nome(self):
        return self.barbeiro.nome if self.barbeiro else None


class ItemComanda(Base):
    __tablename__ = "itens_comanda"

    id = Column(Integer, primary_key=True, index=True)

    comanda_id = Column(
        Integer,
        ForeignKey("comandas.id"),
        nullable=False
    )

    tipo = Column(
        String,
        nullable=False
    )  # servico ou produto

    descricao = Column(
        String,
        nullable=False
    )

    quantidade = Column(
        Integer,
        default=1
    )

    valor_unitario = Column(
        Float,
        default=0
    )

    subtotal = Column(
        Float,
        default=0
    )

    servico_id = Column(
        Integer,
        ForeignKey("servicos.id"),
        nullable=True
    )

    produto_id = Column(
        Integer,
        ForeignKey("produtos.id"),
        nullable=True
    )

    pago_com_plano = Column(
        Boolean,
        default=False,
        nullable=False
    )

    uso_plano_id = Column(
        Integer,
        ForeignKey("usos_planos.id"),
        nullable=True
    )

    comanda = relationship(
        "Comanda",
        back_populates="itens"
    )

    servico = relationship("Servico")
    produto = relationship("Produto")

    uso_plano = relationship(
        "UsoPlano",
        foreign_keys=[uso_plano_id]
    )


class Caixa(BarbeariaMixin, Base):
    __tablename__ = "caixa"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    tipo = Column(
        String,
        nullable=False
    )  # entrada | saida

    descricao = Column(
        String,
        nullable=False
    )

    valor = Column(
        Float,
        nullable=False
    )

    forma_pagamento = Column(
        String,
        nullable=True
    )

    # MANUAL | COMANDA | PLANO | CONTA_RECEBER |
    # CONTA_PAGAR | ESTORNO | SANGRIA | SUPRIMENTO
    origem = Column(
        String,
        default="MANUAL",
        nullable=False,
        index=True
    )

    # ID do registro que originou a movimentação.
    # Exemplo: ID da comanda, assinatura ou conta.
    referencia_id = Column(
        Integer,
        nullable=True,
        index=True
    )

    # ATIVO | ESTORNADO | CANCELADO
    status = Column(
        String,
        default="ATIVO",
        nullable=False,
        index=True
    )

    observacoes = Column(
        String,
        nullable=True
    )

    # Usuário que lançou manualmente ou executou a operação.
    usuario_id = Column(
        Integer,
        ForeignKey("usuarios.id"),
        nullable=True,
        index=True
    )

    # Preenchido quando esta movimentação for um estorno.
    movimentacao_origem_id = Column(
        Integer,
        ForeignKey("caixa.id"),
        nullable=True,
        index=True
    )

    data = Column(
        DateTime,
        default=datetime.now,
        nullable=False,
        index=True
    )

    usuario = relationship(
        "Usuario",
        foreign_keys=[usuario_id]
    )

    movimentacao_origem = relationship(
        "Caixa",
        remote_side=[id],
        foreign_keys=[movimentacao_origem_id]
    )



class Comissao(BarbeariaMixin, Base):
    __tablename__ = "comissoes"

    id = Column(Integer, primary_key=True, index=True)

    barbeiro_id = Column(Integer, ForeignKey("barbeiros.id"), nullable=False)
    comanda_id = Column(Integer, ForeignKey("comandas.id"), nullable=False)

    valor_servico = Column(Float, nullable=False)
    percentual = Column(Float, nullable=False)
    valor_comissao = Column(Float, nullable=False)

    data = Column(DateTime, default=datetime.now)

    barbeiro = relationship("Barbeiro")
    comanda = relationship("Comanda")


class Usuario(BarbeariaMixin, Base):
    __tablename__ = "usuarios"

    # Usu?rios operacionais pertencem a uma barbearia.
    # O superadmin da plataforma ? global e pode usar NULL.
    barbearia_id = Column(
        Integer,
        ForeignKey("barbearias.id", ondelete="RESTRICT"),
        nullable=True,
        index=True
    )

    __table_args__ = (
        UniqueConstraint(
            "barbearia_id",
            "email",
            name="uq_usuario_barbearia_email"
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    nome = Column(
        String,
        nullable=False
    )

    email = Column(
        String,
        index=True,
        nullable=False
    )

    senha_hash = Column(
        String,
        nullable=False
    )

    perfil = Column(
        String,
        default="admin",
        nullable=False
    )

    barbeiro_id = Column(
        Integer,
        ForeignKey("barbeiros.id"),
        nullable=True
    )

    ativo = Column(
        Boolean,
        default=True,
        nullable=False
    )

    data_criacao = Column(
        DateTime,
        default=datetime.now,
        nullable=False
    )

    barbeiro = relationship(
        "Barbeiro"
    )
    


class TokenRecuperacaoSenha(Base):
    __tablename__ = "tokens_recuperacao_senha"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    usuario_id = Column(
        Integer,
        ForeignKey("usuarios.id"),
        nullable=False,
        index=True
    )

    barbearia_id = Column(
        Integer,
        ForeignKey("barbearias.id"),
        nullable=True,
        index=True
    )

    token_hash = Column(
        String,
        nullable=False,
        unique=True,
        index=True
    )

    criado_em = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    expira_em = Column(
        DateTime,
        nullable=False
    )

    utilizado = Column(
        Boolean,
        default=False,
        nullable=False
    )

    utilizado_em = Column(
        DateTime,
        nullable=True
    )

    usuario = relationship("Usuario")
    barbearia = relationship("Barbearia")

class Estilo(BarbeariaMixin, Base):
    __tablename__ = "estilos"

    id = Column(Integer, primary_key=True, index=True)

    nome = Column(String, nullable=False)

    categoria = Column(
        String,
        nullable=False
    )  # corte, barba, sobrancelha

    tipo_cabelo = Column(
        String,
        default="geral"
    )  # afro, liso, cacheado...

    descricao = Column(String, nullable=True)

    imagem_url = Column(String, nullable=True)

    ativo = Column(Boolean, default=True)

    data_criacao = Column(
        DateTime,
        default=datetime.now
    )    


class Agendamento(BarbeariaMixin, Base):
    __tablename__ = "agendamentos"

    id = Column(Integer, primary_key=True, index=True)

    cliente_id = Column(
        Integer,
        ForeignKey("clientes.id"),
        nullable=True
    )

    barbeiro_id = Column(
        Integer,
        ForeignKey("barbeiros.id"),
        nullable=False
    )

    servico_id = Column(
        Integer,
        ForeignKey("servicos.id"),
        nullable=False
    )

    estilo_corte_id = Column(
        Integer,
        ForeignKey("estilos.id"),
        nullable=True
    )

    estilo_barba_id = Column(
        Integer,
        ForeignKey("estilos.id"),
        nullable=True
    )

    data_hora_inicio = Column(DateTime, nullable=False)

    data_hora_fim = Column(
        DateTime,
        nullable=False
    )

    tipo_atendimento = Column(
        String,
        default="avulso"
    )  # plano ou avulso

    # INTERNO | ONLINE | WHATSAPP
    origem = Column(
        String,
        default="INTERNO"
    )

    status = Column(
        String,
        default="agendado"
    )

    observacoes = Column(
        String,
        nullable=True
    )

    data_criacao = Column(
        DateTime,
        default=datetime.now
    )

    cliente = relationship("Cliente")
    barbeiro = relationship("Barbeiro")
    servico = relationship("Servico")

    estilo_corte = relationship(
        "Estilo",
        foreign_keys=[estilo_corte_id]
    )

    estilo_barba = relationship(
        "Estilo",
        foreign_keys=[estilo_barba_id]
    )


class Plano(BarbeariaMixin, Base):
    __tablename__ = "planos"

    __table_args__ = (
        UniqueConstraint(
            "barbearia_id",
            "nome",
            name="uq_plano_barbearia_nome"
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    nome = Column(
        String,
        nullable=False
    )

    descricao = Column(
        String,
        nullable=True
    )

    valor = Column(
        Float,
        nullable=False
    )

    # Pre?os por forma de pagamento. Se nulos, o sistema usa ``valor``.
    valor_pix = Column(Float, nullable=True)
    valor_cartao = Column(Float, nullable=True)
    max_parcelas_cartao = Column(Integer, default=1, nullable=False)

    quantidade_servicos = Column(
        Integer,
        default=0
    )

    validade_dias = Column(
        Integer,
        default=30
    )

    ativo = Column(
        Boolean,
        default=True
    )

    data_criacao = Column(
        DateTime,
        default=datetime.now
    )

    servicos = relationship(
        "PlanoServico",
        back_populates="plano",
        cascade="all, delete-orphan"
    )

    @property
    def servicos_ids(self):
        return [vinculo.servico_id for vinculo in (self.servicos or [])]


class PlanoServico(Base):
    __tablename__ = "planos_servicos"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    plano_id = Column(
        Integer,
        ForeignKey("planos.id"),
        nullable=False
    )

    servico_id = Column(
        Integer,
        ForeignKey("servicos.id"),
        nullable=False
    )

    plano = relationship(
        "Plano",
        back_populates="servicos"
    )

    servico = relationship(
        "Servico"
    )

class AssinaturaCliente(BarbeariaMixin, Base):
    __tablename__ = "assinaturas_clientes"

    id = Column(Integer, primary_key=True, index=True)

    cliente_id = Column(
        Integer,
        ForeignKey("clientes.id"),
        nullable=False
    )

    plano_id = Column(
        Integer,
        ForeignKey("planos.id"),
        nullable=False
    )

    data_inicio = Column(
        DateTime,
        default=datetime.now
    )

    data_fim = Column(
        DateTime,
        nullable=False
    )

    data_ultimo_pagamento = Column(
        DateTime,
        nullable=True
    )

    data_proximo_vencimento = Column(
        DateTime,
        nullable=True
    )

    dias_tolerancia = Column(
        Integer,
        default=5
    )

    valor_mensal = Column(
        Float,
        default=0
    )

    usos_disponiveis = Column(
        Integer,
        default=0
    )

    status = Column(
        String,
        default="ativo"
    )

    # pago | vencido | inadimplente | pendente_pagamento
    status_pagamento = Column(
        String,
        default="pendente_pagamento"
    )

    cliente = relationship("Cliente")
    plano = relationship("Plano")

class UsoPlano(Base):
    __tablename__ = "usos_planos"

    id = Column(Integer, primary_key=True, index=True)

    assinatura_id = Column(
        Integer,
        ForeignKey("assinaturas_clientes.id"),
        nullable=False
    )

    comanda_id = Column(
        Integer,
        ForeignKey("comandas.id"),
        nullable=True
    )

    servico_id = Column(
        Integer,
        ForeignKey("servicos.id"),
        nullable=True
    )

    data_uso = Column(
        DateTime,
        default=datetime.now
    )

    assinatura = relationship("AssinaturaCliente")
    comanda = relationship("Comanda")
    servico = relationship("Servico")

class PagamentoPlano(Base):
    __tablename__ = "pagamentos_planos"

    id = Column(Integer, primary_key=True, index=True)

    assinatura_id = Column(
        Integer,
        ForeignKey("assinaturas_clientes.id"),
        nullable=False
    )

    cliente_id = Column(
        Integer,
        ForeignKey("clientes.id"),
        nullable=False
    )

    plano_id = Column(
        Integer,
        ForeignKey("planos.id"),
        nullable=False
    )

    valor = Column(Float, nullable=False)
    forma_pagamento = Column(String, nullable=False)

    status = Column(String, default="pago")  # pago, estornado, pendente

    referencia_mes = Column(String, nullable=True)  # exemplo: 2026-05

    observacoes = Column(String, nullable=True)

    data_pagamento = Column(DateTime, default=datetime.now)

    assinatura = relationship("AssinaturaCliente")
    cliente = relationship("Cliente")
    plano = relationship("Plano") 
    
    


class ConfiguracaoFuncionamento(BarbeariaMixin, Base):
    __tablename__ = "configuracao_funcionamento"

    __table_args__ = (
        UniqueConstraint(
            "barbearia_id",
            "dia_semana",
            name="uq_config_funcionamento_barbearia_dia"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    dia_semana = Column(Integer, nullable=False)
    trabalha = Column(Boolean, default=True)

    hora_inicio = Column(String, default="08:00")
    hora_fim = Column(String, default="20:00")

class BarbeiroDisponibilidade(BarbeariaMixin, Base):
    __tablename__ = "barbeiro_disponibilidade"

    __table_args__ = (
        UniqueConstraint(
            "barbearia_id",
            "barbeiro_id",
            "dia_semana",
            name="uq_disponibilidade_barbearia_barbeiro_dia"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    barbeiro_id = Column(
        Integer,
        ForeignKey("barbeiros.id"),
        nullable=False
    )

    usa_padrao = Column(Boolean, default=True)

    dia_semana = Column(Integer, nullable=False)  # 0=segunda, 6=domingo

    trabalha = Column(Boolean, default=True)

    hora_inicio = Column(String, default="08:00")
    hora_fim = Column(String, default="20:00")

    barbeiro = relationship("Barbeiro")    

class ContaReceber(BarbeariaMixin, Base):
    __tablename__ = "contas_receber"

    id = Column(Integer, primary_key=True, index=True)
    descricao = Column(String, nullable=False)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=True)
    valor = Column(Float, nullable=False)
    vencimento = Column(Date, nullable=False)
    data_pagamento = Column(Date, nullable=True)
    status = Column(String, default="PENDENTE")
    forma_pagamento = Column(String, nullable=True)
    observacoes = Column(String, nullable=True)


class ContaPagar(BarbeariaMixin, Base):
    __tablename__ = "contas_pagar"

    id = Column(Integer, primary_key=True, index=True)
    descricao = Column(String, nullable=False)
    fornecedor = Column(String, nullable=True)
    valor = Column(Float, nullable=False)
    vencimento = Column(Date, nullable=False)
    data_pagamento = Column(Date, nullable=True)
    status = Column(String, default="PENDENTE")
    forma_pagamento = Column(String, nullable=True)
    observacoes = Column(String, nullable=True)


class MercadoPagoConfiguracao(Base):
    __tablename__ = "mercado_pago_configuracoes"
    __table_args__ = (UniqueConstraint("barbearia_id", name="uq_mp_config_barbearia"),)

    id = Column(Integer, primary_key=True, index=True)
    barbearia_id = Column(Integer, ForeignKey("barbearias.id"), nullable=False, index=True)
    access_token_encrypted = Column(String, nullable=True)
    refresh_token_encrypted = Column(String, nullable=True)
    webhook_secret_encrypted = Column(String, nullable=True)
    public_key = Column(String, nullable=True)
    mercado_pago_user_id = Column(String, nullable=True, index=True)
    token_type = Column(String, nullable=True)
    scope = Column(String, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    oauth_status = Column(String, default="NAO_CONECTADO", nullable=False)
    conectado_em = Column(DateTime, nullable=True)
    ultima_renovacao_em = Column(DateTime, nullable=True)
    ambiente = Column(String, default="producao", nullable=False)
    ativo = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    barbearia = relationship("Barbearia")


class MercadoPagoOAuthState(Base):
    __tablename__ = "mercado_pago_oauth_states"

    id = Column(Integer, primary_key=True, index=True)
    state_hash = Column(String, nullable=False, unique=True, index=True)
    barbearia_id = Column(Integer, ForeignKey("barbearias.id"), nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    code_verifier_encrypted = Column(String, nullable=True)
    criado_em = Column(DateTime, default=datetime.now, nullable=False)
    expira_em = Column(DateTime, nullable=False, index=True)
    utilizado_em = Column(DateTime, nullable=True)

    barbearia = relationship("Barbearia")
    usuario = relationship("Usuario")


class MercadoPagoCobranca(Base):
    __tablename__ = "mercado_pago_cobrancas"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_mp_cobranca_idempotency"),
        UniqueConstraint("external_reference", name="uq_mp_cobranca_external_reference"),
        UniqueConstraint("payment_id", name="uq_mp_cobranca_payment_id"),
        UniqueConstraint("order_id", name="uq_mp_cobranca_order_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    barbearia_id = Column(Integer, ForeignKey("barbearias.id"), nullable=False, index=True)
    # A cobrança pode nascer de Plano, Comanda ou Venda.
    # assinatura_id é mantido por compatibilidade com o fluxo atual de planos.
    assinatura_id = Column(Integer, ForeignKey("assinaturas_clientes.id"), nullable=True, index=True)
    origem_negocio = Column(String, default="PLANO_CLIENTE", nullable=False, index=True)
    origem_id = Column(Integer, nullable=True, index=True)
    payment_id = Column(String, nullable=True, index=True)
    order_id = Column(String, nullable=True, index=True)
    idempotency_key = Column(String, nullable=False, index=True)
    external_reference = Column(String, nullable=False, index=True)
    valor = Column(Float, nullable=False)
    tipo_pagamento = Column(String, default="PIX", nullable=False)
    installments = Column(Integer, default=1, nullable=False)
    valor_parcela = Column(Float, nullable=True)
    payment_method_id = Column(String, nullable=True)
    payment_type_id = Column(String, nullable=True)
    status = Column(String, default="pending", nullable=False, index=True)
    status_detail = Column(String, nullable=True)
    payer_email = Column(String, nullable=True)
    qr_code = Column(String, nullable=True)
    qr_code_base64 = Column(String, nullable=True)
    ticket_url = Column(String, nullable=True)
    processado = Column(Boolean, default=False, nullable=False)
    processado_em = Column(DateTime, nullable=True)
    data_criacao = Column(DateTime, default=datetime.now, nullable=False)
    data_atualizacao = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    assinatura = relationship("AssinaturaCliente")
    barbearia = relationship("Barbearia")


# =========================
# ASSINATURAS SAAS BARBSIST
# =========================
class PlanoSaaS(Base):
    __tablename__ = "planos_saas"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False, unique=True, index=True)
    descricao = Column(String, nullable=True)
    periodo_meses = Column(Integer, nullable=False, default=1)
    valor_pix = Column(Float, nullable=False)
    valor_cartao = Column(Float, nullable=False)
    max_parcelas_cartao = Column(Integer, nullable=False, default=1)
    ativo = Column(Boolean, nullable=False, default=True)
    data_criacao = Column(DateTime, nullable=False, default=datetime.now)
    data_atualizacao = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)


class AssinaturaSaaS(Base):
    __tablename__ = "assinaturas_saas"
    __table_args__ = (
        UniqueConstraint("barbearia_id", name="uq_assinatura_saas_barbearia"),
    )

    id = Column(Integer, primary_key=True, index=True)
    barbearia_id = Column(Integer, ForeignKey("barbearias.id", ondelete="RESTRICT"), nullable=False, index=True)
    plano_id = Column(Integer, ForeignKey("planos_saas.id", ondelete="RESTRICT"), nullable=False, index=True)

    status = Column(String, nullable=False, default="PENDENTE")
    status_pagamento = Column(String, nullable=False, default="PENDENTE")
    forma_pagamento = Column(String, nullable=True)

    data_inicio = Column(DateTime, nullable=True)
    data_fim = Column(DateTime, nullable=True)
    data_proximo_vencimento = Column(DateTime, nullable=True)
    liberado_manual = Column(Boolean, nullable=False, default=False)
    motivo_bloqueio = Column(String, nullable=True)

    criado_em = Column(DateTime, nullable=False, default=datetime.now)
    atualizado_em = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    barbearia = relationship("Barbearia")
    plano = relationship("PlanoSaaS")


class PagamentoSaaS(Base):
    __tablename__ = "pagamentos_saas"
    __table_args__ = (
        UniqueConstraint("payment_id", name="uq_pagamento_saas_payment_id"),
        UniqueConstraint("external_reference", name="uq_pagamento_saas_external_reference"),
        UniqueConstraint("idempotency_key", name="uq_pagamento_saas_idempotency_key"),
    )

    id = Column(Integer, primary_key=True, index=True)
    assinatura_id = Column(Integer, ForeignKey("assinaturas_saas.id", ondelete="RESTRICT"), nullable=False, index=True)
    barbearia_id = Column(Integer, ForeignKey("barbearias.id", ondelete="RESTRICT"), nullable=False, index=True)
    plano_id = Column(Integer, ForeignKey("planos_saas.id", ondelete="RESTRICT"), nullable=False, index=True)

    payment_id = Column(String, nullable=True, index=True)
    external_reference = Column(String, nullable=False, index=True)
    idempotency_key = Column(String, nullable=False, index=True)

    tipo_pagamento = Column(String, nullable=False)  # PIX | CARTAO | MANUAL
    payment_method_id = Column(String, nullable=True)
    payment_type_id = Column(String, nullable=True)
    installments = Column(Integer, nullable=False, default=1)
    valor = Column(Float, nullable=False)
    valor_parcela = Column(Float, nullable=True)
    payer_email = Column(String, nullable=True)

    status = Column(String, nullable=False, default="pending")
    status_detail = Column(String, nullable=True)
    qr_code = Column(String, nullable=True)
    qr_code_base64 = Column(String, nullable=True)
    ticket_url = Column(String, nullable=True)

    processado = Column(Boolean, nullable=False, default=False)
    processado_em = Column(DateTime, nullable=True)
    data_criacao = Column(DateTime, nullable=False, default=datetime.now)

    assinatura = relationship("AssinaturaSaaS")
    barbearia = relationship("Barbearia")
    plano = relationship("PlanoSaaS")
