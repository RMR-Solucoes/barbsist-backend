from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime
from routers import usuarios

from routers import (
    barbearia,
    clientes,
    barbeiros,
    servicos,
    produtos,
    comandas,
    caixa,
    comissoes,
    auth,
    estilos,
    agendamentos,
    planos,
    configuracao_funcionamento_router,
    barbeiro_disponibilidade_router,
    agendamento_online,
    contas_receber,
    contas_pagar,
    auth

)

from database import Base, engine, get_db
import models

from schemas import (
    RegistrarPagamentoPlanoRequest,

    ClienteCreate,
    ClienteResponse,

    BarbeiroCreate,
    BarbeiroResponse,

    ServicoCreate,
    ServicoResponse,

    ProdutoCreate,
    ProdutoResponse,

    ComandaCreate,
    ComandaResponse,

    AdicionarServicoComanda,
    AdicionarProdutoComanda,
    ItemComandaResponse,
    FecharComanda,
    CaixaResponse,
    ComissaoResponse
)


Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Sistema Barbearia",
    description="Backend inicial do sistema de gestão para barbearia",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://barbsist-frontend.vercel.app",
        "https://barbsist-frontend-dkpauelg2-aulaipros-projects.vercel.app",
    ],
    allow_origin_regex=(
        r"https://barbsist-frontend-[a-z0-9-]+"
        r"-aulaipros-projects\.vercel\.app"
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {
        "sistema": "Sistema Barbearia",
        "status": "online",
        "fase": "Fase 1 - Backend inicial"
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "mensagem": "API funcionando corretamente"
    }


app.include_router(clientes.router)
app.include_router(barbeiros.router)
app.include_router(servicos.router)
app.include_router(produtos.router)
app.include_router(comandas.router)
app.include_router(caixa.router)
app.include_router(comissoes.router)
app.include_router(auth.router)
app.include_router(estilos.router)
app.include_router(agendamentos.router)
app.include_router(planos.router)
app.include_router(configuracao_funcionamento_router.router)
app.include_router(barbeiro_disponibilidade_router.router)
app.include_router(agendamento_online.router)
app.include_router(barbearia.router)
app.include_router(contas_receber.router)
app.include_router(contas_pagar.router)
app.include_router(auth.router)
app.include_router(usuarios.router)
