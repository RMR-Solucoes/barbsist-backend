from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models

from auth.permissions import superadmin
from database import get_db
from schemas import (
    AssinaturaSaaSResponse,
    AssinaturaSaaSAuditoriaResponse,
    BloquearAssinaturaSaaSRequest,
    CadastroTesteGratuitoResponse,
    ConcederExcecaoTesteGratuitoSaaSRequest,
    ConcederTesteSaaSRequest,
    LiberarAssinaturaSaaSRequest,
    PagamentoSaaSResponse,
    PlanoSaaSCreate,
    PlanoSaaSResponse,
    PlanoSaaSUpdate,
)
from services.assinatura_saas_service import (
    atualizar_plano_saas_service,
    bloquear_assinatura_service,
    conceder_teste_saas_service,
    criar_plano_saas_service,
    liberar_assinatura_manual_service,
    listar_assinaturas_admin_service,
    listar_auditoria_assinaturas_saas_service,
    listar_pagamentos_admin_service,
    listar_planos_saas_service,
    status_mercado_pago_barbsist_service,
)

from services.teste_gratuito_saas_service import (
    criar_teste_gratuito_sem_commit,
    normalizar_documento,
    normalizar_tipo_documento,
)

router = APIRouter(prefix="/admin/barbsist-assinaturas", tags=["Admin - BarbSist Assinaturas"])

@router.get("/planos", response_model=list[PlanoSaaSResponse])
def planos(db: Session = Depends(get_db), usuario_logado=Depends(superadmin)):
    return listar_planos_saas_service(db, incluir_inativos=True)

@router.post("/planos", response_model=PlanoSaaSResponse)
def criar_plano(dados: PlanoSaaSCreate, db: Session = Depends(get_db), usuario_logado=Depends(superadmin)):
    return criar_plano_saas_service(db, dados)

@router.put("/planos/{plano_id}", response_model=PlanoSaaSResponse)
def atualizar_plano(plano_id: int, dados: PlanoSaaSUpdate, db: Session = Depends(get_db), usuario_logado=Depends(superadmin)):
    return atualizar_plano_saas_service(db, plano_id, dados)

@router.get("/assinaturas", response_model=list[AssinaturaSaaSResponse])
def assinaturas(db: Session = Depends(get_db), usuario_logado=Depends(superadmin)):
    return listar_assinaturas_admin_service(db)


@router.post(
    "/barbearias/{barbearia_id}/teste",
    response_model=AssinaturaSaaSResponse,
)
def conceder_teste(
    barbearia_id: int,
    dados: ConcederTesteSaaSRequest,
    db: Session = Depends(get_db),
    usuario_logado=Depends(superadmin),
):
    return conceder_teste_saas_service(
        db, barbearia_id, dados, usuario_logado
    )

