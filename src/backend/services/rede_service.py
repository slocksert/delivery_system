import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from core.entities.models import RedeEntrega, Deposito, Hub, ZonaEntrega, Rota, Cliente, PrioridadeCliente, Veiculo, TipoVeiculo, FluxoRota, ResultadoOtimizacao
from core.generators.gerador_completo import GeradorMaceioCompleto
from core.data.loader import construir_grafo_networkx_completo
from core.algorithms.flow_algorithms import calculate_network_flow, FlowResult
from typing import List, Dict, Any, Optional, Tuple, Union
import time
import math
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict
try:
    import osmnx as ox
    import networkx as nx
    OSMNX_AVAILABLE = True
except ImportError:
    ox = None
    nx = None
    OSMNX_AVAILABLE = False
    print("OSMNX não disponível - funcionalidades de rota real limitadas")

from ..database.sqlite import SQLiteDB
import asyncio

async def broadcast_log(msg: str):
    print(msg)

# Função utilitária para timestamps brasileiros
def get_brazilian_timestamp() -> datetime:
    """Retorna timestamp atual no fuso horário brasileiro (UTC-3)"""
    # Criar timezone brasileiro (UTC-3)
    brazilian_tz = timezone(timedelta(hours=-3))
    return datetime.now(brazilian_tz)

# Estruturas de dados para WebSocket e rastreamento
@dataclass
class VehiclePosition:
    """Posição atual de um veículo"""
    vehicle_id: str
    latitude: float
    longitude: float
    timestamp: datetime
    speed: float = 0.0  # km/h
    heading: float = 0.0  # graus (0-360)
    status: str = "idle"  # idle, moving, delivering, returning

@dataclass
class RouteWaypoint:
    """Waypoint individual de uma rota"""
    latitude: float
    longitude: float
    sequence: int
    estimated_time: float = 0.0  # minutos desde início da rota
    is_stop: bool = False  # True se é parada (cliente, hub, etc.)
    stop_id: Optional[str] = None  # ID do nó se for parada

@dataclass  
class DetailedRoute:
    """Rota detalhada com waypoints para rastreamento"""
    route_id: str
    origin_id: str
    destination_id: str
    waypoints: List[RouteWaypoint]
    total_distance: float  # km
    estimated_duration: float  # minutos
    traffic_factor: float = 1.0  # multiplicador de tráfego
    optimized: bool = False

