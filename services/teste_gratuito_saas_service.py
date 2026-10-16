from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import hmac
import os
import re
import unicodedata

from sqlalchemy import text

import models


DIAS_TESTE_GRATUITO = 40
DIAS_CARENCIA_TESTE = 15

ENV_FINGERPRINT_SECRET = "BARBSIST_TESTE_FINGERPRINT_SECRET"

FINGERPRINT_VERSION = "HMAC_SHA256_V1"


@dataclass(frozen=True)
class ResultadoElegibilidadeTeste:
    elegivel: bool
    codigo: str
    mensagem: str
    conflito_teste_id: int | None = None
    conflito_barbearia_id: int | None = None
    conflito_claim_id: int | None = None


def _somente_digitos(valor: str | None) -> str:
    return re.sub(r"\D", "", str(valor or ""))


def _normalizar_texto(valor: str | None) -> str:
    texto = str(valor or "").strip().upper()

    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(
        c for c in texto
        if not unicodedata.combining(c)
    )

    texto = re.sub(r"[^A-Z0-9]+", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()

    return texto


def _segredo_fingerprint() -> bytes:
    segredo = str(
        os.getenv(ENV_FINGERPRINT_SECRET) or ""
    ).strip()

    if len(segredo) < 32:
        raise RuntimeError(
            f"{ENV_FINGERPRINT_SECRET} deve possuir "
            "pelo menos 32 caracteres."
        )

    return segredo.encode("utf-8")


def _fingerprint(valor_normalizado: str) -> str:
    return hmac.new(
        _segredo_fingerprint(),
        valor_normalizado.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _chave_advisory(
    fingerprint: str,
) -> int:
    valor = int(
        fingerprint[:16],
        16,
    )

    if valor >= 2 ** 63:
        valor -= 2 ** 64

    return valor


def _adquirir_travas_antirrepeticao(
    db,
    *fingerprints: str,
) -> None:
    bind = db.get_bind()

    dialect = str(
        getattr(
            getattr(
                bind,
                "dialect",
                None,
            ),
            "name",
            "",
        )
        or ""
    ).lower()

    if dialect != "postgresql":
        return

    chaves = sorted(
        {
            _chave_advisory(fp)
            for fp in fingerprints
            if fp
        }
    )

    for chave in chaves:
        db.execute(
            text(
                "SELECT "
                "pg_advisory_xact_lock(:chave)"
            ),
            {
                "chave": chave,
            },
        )


def _cpf_valido(cpf: str) -> bool:
    cpf = _somente_digitos(cpf)

    if len(cpf) != 11:
        return False

    if cpf == cpf[0] * 11:
        return False

    soma = sum(
        int(cpf[i]) * (10 - i)
        for i in range(9)
    )

    d1 = (soma * 10) % 11
    if d1 == 10:
        d1 = 0

    if d1 != int(cpf[9]):
        return False

    soma = sum(
        int(cpf[i]) * (11 - i)
        for i in range(10)
    )

    d2 = (soma * 10) % 11
    if d2 == 10:
        d2 = 0

    return d2 == int(cpf[10])


def _cnpj_valido(cnpj: str) -> bool:
    cnpj = _somente_digitos(cnpj)

    if len(cnpj) != 14:
        return False

    if cnpj == cnpj[0] * 14:
        return False

    def calcular(base: str, pesos: list[int]) -> int:
        soma = sum(
            int(numero) * peso
            for numero, peso in zip(base, pesos)
        )

        resto = soma % 11
        return 0 if resto < 2 else 11 - resto

    d1 = calcular(
        cnpj[:12],
        [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2],
    )

    if d1 != int(cnpj[12]):
        return False

    d2 = calcular(
        cnpj[:13],
        [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2],
    )

    return d2 == int(cnpj[13])


def normalizar_tipo_documento(
    tipo_documento: str,
) -> str:
    tipo = str(tipo_documento or "").strip().upper()

    if tipo not in {"CPF", "CNPJ"}:
        raise ValueError(
            "tipo_documento deve ser CPF ou CNPJ."
        )

    return tipo


def normalizar_documento(
    tipo_documento: str,
    documento: str,
) -> str:
    tipo = normalizar_tipo_documento(
        tipo_documento
    )

    digitos = _somente_digitos(
        documento
    )

    if tipo == "CPF":
        if not _cpf_valido(
            digitos
        ):
            raise ValueError(
                "CPF invalido."
            )

    else:
        if not _cnpj_valido(
            digitos
        ):
            raise ValueError(
                "CNPJ invalido."
            )

    return digitos


def gerar_documento_fingerprint(
    tipo_documento: str,
    documento: str,
) -> str:
    tipo = normalizar_tipo_documento(
        tipo_documento
    )

    digitos = normalizar_documento(
        tipo,
        documento,
    )

    return _fingerprint(
        f"{tipo}:{digitos}"
    )


def gerar_endereco_fingerprint(
    endereco: str,
    cidade: str,
    estado: str,
    cep: str,
) -> str:
    endereco_normalizado = _normalizar_texto(
        endereco
    )
    cidade_normalizada = _normalizar_texto(
        cidade
    )
    estado_normalizado = _normalizar_texto(
        estado
    )
    cep_normalizado = _somente_digitos(cep)

    if not endereco_normalizado:
        raise ValueError(
            "Endereço é obrigatório para o teste gratuito."
        )

    if not cidade_normalizada:
        raise ValueError(
            "Cidade é obrigatória para o teste gratuito."
        )

    if len(estado_normalizado) != 2:
        raise ValueError(
            "Estado inválido para o teste gratuito."
        )

    if len(cep_normalizado) != 8:
        raise ValueError(
            "CEP inválido para o teste gratuito."
        )

    chave = "|".join(
        [
            cep_normalizado,
            endereco_normalizado,
            cidade_normalizada,
            estado_normalizado,
        ]
    )

    return _fingerprint(chave)


def _buscar_claim_antifraude(
    db,
    *,
    tipo_chave: str,
    chave_fingerprint: str,
    excluir_barbearia_id: int | None = None,
):
    consulta = (
        db.query(models.TesteGratuitoSaaSClaim)
        .filter(
            models.TesteGratuitoSaaSClaim.tipo_chave
            == str(tipo_chave).strip().upper(),
            models.TesteGratuitoSaaSClaim.fingerprint_version
            == FINGERPRINT_VERSION,
            models.TesteGratuitoSaaSClaim.chave_fingerprint
            == chave_fingerprint,
        )
    )

    if excluir_barbearia_id is not None:
        consulta = consulta.filter(
            models.TesteGratuitoSaaSClaim.barbearia_id_original
            != int(excluir_barbearia_id)
        )

    return (
        consulta
        .order_by(
            models.TesteGratuitoSaaSClaim.id.asc()
        )
        .first()
    )




def _registrar_claim_se_ausente(
    db,
    *,
    tipo_chave: str,
    chave_fingerprint: str,
    teste_id: int,
    barbearia_id_original: int,
    subtipo_documento: str | None = None,
    origem: str = "CADASTRO_PUBLICO",
):
    existente = _buscar_claim_antifraude(
        db,
        tipo_chave=tipo_chave,
        chave_fingerprint=chave_fingerprint,
    )

    if existente is not None:
        return existente, False

    claim = models.TesteGratuitoSaaSClaim(
        tipo_chave=str(
            tipo_chave
        ).strip().upper(),
        subtipo_documento=(
            str(subtipo_documento)
            .strip()
            .upper()
            if subtipo_documento
            else None
        ),
        chave_fingerprint=chave_fingerprint,
        fingerprint_version=(
            FINGERPRINT_VERSION
        ),
        teste_id=int(teste_id),
        barbearia_id_original=int(
            barbearia_id_original
        ),
        origem=str(
            origem
            or "CADASTRO_PUBLICO"
        ),
    )

    db.add(claim)
    db.flush()

    return claim, True




def avaliar_elegibilidade_novo_teste(
    db,
    *,
    tipo_documento: str,
    documento: str,
    endereco: str,
    cidade: str,
    estado: str,
    cep: str,
    excluir_barbearia_id: int | None = None,
) -> ResultadoElegibilidadeTeste:

    tipo_documento_normalizado = (
        normalizar_tipo_documento(
            tipo_documento
        )
    )

    documento_fp = gerar_documento_fingerprint(
        tipo_documento_normalizado,
        documento,
    )

    endereco_fp = gerar_endereco_fingerprint(
        endereco,
        cidade,
        estado,
        cep,
    )

    conflito_documento = (
        _buscar_claim_antifraude(
            db,
            tipo_chave="DOCUMENTO",
            chave_fingerprint=documento_fp,
            excluir_barbearia_id=(
                excluir_barbearia_id
            ),
        )
    )

    if conflito_documento is not None:
        return ResultadoElegibilidadeTeste(
            elegivel=False,
            codigo="DOCUMENTO_JA_UTILIZOU_TESTE",
            mensagem=(
                "Este respons?vel ou empresa j? utilizou "
                "o per?odo gratuito do BarbSist."
            ),
            conflito_teste_id=(
                conflito_documento.teste_id
            ),
            conflito_barbearia_id=(
                conflito_documento
                .barbearia_id_original
            ),
            conflito_claim_id=(
                conflito_documento.id
            ),
        )

    conflito_endereco = (
        _buscar_claim_antifraude(
            db,
            tipo_chave="ENDERECO",
            chave_fingerprint=endereco_fp,
            excluir_barbearia_id=(
                excluir_barbearia_id
            ),
        )
    )

    if conflito_endereco is not None:
        return ResultadoElegibilidadeTeste(
            elegivel=False,
            codigo="ENDERECO_JA_UTILIZOU_TESTE",
            mensagem=(
                "Este endere?o j? utilizou um per?odo "
                "gratuito do BarbSist. O cadastro pode "
                "prosseguir, mas um novo teste exige "
                "an?lise administrativa."
            ),
            conflito_teste_id=(
                conflito_endereco.teste_id
            ),
            conflito_barbearia_id=(
                conflito_endereco
                .barbearia_id_original
            ),
            conflito_claim_id=(
                conflito_endereco.id
            ),
        )

    return ResultadoElegibilidadeTeste(
        elegivel=True,
        codigo="ELEGIVEL_PRIMEIRO_TESTE",
        mensagem=(
            "Estabelecimento eleg?vel ao primeiro "
            "per?odo gratuito."
        ),
    )






def criar_teste_gratuito_sem_commit(
    db,
    *,
    barbearia_id: int,
    tipo_documento: str,
    documento: str,
    endereco: str,
    cidade: str,
    estado: str,
    cep: str,
    autorizar_excecao: bool = False,
    motivo_liberacao: str | None = None,
    autorizado_por_usuario_id: int | None = None,
    origem: str = "CADASTRO_PUBLICO",
    agora: datetime | None = None,
):
    tipo_documento_normalizado = (
        normalizar_tipo_documento(
            tipo_documento
        )
    )

    documento_fp = gerar_documento_fingerprint(
        tipo_documento_normalizado,
        documento,
    )

    endereco_fp = gerar_endereco_fingerprint(
        endereco,
        cidade,
        estado,
        cep,
    )

    _adquirir_travas_antirrepeticao(
        db,
        documento_fp,
        endereco_fp,
    )

    existente = (
        db.query(
            models.TesteGratuitoSaaS
        )
        .filter(
            models.TesteGratuitoSaaS.barbearia_id
            == int(barbearia_id)
        )
        .first()
    )

    if existente is not None:
        raise ValueError(
            "Esta barbearia ja possui "
            "registro de teste gratuito."
        )

    resultado = avaliar_elegibilidade_novo_teste(
        db,
        tipo_documento=(
            tipo_documento_normalizado
        ),
        documento=documento,
        endereco=endereco,
        cidade=cidade,
        estado=estado,
        cep=cep,
        excluir_barbearia_id=barbearia_id,
    )

    if (
        not resultado.elegivel
        and not autorizar_excecao
    ):
        return None, resultado

    motivo_normalizado = str(
        motivo_liberacao or ""
    ).strip()

    usuario_autorizador = None

    if autorizar_excecao:

        if resultado.elegivel:
            raise ValueError(
                "Nao existe conflito antifraude "
                "que justifique excecao manual."
            )

        if len(motivo_normalizado) < 3:
            raise ValueError(
                "Informe a justificativa da "
                "excecao manual."
            )

        if autorizado_por_usuario_id is None:
            raise ValueError(
                "Informe o SuperAdmin responsavel "
                "pela excecao."
            )

        usuario_autorizador = (
            db.query(models.Usuario)
            .filter(
                models.Usuario.id
                == int(
                    autorizado_por_usuario_id
                ),
                models.Usuario.ativo.is_(True),
            )
            .first()
        )

        if (
            usuario_autorizador is None
            or str(
                usuario_autorizador.perfil
                or ""
            ).strip().lower()
            != "superadmin"
        ):
            raise ValueError(
                "A excecao deve ser autorizada "
                "por um SuperAdmin ativo."
            )

    inicio = agora or datetime.now()

    fim = inicio + timedelta(
        days=DIAS_TESTE_GRATUITO
    )

    teste = models.TesteGratuitoSaaS(
        barbearia_id=int(barbearia_id),
        barbearia_id_original=int(
            barbearia_id
        ),
        tipo_documento=(
            tipo_documento_normalizado
        ),
        documento_fingerprint=documento_fp,
        endereco_fingerprint=endereco_fp,
        fingerprint_version=(
            FINGERPRINT_VERSION
        ),
        data_inicio=inicio,
        data_fim=fim,
        status="ATIVO",
        liberacao_manual=bool(
            autorizar_excecao
        ),
        motivo_liberacao=(
            motivo_normalizado
            if autorizar_excecao
            else None
        ),
        liberado_por_usuario_id=(
            usuario_autorizador.id
            if usuario_autorizador
            else None
        ),
        liberado_em=(
            inicio
            if autorizar_excecao
            else None
        ),
        liberacao_conflito_codigo=(
            resultado.codigo
            if autorizar_excecao
            else None
        ),
        liberacao_claim_id=(
            resultado.conflito_claim_id
            if autorizar_excecao
            else None
        ),
        origem=str(
            origem
            or "CADASTRO_PUBLICO"
        ),
    )

    db.add(teste)
    db.flush()

    _registrar_claim_se_ausente(
        db,
        tipo_chave="DOCUMENTO",
        chave_fingerprint=documento_fp,
        teste_id=teste.id,
        barbearia_id_original=barbearia_id,
        subtipo_documento=(
            tipo_documento_normalizado
        ),
        origem=origem,
    )

    _registrar_claim_se_ausente(
        db,
        tipo_chave="ENDERECO",
        chave_fingerprint=endereco_fp,
        teste_id=teste.id,
        barbearia_id_original=barbearia_id,
        subtipo_documento=None,
        origem=origem,
    )

    return teste, resultado






def obter_teste_da_barbearia(
    db,
    barbearia_id: int,
):
    return (
        db.query(models.TesteGratuitoSaaS)
        .filter(
            models.TesteGratuitoSaaS.barbearia_id
            == barbearia_id
        )
        .first()
    )


def converter_teste_gratuito_por_assinatura_sem_commit(
    db,
    *,
    barbearia_id: int,
    assinatura_id: int,
    agora: datetime | None = None,
):
    """
    Marca o teste gratuito como convertido.

    Nao executa commit. A chamada deve participar
    da mesma transacao que confirma a assinatura
    SaaS paga.
    """

    teste = (
        db.query(models.TesteGratuitoSaaS)
        .filter(
            models.TesteGratuitoSaaS.barbearia_id
            == int(barbearia_id)
        )
        .with_for_update()
        .first()
    )

    if teste is None:
        return None

    status_atual = str(
        getattr(
            teste,
            "status",
            None,
        )
        or "ATIVO"
    ).strip().upper()

    # Idempotencia: webhooks podem ser reenviados.
    if status_atual == "CONVERTIDO":
        return teste

    # Um teste revogado ou em outro estado terminal
    # nunca deve ser reativado implicitamente.
    if status_atual != "ATIVO":
        return teste

    teste.status = "CONVERTIDO"
    teste.convertido_em = (
        agora
        or datetime.now()
    )
    teste.assinatura_convertida_id = int(
        assinatura_id
    )

    db.flush()

    return teste


def situacao_teste_gratuito(
    teste,
    *,
    agora: datetime | None = None,
) -> str:
    if teste is None:
        return "SEM_TESTE"

    status_teste = str(
        getattr(
            teste,
            "status",
            None,
        )
        or "ATIVO"
    ).strip().upper()

    if status_teste != "ATIVO":
        return status_teste

    momento = agora or datetime.now()

    if momento <= teste.data_fim:
        return "TESTE"

    fim_carencia = teste.data_fim + timedelta(
        days=DIAS_CARENCIA_TESTE
    )

    if momento <= fim_carencia:
        return "CARENCIA"

    return "ENCERRADO"
