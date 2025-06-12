"""
Serviço de movimentação automática de veículos para simulação realista.
"""
import asyncio
import random
import math
from datetime import datetime, timedelta, timezone
import networkx as nx
import osmnx as ox
import networkx as nx
import numpy as np
from scipy.optimize import linear_sum_assignment

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from ..services.rede_service import OSMNX_AVAILABLE
from .rede_service import RedeService, VehiclePosition, DetailedRoute

# Função utilitária para timestamps brasileiros
def get_brazilian_timestamp() -> datetime:
    """Retorna timestamp atual no fuso horário brasileiro (UTC-3)"""
    brazilian_tz = timezone(timedelta(hours=-3))
    return datetime.now(brazilian_tz)


@dataclass
class VehicleMovementState:
    """Estado de movimento de um veículo."""
    vehicle_id: str
    route_id: Optional[str] = None
    progress_percent: float = 0.0
    status: str = "idle"  # idle, moving, delivering, returning
    last_update: Optional[datetime] = None
    target_progress: float = 100.0
    movement_speed: float = 10.0  # % por minuto (velocidade muito maior)
    pause_until: Optional[datetime] = None
    current_client_id: Optional[str] = None  # Cliente sendo atendido
    
    # Atributos para retorno direto ao hub
    hub_target_lat: Optional[float] = None
    hub_target_lon: Optional[float] = None
    return_start_lat: Optional[float] = None
    return_start_lon: Optional[float] = None


