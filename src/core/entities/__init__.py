"""
Módulo de entidades - Exporta todas as classes principais
"""

from .models import (
    # Enums
    TipoVeiculo, StatusPedido, PrioridadeCliente,
    # Entidades principais
    Deposito, Hub, Cliente, ZonaEntrega, Veiculo, Pedido, Rota, RedeEntrega,
    # Classes auxiliares
    FluxoRota, CenarioSimulacao, ResultadoOtimizacao
)

__all__ = [
    # Enums
    'TipoVeiculo', 'StatusPedido', 'PrioridadeCliente',
    # Entidades principais
    'Deposito', 'Hub', 'Cliente', 'ZonaEntrega', 'Veiculo', 'Pedido', 'Rota', 'RedeEntrega',
    # Classes auxiliares
    'FluxoRota', 'CenarioSimulacao', 'ResultadoOtimizacao'
]
