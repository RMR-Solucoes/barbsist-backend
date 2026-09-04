from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


TipoParceiro = Literal[
    "VENDEDOR",
    "COLABORADOR",
    "BARBEARIA",
]

TipoBeneficio = Literal[
    "COMISSAO",
    "CREDITO",
]

RegraBeneficio = Literal[
    "PERCENTUAL",
    "VALOR_FIXO",
]

StatusIndicacao = Literal[
    "CADASTRADA",
    "ASSINANTE",
    "CONVERTIDA",
    "CANCELADA",
]

StatusComissao = Literal[
    "PENDENTE",
    "LIBERADA",
    "PAGA",
    "CANCELADA",
]

StatusCredito = Literal[
    "DISPONIVEL",
    "APLICADO",
    "CANCELADO",
]


class ParceiroBase(BaseModel):
    tipo: TipoParceiro
    nome: str = Field(min_length=2, max_length=150)
    email: str = Field(min_length=5, max_length=254)
    telefone: str | None = Field(default=None, max_length=30)

    barbearia_id: int | None = None

    codigo_ref: str = Field(
        min_length=3,
        max_length=80,
    )

    tipo_beneficio: TipoBeneficio
    regra_beneficio: RegraBeneficio

    percentual_beneficio: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )

    valor_fixo_beneficio: float | None = Field(
        default=None,
        ge=0,
    )

    ativo: bool = True
    observacao: str | None = None

    @model_validator(mode="after")
    def validar_regra_beneficio(self):
        if (
            self.regra_beneficio == "PERCENTUAL"
            and self.percentual_beneficio is None
        ):
            raise ValueError(
                "percentual_beneficio é obrigatório "
                "quando regra_beneficio=PERCENTUAL."
            )

        if (
            self.regra_beneficio == "VALOR_FIXO"
            and self.valor_fixo_beneficio is None
        ):
            raise ValueError(
                "valor_fixo_beneficio é obrigatório "
                "quando regra_beneficio=VALOR_FIXO."
            )

        if (
            self.tipo == "BARBEARIA"
            and self.barbearia_id is None
        ):
            raise ValueError(
                "barbearia_id é obrigatório "
                "para parceiro do tipo BARBEARIA."
            )

        if (
            self.tipo == "BARBEARIA"
            and self.tipo_beneficio != "CREDITO"
        ):
            raise ValueError(
                "Parceiro do tipo BARBEARIA "
                "deve utilizar benefício CREDITO."
            )

        if (
            self.tipo in {"VENDEDOR", "COLABORADOR"}
            and self.tipo_beneficio != "COMISSAO"
        ):
            raise ValueError(
                "VENDEDOR ou COLABORADOR "
                "deve utilizar benefício COMISSAO."
            )

        return self


class ParceiroCreate(ParceiroBase):
    pass


class ParceiroUpdate(BaseModel):
    nome: str | None = Field(
        default=None,
        min_length=2,
        max_length=150,
    )

    telefone: str | None = Field(
        default=None,
        max_length=30,
    )

    regra_beneficio: RegraBeneficio | None = None

    percentual_beneficio: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )

    valor_fixo_beneficio: float | None = Field(
        default=None,
        ge=0,
    )

    ativo: bool | None = None
    observacao: str | None = None


class ParceiroOut(ParceiroBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    criado_em: datetime
    atualizado_em: datetime


class IndicacaoCreate(BaseModel):
    parceiro_id: int
    codigo_ref: str = Field(
        min_length=3,
        max_length=80,
    )

    barbearia_indicada_id: int

    assinatura_saas_id: int | None = None
    status: StatusIndicacao = "CADASTRADA"
    observacao: str | None = None


class IndicacaoUpdate(BaseModel):
    assinatura_saas_id: int | None = None
    status: StatusIndicacao | None = None
    data_conversao: datetime | None = None
    observacao: str | None = None


class IndicacaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    parceiro_id: int
    codigo_ref: str
    barbearia_indicada_id: int
    assinatura_saas_id: int | None

    status: str
    data_cadastro: datetime
    data_conversao: datetime | None
    observacao: str | None


class ComissaoParceiroOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    parceiro_id: int
    indicacao_id: int
    pagamento_saas_id: int

    valor_base: float
    percentual: float | None
    valor_comissao: float

    status: str
    data_geracao: datetime
    data_liberacao: datetime | None
    data_pagamento: datetime | None
    observacao: str | None


class CreditoBarbeariaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    parceiro_id: int
    barbearia_parceira_id: int
    indicacao_id: int
    pagamento_saas_id: int

    valor_base: float
    percentual: float | None
    valor_credito: float

    status: str
    referencia_mensalidade: str | None

    data_geracao: datetime
    data_aplicacao: datetime | None
    observacao: str | None


class ResumoParceiroOut(BaseModel):
    parceiro_id: int
    nome: str
    tipo: str
    codigo_ref: str

    indicacoes_total: int
    indicacoes_convertidas: int

    valor_pendente: float
    valor_liberado: float
    valor_pago_ou_aplicado: float
