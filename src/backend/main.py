from fastapi import FastAPI, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .config import settings
from .api import rede, integracao, auth
from .dependencies import get_database

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    debug=settings.debug,
)

@app.on_event("startup")
async def startup_event():
    """Inicializa o banco de dados de produção na startup da API"""
    try:
        # Força a criação do banco de produção
        db = get_database()
        print(f"✓ Banco de dados de produção inicializado: {db.db_path}")
    except Exception as e:
        print(f"❌ Erro ao inicializar banco de dados: {e}")
        raise

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    rede.router,
    prefix="/api/v1",
    tags=["Rede de Entrega"],
)

app.include_router(
    integracao.router,
    prefix="/api/v1",
    tags=["Integração"],
)

app.include_router(
    auth.router,
    prefix="/api/v1",
    tags=["Autenticação"],
)

@app.get("/")
async def root():
    return {"message": "API de Rede de Entrega", "version": settings.version}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": "2024-01-01T00:00:00Z",
        "services": {
            "api": "operational",
            "rede_service": "operational",
            "core_integration": "operational"
        }
    }

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "Ocorreu um erro interno no servidor",
            "detail": str(exc) if settings.debug else "Erro interno"
        }
    )