class VehicleMovementService:
    """Serviço para simular movimento automático e realista de veículos."""
    
    def __init__(self, rede_service: RedeService):
        self.rede_service = rede_service
        self.vehicle_states: Dict[str, VehicleMovementState] = {}
        self.is_running = False
        self.update_interval = 1.0  # segundos entre atualizações (mais frequente)
        self.clientes_atendidos: Dict[str, Set[str]] = {}

        
    async def start_automatic_movement(self, rede_id: str):
        """Inicia movimentação automática para todos os veículos de uma rede."""
        if self.is_running:
            return
        
        self.is_running = True
        
        # Inicializar estados dos veículos
        await self._initialize_vehicle_states(rede_id)
        
        # Loop principal de movimentação
        asyncio.create_task(self._movement_loop(rede_id))
    
    def stop_automatic_movement(self):
        """Para a movimentação automática."""
        self.is_running = False
        print("⏹️ Rastreamento interrompido")
    
    async def _initialize_vehicle_states(self, rede_id: str):
        """Inicializa estados de movimento dos veículos: cada veículo pega o cliente mais próximo disponível (matching guloso sequencial)."""
        self.vehicle_states = {}
        if rede_id not in self.rede_service.redes_cache:
            return
        rede = self.rede_service.redes_cache[rede_id]
        demanda_restante = {c.id: getattr(c, 'demanda_media', getattr(c, 'demanda', 1)) for c in rede.clientes}
        clientes_disponiveis = [c for c in rede.clientes if demanda_restante[c.id] > 0]
        veiculos_livres = [v for v in rede.veiculos]
        clientes_atribuidos = set()
        atribuicoes = {}
        for vehicle in veiculos_livres:
            hub = next((h for h in rede.hubs if h.id == vehicle.hub_base), None)
            if not hub:
                continue
            # Ordena clientes disponíveis por distância ao hub do veículo
            clientes_ordenados = sorted(
                [c for c in clientes_disponiveis if c.id not in clientes_atribuidos],
                key=lambda c: self._calculate_distance(hub.latitude, hub.longitude, c.latitude, c.longitude)
            )
            if clientes_ordenados:
                cliente_mais_proximo = clientes_ordenados[0]
                atribuicoes[vehicle.id] = cliente_mais_proximo
                clientes_atribuidos.add(cliente_mais_proximo.id)
        clientes_em_atendimento = set(clientes_atribuidos)
        for vehicle in rede.veiculos:
            if vehicle.id in atribuicoes:
                cliente = atribuicoes[vehicle.id]
                self.vehicle_states[vehicle.id] = VehicleMovementState(
                    vehicle_id=vehicle.id,
                    route_id=None,
                    progress_percent=0.0,
                    status="moving",
                    last_update=get_brazilian_timestamp(),
                    movement_speed=random.uniform(8.0, 15.0),
                    current_client_id=cliente.id
                )
                await self._assign_new_route(rede_id, vehicle.id)
            else:
                self.vehicle_states[vehicle.id] = VehicleMovementState(
                    vehicle_id=vehicle.id,
                    status="idle",
                    last_update=get_brazilian_timestamp()
                )
        self.demanda_restante = demanda_restante
        self.clientes_em_atendimento = clientes_em_atendimento
    
    def _find_active_route_for_vehicle(self, vehicle_id: str) -> Optional[str]:
        """Encontra rota ativa para um veículo."""
        for route_id, route in self.rede_service.detailed_routes.items():
            if route_id.startswith(vehicle_id):
                return route_id
        return None
    
    def _calculate_current_progress(self, vehicle_id: str, route_id: str) -> float:
        """Calcula progresso atual do veículo na rota."""
        position = self.rede_service.obter_posicao_veiculo(vehicle_id)
        if not position or route_id not in self.rede_service.detailed_routes:
            return 0.0
        
        route = self.rede_service.detailed_routes[route_id]
        if not route.waypoints:
            return 0.0
        
        # Encontrar waypoint mais próximo da posição atual
        min_distance = float('inf')
        closest_waypoint_idx = 0
        
        for i, waypoint in enumerate(route.waypoints):
            distance = self._calculate_distance(
                position.latitude, position.longitude,
                waypoint.latitude, waypoint.longitude
            )
            if distance < min_distance:
                min_distance = distance
                closest_waypoint_idx = i
        
        # Calcular progresso baseado no waypoint mais próximo
        if len(route.waypoints) > 1:
            progress = (closest_waypoint_idx / (len(route.waypoints) - 1)) * 100
            return min(100.0, max(0.0, progress))
        
        return 0.0
    
    async def _assign_new_route(self, rede_id: str, vehicle_id: str):
        """Atribui uma nova rota para um veículo idle usando matching guloso (greedy):
        o veículo escolhe o cliente de maior prioridade mais próximo do seu hub."""
        try:
            rede = self.rede_service.redes_cache[rede_id]
            demanda_restante = getattr(self, 'demanda_restante', None)
            if demanda_restante is None:
                demanda_restante = {c.id: getattr(c, 'demanda_media', getattr(c, 'demanda', 1)) for c in rede.clientes}
            clientes_em_atendimento = getattr(self, 'clientes_em_atendimento', set())
            vehicle = next((v for v in rede.veiculos if v.id == vehicle_id), None)
            if not vehicle:
                return
            hub = next((h for h in rede.hubs if h.id == vehicle.hub_base), None)
            if not hub:
                return
            # Filtrar clientes disponíveis (demanda > 0 e não em atendimento)
            clientes_disponiveis = [c for c in rede.clientes if demanda_restante.get(c.id, 0) > 0 and c.id not in clientes_em_atendimento]
            if not clientes_disponiveis:
                return
            # Selecionar clientes de maior prioridade
            prioridade_min = min(getattr(c.prioridade, 'value', c.prioridade) for c in clientes_disponiveis)
            candidatos_prioridade = [c for c in clientes_disponiveis if getattr(c.prioridade, 'value', c.prioridade) == prioridade_min]
            # Escolher o cliente mais próximo do hub do veículo
            melhor_cliente = None
            melhor_dist = float('inf')
            for cliente in candidatos_prioridade:
                dist = self._calculate_distance(hub.latitude, hub.longitude, cliente.latitude, cliente.longitude)
                if dist < melhor_dist:
                    melhor_dist = dist
                    melhor_cliente = cliente
            if melhor_cliente:
                clientes_em_atendimento.add(melhor_cliente.id)
                self.demanda_restante = demanda_restante
                self.clientes_em_atendimento = clientes_em_atendimento
                client_ids = [melhor_cliente.id]
                routes = self.rede_service.obter_rotas_otimizadas_para_veiculo(
                    rede_id, vehicle.id, client_ids
                )
                if routes and client_ids[0] is not None:
                    first_route = routes[0]
                    self.vehicle_states[vehicle.id] = VehicleMovementState(
                        vehicle_id=vehicle.id,
                        route_id=first_route.route_id,
                        progress_percent=0.0,
                        status="moving",
                        last_update=get_brazilian_timestamp(),
                        movement_speed=random.uniform(10.0, 20.0),
                        target_progress=100.0,
                        current_client_id=client_ids[0]
                    )
                    print(f"🛣️ Veículo {vehicle.id}: {first_route.route_id} -> Cliente {client_ids[0]} (demanda restante: {demanda_restante[client_ids[0]]})")
                else:
                    self.vehicle_states[vehicle.id] = VehicleMovementState(
                        vehicle_id=vehicle.id,
                        status="idle",
                        last_update=get_brazilian_timestamp()
                    )
                    print(f"⚠️Não foi possível criar rota válida para o veículo {vehicle.id}, ficará idle.")
        except Exception as e:
            print(f"❌ Erro no matching guloso dinâmico: {e}")

    async def _assign_global_optimal_routes(self, rede_id: str):
        """(Desativado) Não usar matching ótimo, apenas guloso."""
        return

    async def _maybe_assign_new_routes(self, rede_id: str):
        """Atribui novas rotas para veículos idle usando matching guloso."""
        idle_vehicles = [
            vehicle_id for vehicle_id, state in self.vehicle_states.items()
            if state.status == "idle" and (not state.pause_until or get_brazilian_timestamp() >= state.pause_until)
        ]
        for vehicle_id in idle_vehicles:
            await self._assign_new_route(rede_id, vehicle_id)

    async def _create_initial_position(self, rede_id: str, vehicle):
        """Cria posição inicial para um veículo em seu hub base."""
        try:
            rede = self.rede_service.redes_cache[rede_id]

            # Encontrar hub base
            hub_base = None
            for hub in rede.hubs:
                if hub.id == vehicle.hub_base:
                    hub_base = hub
                    break

            if hub_base:
                # Usar o nó mais próximo na rede real como posição inicial
                G = self.rede_service.real_network_graph
                if G is not None and hasattr(ox, 'distance'):
                    try:
                        nearest_node = ox.distance.nearest_nodes(G, hub_base.longitude, hub_base.latitude)
                        node_data = G.nodes[nearest_node]

                        self.rede_service.atualizar_posicao_veiculo(
                            vehicle_id=vehicle.id,
                            latitude=node_data['y'],
                            longitude=node_data['x'],
                            speed=0.0,
                            heading=random.uniform(0, 360),
                            status="idle"
                        )

                        self.vehicle_states[vehicle.id] = VehicleMovementState(
                            vehicle_id=vehicle.id,
                            status="idle",
                            last_update=datetime.now()
                        )

                        return

                    except Exception as e:
                        print(f"⚠️ Falha ao usar grafo real para veículo {vehicle.id}: {e}")

                # Fallback (caso grafo não exista ou falhe)
                lat_variation = random.uniform(-0.0002, 0.0002)
                lon_variation = random.uniform(-0.0002, 0.0002)

                self.rede_service.atualizar_posicao_veiculo(
                    vehicle_id=vehicle.id,
                    latitude=hub_base.latitude + lat_variation,
                    longitude=hub_base.longitude + lon_variation,
                    speed=0.0,
                    heading=random.uniform(0, 360),
                    status="idle"
                )

                self.vehicle_states[vehicle.id] = VehicleMovementState(
                    vehicle_id=vehicle.id,
                    status="idle",
                    last_update=get_brazilian_timestamp()
                )

    
        except Exception as e:
            print(f"❌ Erro ao criar posição inicial para veículo {vehicle.id}: {e}")

    
    async def _movement_loop(self, rede_id: str):
        """Loop principal de movimentação dos veículos."""
        
        while self.is_running:
            try:
                current_time = get_brazilian_timestamp()
                
                # Atualizar cada veículo
                for vehicle_id, state in list(self.vehicle_states.items()):
                    await self._update_vehicle_movement(rede_id, vehicle_id, state, current_time)
                
                # Ocasionalmente atribuir novas rotas para veículos idle
                if random.random() < 0.1:  # 10% chance a cada ciclo
                    await self._maybe_assign_new_routes(rede_id)
                
                # Aguardar próximo ciclo
                await asyncio.sleep(self.update_interval)
                
            except Exception as e:
                print(f"❌ Erro no loop de movimentação: {e}")
                await asyncio.sleep(5.0)
    
    async def _update_vehicle_movement(self, rede_id: str, vehicle_id: str, 
                                     state: VehicleMovementState, current_time: datetime):
        """Atualiza movimento de um veículo específico."""
    
        try:
            # Verificar se veículo está pausado
            if state.pause_until and current_time < state.pause_until:
                return

            # NOVO: Se estava reabastecendo e o tempo acabou, já tenta nova entrega
            if state.status == "refueling":
                if not state.pause_until or current_time >= state.pause_until:
                    # Tenta atribuir nova rota imediatamente
                    await self._assign_new_route(rede_id, vehicle_id)
                    return
            
            # Calcular tempo desde última atualização
            if state.last_update:
                time_delta = (current_time - state.last_update).total_seconds()
            else:
                time_delta = self.update_interval
        
            if state.status == "idle":
                # Veículo parado - ocasionalmente atribuir nova rota
                if random.random() < 0.05:  # 5% chance por ciclo
                    await self._assign_new_route(rede_id, vehicle_id)
        
            elif state.status == "moving" and state.route_id:
                # Veículo em movimento - atualizar progresso
                progress_increment = state.movement_speed * (time_delta / 60.0)  # % por minuto
                new_progress = min(state.target_progress, state.progress_percent + progress_increment)
            
                # Simular movimento ao longo da rota
                new_position = self.rede_service.simular_movimento_veiculo(
                    vehicle_id, state.route_id, new_progress
                )
            
                if new_position:
                    state.progress_percent = new_progress

                    # Variação realística de velocidade
                    if hasattr(new_position, 'speed') and new_position.speed > 0:
                        speed_variation = random.uniform(0.8, 1.2)
                        varied_speed = new_position.speed * speed_variation
                        new_position.speed = max(5.0, min(70.0, varied_speed))
                
                    # Verificar se chegou ao destino
                    if new_progress >= state.target_progress:
                        # Pausar para entrega
                        state.status = "delivering"
                        delivery_time = random.randint(0, 1)  # 0–1 min
                        state.pause_until = current_time + timedelta(minutes=delivery_time)

                        self.rede_service.atualizar_posicao_veiculo(
                            vehicle_id=vehicle_id,
                            latitude=new_position.latitude,
                            longitude=new_position.longitude,
                            speed=0.0,
                            heading=new_position.heading,
                            status="delivering"
                        )

                        print(f"📦 Veículo {vehicle_id} chegou ao destino e está entregando (tempo estimado: {delivery_time} min)")
                        # Só adiciona cliente válido
                        if state.current_client_id is not None:
                            self.clientes_atendidos.setdefault(rede_id, set()).add(state.current_client_id)
                            # Remover cliente do set de em atendimento
                            if hasattr(self, 'clientes_em_atendimento'):
                                self.clientes_em_atendimento.discard(state.current_client_id)
                            print(f"✅  O cliente {state.current_client_id} foi atendido.")
                        else:
                            print(f"⚠️ Atenção: Veículo {vehicle_id} chegou ao destino mas current_client_id é None. Nenhum cliente será marcado como atendido.")

            elif state.status == "delivering":
                # Veículo entregando - verificar se terminou
                if not state.pause_until or current_time >= state.pause_until:

                    # Decrementa demanda do cliente entregue
                    if hasattr(self, 'demanda_restante') and state.current_client_id:
                        self.demanda_restante[state.current_client_id] -= 1

                    # Obter ponto exato da entrega (último waypoint)
                    rota_entrega = self.rede_service.detailed_routes.get(state.route_id)
                    if rota_entrega and rota_entrega.waypoints:
                        ponto_entrega = rota_entrega.waypoints[-1]
                    else:
                        ponto_entrega = self.rede_service.obter_posicao_veiculo(vehicle_id)

                    # Iniciar retorno ao hub a partir da posição de entrega
                    await self._start_return_to_hub(
                        rede_id=rede_id,
                        vehicle_id=vehicle_id,
                        state=state,
                        current_time=current_time,
                        current_position=ponto_entrega
                    )

                    print(f"🔄 O veículo {vehicle_id} está retornando ao HUB.")
        
            elif state.status == "returning":
                # Veículo retornando - movimentar em direção ao hub
                if state.route_id:
                    progress_increment = state.movement_speed * (time_delta / 60.0)
                    new_progress = min(100.0, state.progress_percent + progress_increment)

                    new_position = self.rede_service.simular_movimento_veiculo(
                        vehicle_id, state.route_id, new_progress
                    )

                    if new_position:
                        state.progress_percent = new_progress

                        if hasattr(new_position, 'speed'):
                            new_position.speed = random.uniform(30, 50)

                        if new_progress >= 100.0:
                            await self._vehicle_arrived_at_hub(rede_id, vehicle_id, state, current_time)
                else:
                    await self._direct_return_to_hub(rede_id, vehicle_id, state, current_time, time_delta)

            # Atualizar timestamp
            state.last_update = current_time

        except Exception as e:
            print(f"❌ Erro ao atualizar movimento do veículo {vehicle_id}: {e}")

    
    async def _start_return_to_hub(self, rede_id: str, vehicle_id: str, state: VehicleMovementState, current_time: datetime, current_position=None):
        """Inicia o retorno do veículo ao hub com movimento real."""

        if current_position is None:
            current_position = self.rede_service.obter_posicao_veiculo(vehicle_id)

        try:
            rede = self.rede_service.redes_cache.get(rede_id)
            if not rede:
                print(f"❌ Rede {rede_id} não encontrada no cache.")
                return

            vehicle = next((v for v in rede.veiculos if v.id == vehicle_id), None)
            if not vehicle:
                print(f"⚠️ Veículo {vehicle_id} não encontrado na rede {rede_id}")
                return

            hub_base = next((h for h in rede.hubs if h.id == vehicle.hub_base), None)
            current_position = self.rede_service.obter_posicao_veiculo(vehicle_id)

            if not hub_base or not current_position:
                print(f"⚠️ Hub base ou posição atual não encontrados para veículo {vehicle_id}")
                return

            # Gerar ID único para a rota de retorno
            return_route_id = f"{vehicle_id}_return_{int(current_time.timestamp())}"

            # Tentar criar rota com grafo real
            return_route = None
            try:
                return_route = self._create_return_route(
                    return_route_id,
                    current_position,
                    hub_base
                )
            except Exception as e:
                print(f"❌ Erro ao criar rota de retorno para {vehicle_id}: {e}")

            if return_route:
                # Armazenar e configurar retorno com rota real
                self.rede_service.detailed_routes[return_route_id] = return_route

                state.status = "returning"
                state.route_id = return_route_id
                state.progress_percent = 0.0
                state.current_client_id = None
                state.movement_speed = random.uniform(12.0, 18.0)
                state.pause_until = None

                self.rede_service.atualizar_posicao_veiculo(
                    vehicle_id=vehicle_id,
                    latitude=current_position.latitude,
                    longitude=current_position.longitude,
                    speed=random.uniform(30, 45),
                    heading=self._calculate_heading_to_hub(current_position, hub_base),
                    status="returning"
                )

            else:
                # Fallback para movimento direto linear (interpolação)
                await self._setup_direct_return(rede_id, vehicle_id, state, hub_base)

        except Exception as e:
            print(f"❌ Erro inesperado ao iniciar retorno ao hub para veículo {vehicle_id}: {e}")

    
    def _create_return_route(self, route_id: str, current_pos, hub_base):
        """Cria uma rota real de retorno ao hub usando o grafo do OSMnx."""
        from .rede_service import DetailedRoute, RouteWaypoint
        import networkx as nx
        import osmnx as ox
        import math

        def haversine(lat1, lon1, lat2, lon2):
            R = 6371  # km
            lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
            dlat = lat2 - lat1
            dlon = lat2 - lon1
            a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
            c = 2 * math.asin(math.sqrt(a))
            return R * c

        try:
            G = self.rede_service.real_network_graph
            if G is None:
                print("⚠️ Grafo real não disponível.")
                return None

            # Encontrar nós mais próximos
            origin_node = ox.distance.nearest_nodes(G, current_pos.longitude, current_pos.latitude)
            dest_node = ox.distance.nearest_nodes(G, hub_base.longitude, hub_base.latitude)

            # Calcular menor caminho baseado em tempo de viagem
            path = nx.shortest_path(G, origin_node, dest_node, weight="travel_time")

            waypoints = []
            total_distance = 0.0
            total_time = 0.0

            for i, node in enumerate(path):
                data = G.nodes[node]
                lat = data["y"]
                lon = data["x"]
                waypoints.append(RouteWaypoint(
                    latitude=lat,
                    longitude=lon,
                    sequence=i,
                    estimated_time=0.0,  # será atualizado depois
                    is_stop=(i == 0 or i == len(path) - 1)
                ))
                if i > 0:
                    prev = G.nodes[path[i - 1]]
                    dist = haversine(prev["y"], prev["x"], lat, lon)
                    total_distance += dist

            # Estimar tempo com base na distância total
            average_speed_kmh = 30.0  # velocidade média urbana
            estimated_duration = (total_distance / average_speed_kmh) * 60  # minutos

            # Preencher tempos estimados nos waypoints
            cumulative_time = 0.0
            for i in range(len(waypoints)):
                if i == 0:
                    waypoints[i].estimated_time = 0.0
                else:
                    a = waypoints[i - 1]
                    b = waypoints[i]
                    seg_dist = haversine(a.latitude, a.longitude, b.latitude, b.longitude)
                    time = (seg_dist / total_distance) * estimated_duration
                    cumulative_time += time
                    waypoints[i].estimated_time = cumulative_time

            return DetailedRoute(
                route_id=route_id,
                origin_id=f"coord_{current_pos.latitude}_{current_pos.longitude}",
                destination_id=hub_base.id,
                waypoints=waypoints,
                total_distance=total_distance,
                estimated_duration=estimated_duration,
                optimized=True
            )

        except Exception as e:
            print(f"❌ Erro ao criar rota de retorno usando grafo: {e}")
            return None

    
    async def _vehicle_arrived_at_hub(self, rede_id: str, vehicle_id: str, 
                                     state: VehicleMovementState, current_time: datetime):
        """Processa a chegada do veículo ao hub."""
        try:
            rede = self.rede_service.redes_cache[rede_id]
            vehicle = next((v for v in rede.veiculos if v.id == vehicle_id), None)
            
            if vehicle:
                hub_base = next((h for h in rede.hubs if h.id == vehicle.hub_base), None)
                if hub_base:
                    # Posicionar veículo no hub
                    self.rede_service.atualizar_posicao_veiculo(
                        vehicle_id=vehicle_id,
                        latitude=hub_base.latitude + random.uniform(-0.001, 0.001),
                        longitude=hub_base.longitude + random.uniform(-0.001, 0.001),
                        speed=0.0,  # Zera a velocidade
                        heading=random.uniform(0, 360),
                        status="refueling"  # Novo status para reabastecimento
                    )
                    # Limpar rota de retorno
                    if state.route_id and state.route_id in self.rede_service.detailed_routes:
                        del self.rede_service.detailed_routes[state.route_id]
                    # Configurar para reabastecimento
                    state.status = "refueling"  # Atualiza status do backend
                    state.route_id = None
                    state.progress_percent = 0.0
                    state.movement_speed = 0.0  # Garante velocidade zero
                    # Tempo de reabastecimento entre 1.5 e 2 minutos
                    state.pause_until = current_time + timedelta(minutes=random.uniform(1.5, 2.0))
                    print(f"🏠 Veículo {vehicle_id} chegou ao hub e está pegando outra encomenda.")

                    # NOVO: Verificar se todos os veículos estão idle e não há mais clientes
                    if self._should_finish_simulation(rede_id):
                        print("✅ Todos os clientes foram atendidos. Finalizando rastreamento de entregas.")
                        self.stop_automatic_movement()
        except Exception as e:
            print(f"❌ Erro ao processar chegada no hub: {e}")

    def _should_finish_simulation(self, rede_id: str) -> bool:
        """Retorna True se todos os veículos estão idle e não há mais clientes para atender."""
        # Todos os veículos precisam estar idle
        all_idle = all(state.status == "idle" for state in self.vehicle_states.values())
        # Não pode haver clientes disponíveis
        rede = self.rede_service.redes_cache.get(rede_id)
        if not rede:
            return False
        atendidos = self.clientes_atendidos.get(rede_id, set())
        em_atendimento = set(
            state.current_client_id for state in self.vehicle_states.values() if state.current_client_id
        )
        clientes_disponiveis = [c for c in rede.clientes if c.id not in atendidos and c.id not in em_atendimento]
        return all_idle and not clientes_disponiveis
    async def _direct_return_to_hub(self, rede_id: str, vehicle_id: str, 
                                   state: VehicleMovementState, current_time: datetime, time_delta: float):
        """Gerencia retorno direto ao hub com movimento real e contínuo."""
        try:
            rede = self.rede_service.redes_cache[rede_id]
            vehicle = next((v for v in rede.veiculos if v.id == vehicle_id), None)
            
            if vehicle:
                hub_base = next((h for h in rede.hubs if h.id == vehicle.hub_base), None)
                current_pos = self.rede_service.obter_posicao_veiculo(vehicle_id)
                
                if hub_base and current_pos:
                    # Calcular progresso incremental baseado na velocidade
                    progress_increment = state.movement_speed * (time_delta / 60.0)  # % por minuto
                    new_progress = min(100.0, state.progress_percent + progress_increment)

                    # Usar coordenadas armazenadas no estado ou calcular se não existirem
                    if state.return_start_lat is None or state.return_start_lon is None:
                        state.return_start_lat = current_pos.latitude
                        state.return_start_lon = current_pos.longitude
                        state.hub_target_lat = hub_base.latitude
                        state.hub_target_lon = hub_base.longitude
                    
                    # Verificar se todas as coordenadas estão definidas
                    if (state.return_start_lat is not None and state.return_start_lon is not None and
                        state.hub_target_lat is not None and state.hub_target_lon is not None):
                        
                        # Interpolar posição baseada no progresso
                        progress_ratio = new_progress / 100.0
                        new_lat = state.return_start_lat + (state.hub_target_lat - state.return_start_lat) * progress_ratio
                        new_lon = state.return_start_lon + (state.hub_target_lon - state.return_start_lon) * progress_ratio
                        
                        # Calcular heading em direção ao hub
                        heading = self._calculate_heading_to_hub(current_pos, hub_base)
                        
                        # Atualizar posição com movimento realístico
                        self.rede_service.atualizar_posicao_veiculo(
                            vehicle_id=vehicle_id,
                            latitude=new_lat,
                            longitude=new_lon,
                            speed=random.uniform(25, 40),  # Velocidade de retorno
                            heading=heading,
                            status="returning"
                        )
                        
                        state.progress_percent = new_progress
                        
                        # Verificar se chegou ao hub
                        if new_progress >= 100.0:
                            await self._vehicle_arrived_at_hub(rede_id, vehicle_id, state,current_time)                      
                    else:
                        print(f"⚠️ Coordenadas inválidas para retorno do veículo {vehicle_id}")
                else:
                    print(f"⚠️ Não foi possível obter posição ou hub base para veículo {vehicle_id}")
                        
        except Exception as e:
            print(f"❌ Erro no retorno direto: {e}")
            
    def _calculate_heading_to_hub(self, current_pos, hub_base) -> float:
        """Calcula a direção (heading) do ponto atual para o hub."""
        try:
            lat_diff = hub_base.latitude - current_pos.latitude
            lon_diff = hub_base.longitude - current_pos.longitude

            # Calcular ângulo em radianos e converter para graus
            angle_rad = math.atan2(lon_diff, lat_diff)
            angle_deg = math.degrees(angle_rad)

            # Normalizar para 0-360
            if angle_deg < 0:
                angle_deg += 360

            return angle_deg
        except Exception as e:
            print(f"⚠️ Erro ao calcular heading: {e}")
            return random.uniform(0, 360)
    
    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calcula a distância em km entre dois pontos geográficos usando a fórmula de Haversine."""
        R = 6371  # Raio da Terra em km
        lat1_rad, lon1_rad, lat2_rad, lon2_rad = map(math.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2_rad - lat1_rad
        dlon = lat2_rad - lon1_rad
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        c = 2 * math.asin(math.sqrt(a))
        return R * c

    def get_movement_statistics(self, rede_id: str = None):
        """Retorna estatísticas básicas de movimentação dos veículos. (Stub seguro)"""
        # Você pode expandir para retornar estatísticas reais depois
        return {}
