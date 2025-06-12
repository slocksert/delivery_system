"""
Entidades principais do Sistema de Otimização de Rede de Entregas
Versão expandida com todas as entidades necessárias para o sistema completo
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class TipoVeiculo(Enum):
    MOTO = "moto"
    CARRO = "carro" 
    VAN = "van"
    CAMINHAO = "caminhao"


class StatusPedido(Enum):
    PENDENTE = "pendente"
    COLETADO = "coletado"
    EM_ROTA = "em_rota"
    ENTREGUE = "entregue"
    CANCELADO = "cancelado"


class PrioridadeCliente(Enum):
    URGENTE = 1
    ALTA = 2
    NORMAL = 3
    BAIXA = 4



@dataclass
class Deposito:
    """Depósito principal - origem dos produtos"""
    id: str
    latitude: float
    longitude: float
    nome: str = ""
    capacidade_maxima: int = 1000
    endereco: str = ""


@dataclass
class Hub:
    """Hub logístico - ponto intermediário de distribuição"""
    id: str
    latitude: float
    longitude: float
    capacidade: int
    nome: str = ""
    endereco: str = ""
    operacional: bool = True


@dataclass
class Cliente:
    """Cliente final - destino das entregas"""
    id: str
    latitude: float
    longitude: float
    demanda_media: int = 1  # Pedidos por dia
    prioridade: PrioridadeCliente = PrioridadeCliente.NORMAL
    endereco: str = ""
    zona_id: str = ""
    ativo: bool = True


@dataclass
class ZonaEntrega:
    """Zona de entrega - agrupamento de clientes por região"""
    id: str
    nome: str
    hubs: List[Hub] = field(default_factory=list)
    clientes: List[Cliente] = field(default_factory=list)
    demanda_total: int = 0
    area_cobertura: float = 0.0  # km²


@dataclass
class Veiculo:
    """Veículo de entrega"""
    id: str
    tipo: TipoVeiculo
    capacidade: int  # Número máximo de pedidos
    velocidade_media: float  # km/h
    hub_base: str
    disponivel: bool = True
    condutor: str = ""


@dataclass
class Pedido:
    """Pedido de entrega"""
    id: str
    cliente_id: str
    origem_hub: str = ""
    veiculo_id: str = ""
    timestamp_criacao: datetime = field(default_factory=datetime.now)
    timestamp_entrega: Optional[datetime] = None
    prioridade: PrioridadeCliente = PrioridadeCliente.NORMAL
    peso: float = 1.0  # kg
    volume: float = 1.0  # litros
    status: StatusPedido = StatusPedido.PENDENTE
    observacoes: str = ""


@dataclass
class Rota:
    """Rota entre dois pontos da rede"""
    origem: str
    destino: str
    peso: float  # Distância ou tempo
    capacidade: int  # Capacidade máxima (pedidos por hora)
    tipo_rota: str = "terrestre"  # terrestre, expressa, etc.
    tempo_medio: float = 0.0  # minutos
    custo: float = 0.0  # custo operacional
    ativa: bool = True


@dataclass
class RedeEntrega:
    """Classe que representa toda a rede de entregas como um grafo"""
    depositos: List[Deposito] = field(default_factory=list)
    hubs: List[Hub] = field(default_factory=list)
    clientes: List[Cliente] = field(default_factory=list)
    zonas: List[ZonaEntrega] = field(default_factory=list)
    veiculos: List[Veiculo] = field(default_factory=list)
    rotas: List[Rota] = field(default_factory=list)
    pedidos: List[Pedido] = field(default_factory=list)
    
    def obter_vertices(self) -> List[str]:
        """Retorna todos os vértices da rede"""
        vertices = []
        vertices.extend([d.id for d in self.depositos])
        vertices.extend([h.id for h in self.hubs])
        vertices.extend([c.id for c in self.clientes])
        vertices.extend([z.id for z in self.zonas])
        return vertices
    
    def obter_capacidade_rota(self, origem: str, destino: str) -> int:
        """Retorna a capacidade de uma rota específica"""
        for rota in self.rotas:
            if rota.origem == origem and rota.destino == destino and rota.ativa:
                return rota.capacidade
        return 0
    
    def obter_clientes_zona(self, zona_id: str) -> List[Cliente]:
        """Retorna todos os clientes de uma zona específica"""
        return [c for c in self.clientes if c.zona_id == zona_id and c.ativo]
    
    def obter_demanda_total(self) -> int:
        """Calcula a demanda total da rede"""
        return sum(c.demanda_media for c in self.clientes if c.ativo)
    
    def obter_capacidade_total(self) -> int:
        """Calcula a capacidade total da rede"""
        return sum(h.capacidade for h in self.hubs if h.operacional)
    
    def obter_pedidos_pendentes(self) -> List[Pedido]:
        """Retorna pedidos pendentes"""
        return [p for p in self.pedidos if p.status == StatusPedido.PENDENTE]
    
    def obter_veiculos_disponiveis(self, hub_id: Optional[str] = None) -> List[Veiculo]:
        """Retorna veículos disponíveis, opcionalmente de um hub específico"""
        veiculos = [v for v in self.veiculos if v.disponivel]
        if hub_id:
            veiculos = [v for v in veiculos if v.hub_base == hub_id]
        return veiculos
    
    def adicionar_cliente(self, cliente: Cliente) -> None:
        """Adiciona um cliente à rede"""
        if cliente.id not in [c.id for c in self.clientes]:
            self.clientes.append(cliente)
            
            # Atualizar zona correspondente
            for zona in self.zonas:
                if zona.id == cliente.zona_id:
                    zona.clientes.append(cliente)
                    zona.demanda_total += cliente.demanda_media
                    break
    
    def adicionar_pedido(self, pedido: Pedido) -> None:
        """Adiciona um pedido à rede"""
        if pedido.id not in [p.id for p in self.pedidos]:
            self.pedidos.append(pedido)
    
    def obter_estatisticas(self) -> Dict[str, Any]:
        """Retorna estatísticas da rede"""
        return {
            'total_depositos': len(self.depositos),
            'total_hubs': len([h for h in self.hubs if h.operacional]),
            'total_clientes': len([c for c in self.clientes if c.ativo]),
            'total_zonas': len(self.zonas),
            'total_veiculos': len([v for v in self.veiculos if v.disponivel]),
            'total_rotas': len([r for r in self.rotas if r.ativa]),
            'total_pedidos_pendentes': len(self.obter_pedidos_pendentes()),
            'demanda_total': self.obter_demanda_total(),
            'capacidade_total': self.obter_capacidade_total(),
            'taxa_utilizacao': (self.obter_demanda_total() / max(1, self.obter_capacidade_total())) * 100
        }


# Classes auxiliares para análise e otimização

@dataclass
class FluxoRota:
    """Representa o fluxo atual em uma rota"""
    rota_id: str
    origem: str
    destino: str
    fluxo_atual: int
    capacidade_maxima: int
    utilizacao: float = field(init=False)
    
    def __post_init__(self):
        self.utilizacao = (self.fluxo_atual / max(1, self.capacidade_maxima)) * 100


@dataclass
class CenarioSimulacao:
    """Cenário para simulação"""
    id: str
    nome: str
    descricao: str
    parametros: Dict[str, Any] = field(default_factory=dict)
    timestamp_criacao: datetime = field(default_factory=datetime.now)


@dataclass
class ResultadoOtimizacao:
    """Resultado de um algoritmo de otimização"""
    algoritmo: str
    fluxo_maximo: int
    caminho_otimo: List[str]
    tempo_execucao: float
    iteracoes: int = 0
    convergiu: bool = True
    detalhes: Dict[str, Any] = field(default_factory=dict)
