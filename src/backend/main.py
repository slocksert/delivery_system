from fastapi import FastAPI, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from .config import settings
from .api import rede, integracao, auth, websocket
from .dependencies import get_database
import os

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    debug=settings.debug,
)

# Configurar diretórios de templates e arquivos estáticos
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend")
print(f"Frontend directory path: {frontend_dir}")
print(f"Frontend directory exists: {os.path.exists(frontend_dir)}")

templates = Jinja2Templates(directory=os.path.join(frontend_dir, "templates"))

# Montar arquivos estáticos (criar diretório se não existir)
static_dir = os.path.join(frontend_dir, "static")
print(f"Static directory path: {static_dir}")
print(f"Static directory exists: {os.path.exists(static_dir)}")

if not os.path.exists(static_dir):
    print("Creating static directory...")
    os.makedirs(static_dir, exist_ok=True)
    # Criar subdiretórios básicos
    os.makedirs(os.path.join(static_dir, "css"), exist_ok=True)
    os.makedirs(os.path.join(static_dir, "js"), exist_ok=True)
    print("Static directory created successfully")

app.mount("/static", StaticFiles(directory=static_dir), name="static")

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
    allow_origins=["*"],
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

app.include_router(
    websocket.router,
    tags=["WebSocket - Rastreamento em Tempo Real"],
)

@app.get("/")
async def root():
    """Redireciona para a aplicação frontend ou retorna informações da API"""
    return RedirectResponse(url="/app")

@app.get("/api")
async def api_info():
    """Informações da API"""
    return {"message": "API de Rede de Entrega", "version": settings.version}

@app.get("/app")
async def frontend_app(request: Request):
    """Serve a aplicação frontend"""
    return templates.TemplateResponse("mapa.html", {"request": request})

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