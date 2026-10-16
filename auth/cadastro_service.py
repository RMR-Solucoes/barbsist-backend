from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models

from auth.security import criar_hash_senha
from auth.usuario_service import (
    normalizar_email,
    validar_senha,
)
from services.barbearia_service import (
    gerar_proximo_codigo,
    gerar_slug_unico,
    normalizar_texto,
    validar_nome_barbearia,
)
from services.configuracao_funcionamento_service import (
    criar_configuracao_padrao_por_barbearia,
)
from services.sequencia_service import PREFIXOS_CODIGO
from services.teste_gratuito_saas_service import (
    criar_teste_gratuito_sem_commit,
    normalizar_documento,
    normalizar_tipo_documento,
)


def validar_dados_cadastro(dados):
    nome_barbearia = validar_nome_barbearia(
        dados.nome_barbearia
    )

    responsavel = normalizar_texto(
        dados.responsavel
    )

    if not responsavel:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "O nome do respons\u00e1vel "
                "\u00e9 obrigat\u00f3rio."
            ),
        )

    try:
        tipo_documento = (
            normalizar_tipo_documento(
                dados.tipo_documento
            )
        )

        documento = normalizar_documento(
            tipo_documento,
            dados.documento,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    email = normalizar_email(
        dados.email
    )

    if not email or "@" not in email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Informe um e-mail "
                "v\u00e1lido."
            ),
        )

    telefone_whatsapp = normalizar_texto(
        dados.telefone_whatsapp
    )

    if not telefone_whatsapp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "O telefone ou WhatsApp "
                "\u00e9 obrigat\u00f3rio."
            ),
        )

    endereco = str(
        dados.endereco
        or ""
    ).strip()

    if not endereco:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "O endere\u00e7o completo "
                "do estabelecimento "
                "\u00e9 obrigat\u00f3rio."
            ),
        )

    cep = "".join(
        caractere
        for caractere
        in str(
            dados.cep
            or ""
        )
        if caractere.isdigit()
    )

    if len(cep) != 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Informe um CEP "
                "v\u00e1lido com 8 d\u00edgitos."
            ),
        )

    cidade = normalizar_texto(
        dados.cidade
    )

    if not cidade:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "A cidade "
                "\u00e9 obrigat\u00f3ria."
            ),
        )

    estado = normalizar_texto(
        dados.estado
    ).upper()

    if len(estado) != 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Informe o estado usando "
                "duas letras, por exemplo: SP."
            ),
        )

    validar_senha(
        dados.senha
    )

    if (
        dados.senha
        != dados.confirmar_senha
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "A confirma\u00e7\u00e3o da senha "
                "n\u00e3o confere."
            ),
        )

    if not dados.aceite_termos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "\u00c9 necess\u00e1rio aceitar "
                "os termos para realizar "
                "o cadastro."
            ),
        )

    return {
        "nome_barbearia": nome_barbearia,
        "responsavel": responsavel,
        "tipo_documento": tipo_documento,
        "documento": documento,
        "email": email,
        "telefone_whatsapp": telefone_whatsapp,
        "endereco": endereco,
        "cep": cep,
        "cidade": cidade,
        "estado": estado,
    }


def criar_sequencias_iniciais(
    db: Session,
    barbearia_id: int,
):
    for tipo in PREFIXOS_CODIGO:
        sequencia = models.SequenciaBarbearia(
            barbearia_id=barbearia_id,
            tipo=tipo,
            ultimo_numero=0,
        )

        db.add(sequencia)

    db.flush()


