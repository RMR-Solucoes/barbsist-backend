from sqlalchemy import Column, Integer, String, Float, Boolean,Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from database import Base

class Barbearia(Base):
    __tablename__ = "barbearias"

    id = Column(Integer, primary_key=True, index=True)

    nome = Column(String, nullable=False)
    telefone_whatsapp = Column(String, nullable=True)
    endereco = Column(String, nullable=True)
    instagram = Column(String, nullable=True)
    logo_url = Column(String, nullable=True)
    slogan = Column(String, nullable=True)
    imagem_capa_url = Column(String, nullable=True)

    ativa = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)

class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    telefone = Column(String)
    email = Column(String)
    observacoes = Column(String)
    ativo = Column(Boolean, default=True)

    comandas = relationship("Comanda", back_populates="cliente")


class Barbeiro(Base):
    __tablename__ = "barbeiros"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    telefone = Column(String)
    email = Column(String, nullable=True)
    tipo = Column(String, default="associado")
    percentual_comissao = Column(Float, default=50.0)
    especialidades = Column(String, nullable=True)
    observacoes = Column(String, nullable=True)
    ativo = Column(Boolean, default=True)

    comandas = relationship("Comanda", back_populates="barbeiro")


class Servico(Base):
    __tablename__ = "servicos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    preco = Column(Float, nullable=False)
    tempo_medio_minutos = Column(Integer, default=30)
    ativo = Column(Boolean, default=True)


class Produto(Base):
    __tablename__ = "produtos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    categoria = Column(String)
    preco_custo = Column(Float, default=0)
    preco_venda = Column(Float, nullable=False)
    estoque = Column(Integer, default=0)
    codigo_qr = Column(String)
    ativo = Column(Boolean, default=True)


class Comanda(Base):
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


class Caixa(Base):
    __tablename__ = "caixa"

    id = Column(Integer, primary_key=True, index=True)

    tipo = Column(String, nullable=False)  # entrada ou saida
    descricao = Column(String, nullable=False)

    valor = Column(Float, nullable=False)

    forma_pagamento = Column(String, nullable=True)

    data = Column(DateTime, default=datetime.now)



class Comissao(Base):
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


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    senha_hash = Column(String, nullable=False)
    perfil = Column(String, default="admin")
    barbeiro_id = Column(Integer, ForeignKey("barbeiros.id"), nullable=True)
    ativo = Column(Boolean, default=True)
    data_criacao = Column(DateTime, default=datetime.now)

    barbeiro = relationship("Barbeiro")

    

class Estilo(Base):
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


class Agendamento(Base):
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


class Plano(Base):
    __tablename__ = "planos"

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

class AssinaturaCliente(Base):
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
    
    


class ConfiguracaoFuncionamento(Base):
    __tablename__ = "configuracao_funcionamento"

    id = Column(Integer, primary_key=True, index=True)

    dia_semana = Column(Integer, nullable=False)
    trabalha = Column(Boolean, default=True)

    hora_inicio = Column(String, default="08:00")
    hora_fim = Column(String, default="20:00")

class BarbeiroDisponibilidade(Base):
    __tablename__ = "barbeiro_disponibilidade"

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

class ContaReceber(Base):
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


class ContaPagar(Base):
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