class RedeService:
    def __init__(self, db: Optional[SQLiteDB] = None) -> None:
        if db is not None:
            self.db = db
        else:
            # Lazy import to avoid circular dependency
            from ..dependencies import get_database
            self.db = get_database()
        self.redes_cache: Dict[str, RedeEntrega] = {}
        self.metadata_cache: Dict[str, Dict[str, Any]] = {}
        
        # Cache para rastreamento de veículos e rotas detalhadas
        self.vehicle_positions: Dict[str, VehiclePosition] = {}
        self.detailed_routes: Dict[str, DetailedRoute] = {}
        self.real_network_graph = None
        self._real_network_loaded = False  # Flag para controlar se a rede real foi carregada
        
        # Inicializar serviço de movimento de veículos
        try:
            from .vehicle_movement_service import VehicleMovementService
            self.movement_service = VehicleMovementService(self)
        except ImportError:
            print("⚠️ VehicleMovementService não disponível")
            self.movement_service = None
        
        self._carregar_redes_do_banco()
        # Remover inicialização automática da rede real
        # self._inicializar_rede_real()

    def _inicializar_rede_real(self):
        """Inicializa o grafo real de Maceió para cálculos de rota"""
        if self._real_network_loaded or not OSMNX_AVAILABLE or ox is None:
            return
            
        try:
            print("Carregando rede real de Maceió para suporte a WebSocket...")
            lugar = "Maceió, Alagoas, Brazil"
            self.real_network_graph = ox.graph_from_place(
                lugar, 
                network_type='drive',
                simplify=True
            )
            self.real_network_graph = ox.add_edge_speeds(self.real_network_graph)
            self.real_network_graph = ox.add_edge_travel_times(self.real_network_graph)
            print(f"Rede real carregada: {len(self.real_network_graph.nodes)} nós, {len(self.real_network_graph.edges)} arestas")
            self._real_network_loaded = True
        except Exception as e:
            print(f"Erro ao carregar rede real: {e}")
            self.real_network_graph = None
    
    def _garantir_rede_real_carregada(self):
        """Garante que a rede real esteja carregada apenas quando necessário"""
        if not self._real_network_loaded:
            self._inicializar_rede_real()

    def _carregar_redes_do_banco(self):
        redes_list = self.db.listar_redes()
        for rede_data in redes_list:
            rede_id = rede_data["id"]
            rede = self._from_dict(rede_data)
            self.redes_cache[rede_id] = rede
            self.metadata_cache[rede_id] = {
                "nome": rede_data.get("nome", ""),
                "descricao": rede_data.get("descricao", ""),
                "created_at": rede_data.get("created_at")
            }

    def _from_dict(self, data: Dict[str, Any]) -> RedeEntrega:
        rede = RedeEntrega()
        for node in data.get("nodes", []):
            if node["tipo"] == "deposito":
                rede.depositos.append(Deposito(
                    id=node["id"],
                    latitude=node["latitude"],
                    longitude=node["longitude"],
                    nome=node["nome"],
                    capacidade_maxima=node.get("capacidade_maxima", 1000)
                ))
            elif node["tipo"] == "hub":
                rede.hubs.append(Hub(
                    id=node["id"],
                    latitude=node["latitude"],
                    longitude=node["longitude"],
                    capacidade=node.get("capacidade", 100),
                    nome=node["nome"],
                    endereco=node.get("endereco", '')
                ))
            elif node["tipo"] == "zona":
                rede.zonas.append(ZonaEntrega(
                    id=node["id"],
                    nome=node["nome"]
                ))
            elif node["tipo"] == "cliente":
                # Converter prioridade de volta para enum
                prioridade_valor = node.get("prioridade", 2)  # Default: NORMAL
                try:
                    # Se for string ou int, tenta converter
                    if isinstance(prioridade_valor, str) and prioridade_valor.isdigit():
                        prioridade_valor = int(prioridade_valor)
                    prioridade = PrioridadeCliente(prioridade_valor)
                except (ValueError, TypeError):
                    prioridade = PrioridadeCliente.NORMAL
                
                rede.clientes.append(Cliente(
                    id=node["id"],
                    latitude=node["latitude"],
                    longitude=node["longitude"],
                    demanda_media=node.get("demanda_media", 1),
                    prioridade=prioridade,
                    endereco=node.get("endereco", ""),
                    zona_id=node.get("zona_id", "")
                ))
            elif node["tipo"] == "veiculo":
                # Converter tipo de veículo de volta para enum
                tipo_veiculo_valor = node.get("tipo_veiculo", "MOTO")
                try:
                    if isinstance(tipo_veiculo_valor, str):
                        tipo_veiculo = TipoVeiculo[tipo_veiculo_valor]
                    else:
                        tipo_veiculo = TipoVeiculo(tipo_veiculo_valor)
                except (ValueError, KeyError):
                    tipo_veiculo = TipoVeiculo.MOTO
                
                rede.veiculos.append(Veiculo(
                    id=node["id"],
                    tipo=tipo_veiculo,
                    capacidade=node.get("capacidade", 5),
                    velocidade_media=node.get("velocidade_media", 25),
                    hub_base=node.get("hub_base", ""),
                    condutor=node.get("condutor", "")
                ))
        for edge in data.get("edges", []):
            origem = edge.get("origem", edge.get("source"))
            destino = edge.get("destino", edge.get("target"))
            if origem is None or destino is None:
                continue  # Ignora arestas inválidas
            rede.rotas.append(Rota(
                origem=origem,
                destino=destino,
                peso=edge.get("peso", edge.get("distancia", 1.0)),
                capacidade=edge.get("capacidade", edge.get("capacity", 1))
            ))
        return rede
    def bloquear_rota(self, rede_id: str, origem_id: str, destino_id: str) -> bool:
        """Simula o bloqueio de uma rota (aresta) entre dois nós."""
        if rede_id not in self.redes_cache:
            return False
        rede = self.redes_cache[rede_id]
        rotas_antes = len(rede.rotas)
        # Marca a rota como inativa, se o modelo tiver atributo 'ativa'
        for rota in rede.rotas:
            if rota.origem == origem_id and rota.destino == destino_id:
                if hasattr(rota, 'ativa'):
                    rota.ativa = False
                else:
                    # Se não houver atributo, remove a rota
                    rede.rotas = [r for r in rede.rotas if not (r.origem == origem_id and r.destino == destino_id)]
                break
        rotas_depois = len(rede.rotas)
        print(f"Bloqueio de rota: {origem_id} -> {destino_id} ({rotas_antes} → {rotas_depois})")
        return True

    def desbloquear_rota(self, rede_id: str, origem_id: str, destino_id: str, peso: float = 1.0, capacidade: int = 1) -> bool:
        """Desbloqueia (adiciona) uma rota entre dois nós."""
        if rede_id not in self.redes_cache:
            return False
        rede = self.redes_cache[rede_id]
        if any(r.origem == origem_id and r.destino == destino_id for r in rede.rotas):
            # Se a rota existe e tem atributo 'ativa', reativa
            for r in rede.rotas:
                if r.origem == origem_id and r.destino == destino_id and hasattr(r, 'ativa'):
                    r.ativa = True
                    return True
            return False  # Já existe
        rede.rotas.append(Rota(origem=origem_id, destino=destino_id, peso=peso, capacidade=capacidade))
        print(f"Rota desbloqueada: {origem_id} -> {destino_id}")
        return True

    def aumentar_demanda_zona(self, rede_id: str, zona_id: str, fator: float = 2.0) -> int:
        """Aumenta a demanda de todos os clientes de uma zona."""
        if rede_id not in self.redes_cache:
            return 0
        rede = self.redes_cache[rede_id]
        clientes_afetados = 0
        for cliente in rede.clientes:
            if getattr(cliente, "zona_id", None) == zona_id:
                cliente.demanda_media = getattr(cliente, "demanda_media", 1) * fator
                clientes_afetados += 1
        print(f"Demanda aumentada em {clientes_afetados} clientes da zona {zona_id}")
        return clientes_afetados

    def criar_rede_schema(self, data: Dict[str, Any]) -> str:
        rede = RedeEntrega()
        
        for node_data in data['nodes']:
            if node_data['tipo'] == 'deposito':
                deposito = Deposito(
                    id=node_data['id'],
                    latitude=node_data['latitude'],
                    longitude=node_data['longitude'],
                    nome=node_data['nome'],
                    capacidade_maxima=node_data.get('capacidade_maxima', 1000)
                )
                rede.depositos.append(deposito)
                
            elif node_data['tipo'] == 'hub':
                hub = Hub(
                    id=node_data['id'],
                    latitude=node_data['latitude'],
                    longitude=node_data['longitude'],
                    capacidade=node_data.get('capacidade', 100),
                    nome=node_data['nome'],
                    endereco=node_data.get('endereco', '')
                )
                rede.hubs.append(hub)
                
            elif node_data['tipo'] == 'zona':
                zona = ZonaEntrega(
                    id=node_data['id'],
                    nome=node_data['nome']
                )
                rede.zonas.append(zona)
                
            elif node_data['tipo'] == 'cliente':
                # Converter prioridade de volta para enum
                prioridade_valor = node_data.get("prioridade", 2)  # Default: NORMAL
                try:
                    # Se for string ou int, tenta converter
                    if isinstance(prioridade_valor, str) and prioridade_valor.isdigit():
                        prioridade_valor = int(prioridade_valor)
                    prioridade = PrioridadeCliente(prioridade_valor)
                except (ValueError, TypeError):
                    prioridade = PrioridadeCliente.NORMAL
                
                cliente = Cliente(
                    id=node_data['id'],
                    latitude=node_data['latitude'],
                    longitude=node_data['longitude'],
                    demanda_media=node_data.get('demanda_media', 1),
                    prioridade=prioridade,
                    endereco=node_data.get('endereco', ''),
                    zona_id=node_data.get('zona_id', '')
                )
                rede.clientes.append(cliente)
                
            elif node_data['tipo'] == 'veiculo':
                # Converter tipo de veículo de volta para enum
                tipo_veiculo_valor = node_data.get("tipo_veiculo", "MOTO")
                try:
                    if isinstance(tipo_veiculo_valor, str):
                        tipo_veiculo = TipoVeiculo[tipo_veiculo_valor]
                    else:
                        tipo_veiculo = TipoVeiculo(tipo_veiculo_valor)
                except (ValueError, KeyError):
                    tipo_veiculo = TipoVeiculo.MOTO
                
                veiculo = Veiculo(
                    id=node_data['id'],
                    tipo=tipo_veiculo,
                    capacidade=node_data.get('capacidade', 5),
                    velocidade_media=node_data.get('velocidade_media', 25),
                    hub_base=node_data.get('hub_base', ''),
                    condutor=node_data.get('condutor', '')
                )
                rede.veiculos.append(veiculo)
        
        edges_data = data.get('edges', data.get('edge', []))
        for edge_data in edges_data:
            rota = Rota(
                origem=edge_data['origem'],
                destino=edge_data['destino'],
                peso=edge_data.get('peso', edge_data.get('distancia', 1.0)),
                capacidade=edge_data['capacidade']
            )
            rede.rotas.append(rota)
        
        rede_id = f"rede_{int(time.time() * 1000)}"
        self.redes_cache[rede_id] = rede
        
        self.db.salvar_rede(
            rede_id,
            data.get("nome", ""),
            data.get("descricao", ""),
            data
        )
        
        redes_db = self.db.listar_redes()
        rede_db_data = next((r for r in redes_db if r["id"] == rede_id), None)
        
        self.metadata_cache[rede_id] = {
            "nome": data.get("nome", ""),
            "descricao": data.get("descricao", ""),
            "created_at": rede_db_data.get("created_at") if rede_db_data else None
        }
        
        return rede_id
    
    def remover_rede(self, rede_id: str):
        if rede_id in self.redes_cache:
            del self.redes_cache[rede_id]
            del self.metadata_cache[rede_id]
            self.db.remover_rede(rede_id)

    def obter_info_rede(self, rede_id: str) -> Dict[str, Any]:
        if rede_id not in self.redes_cache:
            raise ValueError("Rede não encontrada")
        
        rede = self.redes_cache[rede_id]
        metadata = self.metadata_cache.get(rede_id, {})
        
        # NÃO inicializar posições automaticamente - apenas quando solicitado
        # self._inicializar_posicoes_veiculos(rede_id, rede)
        
        todos_nos = []
        
        for deposito in rede.depositos:
            todos_nos.append({
                "id": deposito.id,
                "name": deposito.nome,
                "tipo": "deposito",
                "type": "depot",  # Frontend expects 'type' field
                "latitude": deposito.latitude,
                "longitude": deposito.longitude,
                "capacity": deposito.capacidade_maxima
            })
        for hub in rede.hubs:
            todos_nos.append({
                "id": hub.id,
                "name": hub.nome,
                "tipo": "hub",
                "type": "hub",  # Frontend expects 'type' field
                "latitude": hub.latitude,
                "longitude": hub.longitude,
                "capacity": hub.capacidade,
                "endereco": getattr(hub, 'endereco', '')
            })
        for cliente in rede.clientes:
            todos_nos.append({
                "id": cliente.id,
                "name": f"Cliente {cliente.id}",
                "tipo": "cliente",
                "type": "client",  # Frontend expects 'type' field
                "latitude": cliente.latitude,
                "longitude": cliente.longitude,
                "demand": cliente.demanda_media,
                "priority": cliente.prioridade.name if hasattr(cliente.prioridade, 'name') else str(cliente.prioridade)
            })
        for zona in rede.zonas:
            # For zones, we'll use a central point or the first hub's location
            lat, lon = -9.65, -35.72  # Default to Maceió center
            if zona.hubs:
                lat = zona.hubs[0].latitude
                lon = zona.hubs[0].longitude
            
            todos_nos.append({
                "id": zona.id,
                "name": zona.nome,
                "tipo": "zona",
                "type": "zone",  # Frontend expects 'type' field
                "latitude": lat,
                "longitude": lon
            })
        
        # Build edges/routes information
        todas_rotas = []
        for rota in rede.rotas:
            todas_rotas.append({
                "source": rota.origem,
                "target": rota.destino,
                "capacity": rota.capacidade,
                "distance": getattr(rota, 'distancia', None),
                "travel_time": getattr(rota, 'tempo_medio', None)
            })
        
        # Obter informações dos veículos e suas posições
        todos_veiculos = []
        posicoes_veiculos = self.obter_todas_posicoes_veiculos(rede_id)
        posicoes_map = {pos.vehicle_id: pos for pos in posicoes_veiculos}
        
        for veiculo in rede.veiculos:
            veiculo_info = {
                "id": veiculo.id,
                "tipo": veiculo.tipo.name if hasattr(veiculo.tipo, 'name') else str(veiculo.tipo),
                "capacidade": veiculo.capacidade,
                "velocidade_media": veiculo.velocidade_media,
                "hub_base": veiculo.hub_base,
                "condutor": veiculo.condutor,
                "disponivel": veiculo.disponivel
            }
            
            # Adicionar posição atual se disponível
            if veiculo.id in posicoes_map:
                pos = posicoes_map[veiculo.id]
                # Converter timestamp para string de forma segura
                try:
                    timestamp_str = pos.timestamp.isoformat() if hasattr(pos.timestamp, 'isoformat') else str(pos.timestamp)
                except (AttributeError, TypeError):
                    timestamp_str = get_brazilian_timestamp().isoformat()
                
                veiculo_info.update({
                    "posicao_atual": {
                        "latitude": pos.latitude,
                        "longitude": pos.longitude,
                        "timestamp": timestamp_str,
                        "speed": pos.speed,
                        "heading": pos.heading,
                        "status": pos.status
                    }
                })
            
            todos_veiculos.append(veiculo_info)
        
        return {
            'nome': metadata.get('nome', 'Rede sem nome'),
            'total_nodes': len(todos_nos),
            'total_edges': len(rede.rotas),
            'nodes_por_tipo': self._contar_nodes_por_tipo(rede),
            'capacidade_total': sum(rota.capacidade for rota in rede.rotas),
            'nodes': todos_nos,
            'edges': todas_rotas,
            'vehicles': todos_veiculos
        }
    
    def preparar_para_calculo_fluxo(self, rede_id: str, origem: str, destino: str) -> Dict[str, Any]:
        """
        Calcula o fluxo máximo entre dois nós da rede usando algoritmos Ford-Fulkerson e Edmonds-Karp.
        
        Args:
            rede_id: ID da rede
            origem: Nó de origem para o cálculo de fluxo
            destino: Nó de destino para o cálculo de fluxo
            
        Returns:
            Dicionário com resultados dos algoritmos de fluxo máximo
        """
        if rede_id not in self.redes_cache:
            raise ValueError("Rede não encontrada")
        
        rede = self.redes_cache[rede_id]
        
        # Validar nós
        todos_ids = []
        todos_ids.extend([d.id for d in rede.depositos])
        todos_ids.extend([h.id for h in rede.hubs])
        todos_ids.extend([z.id for z in rede.zonas])
        
        if origem not in todos_ids:
            raise ValueError(f"Nó origem '{origem}' não encontrado")
        if destino not in todos_ids:
            raise ValueError(f"Nó destino '{destino}' não encontrado")
        
        # Construir grafo NetworkX
        grafo = construir_grafo_networkx_completo(rede)
        
        if not grafo.has_node(origem) or not grafo.has_node(destino):
            return {
                'erro': 'Nós não encontrados no grafo',
                'grafo_info': {
                    'total_nodes': len(todos_ids),
                    'total_edges': len(rede.rotas),
                    'nodes_disponiveis': todos_ids
                }
            }
        
        try:
            # Calcular fluxo máximo com ambos algoritmos
            resultado_edmonds_karp = calculate_network_flow(
                grafo, origem, destino, algorithm="edmonds_karp"
            )
            
            resultado_ford_fulkerson = calculate_network_flow(
                grafo, origem, destino, algorithm="ford_fulkerson"  
            )
            
            # Converter FlowResult para ResultadoOtimizacao
            resultado_ek = self._flow_result_to_resultado_otimizacao(resultado_edmonds_karp)
            resultado_ff = self._flow_result_to_resultado_otimizacao(resultado_ford_fulkerson)
            
            # Construir fluxos por rota
            fluxos_rotas_ek = self._construir_fluxos_rotas(resultado_edmonds_karp, rede)
            fluxos_rotas_ff = self._construir_fluxos_rotas(resultado_ford_fulkerson, rede)
            
            return {
                'status': 'sucesso',
                'origem': origem,
                'destino': destino,
                'algoritmos': {
                    'edmonds_karp': {
                        'resultado': asdict(resultado_ek),
                        'fluxos_rotas': [asdict(fr) for fr in fluxos_rotas_ek],
                        'performance': {
                            'tempo_execucao': resultado_edmonds_karp.execution_time,
                            'valor_fluxo_maximo': resultado_edmonds_karp.max_flow_value,
                            'caminhos_utilizados': len(resultado_edmonds_karp.paths_used),
                            'arestas_corte_minimo': len(resultado_edmonds_karp.cut_edges)
                        }
                    },
                    'ford_fulkerson': {
                        'resultado': asdict(resultado_ff),
                        'fluxos_rotas': [asdict(fr) for fr in fluxos_rotas_ff],
                        'performance': {
                            'tempo_execucao': resultado_ford_fulkerson.execution_time,
                            'valor_fluxo_maximo': resultado_ford_fulkerson.max_flow_value,
                            'caminhos_utilizados': len(resultado_ford_fulkerson.paths_used),
                            'arestas_corte_minimo': len(resultado_ford_fulkerson.cut_edges)
                        }
                    }
                },
                'comparacao': {
                    'valores_identicos': resultado_edmonds_karp.max_flow_value == resultado_ford_fulkerson.max_flow_value,
                    'algoritmo_mais_rapido': 'edmonds_karp' if resultado_edmonds_karp.execution_time < resultado_ford_fulkerson.execution_time else 'ford_fulkerson',
                    'diferenca_tempo': abs(resultado_edmonds_karp.execution_time - resultado_ford_fulkerson.execution_time)
                },
                'grafo_info': {
                    'total_nodes': grafo.number_of_nodes(),
                    'total_edges': grafo.number_of_edges(),
                    'nodes_disponiveis': list(grafo.nodes()),
                    'capacidade_total_rede': sum(rota.capacidade for rota in rede.rotas if rota.ativa)
                },
                'detalhes_caminhos': {
                    'edmonds_karp': resultado_edmonds_karp.paths_used,
                    'ford_fulkerson': resultado_ford_fulkerson.paths_used
                },
                'cortes_minimos': {
                    'edmonds_karp': resultado_edmonds_karp.cut_edges,
                    'ford_fulkerson': resultado_ford_fulkerson.cut_edges
                }
            }
            
        except Exception as e:
            return {
                'status': 'erro',
                'origem': origem,
                'destino': destino,
                'erro': str(e),
                'grafo_info': {
                    'total_nodes': grafo.number_of_nodes(),
                    'total_edges': grafo.number_of_edges(),
                    'nodes_disponiveis': list(grafo.nodes())
                }
            }
    
    def _flow_result_to_resultado_otimizacao(self, flow_result: FlowResult) -> ResultadoOtimizacao:
        """Converte FlowResult para ResultadoOtimizacao."""
        # Encontrar o melhor caminho (maior fluxo)
        melhor_caminho = []
        if flow_result.paths_used:
            # Se temos caminhos, pegar o primeiro (geralmente é um dos principais)
            melhor_caminho = flow_result.paths_used[0]
        
        return ResultadoOtimizacao(
            algoritmo=flow_result.algorithm_used,
            fluxo_maximo=int(flow_result.max_flow_value),
            caminho_otimo=melhor_caminho,
            tempo_execucao=flow_result.execution_time,
            iteracoes=len(flow_result.paths_used),
            convergiu=True,
            detalhes={
                'fluxos_por_aresta': flow_result.flow_dict,
                'arestas_corte_minimo': flow_result.cut_edges,
                'total_caminhos_aumentantes': len(flow_result.paths_used),
                'todos_caminhos': flow_result.paths_used
            }
        )
    
    def _construir_fluxos_rotas(self, flow_result: FlowResult, rede: RedeEntrega) -> List[FluxoRota]:
        """Constrói lista de FluxoRota a partir do resultado do fluxo."""
        fluxos_rotas = []
        
        # Mapear rotas da rede para facilitar busca
        rotas_map = {}
        for rota in rede.rotas:
            key = f"{rota.origem}->{rota.destino}"
            rotas_map[key] = rota
        
        # Criar FluxoRota para cada aresta com fluxo
        for origem, destinos in flow_result.flow_dict.items():
            for destino, fluxo in destinos.items():
                if fluxo > 0:
                    key = f"{origem}->{destino}"
                    rota = rotas_map.get(key)
                    
                    if rota:
                        fluxo_rota = FluxoRota(
                            rota_id=f"{origem}_{destino}",
                            origem=origem,
                            destino=destino,
                            fluxo_atual=int(fluxo),
                            capacidade_maxima=rota.capacidade
                        )
                        fluxos_rotas.append(fluxo_rota)
        
        return fluxos_rotas
    
    def listar_redes(self) -> List[str]:
        return list(self.redes_cache.keys())
    
    def obter_detalhes_todas_redes(self) -> List[Dict[str, Any]]:
        resultado = []
        
        redes_db = self.db.listar_redes()
        
        for rede_data in redes_db:
            rede_id = rede_data["id"]
            try:
                info = self.obter_info_rede(rede_id)
                
                resultado.append({
                    'id': rede_id,
                    'nome': info['nome'],
                    'total_nodes': info['total_nodes'],
                    'total_edges': info['total_edges'],
                    'created_at': rede_data.get('created_at')
                })
            except Exception as e:
                resultado.append({
                    'id': rede_id,
                    'erro': str(e)
                })
        
        return resultado
    
    def _contar_nodes_por_tipo(self, rede: RedeEntrega) -> Dict[str, int]:
        """Conta nós por tipo"""
        return {
            'deposito': len(rede.depositos),
            'hub': len(rede.hubs),
            'zona': len(rede.zonas)
        }
    
    def validar_rede(self, rede_id: str) -> Dict[str, Any]:
        """Validação básica da integridade da rede"""
        if rede_id not in self.redes_cache:
            raise ValueError("Rede não encontrada")
        
        # Assegurar que temos os dados mais recentes da rede do banco
        try:
            # Recarregar do banco para garantir que clientes estão incluídos
            rede_data = self.db.carregar_rede(rede_id)
            if rede_data:
                self.redes_cache[rede_id] = self._from_dict(rede_data)
        except Exception as e:
            print(f"Erro ao recarregar rede do banco: {e}")
        
        rede = self.redes_cache[rede_id]
        problemas = []
        
        # Verificar se há pelo menos um depósito
        if len(rede.depositos) == 0:
            problemas.append("Rede deve ter pelo menos um depósito")
        
        # Verificar se há pelo menos uma zona
        if len(rede.zonas) == 0:
            problemas.append("Rede deve ter pelo menos uma zona de entrega")
        
        # Verificar se há rotas
        if len(rede.rotas) == 0:
            problemas.append("Rede deve ter pelo menos uma rota")
            
        # Verificar se há clientes
        if len(rede.clientes) == 0:
            print(f"AVISO: Rede {rede_id} não tem clientes carregados.")
        
        # Verificar rotas órfãs (que referenciam nós inexistentes)
        todos_ids = []
        todos_ids.extend([d.id for d in rede.depositos])
        todos_ids.extend([h.id for h in rede.hubs]) 
        todos_ids.extend([c.id for c in rede.clientes])
        todos_ids.extend([z.id for z in rede.zonas])
        
        # Verificar e criar clientes virtuais se necessário para rotas existentes
        clientes_faltando = set()
        for rota in rede.rotas:
            if rota.destino.startswith("CLI_") and rota.destino not in todos_ids:
                clientes_faltando.add(rota.destino)
        
        # Adicionar clientes virtuais para rotas existentes
        if clientes_faltando:
            print(f"Adicionando {len(clientes_faltando)} clientes virtuais para validação")
            for cliente_id in clientes_faltando:
                from core.entities.models import Cliente
                rede.clientes.append(Cliente(
                    id=cliente_id,
                    latitude=-9.65,  # Coordenadas no centro de Maceió
                    longitude=-35.72,
                    demanda_media=1,
                    prioridade=PrioridadeCliente.NORMAL,
                    zona_id="ZONA_CENTRO"
                ))
            # Atualizar a lista de IDs
            todos_ids.extend(list(clientes_faltando))
        
        # Verificar se ainda há rotas órfãs
        for rota in rede.rotas:
            if rota.origem not in todos_ids:
                problemas.append(f"Rota referencia origem inexistente: {rota.origem}")
            if rota.destino not in todos_ids:
                problemas.append(f"Rota referencia destino inexistente: {rota.destino}")
        
        return {
            'valida': len(problemas) == 0,
            'problemas': problemas,
            'resumo': {
                'total_depositos': len(rede.depositos),
                'total_hubs': len(rede.hubs),
                'total_zonas': len(rede.zonas),
                'total_clientes': len(rede.clientes),
                'total_rotas': len(rede.rotas)
            }
        }

    def criar_rede_maceio_completo(self, num_clientes: int = 100, num_entregadores: Optional[int] = None, nome_rede: Optional[str] = None) -> str:
        """Cria uma rede completa de Maceió usando o gerador automático"""
        try:
            gerador = GeradorMaceioCompleto()
            rede_completa = gerador.gerar_rede_completa(num_clientes=num_clientes, num_entregadores=num_entregadores)
            
            nome_final = nome_rede or f"Maceió Completo - {num_clientes} Clientes"
            if num_entregadores:
                nome_final += f" - {num_entregadores} Entregadores"
            
            rede_dict = self._rede_to_dict(rede_completa, nome_final)
            
            rede_id = self.criar_rede_schema(rede_dict)
            
            return rede_id
        except Exception as e:
            raise Exception(f"Erro ao gerar rede completa de Maceió: {str(e)}")

    def _rede_to_dict(self, rede: RedeEntrega, nome: str) -> Dict[str, Any]:
        """Converte uma RedeEntrega para o formato dict usado pela API"""
        nodes = []
        edges = []
        
        # Adicionar depósitos
        for deposito in rede.depositos:
            nodes.append({
                "id": deposito.id,
                "nome": deposito.nome,
                "tipo": "deposito",
                "latitude": deposito.latitude,
                "longitude": deposito.longitude,
                "capacidade_maxima": deposito.capacidade_maxima
            })
        
        # Adicionar hubs
        for hub in rede.hubs:
            nodes.append({
                "id": hub.id,
                "nome": hub.nome,
                "tipo": "hub",
                "latitude": hub.latitude,
                "longitude": hub.longitude,
                "capacidade": hub.capacidade
            })
        
        # Adicionar zonas de entrega (criar coordenadas médias dos clientes)
        for zona in rede.zonas:
            # Calcular coordenadas médias dos clientes da zona
            clientes_zona = [c for c in rede.clientes if c.zona_id == zona.id]
            if clientes_zona:
                lat_media = sum(c.latitude for c in clientes_zona) / len(clientes_zona)
                lon_media = sum(c.longitude for c in clientes_zona) / len(clientes_zona)
            else:
                lat_media, lon_media = -9.6658, -35.7350  # Coordenadas padrão de Maceió
            
            nodes.append({
                "id": zona.id,
                "nome": zona.nome,
                "tipo": "zona",
                "latitude": lat_media,
                "longitude": lon_media
            })
        
        # Adicionar clientes
        for cliente in rede.clientes:
            nodes.append({
                "id": cliente.id,
                "nome": f"Cliente {cliente.id}",
                "tipo": "cliente",
                "latitude": cliente.latitude,
                "longitude": cliente.longitude,
                "prioridade": cliente.prioridade.value if hasattr(cliente.prioridade, 'value') else str(cliente.prioridade),
                "zona_id": cliente.zona_id,
                "demanda_media": cliente.demanda_media
            })
        
        # Adicionar veículos
        for veiculo in rede.veiculos:
            nodes.append({
                "id": veiculo.id,
                "nome": f"Veículo {veiculo.id}",
                "tipo": "veiculo",
                "latitude": 0,  # Veículos não têm posição fixa
                "longitude": 0,
                "tipo_veiculo": veiculo.tipo.value if hasattr(veiculo.tipo, 'value') else str(veiculo.tipo),
                "capacidade": veiculo.capacidade,
                "velocidade_media": veiculo.velocidade_media,
                "hub_base": veiculo.hub_base,
                "condutor": veiculo.condutor
            })
        
        # Adicionar rotas como edges
        for rota in rede.rotas:
            edges.append({
                "origem": rota.origem,
                "destino": rota.destino,
                "distancia": rota.peso,  # peso é usado como distância
                "custo": rota.custo,
                "capacidade": rota.capacidade
            })
        
        return {
            "nome": nome,
            "descricao": f"Rede completa gerada automaticamente para Maceió com {len(rede.clientes)} clientes, {len(rede.depositos)} depósitos, {len(rede.hubs)} hubs e {len(rede.zonas)} zonas",
            "nodes": nodes,
            "edges": edges
        }
    
    # Métodos para WebSocket e rastreamento de veículos
    
    def obter_posicao_veiculo(self, vehicle_id: str) -> Optional[VehiclePosition]:
        """Obtém a posição atual de um veículo"""
        return self.vehicle_positions.get(vehicle_id)
    
    def atualizar_posicao_veiculo(self, vehicle_id: str, latitude: float, longitude: float, 
                                speed: float = 0.0, heading: float = 0.0, status: str = "moving") -> VehiclePosition:
        """Atualiza a posição de um veículo"""
        position = VehiclePosition(
            vehicle_id=vehicle_id,
            latitude=latitude,
            longitude=longitude,
            timestamp=get_brazilian_timestamp(),
            speed=speed,
            heading=heading,
            status=status
        )
        self.vehicle_positions[vehicle_id] = position
        return position
    
    def obter_todas_posicoes_veiculos(self, rede_id: Optional[str] = None) -> List[VehiclePosition]:
        """Obtém todas as posições de veículos, opcionalmente filtradas por rede.
        Veículos com status 'idle' e sem cliente atribuído não são retornados (somem do mapa).
        """
        positions = list(self.vehicle_positions.values())

        # Filtro por rede, se fornecido
        if rede_id and rede_id in self.redes_cache:
            rede = self.redes_cache[rede_id]
            vehicle_ids = {v.id for v in rede.veiculos}
            positions = [p for p in positions if p.vehicle_id in vehicle_ids]

        # Filtro para sumir veículos 'idle' sem cliente
        def is_active_or_waiting(p: VehiclePosition) -> bool:
            if p.status != "idle":
                return True
            # Consultar estado de movimento para saber se tem cliente atribuído
            movement_service = getattr(self, 'movement_service', None)
            if movement_service and hasattr(movement_service, 'vehicle_states'):
                state = movement_service.vehicle_states.get(p.vehicle_id)
                if state and getattr(state, 'current_client_id', None):
                    return True  # Está idle mas aguardando cliente
            return False  # Idle e sem cliente: some do mapa

        positions = [p for p in positions if is_active_or_waiting(p)]
        return positions
    
    def calcular_rota_detalhada(self, origin_lat: float, origin_lon: float,
                              dest_lat: float, dest_lon: float, 
                              route_id: Optional[str] = None) -> Optional[DetailedRoute]:
        """Calcula uma rota detalhada com waypoints usando a rede real"""
        # Carregar rede real apenas quando necessário
        self._garantir_rede_real_carregada()
        
        if not OSMNX_AVAILABLE or self.real_network_graph is None or ox is None:
            return self._calcular_rota_sintetica(origin_lat, origin_lon, dest_lat, dest_lon, route_id)
        
        try:
            # Encontrar nós mais próximos
            origin_node = ox.nearest_nodes(self.real_network_graph, origin_lon, origin_lat)
            dest_node = ox.nearest_nodes(self.real_network_graph, dest_lon, dest_lat)
            
            if nx is None:
                return self._calcular_rota_sintetica(origin_lat, origin_lon, dest_lat, dest_lon, route_id)
            
            # Calcular caminho mais curto
            path = nx.shortest_path(self.real_network_graph, origin_node, dest_node, weight='travel_time')
            
            # Extrair waypoints
            waypoints = []
            total_distance = 0.0
            total_time = 0.0
            
            for i, node in enumerate(path):
                node_data = self.real_network_graph.nodes[node]
                waypoint = RouteWaypoint(
                    latitude=node_data['y'],
                    longitude=node_data['x'],
                    sequence=i,
                    estimated_time=total_time,
                    is_stop=i == 0 or i == len(path) - 1
                )
                waypoints.append(waypoint)
                
                # Calcular distância e tempo para próximo nó
                if i < len(path) - 1:
                    next_node = path[i + 1]
                    if self.real_network_graph.has_edge(node, next_node):
                        edge_data = self.real_network_graph[node][next_node][0]
                        total_distance += edge_data.get('length', 0) / 1000  # converter para km
                        total_time += edge_data.get('travel_time', 0) / 60  # converter para minutos
            
            detailed_route = DetailedRoute(
                route_id=route_id or f"route_{int(time.time())}",
                origin_id=f"coord_{origin_lat}_{origin_lon}",
                destination_id=f"coord_{dest_lat}_{dest_lon}",
                waypoints=waypoints,
                total_distance=total_distance,
                estimated_duration=total_time,
                optimized=True
            )
            
            if route_id:
                self.detailed_routes[route_id] = detailed_route
            
            return detailed_route
            
        except Exception as e:
            print(f"Erro ao calcular rota real: {e}")
            return self._calcular_rota_sintetica(origin_lat, origin_lon, dest_lat, dest_lon, route_id)
    
    def _calcular_rota_sintetica(self, origin_lat: float, origin_lon: float, 
                               dest_lat: float, dest_lon: float, route_id: Optional[str] = None) -> DetailedRoute:
        """Calcula uma rota sintética simples como fallback"""
        # Rota direta com interpolação linear
        num_waypoints = 10
        waypoints = []
        
        lat_step = (dest_lat - origin_lat) / (num_waypoints - 1)
        lon_step = (dest_lon - origin_lon) / (num_waypoints - 1)
        
        # Calcular distância total (aproximada)
        distance_km = self._calcular_distancia_haversine(origin_lat, origin_lon, dest_lat, dest_lon)
        estimated_speed = 25  # km/h velocidade média urbana
        total_time = (distance_km / estimated_speed) * 60  # minutos
        
        for i in range(num_waypoints):
            lat = origin_lat + (lat_step * i)
            lon = origin_lon + (lon_step * i)
            
            waypoint = RouteWaypoint(
                latitude=lat,
                longitude=lon,
                sequence=i,
                estimated_time=(total_time / (num_waypoints - 1)) * i,
                is_stop=i == 0 or i == num_waypoints - 1
            )
            waypoints.append(waypoint)
        
        detailed_route = DetailedRoute(
            route_id=route_id or f"synthetic_route_{int(time.time())}",
            origin_id=f"coord_{origin_lat}_{origin_lon}",
            destination_id=f"coord_{dest_lat}_{dest_lon}",
            waypoints=waypoints,
            total_distance=distance_km,
            estimated_duration=total_time,
            optimized=False
        )
        
        if route_id:
            self.detailed_routes[route_id] = detailed_route
        
        return detailed_route
    
    def _calcular_distancia_haversine(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calcula distância usando fórmula de Haversine"""
        R = 6371  # Raio da Terra em km
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat / 2) ** 2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    def obter_rota_detalhada(self, route_id: str) -> Optional[DetailedRoute]:
        """Obtém uma rota detalhada pelo ID"""
        return self.detailed_routes.get(route_id)
    
    def calcular_rota_entre_nos(self, rede_id: str, origin_id: str, dest_id: str) -> Optional[DetailedRoute]:
        """Calcula rota detalhada entre dois nós da rede"""
        if rede_id not in self.redes_cache:
            return None
        
        rede = self.redes_cache[rede_id]
        
        # Encontrar coordenadas dos nós
        origin_coords = self._obter_coordenadas_no(rede, origin_id)
        dest_coords = self._obter_coordenadas_no(rede, dest_id)
        
        if not origin_coords or not dest_coords:
            return None
        
        route_id = f"{origin_id}_{dest_id}_{int(time.time())}"
        return self.calcular_rota_detalhada(
            origin_coords[0], origin_coords[1],
            dest_coords[0], dest_coords[1],
            route_id
        )
    
    def _obter_coordenadas_no(self, rede: RedeEntrega, node_id: str) -> Optional[Tuple[float, float]]:
        """Obtém coordenadas de um nó da rede"""
        # Verificar depósitos
        for deposito in rede.depositos:
            if deposito.id == node_id:
                return (deposito.latitude, deposito.longitude)
        
        # Verificar hubs
        for hub in rede.hubs:
            if hub.id == node_id:
                return (hub.latitude, hub.longitude)
        
        # Verificar clientes
        for cliente in rede.clientes:
            if cliente.id == node_id:
                return (cliente.latitude, cliente.longitude)
        
        return None
    
    def obter_rotas_otimizadas_para_veiculo(self, rede_id: str, vehicle_id: str, 
                                          clientes_ids: List[str]) -> List[DetailedRoute]:
        """Gera rotas otimizadas para um veículo visitar múltiplos clientes"""
        if rede_id not in self.redes_cache:
            return []
        
        rede = self.redes_cache[rede_id]
        
        # Encontrar veículo
        veiculo = None
        for v in rede.veiculos:
            if v.id == vehicle_id:
                veiculo = v
                break
        
        if not veiculo:
            return []
        
        # Encontrar hub base
        hub_coords = None
        for hub in rede.hubs:
            if hub.id == veiculo.hub_base:
                hub_coords = (hub.latitude, hub.longitude)
                break
        
        if not hub_coords:
            return []

         # Remover clientes já atendidos
        clientes_atendidos = set()

        # Verifica se há controle de clientes atendidos no VehicleMovementService
        if hasattr(self, 'vehicle_movement_service'):
            clientes_atendidos = self.vehicle_movement_service.clientes_atendidos.get(rede_id, set())

        # Filtrar os clientes disponíveis
        clientes_ids = [
            cid for cid in clientes_ids
            if cid not in clientes_atendidos
        ]

        if not clientes_ids:
            print(f"✅ Todos os clientes da rede {rede_id} já foram atendidos.")
            asyncio.create_task(broadcast_log(f"✅ Todos os clientes da rede {rede_id} já foram atendidos."))
            return []
   
        
        # Otimização simples: ordenar clientes por distância do hub
        clientes_coords = []
        for cliente_id in clientes_ids:
            coords = self._obter_coordenadas_no(rede, cliente_id)
            if coords:
                dist = self._calcular_distancia_haversine(hub_coords[0], hub_coords[1], coords[0], coords[1])
                clientes_coords.append((cliente_id, coords, dist))
        
        # Ordenar por distância
        clientes_coords.sort(key=lambda x: x[2])
        
        # Gerar rotas sequenciais
        rotas = []
        current_coords = hub_coords
        current_id = veiculo.hub_base
        
        for i, (cliente_id, cliente_coords, _) in enumerate(clientes_coords):
            route_id = f"{vehicle_id}_route_{i+1}"
            rota = self.calcular_rota_detalhada(
                current_coords[0], current_coords[1],
                cliente_coords[0], cliente_coords[1],
                route_id
            )
            if rota:
                rota.origin_id = current_id
                rota.destination_id = cliente_id
                rotas.append(rota)
            
            current_coords = cliente_coords
            current_id = cliente_id
        
        # Rota de volta ao hub
        if clientes_coords:
            route_id = f"{vehicle_id}_return"
            rota_volta = self.calcular_rota_detalhada(
                current_coords[0], current_coords[1],
                hub_coords[0], hub_coords[1],
                route_id
            )
            if rota_volta:
                rota_volta.origin_id = current_id
                rota_volta.destination_id = veiculo.hub_base
                rotas.append(rota_volta)
        
        return rotas
    
    # Métodos para análise de tráfego e otimização
    
    def aplicar_fator_trafego(self, route_id: str, traffic_factor: float) -> bool:
        """Aplica fator de tráfego a uma rota (1.0 = normal, >1.0 = congestionamento)"""
        if route_id in self.detailed_routes:
            route = self.detailed_routes[route_id]
            route.traffic_factor = traffic_factor
            route.estimated_duration = route.estimated_duration * traffic_factor
            return True
        return False
    
    def obter_estatisticas_tempo_real(self, rede_id: str) -> Dict[str, Any]:
        """Obtém estatísticas da rede em tempo real"""
        if rede_id not in self.redes_cache:
            return {}
        
        rede = self.redes_cache[rede_id]
        positions = self.obter_todas_posicoes_veiculos(rede_id)
        
        # Obter estatísticas do serviço de movimento se disponível
        movement_stats = {}
        if self.movement_service:
            movement_stats = self.movement_service.get_movement_statistics()
        
        # Estatísticas de veículos (usar dados do movement service quando disponível)
        veiculos_ativos = movement_stats.get('active_vehicles', 
                                           len([p for p in positions if p.status in ["moving", "delivering", "returning"]]))
        veiculos_idle = movement_stats.get('idle', 
                                         len([p for p in positions if p.status == "idle"]))
        velocidade_media = sum(p.speed for p in positions) / len(positions) if positions else 0
        
        # Estatísticas de rotas
        rotas_ativas = movement_stats.get('total_routes', 
                                        len([r for r in self.detailed_routes.values() 
                                           if any(r.route_id.startswith(v.id) for v in rede.veiculos)]))
        
        return {
            "timestamp": get_brazilian_timestamp().isoformat(),
            "rede_id": rede_id,
            "veiculos": {
                "total": len(rede.veiculos),
                "ativos": veiculos_ativos,
                "idle": veiculos_idle,
                "velocidade_media": round(velocidade_media, 2)
            },
            "rotas": {
                "ativas": rotas_ativas,
                "em_cache": len(self.detailed_routes)
            },
            "cobertura": {
                "total_clientes": len(rede.clientes),
                "total_hubs": len(rede.hubs),
                "total_zonas": len(rede.zonas)
            }
        }
    
    def simular_movimento_veiculo(self, vehicle_id: str, route_id: str, 
                                progress_percent: float) -> Optional[VehiclePosition]:
        """Simula movimento de veículo ao longo de uma rota"""
        if route_id not in self.detailed_routes:
            return None
        
        route = self.detailed_routes[route_id]
        if not route.waypoints:
            return None
        
        # Garantir que progress está entre 0 e 100
        progress_percent = max(0, min(100, progress_percent))
        
        # Calcular posição interpolada
        total_waypoints = len(route.waypoints) - 1
        if total_waypoints == 0:
            waypoint = route.waypoints[0]
            # Velocidade variável baseada no contexto
            import random
            speed = random.uniform(15.0, 70.0) if progress_percent < 100 else 0.0
            return self.atualizar_posicao_veiculo(
                vehicle_id, waypoint.latitude, waypoint.longitude, 
                speed, 0.0, "moving" if progress_percent < 100 else "idle"
            )
        
        # Encontrar waypoints para interpolação
        position_index = (progress_percent / 100.0) * total_waypoints
        waypoint1_idx = int(position_index)
        waypoint2_idx = min(waypoint1_idx + 1, total_waypoints)
        
        waypoint1 = route.waypoints[waypoint1_idx]
        waypoint2 = route.waypoints[waypoint2_idx]
        
        # Interpolação linear
        if waypoint1_idx == waypoint2_idx:
            lat = waypoint1.latitude
            lon = waypoint1.longitude
        else:
            t = position_index - waypoint1_idx
            lat = waypoint1.latitude + t * (waypoint2.latitude - waypoint1.latitude)
            lon = waypoint1.longitude + t * (waypoint2.longitude - waypoint1.longitude)
        
        # Calcular heading (direção)
        heading = self._calcular_heading(waypoint1.latitude, waypoint1.longitude,
                                       waypoint2.latitude, waypoint2.longitude)
        
        # Estimar velocidade baseada no tipo de via, tráfego e variação realística
        import random
        base_speed = random.uniform(20.0, 40.0)  # Velocidade base variável
        traffic_adjustment = (2.0 - route.traffic_factor)  # Ajuste por tráfego
        estimated_speed = base_speed * traffic_adjustment
        
        # Limitar velocidade entre valores razoáveis
        estimated_speed = max(5.0, min(60.0, estimated_speed))
        
        status = "moving"
        if progress_percent >= 100:
            status = "idle"
        elif waypoint2.is_stop and abs(position_index - waypoint2_idx) < 0.1:
            status = "delivering"
        
        return self.atualizar_posicao_veiculo(
            vehicle_id, lat, lon, estimated_speed, heading, status
        )
    
    def _calcular_heading(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calcula o heading (direção) entre dois pontos em graus (0-360)"""
        if lat1 == lat2 and lon1 == lon2:
            return 0.0
            
        # Converter para radianos
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlon_rad = math.radians(lon2 - lon1)
        
        # Calcular heading usando fórmula de bearing
        y = math.sin(dlon_rad) * math.cos(lat2_rad)
        x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon_rad)
        
        heading_rad = math.atan2(y, x)
        heading_deg = math.degrees(heading_rad)
        
        # Normalizar para 0-360 graus
        return (heading_deg + 360) % 360
    
    def obter_dados_websocket(self, rede_id: str) -> Dict[str, Any]:
        """Obtém todos os dados necessários para WebSocket em formato JSON serializável"""
        estatisticas = self.obter_estatisticas_tempo_real(rede_id)
        posicoes = self.obter_todas_posicoes_veiculos(rede_id)
        
        # Converter posições para formato serializável
        posicoes_json = []
        for pos in posicoes:
            # Converter timestamp para string de forma segura
            try:
                timestamp_str = pos.timestamp.isoformat() if hasattr(pos.timestamp, 'isoformat') else str(pos.timestamp)
            except (AttributeError, TypeError):
                timestamp_str = get_brazilian_timestamp().isoformat()
                
            posicoes_json.append({
                "vehicle_id": pos.vehicle_id,
                "latitude": pos.latitude,
                "longitude": pos.longitude,
                "timestamp": timestamp_str,
                "speed": pos.speed,
                "heading": pos.heading,
                "status": pos.status
            })
        
        # Obter rotas ativas
        rotas_ativas = []
        if rede_id in self.redes_cache:
            rede = self.redes_cache[rede_id]
            vehicle_ids = {v.id for v in rede.veiculos}
            
            for route_id, route in self.detailed_routes.items():
                # Verificar se a rota pertence a um veículo desta rede
                if any(route_id.startswith(vid) for vid in vehicle_ids):
                    waypoints_json = []
                    for wp in route.waypoints:
                        waypoints_json.append({
                            "latitude": wp.latitude,
                            "longitude": wp.longitude,
                            "sequence": wp.sequence,
                            "estimated_time": wp.estimated_time,
                            "is_stop": wp.is_stop,
                            "stop_id": wp.stop_id
                        })
                    
                    rotas_ativas.append({
                        "route_id": route.route_id,
                        "origin_id": route.origin_id,
                        "destination_id": route.destination_id,
                        "waypoints": waypoints_json,
                        "total_distance": route.total_distance,
                        "estimated_duration": route.estimated_duration,
                        "traffic_factor": route.traffic_factor,
                        "optimized": route.optimized
                    })
        
        return {
            "type": "network_update",
            "rede_id": rede_id,
            "timestamp": get_brazilian_timestamp().isoformat(),
            "estatisticas": estatisticas,
            "posicoes_veiculos": posicoes_json,
            "rotas_ativas": rotas_ativas
        }
    
    def limpar_dados_antigos(self, max_age_minutes: int = 60):
        """Remove dados antigos de posições e rotas"""
        current_time = get_brazilian_timestamp()
        
        # Limpar posições antigas
        old_positions = []
        for vehicle_id, position in self.vehicle_positions.items():
            age_minutes = (current_time - position.timestamp).total_seconds() / 60
            if age_minutes > max_age_minutes:
                old_positions.append(vehicle_id)
        
        for vehicle_id in old_positions:
            del self.vehicle_positions[vehicle_id]
        
    
    # Métodos para demonstração e simulação
    def simular_rastreamento_veiculo(self, vehicle_id: str, route_id: str) -> List[VehiclePosition]:
        """Simula o movimento de um veículo ao longo de uma rota para demonstração"""
        if route_id not in self.detailed_routes:
            raise ValueError(f"Rota detalhada {route_id} não encontrada")
        
        route = self.detailed_routes[route_id]
        positions = []
        
        # Simular posições ao longo dos waypoints
        current_time = get_brazilian_timestamp()
        import random
        for i, waypoint in enumerate(route.waypoints):
            # Velocidade realística variável
            base_speed = random.uniform(15.0, 45.0)
            speed_variation = random.uniform(-5.0, 10.0)
            current_speed = max(5.0, min(60.0, base_speed + speed_variation))
            
            position = VehiclePosition(
                vehicle_id=vehicle_id,
                latitude=waypoint.latitude,
                longitude=waypoint.longitude,
                timestamp=current_time,
                speed=current_speed,
                heading=self._calcular_heading(
                    waypoint.latitude, waypoint.longitude,
                    route.waypoints[i+1].latitude if i+1 < len(route.waypoints) else waypoint.latitude,
                    route.waypoints[i+1].longitude if i+1 < len(route.waypoints) else waypoint.longitude
                ),
                status="moving" if i < len(route.waypoints)-1 else "delivering"
            )
            positions.append(position)
            
            # Atualizar cache de posição atual
            self.vehicle_positions[vehicle_id] = position
            
            # Simular tempo de viagem
            current_time = datetime.fromtimestamp(current_time.timestamp() + waypoint.estimated_time * 60)
        
        return positions
    
    def obter_estatisticas_trafego(self, zona_id: Optional[str] = None) -> Dict[str, Any]:
        """Obtém estatísticas de tráfego e fluxo da rede"""
        stats = {
            "total_vehicles": len(self.vehicle_positions),
            "active_routes": len(self.detailed_routes),
            "average_speed": 0.0,
            "traffic_density": 0.0,
            "congested_areas": []
        }
        
        if self.vehicle_positions:
            speeds = [pos.speed for pos in self.vehicle_positions.values()]
            stats["average_speed"] = sum(speeds) / len(speeds)
            
            # Identificar áreas congestionadas (velocidade < 15 km/h)
            for vehicle_id, position in self.vehicle_positions.items():
                if position.speed < 15.0:
                    stats["congested_areas"].append({
                        "vehicle_id": vehicle_id,
                        "location": [position.latitude, position.longitude],
                        "speed": position.speed
                    })
        
        # Calcular densidade de tráfego baseada no número de veículos ativos
        if self._real_network_loaded and self.real_network_graph:
            network_area = len(self.real_network_graph.nodes) / 1000  # Normalizar
            stats["traffic_density"] = len(self.vehicle_positions) / network_area
        
        return stats
    
    def gerar_relatorio_otimizacao(self, rede_id: str) -> Dict[str, Any]:
        """Gera relatório de otimização baseado em dados reais da rede"""
        if rede_id not in self.redes_cache:
            raise ValueError("Rede não encontrada")
        
        rede = self.redes_cache[rede_id]
        stats_trafego = self.obter_estatisticas_trafego()
        
        relatorio = {
            "rede_id": rede_id,
            "timestamp": get_brazilian_timestamp().isoformat(),
            "resumo_rede": {
                "depositos": len(rede.depositos),
                "hubs": len(rede.hubs),
                "clientes": len(rede.clientes),
                "veiculos": len(rede.veiculos),
                "rotas": len(rede.rotas)
            },
            "performance_atual": stats_trafego,
            "gargalos_identificados": [],
            "sugestoes_otimizacao": []
        }
        
        # Identificar gargalos baseado em capacidade vs demanda
        for rota in rede.rotas:
            if rota.capacidade < 30:  # Capacidade baixa
                relatorio["gargalos_identificados"].append({
                    "tipo": "capacidade_baixa",
                    "rota": f"{rota.origem} -> {rota.destino}",
                    "capacidade_atual": rota.capacidade,
                    "sugestao": "Aumentar frota ou otimizar rota"
                })
        
        # Sugestões de otimização
        if stats_trafego["average_speed"] < 20:
            relatorio["sugestoes_otimizacao"].append({
                "prioridade": "alta",
                "tipo": "roteamento",
                "descricao": "Implementar roteamento dinâmico baseado em tráfego real",
                "impacto_estimado": "15-25% melhoria no tempo de entrega"
            })
        
        if len(stats_trafego["congested_areas"]) > 3:
            relatorio["sugestoes_otimizacao"].append({
                "prioridade": "média", 
                "tipo": "redistribuicao",
                "descricao": "Redistribuir veículos para evitar áreas congestionadas",
                "impacto_estimado": "10-20% redução no tempo de entrega"
            })
        
        return relatorio
    
    def exportar_dados_websocket(self, rede_id: str) -> Dict[str, Any]:
        """Exporta todos os dados necessários para o serviço WebSocket"""
        if rede_id not in self.redes_cache:
            raise ValueError("Rede não encontrada")
        
        rede = self.redes_cache[rede_id]
        
        # Preparar dados no formato adequado para WebSocket
        websocket_data = {
            "network_info": {
                "id": rede_id,
                "nodes": [],
                "edges": [],
                "bounds": self._obter_limites_rede(rede)
            },
            "vehicles": [],
            "routes": [],
            "real_time_data": {
                "traffic_stats": self.obter_estatisticas_trafego(),
                "last_update": get_brazilian_timestamp().isoformat()
            }
        }
        
        # Converter posições de veículos para formato JSON serializável
        for pos in self.vehicle_positions.values():
            try:
                timestamp_str = pos.timestamp.isoformat() if hasattr(pos.timestamp, 'isoformat') else str(pos.timestamp)
            except (AttributeError, TypeError):
                timestamp_str = get_brazilian_timestamp().isoformat()
                
            websocket_data["vehicles"].append({
                "vehicle_id": pos.vehicle_id,
                "latitude": pos.latitude,
                "longitude": pos.longitude,
                "timestamp": timestamp_str,
                "speed": pos.speed,
                "heading": pos.heading,
                "status": pos.status
            })
        
        # Converter rotas para formato JSON serializável
        for route in self.detailed_routes.values():
            route_dict = asdict(route)
            # Converter waypoints se necessário
            if 'waypoints' in route_dict:
                for wp in route_dict['waypoints']:
                    # Garantir que todos os campos são serializáveis
                    pass
            websocket_data["routes"].append(route_dict)
        
        # Adicionar nós (depósitos, hubs, clientes)
        for deposito in rede.depositos:
            websocket_data["network_info"]["nodes"].append({
                "id": deposito.id,
                "type": "depot",
                "coordinates": [deposito.latitude, deposito.longitude],
                "name": deposito.nome,
                "capacity": deposito.capacidade_maxima
            })
        
        for hub in rede.hubs:
            websocket_data["network_info"]["nodes"].append({
                "id": hub.id,
                "type": "hub", 
                "coordinates": [hub.latitude, hub.longitude],
                "name": hub.nome,
                "capacity": hub.capacidade,
                "endereco": getattr(hub, 'endereco', '')
            })
        
        for cliente in rede.clientes:
            websocket_data["network_info"]["nodes"].append({
                "id": cliente.id,
                "type": "client",
                "coordinates": [cliente.latitude, cliente.longitude],
                "demand": cliente.demanda_media,
                "priority": cliente.prioridade.value if hasattr(cliente.prioridade, 'value') else str(cliente.prioridade)
            })
        
        # Adicionar arestas (rotas)
        for rota in rede.rotas:
            websocket_data["network_info"]["edges"].append({
                "id": f"{rota.origem}_{rota.destino}",
                "source": rota.origem,
                "target": rota.destino,
                "capacity": rota.capacidade,
                "distance": rota.peso,
                "travel_time": rota.tempo_medio,
                "active": rota.ativa
            })
        
        return websocket_data
    
    def _obter_limites_rede(self, rede: RedeEntrega) -> Dict[str, float]:
        """Calcula os limites geográficos da rede para visualização"""
        all_lats = []
        all_lons = []
        
        for deposito in rede.depositos:
            all_lats.append(deposito.latitude)
            all_lons.append(deposito.longitude)
        
        for hub in rede.hubs:
            all_lats.append(hub.latitude)
            all_lons.append(hub.longitude)
            
        for cliente in rede.clientes:
            all_lats.append(cliente.latitude)
            all_lons.append(cliente.longitude)
        
        if all_lats and all_lons:
            return {
                "min_lat": min(all_lats),
                "max_lat": max(all_lats),
                "min_lon": min(all_lons),
                "max_lon": max(all_lons)
            }
        
        # Retornar limites padrão de Maceió se não houver dados
        return {
            "min_lat": -9.75,
            "max_lat": -9.50,
            "min_lon": -35.85,
            "max_lon": -35.65
        }
    
    def _inicializar_posicoes_veiculos(self, rede_id: str, rede: RedeEntrega):
        """Inicializa posições de veículos nos seus hubs base (sem rotas ou movimento)."""
        import random
        # Verificar se já temos posições para esta rede
        existing_positions = self.obter_todas_posicoes_veiculos(rede_id)
        if existing_positions:
            return  # Já inicializado

        # Inicializar posições dos veículos nos seus hubs base
        for veiculo in rede.veiculos:
            # Encontrar o hub base
            hub_base = None
            for hub in rede.hubs:
                if hub.id == veiculo.hub_base:
                    hub_base = hub
                    break
            if hub_base:
                # Adicionar pequena variação aleatória para simular veículos próximos mas não exatamente no mesmo local
                lat_variation = random.uniform(-0.001, 0.001)  # ~100m de variação
                lon_variation = random.uniform(-0.001, 0.001)
                self.atualizar_posicao_veiculo(
                    vehicle_id=veiculo.id,
                    latitude=hub_base.latitude + lat_variation,
                    longitude=hub_base.longitude + lon_variation,
                    speed=0.0,
                    heading=random.uniform(0, 360),
                    status="idle"
                )
        print(f"✅ Inicializadas {len(rede.veiculos)} posições de veículos para rede {rede_id}")
        # NÃO criar rotas ativas nem iniciar movimento automático aqui!

    def inicializar_posicoes_se_necessario(self, rede_id: str):
        """Inicializa posições de veículos apenas se solicitado explicitamente"""
        if rede_id not in self.redes_cache:
            raise ValueError("Rede não encontrada")
        
        rede = self.redes_cache[rede_id]
        self._inicializar_posicoes_veiculos(rede_id, rede)

