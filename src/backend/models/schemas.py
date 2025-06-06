from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class NodeBase(BaseModel):
    id: str = Field(..., description="ID único do nó")
    nome: str = Field(..., description="Nome do nó")
    tipo: str = Field(..., description="Tipo: deposito, hub, zona")
    latitude: float = Field(..., description="Latitude do nó")
    longitude: float = Field(..., description="Longitude do nó")

class EdgeBase(BaseModel):
    origem: str = Field(..., description="Ponto de origem")
    destino: str = Field(..., description="Destino final")
    capacidade: int = Field(..., description="Capacidade da via")
    distancia: Optional[float] = Field(None, description="Distância em km")

class NetworkCreate(BaseModel):
    nome: str = Field(..., description="Nome da rede")
    descricao: Optional[str] = None 
    nodes: List[NodeBase]
    edges: List[EdgeBase]
    
class PrepareFluxRequest(BaseModel):
    rede_id: Optional[str] = None
    origem: str = Field(..., description="Ponto de origem")
    destino: str = Field(..., description="Destino final")

class NetworkResponse(BaseModel):
    id: str
    nome: str
    descricao: Optional[str]
    total_nodes: int
    total_edges: int
    created_at: datetime

class StatusResponse(BaseModel):
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None

class NetworkInfoResponse(BaseModel):
    nome: str
    total_nodes: int
    total_edges: int
    nodes_tipo: Dict[str, int]
    capacidade_total: int
    nodes: List[Dict[str, str]]