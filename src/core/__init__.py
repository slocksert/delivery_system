"""
Módulo Core - Funcionalidades principais do sistema
Sistema de Otimização de Rede de Entregas
"""

# Entidades principais
from .entities import (
    # Enums
    TipoVeiculo, StatusPedido, PrioridadeCliente,
    # Entidades
    Deposito, Hub, Cliente, ZonaEntrega, Veiculo, Pedido, Rota, RedeEntrega,
    # Classes auxiliares
    FluxoRota, CenarioSimulacao, ResultadoOtimizacao
)

# Manipulação de dados
from .data.loader import (
    carregar_rede_completa,
    validar_rede_completa,
    construir_grafo_networkx_completo,
    exportar_para_diversos_formatos
)

# Geradores
from .generators.gerador_completo import (
    GeradorMaceioCompleto,
    gerar_rede_maceio_completa
)

__version__ = "2.0.0"
__author__ = "Sistema de Otimização de Rede de Entregas"

__all__ = [
    # Enums
    'TipoVeiculo', 'StatusPedido', 'PrioridadeCliente',
    
    # Entidades principais
    'Deposito', 'Hub', 'Cliente', 'ZonaEntrega', 'Veiculo', 'Pedido', 'Rota', 'RedeEntrega',
    
    # Classes auxiliares
    'FluxoRota', 'CenarioSimulacao', 'ResultadoOtimizacao',
    
    # Funções de dados
    'carregar_rede_completa', 'validar_rede_completa',
    'construir_grafo_networkx_completo', 'exportar_para_diversos_formatos',
    
    # Geradores
    'GeradorMaceioCompleto', 'gerar_rede_maceio_completa'
]