# Novo modelo de teste gratuito:
# separado de AssinaturaSaaS e sem plano.
@router.post(
    "/barbearias/{barbearia_id}/teste-gratuito/excecao",
    response_model=CadastroTesteGratuitoResponse,
)
def conceder_excecao_teste_gratuito(
    barbearia_id: int,
    dados: ConcederExcecaoTesteGratuitoSaaSRequest,
    db: Session = Depends(get_db),
    usuario_logado=Depends(superadmin),
):
    try:
        barbearia = (
            db.query(models.Barbearia)
            .filter(
                models.Barbearia.id
                == int(barbearia_id)
            )
            .with_for_update()
            .first()
        )

        if barbearia is None:
            raise HTTPException(
                status_code=404,
                detail="Barbearia n\u00e3o encontrada.",
            )

        tipo_documento = (
            normalizar_tipo_documento(
                dados.tipo_documento
            )
        )

        documento = normalizar_documento(
            tipo_documento,
            dados.documento,
        )

        cnpj_cadastrado = str(
            barbearia.cnpj or ""
        ).strip()

        if cnpj_cadastrado:
            if tipo_documento != "CNPJ":
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Esta barbearia possui CNPJ "
                        "cadastrado. A exce\u00e7\u00e3o deve "
                        "utilizar o CNPJ."
                    ),
                )

            cnpj_normalizado = (
                normalizar_documento(
                    "CNPJ",
                    cnpj_cadastrado,
                )
            )

            if documento != cnpj_normalizado:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "O CNPJ informado n\u00e3o "
                        "corresponde ao CNPJ "
                        "cadastrado da barbearia."
                    ),
                )

        elif tipo_documento != "CPF":
            raise HTTPException(
                status_code=400,
                detail=(
                    "Barbearia sem CNPJ deve "
                    "utilizar o CPF do respons\u00e1vel."
                ),
            )

        endereco = str(
            barbearia.endereco or ""
        ).strip()

        cidade = str(
            barbearia.cidade or ""
        ).strip()

        estado = str(
            barbearia.estado or ""
        ).strip()

        cep = str(
            barbearia.cep or ""
        ).strip()

        if not all(
            (
                endereco,
                cidade,
                estado,
                cep,
            )
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Complete endere\u00e7o, CEP, "
                    "cidade e estado da barbearia "
                    "antes de conceder a exce\u00e7\u00e3o."
                ),
            )

        teste, resultado = (
            criar_teste_gratuito_sem_commit(
                db,
                barbearia_id=barbearia.id,
                tipo_documento=tipo_documento,
                documento=documento,
                endereco=endereco,
                cidade=cidade,
                estado=estado,
                cep=cep,
                autorizar_excecao=True,
                motivo_liberacao=dados.motivo,
                autorizado_por_usuario_id=(
                    usuario_logado.id
                ),
                origem="SUPERADMIN_EXCECAO",
            )
        )

        if teste is None:
            raise HTTPException(
                status_code=409,
                detail={
                    "codigo": resultado.codigo,
                    "mensagem": resultado.mensagem,
                },
            )

        db.commit()
        db.refresh(teste)

        return {
            "concedido": True,
            "codigo": (
                "EXCECAO_TESTE_GRATUITO_CONCEDIDA"
            ),
            "mensagem": (
                "Teste gratuito concedido por "
                "exce\u00e7\u00e3o administrativa."
            ),
            "data_inicio": (
                teste.data_inicio.isoformat()
                if teste.data_inicio
                else None
            ),
            "data_fim": (
                teste.data_fim.isoformat()
                if teste.data_fim
                else None
            ),
        }

    except HTTPException:
        db.rollback()
        raise

    except ValueError as exc:
        db.rollback()

        detalhe = str(exc)

        codigo = (
            409
            if "ja possui" in detalhe.lower()
            else 400
        )

        raise HTTPException(
            status_code=codigo,
            detail=detalhe,
        ) from exc

    except RuntimeError as exc:
        db.rollback()

        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail=(
                "N\u00e3o foi poss\u00edvel conceder o "
                "teste porque existe um registro "
                "antifraude conflitante."
            ),
        ) from exc


@router.get("/pagamentos", response_model=list[PagamentoSaaSResponse])
def pagamentos(db: Session = Depends(get_db), usuario_logado=Depends(superadmin)):
    return listar_pagamentos_admin_service(db)

@router.put("/assinaturas/{assinatura_id}/liberar", response_model=AssinaturaSaaSResponse)
def liberar(assinatura_id: int, dados: LiberarAssinaturaSaaSRequest, db: Session = Depends(get_db), usuario_logado=Depends(superadmin)):
    return liberar_assinatura_manual_service(db, assinatura_id, dados, usuario_logado)

@router.put("/assinaturas/{assinatura_id}/bloquear", response_model=AssinaturaSaaSResponse)
def bloquear(assinatura_id: int, dados: BloquearAssinaturaSaaSRequest, db: Session = Depends(get_db), usuario_logado=Depends(superadmin)):
    return bloquear_assinatura_service(db, assinatura_id, dados, usuario_logado)


@router.get("/mercado-pago/status")
def mercado_pago_status(request: Request, usuario_logado=Depends(superadmin)):
    return status_mercado_pago_barbsist_service(str(request.base_url).rstrip("/"))


@router.get(
    "/auditoria",
    response_model=list[AssinaturaSaaSAuditoriaResponse],
)
def auditoria_assinaturas(
    assinatura_id: int | None = None,
    db: Session = Depends(get_db),
    usuario_logado=Depends(superadmin),
):
    return listar_auditoria_assinaturas_saas_service(
        db,
        assinatura_id=assinatura_id,
    )