def cadastrar_barbearia_service(
    db: Session,
    dados,
):
    dados_validados = validar_dados_cadastro(
        dados
    )

    # Evita duplicidade evidente de conta.
    # A regra de teste gratuito e separada:
    # documento/endereco podem impedir o beneficio
    # sem impedir a criacao da conta.
    duplicada = (
        db.query(models.Barbearia)
        .filter(
            models.Barbearia.email
            == dados_validados["email"],
            models.Barbearia.telefone_whatsapp
            == dados_validados[
                "telefone_whatsapp"
            ],
        )
        .first()
    )

    if duplicada is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "J\u00e1 existe uma barbearia "
                "cadastrada com este e-mail "
                "e WhatsApp. Utilize a "
                "recupera\u00e7\u00e3o de senha "
                "ou entre em contato "
                "com o suporte."
            ),
        )

    try:
        codigo = gerar_proximo_codigo(
            db
        )

        slug = gerar_slug_unico(
            db=db,
            nome=dados_validados[
                "nome_barbearia"
            ],
        )

        cnpj = None

        if (
            dados_validados[
                "tipo_documento"
            ]
            == "CNPJ"
        ):
            cnpj = dados_validados[
                "documento"
            ]

        barbearia = models.Barbearia(
            codigo=codigo,
            slug=slug,
            nome=dados_validados[
                "nome_barbearia"
            ],
            responsavel=dados_validados[
                "responsavel"
            ],
            email=dados_validados[
                "email"
            ],
            telefone=dados_validados[
                "telefone_whatsapp"
            ],
            telefone_whatsapp=(
                dados_validados[
                    "telefone_whatsapp"
                ]
            ),
            cnpj=cnpj,
            endereco=dados_validados[
                "endereco"
            ],
            cidade=dados_validados[
                "cidade"
            ],
            estado=dados_validados[
                "estado"
            ],
            cep=dados_validados[
                "cep"
            ],
            ativa=True,
        )

        db.add(
            barbearia
        )
        db.flush()

        administrador = models.Usuario(
            nome=dados_validados[
                "responsavel"
            ],
            email=dados_validados[
                "email"
            ],
            senha_hash=criar_hash_senha(
                dados.senha
            ),
            perfil="admin",
            barbeiro_id=None,
            barbearia_id=barbearia.id,
            ativo=True,
        )

        db.add(
            administrador
        )
        db.flush()

        criar_configuracao_padrao_por_barbearia(
            db=db,
            barbearia_id=barbearia.id,
            realizar_commit=False,
        )

        criar_sequencias_iniciais(
            db=db,
            barbearia_id=barbearia.id,
        )

        (
            teste_gratuito,
            resultado_teste,
        ) = criar_teste_gratuito_sem_commit(
            db,
            barbearia_id=barbearia.id,
            tipo_documento=(
                dados_validados[
                    "tipo_documento"
                ]
            ),
            documento=(
                dados_validados[
                    "documento"
                ]
            ),
            endereco=(
                dados_validados[
                    "endereco"
                ]
            ),
            cidade=(
                dados_validados[
                    "cidade"
                ]
            ),
            estado=(
                dados_validados[
                    "estado"
                ]
            ),
            cep=(
                dados_validados[
                    "cep"
                ]
            ),
            origem="CADASTRO_PUBLICO",
        )

        db.commit()

        db.refresh(
            barbearia
        )
        db.refresh(
            administrador
        )

        teste_concedido = (
            teste_gratuito
            is not None
        )

        if teste_concedido:
            codigo_teste = (
                "TESTE_GRATUITO_CONCEDIDO"
            )

            mensagem_teste = (
                "Teste gratuito de 40 dias "
                "iniciado. Nenhum plano, "
                "cart\u00e3o ou pagamento "
                "foi exigido."
            )

            data_inicio_teste = (
                teste_gratuito
                .data_inicio
                .isoformat()
            )

            data_fim_teste = (
                teste_gratuito
                .data_fim
                .isoformat()
            )

            mensagem = (
                "Cadastro realizado com "
                "sucesso! Seu per\u00edodo "
                "gratuito de 40 dias "
                "j\u00e1 come\u00e7ou."
            )

            proximo_passo = (
                "Fa\u00e7a login utilizando "
                "o slug, o e-mail e "
                "a senha cadastrada."
            )

        else:
            codigo_teste = (
                resultado_teste.codigo
            )

            mensagem_teste = (
                resultado_teste.mensagem
            )

            data_inicio_teste = None
            data_fim_teste = None

            mensagem = (
                "Cadastro realizado com "
                "sucesso. O per\u00edodo "
                "gratuito n\u00e3o foi "
                "liberado automaticamente."
            )

            if (
                resultado_teste.codigo
                == "ENDERECO_JA_UTILIZOU_TESTE"
            ):
                proximo_passo = (
                    "Fa\u00e7a login. "
                    "Se este for um novo "
                    "estabelecimento ou novo "
                    "propriet\u00e1rio no mesmo "
                    "endere\u00e7o, solicite "
                    "revis\u00e3o ao suporte."
                )

            else:
                proximo_passo = (
                    "Fa\u00e7a login e escolha "
                    "um plano para continuar "
                    "utilizando os recursos "
                    "comerciais."
                )

        return {
            "sucesso": True,
            "mensagem": mensagem,
            "barbearia": {
                "id": barbearia.id,
                "codigo": barbearia.codigo,
                "nome": barbearia.nome,
                "slug": barbearia.slug,
            },
            "administrador": {
                "email": administrador.email,
            },
            "login": {
                "slug": barbearia.slug,
                "email": administrador.email,
            },
            "teste_gratuito": {
                "concedido": teste_concedido,
                "codigo": codigo_teste,
                "mensagem": mensagem_teste,
                "data_inicio": (
                    data_inicio_teste
                ),
                "data_fim": (
                    data_fim_teste
                ),
            },
            "proximo_passo": (
                proximo_passo
            ),
        }

    except HTTPException:
        db.rollback()
        raise

    except RuntimeError as exc:
        db.rollback()

        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "N\u00e3o foi poss\u00edvel "
                "validar o per\u00edodo gratuito "
                "neste momento. Tente novamente "
                "em alguns minutos."
            ),
        ) from exc

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "N\u00e3o foi poss\u00edvel "
                "concluir o cadastro porque "
                "existe um registro conflitante."
            ),
        ) from exc

    except Exception:
        db.rollback()
        raise
