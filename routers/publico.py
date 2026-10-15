from math import asin, cos, radians, sin, sqrt

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
import models
from routers.agendamento_online import agendamento_online_habilitado


router = APIRouter(
    prefix="/publico",
    tags=["Publico"],
)


class BarbeariaPublicaProxima(BaseModel):
    slug: str
    nome: str
    distancia_km: float
    endereco: str | None = None
    cidade: str | None = None
    estado: str | None = None
    cep: str | None = None
    telefone_whatsapp: str | None = None
    instagram: str | None = None
    logo_url: str | None = None
    slogan: str | None = None
    imagem_capa_url: str | None = None
    permitir_agendamento_portal: bool


class BuscaBarbeariasProximasResponse(BaseModel):
    raio_km: float
    total: int
    barbearias: list[BarbeariaPublicaProxima]


class ServicoPublicoPerfil(BaseModel):
    nome: str
    preco: float
    tempo_medio_minutos: int


class BarbeariaPublicaPerfil(BaseModel):
    slug: str
    nome: str
    endereco: str | None = None
    cidade: str | None = None
    estado: str | None = None
    cep: str | None = None
    telefone_whatsapp: str | None = None
    instagram: str | None = None
    logo_url: str | None = None
    slogan: str | None = None
    imagem_capa_url: str | None = None
    permitir_agendamento_portal: bool
    servicos: list[ServicoPublicoPerfil]


def calcular_distancia_km(
    latitude_origem: float,
    longitude_origem: float,
    latitude_destino: float,
    longitude_destino: float,
) -> float:
    """Calcula a distância entre duas coordenadas usando Haversine."""

    raio_terra_km = 6371.0088

    lat1 = radians(latitude_origem)
    lon1 = radians(longitude_origem)
    lat2 = radians(latitude_destino)
    lon2 = radians(longitude_destino)

    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1

    haversine = (
        sin(delta_lat / 2) ** 2
        + cos(lat1)
        * cos(lat2)
        * sin(delta_lon / 2) ** 2
    )

    arco = 2 * asin(
        min(1.0, sqrt(haversine))
    )

    return raio_terra_km * arco


@router.get(
    "/barbearias/proximas",
    response_model=BuscaBarbeariasProximasResponse,
)
def listar_barbearias_proximas(
    latitude: float = Query(
        ...,
        ge=-90,
        le=90,
        description="Latitude atual do cliente.",
    ),
    longitude: float = Query(
        ...,
        ge=-180,
        le=180,
        description="Longitude atual do cliente.",
    ),
    raio_km: float = Query(
        5.0,
        gt=0,
        le=50,
        description="Raio máximo da busca em quilômetros.",
    ),
    limite: int = Query(
        50,
        ge=1,
        le=100,
        description="Quantidade máxima de resultados.",
    ),
    db: Session = Depends(get_db),
):
    candidatas = (
        db.query(models.Barbearia)
        .filter(
            models.Barbearia.ativa.is_(True),
            models.Barbearia.catalogo_publico_ativo.is_(True),
            models.Barbearia.latitude.isnot(None),
            models.Barbearia.longitude.isnot(None),
        )
        .all()
    )

    encontradas = []

    for barbearia in candidatas:
        distancia = calcular_distancia_km(
            latitude,
            longitude,
            float(barbearia.latitude),
            float(barbearia.longitude),
        )

        if distancia > raio_km:
            continue

        encontradas.append(
            BarbeariaPublicaProxima(
                slug=barbearia.slug,
                nome=barbearia.nome,
                distancia_km=round(distancia, 2),
                endereco=barbearia.endereco,
                cidade=barbearia.cidade,
                estado=barbearia.estado,
                cep=barbearia.cep,
                telefone_whatsapp=barbearia.telefone_whatsapp,
                instagram=barbearia.instagram,
                logo_url=barbearia.logo_url,
                slogan=barbearia.slogan,
                imagem_capa_url=barbearia.imagem_capa_url,
                permitir_agendamento_portal=(
                    agendamento_online_habilitado(
                        db,
                        barbearia.id,
                    )
                ),
            )
        )

    encontradas.sort(
        key=lambda item: (
            item.distancia_km,
            item.nome.lower(),
        )
    )

    barbearias = encontradas[:limite]

    return BuscaBarbeariasProximasResponse(
        raio_km=raio_km,
        total=len(barbearias),
        barbearias=barbearias,
    )


@router.get(
    "/barbearias/{slug}",
    response_model=BarbeariaPublicaPerfil,
)
def consultar_perfil_publico_barbearia(
    slug: str,
    db: Session = Depends(get_db),
):
    barbearia = (
        db.query(models.Barbearia)
        .filter(
            models.Barbearia.slug == slug,
            models.Barbearia.ativa.is_(True),
            models.Barbearia.catalogo_publico_ativo.is_(True),
        )
        .first()
    )

    if not barbearia:
        raise HTTPException(
            status_code=404,
            detail="Barbearia não encontrada.",
        )

    servicos = (
        db.query(models.Servico)
        .filter(
            models.Servico.barbearia_id == barbearia.id,
            models.Servico.ativo.is_(True),
        )
        .order_by(models.Servico.nome.asc())
        .all()
    )

    return BarbeariaPublicaPerfil(
        slug=barbearia.slug,
        nome=barbearia.nome,
        endereco=barbearia.endereco,
        cidade=barbearia.cidade,
        estado=barbearia.estado,
        cep=barbearia.cep,
        telefone_whatsapp=barbearia.telefone_whatsapp,
        instagram=barbearia.instagram,
        logo_url=barbearia.logo_url,
        slogan=barbearia.slogan,
        imagem_capa_url=barbearia.imagem_capa_url,
        permitir_agendamento_portal=agendamento_online_habilitado(
            db,
            barbearia.id,
        ),
        servicos=[
            ServicoPublicoPerfil(
                nome=servico.nome,
                preco=float(servico.preco or 0),
                tempo_medio_minutos=int(
                    servico.tempo_medio_minutos or 30
                ),
            )
            for servico in servicos
        ],
    )
