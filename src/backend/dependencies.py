from fastapi import HTTPException

from core.generators.gerador_completo import GeradorMaceioCompleto
from .services.rede_service import RedeService
from .database.sqlite import SQLiteDB

_rede_service_instance = None
_db_instance = None

def get_gerador_dados() -> GeradorMaceioCompleto:
    return GeradorMaceioCompleto()

def get_database():
    """Retorna instância do banco de dados de produção"""
    global _db_instance
    if _db_instance is None:
        _db_instance = SQLiteDB.create_production_instance()
    return _db_instance

def get_test_database():
    """Cria uma nova instância do banco de dados de teste"""
    return SQLiteDB.create_test_instance()

def override_database_for_testing(test_db: SQLiteDB):
    """Substitui temporariamente o banco de produção pelo de teste"""
    global _db_instance
    _db_instance = test_db

def reset_database():
    """Reseta a instância do banco para forçar recriação"""
    global _db_instance
    _db_instance = None

def get_rede_service():
    global _rede_service_instance
    if _rede_service_instance is None:
        _rede_service_instance = RedeService()
    return _rede_service_instance

def validar_node_id(origem: str, destino: str):
    if origem == destino:
        raise HTTPException(
            status_code=400,
            detail="Origem e destino não podem ser iguais."
        )
    return origem, destino