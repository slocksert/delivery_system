"""
Serviço de movimentação automática de veículos para simulação realista.
"""
import asyncio
import random
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from .rede_service import RedeService, VehiclePosition, DetailedRoute


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
        
    async def start_automatic_movement(self, rede_id: str):
        """Inicia movimentação automática para todos os veículos de uma rede."""
        if self.is_running:
            return
        
        self.is_running = True
        print(f"🚀 Iniciando movimentação automática para rede {rede_id}")
        
        # Inicializar estados dos veículos
        await self._initialize_vehicle_states(rede_id)
        
        # Loop principal de movimentação
        asyncio.create_task(self._movement_loop(rede_id))
    
    def stop_automatic_movement(self):
        """Para a movimentação automática."""
        self.is_running = False
        print("⏹️ Movimentação automática interrompida")
    
    async def _initialize_vehicle_states(self, rede_id: str):
        """Inicializa estados de movimento dos veículos."""
        
        if rede_id not in self.rede_service.redes_cache:
            return
        
        rede = self.rede_service.redes_cache[rede_id]
        
        for vehicle in rede.veiculos:
            # Verificar se já tem posição
            position = self.rede_service.obter_posicao_veiculo(vehicle.id)
            
            if position:
                # Determinar status inicial baseado na posição atual
                if position.status == "moving" and position.speed > 5:
                    # Veículo em movimento - tentar encontrar rota ativa
                    route_id = self._find_active_route_for_vehicle(vehicle.id)
                    if route_id:
                        # Calcular progresso atual na rota
                        progress = self._calculate_current_progress(vehicle.id, route_id)
                        self.vehicle_states[vehicle.id] = VehicleMovementState(
                            vehicle_id=vehicle.id,
                            route_id=route_id,
                            progress_percent=progress,
                            status="moving",
                            last_update=datetime.now(),
                            movement_speed=random.uniform(8.0, 15.0)  # % por minuto (velocidade mais alta)
                        )
                    else:
                        # Criar nova rota para veículo em movimento
                        await self._assign_new_route(rede_id, vehicle.id)
                elif position.status == "delivering":
                    # Veículo entregando - pausar por um tempo
                    self.vehicle_states[vehicle.id] = VehicleMovementState(
                        vehicle_id=vehicle.id,
                        status="delivering",
                        last_update=datetime.now(),
                        pause_until=datetime.now() + timedelta(minutes=random.randint(5, 15))
                    )
                else:
                    # Veículo idle - decidir se deve sair para entrega
                    if random.random() < 0.3:  # 30% chance de sair
                        await self._assign_new_route(rede_id, vehicle.id)
                    else:
                        self.vehicle_states[vehicle.id] = VehicleMovementState(
                            vehicle_id=vehicle.id,
                            status="idle",
                            last_update=datetime.now()
                        )
            else:
                # Criar posição inicial se não existe
                await self._create_initial_position(rede_id, vehicle)
        
        print(f"✅ Estados inicializados para {len(self.vehicle_states)} veículos")
    
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
        """Atribui nova rota para um veículo."""
        try:
            rede = self.rede_service.redes_cache[rede_id]
            
            # Selecionar clientes aleatórios para visitar
            if rede.clientes:
                # Selecionar alguns clientes aleatórios para visitar
                num_clients = random.randint(1, min(3, len(rede.clientes)))
                selected_clients = random.sample(rede.clientes, num_clients)
                client_ids = [c.id for c in selected_clients]
                
                # Gerar rotas otimizadas
                routes = self.rede_service.obter_rotas_otimizadas_para_veiculo(
                    rede_id, vehicle_id, client_ids
                )
                
                if routes:
                    # Usar primeira rota
                    first_route = routes[0]
                    
                    # Criar estado de movimento
                    self.vehicle_states[vehicle_id] = VehicleMovementState(
                        vehicle_id=vehicle_id,
                        route_id=first_route.route_id,
                        progress_percent=0.0,
                        status="moving",
                        last_update=datetime.now(),
                        movement_speed=random.uniform(10.0, 20.0),  # % por minuto (velocidade alta)
                        target_progress=100.0,
                        current_client_id=client_ids[0]  # Primeiro cliente da rota
                    )
                    
                    print(f"🛣️ Nova rota atribuída ao veículo {vehicle_id}: {first_route.route_id} -> Cliente {client_ids[0]}")
                else:
                    # Não conseguiu criar rota - manter idle
                    self.vehicle_states[vehicle_id] = VehicleMovementState(
                        vehicle_id=vehicle_id,
                        status="idle",
                        last_update=datetime.now()
                    )
        except Exception as e:
            print(f"❌ Erro ao atribuir rota para veículo {vehicle_id}: {e}")
    
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
                # Criar posição próxima ao hub
                lat_variation = random.uniform(-0.001, 0.001)
                lon_variation = random.uniform(-0.001, 0.001)
                
                self.rede_service.atualizar_posicao_veiculo(
                    vehicle_id=vehicle.id,
                    latitude=hub_base.latitude + lat_variation,
                    longitude=hub_base.longitude + lon_variation,
                    speed=0.0,
                    heading=random.uniform(0, 360),
                    status="idle"
                )
                
                # Criar estado idle
                self.vehicle_states[vehicle.id] = VehicleMovementState(
                    vehicle_id=vehicle.id,
                    status="idle",
                    last_update=datetime.now()
                )
                
                print(f"📍 Posição inicial criada para veículo {vehicle.id}")
        except Exception as e:
            print(f"❌ Erro ao criar posição inicial para veículo {vehicle.id}: {e}")
    
    async def _movement_loop(self, rede_id: str):
        """Loop principal de movimentação dos veículos."""
        
        while self.is_running:
            try:
                current_time = datetime.now()
                
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
                progress_increment = state.movement_speed * (time_delta / 60.0)  # movement_speed já está em % por minuto
                new_progress = min(state.target_progress, state.progress_percent + progress_increment)
                
                # Simular movimento ao longo da rota
                new_position = self.rede_service.simular_movimento_veiculo(
                    vehicle_id, state.route_id, new_progress
                )
                
                if new_position:
                    state.progress_percent = new_progress
                    
                    # Adicionar variação de velocidade realística durante o movimento
                    # A velocidade já vem do simular_movimento_veiculo com variação
                    # Mas vamos adicionar pequenas flutuações para simular condições de trânsito
                    if hasattr(new_position, 'speed') and new_position.speed > 0:
                        speed_variation = random.uniform(0.8, 1.2)  # ±20% de variação
                        varied_speed = new_position.speed * speed_variation
                        new_position.speed = max(5.0, min(70.0, varied_speed))
                    
                    # Verificar se chegou ao destino
                    if new_progress >= state.target_progress:
                        # Parar para entrega
                        state.status = "delivering"
                        delivery_time = random.randint(0, 1)  # 2-5 minutos para entrega
                        state.pause_until = current_time + timedelta(minutes=delivery_time)
                        
                        # Atualizar status do veículo
                        self.rede_service.atualizar_posicao_veiculo(
                            vehicle_id=vehicle_id,
                            latitude=new_position.latitude,
                            longitude=new_position.longitude,
                            speed=0.0,
                            heading=new_position.heading,
                            status="delivering"
                        )
                        
                        print(f"📦 Veículo {vehicle_id} chegou ao destino e está entregando (tempo estimado: {delivery_time} min)")
            
            elif state.status == "delivering":
                # Veículo entregando - verificar se terminou
                if not state.pause_until or current_time >= state.pause_until:
                    
                    # Sempre voltar ao hub após entrega com movimento real
                    await self._start_return_to_hub(rede_id, vehicle_id, state, current_time)
                    
                    print(f"🔄 Veículo {vehicle_id} iniciando retorno ao hub com movimento contínuo")
            
            elif state.status == "returning":
                # Veículo retornando - movimentar em direção ao hub
                if state.route_id:
                    # Usando rota de retorno - atualizar progresso
                    progress_increment = state.movement_speed * (time_delta / 60.0)
                    new_progress = min(100.0, state.progress_percent + progress_increment)
                    
                    # Simular movimento de retorno
                    new_position = self.rede_service.simular_movimento_veiculo(
                        vehicle_id, state.route_id, new_progress
                    )
                    
                    if new_position:
                        state.progress_percent = new_progress
                        
                        # Velocidade de retorno
                        if hasattr(new_position, 'speed'):
                            new_position.speed = random.uniform(30, 50)  # Velocidade de retorno
                        
                        # Verificar se chegou ao hub
                        if new_progress >= 100.0:
                            # Chegou ao hub
                            await self._vehicle_arrived_at_hub(rede_id, vehicle_id, state, current_time)
                else:
                    # Sem rota de retorno - usar movimento direto
                    await self._direct_return_to_hub(rede_id, vehicle_id, state, current_time, time_delta)
            
            # Atualizar timestamp
            state.last_update = current_time
            
        except Exception as e:
            print(f"❌ Erro ao atualizar movimento do veículo {vehicle_id}: {e}")
    
    async def _maybe_assign_new_routes(self, rede_id: str):
        """Ocasionalmente atribui novas rotas para veículos idle."""
        
        idle_vehicles = [
            vehicle_id for vehicle_id, state in self.vehicle_states.items()
            if state.status == "idle" and (not state.pause_until or datetime.now() >= state.pause_until)
        ]
        
        if idle_vehicles and random.random() < 0.3:  # 30% chance
            selected_vehicle = random.choice(idle_vehicles)
            await self._assign_new_route(rede_id, selected_vehicle)
    
    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calcula distância entre duas coordenadas."""
        return math.sqrt((lat2 - lat1)**2 + (lon2 - lon1)**2)
    
    def get_movement_statistics(self) -> Dict:
        """Obtém estatísticas de movimento dos veículos."""
        
        stats = {
            'total_vehicles': len(self.vehicle_states),
            'active_vehicles': 0,  # Veículos em movimento ou entregando
            'idle': 0,
            'moving': 0,
            'delivering': 0,
            'returning': 0,
            'is_running': self.is_running,
            'total_routes': len([s for s in self.vehicle_states.values() if s.route_id])
        }
        
        for state in self.vehicle_states.values():
            stats[state.status] = stats.get(state.status, 0) + 1
            
            # Contar veículos ativos (não idle)
            if state.status in ['moving', 'delivering', 'returning']:
                stats['active_vehicles'] += 1
        
        return stats
    
    async def _start_return_to_hub(self, rede_id: str, vehicle_id: str, 
                                  state: VehicleMovementState, current_time: datetime):
        """Inicia o retorno do veículo ao hub com movimento real."""
        try:
            rede = self.rede_service.redes_cache[rede_id]
            vehicle = next((v for v in rede.veiculos if v.id == vehicle_id), None)
            
            if vehicle:
                hub_base = next((h for h in rede.hubs if h.id == vehicle.hub_base), None)
                current_position = self.rede_service.obter_posicao_veiculo(vehicle_id)
                
                if hub_base and current_position:
                    # Criar rota de retorno simples (direta ao hub)
                    return_route_id = f"{vehicle_id}_return_{int(current_time.timestamp())}"
                    
                    # Simular uma rota de retorno
                    return_route = self._create_return_route(
                        return_route_id, 
                        current_position, 
                        hub_base
                    )
                    
                    if return_route:
                        # Armazenar a rota
                        self.rede_service.detailed_routes[return_route_id] = return_route
                        
                        # Configurar estado de retorno
                        state.status = "returning"
                        state.route_id = return_route_id
                        state.progress_percent = 0.0
                        state.current_client_id = None
                        state.movement_speed = random.uniform(12.0, 18.0)  # Velocidade de retorno
                        state.pause_until = None
                        
                        # Atualizar status do veículo
                        self.rede_service.atualizar_posicao_veiculo(
                            vehicle_id=vehicle_id,
                            latitude=current_position.latitude,
                            longitude=current_position.longitude,
                            speed=random.uniform(30, 45),
                            heading=self._calculate_heading_to_hub(current_position, hub_base),
                            status="returning"
                        )
                        
                        print(f"🛣️ Rota de retorno criada para veículo {vehicle_id}: {return_route_id}")
                    else:
                        # Fallback para movimento direto
                        await self._setup_direct_return(rede_id, vehicle_id, state, hub_base)
                        print(f"🔄 Usando retorno direto para veículo {vehicle_id}")
                else:
                    print(f"⚠️ Não foi possível encontrar hub base para veículo {vehicle_id}")
                    
        except Exception as e:
            print(f"❌ Erro ao iniciar retorno ao hub para veículo {vehicle_id}: {e}")
    
    def _create_return_route(self, route_id: str, current_pos, hub_base):
        """Cria uma rota simples de retorno ao hub."""
        from .rede_service import DetailedRoute, RouteWaypoint
        
        try:
            # Criar waypoints simples do ponto atual ao hub
            waypoints = []
            
            # Ponto de partida (posição atual)
            waypoints.append(RouteWaypoint(
                latitude=current_pos.latitude,
                longitude=current_pos.longitude,
                sequence=0,
                estimated_time=0.0,
                is_stop=True
            ))
            
            # Alguns pontos intermediários para simular rota
            lat_diff = hub_base.latitude - current_pos.latitude
            lon_diff = hub_base.longitude - current_pos.longitude
            
            # Criar 2-3 waypoints intermediários
            for i in range(1, 3):
                fraction = i / 3.0
                intermediate_lat = current_pos.latitude + (lat_diff * fraction)
                intermediate_lon = current_pos.longitude + (lon_diff * fraction)
                
                waypoints.append(RouteWaypoint(
                    latitude=intermediate_lat,
                    longitude=intermediate_lon,
                    sequence=i,
                    estimated_time=i * 3.0,  # 3 minutos por waypoint
                    is_stop=False
                ))
            
            # Ponto final (hub)
            waypoints.append(RouteWaypoint(
                latitude=hub_base.latitude,
                longitude=hub_base.longitude,
                sequence=3,
                estimated_time=9.0,  # Tempo total estimado
                is_stop=True
            ))
            
            return DetailedRoute(
                route_id=route_id,
                origin_id=f"client_{current_pos.latitude}_{current_pos.longitude}",
                destination_id=f"hub_{hub_base.id}",
                waypoints=waypoints,
                total_distance=self._calculate_distance(
                    current_pos.latitude, current_pos.longitude,
                    hub_base.latitude, hub_base.longitude
                ) * 111.0,  # Conversão aproximada para km
                estimated_duration=random.uniform(8.0, 15.0),  # 8-15 minutos estimados
                optimized=False
            )
            
        except Exception as e:
            print(f"❌ Erro ao criar rota de retorno: {e}")
            return None
    
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
        except:
            return random.uniform(0, 360)
    
    async def _setup_direct_return(self, rede_id: str, vehicle_id: str, 
                                  state: VehicleMovementState, hub_base):
        """Configura retorno direto sem rota específica com movimento real."""
        current_pos = self.rede_service.obter_posicao_veiculo(vehicle_id)
        if current_pos:
            # Configurar estado de retorno direto
            state.status = "returning"
            state.route_id = None
            state.progress_percent = 0.0
            state.current_client_id = None
            state.movement_speed = random.uniform(15.0, 25.0)  # % por minuto
            state.target_progress = 100.0
            state.pause_until = None  # Remover pause - usar movimento contínuo
            
            # Armazenar coordenadas para interpolação
            state.hub_target_lat = hub_base.latitude
            state.hub_target_lon = hub_base.longitude
            state.return_start_lat = current_pos.latitude
            state.return_start_lon = current_pos.longitude
            
            # Atualizar status do veículo para "returning"
            self.rede_service.atualizar_posicao_veiculo(
                vehicle_id=vehicle_id,
                latitude=current_pos.latitude,
                longitude=current_pos.longitude,
                speed=random.uniform(25, 40),
                heading=self._calculate_heading_to_hub(current_pos, hub_base),
                status="returning"
            )
            
            print(f"🔄 Configurando retorno direto do veículo {vehicle_id} para hub em [{hub_base.latitude}, {hub_base.longitude}]")
    
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
                        speed=0.0,
                        heading=random.uniform(0, 360),
                        status="idle"
                    )
                    
                    # Limpar rota de retorno
                    if state.route_id and state.route_id in self.rede_service.detailed_routes:
                        del self.rede_service.detailed_routes[state.route_id]
                    
                    # Configurar para reabastecimento
                    state.status = "idle"
                    state.route_id = None
                    state.progress_percent = 0.0
                    state.pause_until = current_time + timedelta(minutes=random.randint(2, 5))
                    
                    print(f"🏠 Veículo {vehicle_id} chegou ao hub e está reabastecendo")
                    
        except Exception as e:
            print(f"❌ Erro ao processar chegada no hub: {e}")
    
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
                            await self._vehicle_arrived_at_hub(rede_id, vehicle_id, state, current_time)
                        else:
                            # Debug: mostrar progresso do retorno ocasionalmente
                            if random.random() < 0.1:  # 10% chance de mostrar log
                                print(f"🔄 Veículo {vehicle_id} retornando: {new_progress:.1f}% concluído")
                    else:
                        print(f"⚠️ Coordenadas inválidas para retorno do veículo {vehicle_id}")
                else:
                    print(f"⚠️ Não foi possível obter posição ou hub base para veículo {vehicle_id}")
                        
        except Exception as e:
            print(f"❌ Erro no retorno direto: {e}")
