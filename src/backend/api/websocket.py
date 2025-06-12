from jose import JWTError, jwt
import asyncio
import json
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Set, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse
from starlette.websockets import WebSocketState

from ..services.rede_service import RedeService

# Função utilitária para timestamps brasileiros
def get_brazilian_timestamp() -> datetime:
    """Retorna timestamp atual no fuso horário brasileiro (UTC-3)"""
    brazilian_tz = timezone(timedelta(hours=-3))
    return datetime.now(brazilian_tz)
from ..services.vehicle_movement_service import VehicleMovementService
from ..dependencies import get_rede_service
from ..auth.auth import User, get_current_active_user, SECRET_KEY, ALGORITHM


class ConnectionManager:
    """Gerencia conexões WebSocket ativas para diferentes redes"""
    
    def __init__(self):
        # Conexões ativas por rede_id
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Dados da última atualização por rede_id
        self.last_data: Dict[str, Dict[str, Any]] = {}
        # Status de transmissão ativa
        self.broadcasting: Dict[str, bool] = {}
        # Serviços de movimento por rede
        self.movement_services: Dict[str, VehicleMovementService] = {}
    
    async def connect(self, websocket: WebSocket, rede_id: str):
        """Conecta um novo cliente WebSocket a uma rede específica"""
        await websocket.accept()
        
        if rede_id not in self.active_connections:
            self.active_connections[rede_id] = set()
        
        self.active_connections[rede_id].add(websocket)
        print(f"✓ Cliente conectado à rede {rede_id}. Total: {len(self.active_connections[rede_id])}")
    
    def disconnect(self, websocket: WebSocket, rede_id: str):
        """Remove conexão WebSocket de uma rede"""
        if rede_id in self.active_connections:
            self.active_connections[rede_id].discard(websocket)
            print(f"✓ Cliente desconectado da rede {rede_id}. Restantes: {len(self.active_connections[rede_id])}")
            
            # Remove rede se não houver mais conexões
            if not self.active_connections[rede_id]:
                print(f"🧹 Limpando dados para rede {rede_id} sem conexões ativas")
                del self.active_connections[rede_id]
                if rede_id in self.last_data:
                    del self.last_data[rede_id]
                if rede_id in self.broadcasting:
                    self.broadcasting[rede_id] = False
                # Parar movimento automático se não há mais clientes
                if rede_id in self.movement_services:
                    self.movement_services[rede_id].stop_automatic_movement()
                    del self.movement_services[rede_id]
    
    def cleanup_inactive_connections(self, rede_id: str):
        """Remove conexões inativas de uma rede específica"""
        if rede_id not in self.active_connections:
            return
        
        inactive_connections = set()
        for connection in self.active_connections[rede_id]:
            if connection.client_state != WebSocketState.CONNECTED:
                inactive_connections.add(connection)
        
        for conn in inactive_connections:
            self.active_connections[rede_id].discard(conn)
                    
        # Se não há mais conexões após limpeza, desativar broadcast
        if len(self.active_connections[rede_id]) == 0:
            self.broadcasting[rede_id] = False
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Envia mensagem para um cliente específico"""
        try:
            # Verificar se a conexão ainda está ativa
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_text(message)
            else:
                print(f"⚠️ Tentativa de envio para WebSocket fechado (estado: {websocket.client_state})")
        except Exception as e:
            print(f"❌ Erro ao enviar mensagem pessoal: {e}")
    
    async def broadcast_to_network(self, rede_id: str, data: Dict[str, Any]):
        """Envia dados para todos os clientes conectados a uma rede"""
        if rede_id not in self.active_connections:
            return
        
        message = json.dumps(data)
        disconnected = set()
        
        # Criar uma cópia do conjunto para evitar modificação durante iteração
        connections_copy = self.active_connections[rede_id].copy()
        
        for connection in connections_copy:
            try:
                # Verificar se a conexão ainda está ativa antes de enviar
                if connection.client_state == WebSocketState.CONNECTED:
                    await connection.send_text(message)
                else:
                    print(f"⚠️ Removendo conexão inativa (estado: {connection.client_state})")
                    disconnected.add(connection)
            except Exception as e:
                print(f"❌ Erro ao transmitir para cliente: {e}")
                disconnected.add(connection)
        
        # Remove conexões quebradas
        for conn in disconnected:
            self.active_connections[rede_id].discard(conn)
            
        # Se não há mais conexões ativas, limpar dados da rede
        if rede_id in self.active_connections and len(self.active_connections[rede_id]) == 0:
            del self.active_connections[rede_id]
            if rede_id in self.last_data:
                del self.last_data[rede_id]
            if rede_id in self.broadcasting:
                self.broadcasting[rede_id] = False
    
    def get_network_stats(self, rede_id: str) -> Dict[str, Any]:
        """Obtém estatísticas de conexão para uma rede"""
        connections_count = len(self.active_connections.get(rede_id, set()))
        is_broadcasting = self.broadcasting.get(rede_id, False)
        last_update = None
        movement_stats = {}
        
        if rede_id in self.last_data:
            last_update = self.last_data[rede_id].get("timestamp")
        
        if rede_id in self.movement_services:
            movement_stats = self.movement_services[rede_id].get_movement_statistics()
        
        return {
            "rede_id": rede_id,
            "active_connections": connections_count,
            "is_broadcasting": is_broadcasting,
            "last_update": last_update,
            "movement_stats": movement_stats
        }


# Instância global do gerenciador de conexões
manager = ConnectionManager()

router = APIRouter(
    tags=["WebSocket - Rastreamento em Tempo Real"],
)


@router.websocket("/tracking/{rede_id}")
async def websocket_endpoint(
    websocket: WebSocket, 
    rede_id: str,
    rede_service: RedeService = Depends(get_rede_service)
):
    """
    Endpoint WebSocket principal para rastreamento em tempo real de uma rede.
    
    Args:
        rede_id: ID da rede para rastreamento
        
    Fornece em tempo real:
        - Posições GPS dos veículos
        - Rotas otimizadas com waypoints
        - Estatísticas de tráfego
        - Informações da rede (nós, arestas)
    """
    print(f"🔌 Nova conexão WebSocket para rede: {rede_id}")
    
    await manager.connect(websocket, rede_id)
    
    try:
        # Enviar dados iniciais da rede
        try:
            network_data = rede_service.exportar_dados_websocket(rede_id)
            await manager.send_personal_message(
                json.dumps({
                    "type": "initial_data",
                    "data": network_data
                }), 
                websocket
            )
        except Exception as e:
            await manager.send_personal_message(
                json.dumps({
                    "type": "error",
                    "message": f"Erro ao carregar dados da rede: {str(e)}"
                }), 
                websocket
            )
        
        # Iniciar transmissão em tempo real se ainda não estiver ativa
        if not manager.broadcasting.get(rede_id, False):
            manager.broadcasting[rede_id] = True
            
            # Iniciar serviço de movimento automático se não existe
            if rede_id not in manager.movement_services:
                movement_service = VehicleMovementService(rede_service)
                manager.movement_services[rede_id] = movement_service
                asyncio.create_task(movement_service.start_automatic_movement(rede_id))
                print(f"🚀 Movimento automático iniciado para rede {rede_id}")
            
            asyncio.create_task(broadcast_real_time_updates(rede_id, rede_service))
            # Iniciar tarefa de limpeza periódica de conexões inativas
            asyncio.create_task(periodic_cleanup(rede_id))
        
        # Manter conexão ativa e aguardar mensagens do cliente
        while True:
            try:
                # Aguardar mensagem do cliente
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Processar comandos do cliente
                await handle_client_message(websocket, rede_id, message, rede_service)
                
            except WebSocketDisconnect:
                break
            except Exception as e:
                await manager.send_personal_message(
                    json.dumps({
                        "type": "error", 
                        "message": f"Erro ao processar mensagem: {str(e)}"
                    }), 
                    websocket
                )
    
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, rede_id)
        
        # Parar transmissão se não houver mais clientes
        if rede_id not in manager.active_connections:
            manager.broadcasting[rede_id] = False


async def handle_client_message(
    websocket: WebSocket, 
    rede_id: str, 
    message: Dict[str, Any],
    rede_service: RedeService
):
    """Processa mensagens recebidas do cliente WebSocket"""
    
    command = message.get("command")
    
    if command == "update_vehicle_position":
        # Cliente solicita atualização de posição de veículo
        vehicle_data = message.get("data", {})
        try:
            rede_service.atualizar_posicao_veiculo(
                vehicle_id=vehicle_data.get("vehicle_id"),
                latitude=vehicle_data.get("latitude"),
                longitude=vehicle_data.get("longitude"),
                speed=vehicle_data.get("speed", 0),
                heading=vehicle_data.get("heading", 0),
                status=vehicle_data.get("status", "moving")
            )
            
            await manager.send_personal_message(
                json.dumps({
                    "type": "command_response",
                    "command": "update_vehicle_position",
                    "status": "success"
                }), 
                websocket
            )
        except Exception as e:
            await manager.send_personal_message(
                json.dumps({
                    "type": "command_response",
                    "command": "update_vehicle_position",
                    "status": "error",
                    "message": str(e)
                }), 
                websocket
            )
    
    elif command == "generate_route":
        # Cliente solicita geração de nova rota
        route_data = message.get("data", {})
        try:
            route = rede_service.calcular_rota_detalhada(
                origin_lat=route_data.get("origin_lat"),
                origin_lon=route_data.get("origin_lon"), 
                dest_lat=route_data.get("dest_lat"),
                dest_lon=route_data.get("dest_lon"),
                route_id=route_data.get("route_id", f"route_{int(time.time())}")
            )
            
            if route:
                await manager.send_personal_message(
                    json.dumps({
                        "type": "command_response",
                        "command": "generate_route",
                        "status": "success",
                        "data": {
                            "route_id": route.route_id,
                            "total_distance": route.total_distance,
                            "estimated_duration": route.estimated_duration,
                            "waypoints_count": len(route.waypoints)
                        }
                    }), 
                    websocket
                )
            else:
                await manager.send_personal_message(
                    json.dumps({
                        "type": "command_response",
                        "command": "generate_route",
                        "status": "error",
                        "message": "Não foi possível calcular a rota"
                    }), 
                    websocket
                )
        except Exception as e:
            await manager.send_personal_message(
                json.dumps({
                    "type": "command_response",
                    "command": "generate_route",
                    "status": "error",
                    "message": str(e)
                }), 
                websocket
            )
    
    elif command == "get_traffic_stats":
        # Cliente solicita estatísticas de tráfego
        try:
            stats = rede_service.obter_estatisticas_trafego()
            
            await manager.send_personal_message(
                json.dumps({
                    "type": "command_response",
                    "command": "get_traffic_stats",
                    "status": "success",
                    "data": stats
                }), 
                websocket
            )
        except Exception as e:
            await manager.send_personal_message(
                json.dumps({
                    "type": "command_response",
                    "command": "get_traffic_stats",
                    "status": "error",
                    "message": str(e)
                }), 
                websocket
            )
    
    elif command == "start_movement":
        # Cliente solicita iniciar movimento automático
        try:
            if rede_id not in manager.movement_services:
                movement_service = VehicleMovementService(rede_service)
                manager.movement_services[rede_id] = movement_service
                await movement_service.start_automatic_movement(rede_id)
            
            await manager.send_personal_message(
                json.dumps({
                    "type": "command_response",
                    "command": "start_movement",
                    "status": "success",
                    "message": "Movimento automático iniciado"
                }), 
                websocket
            )
        except Exception as e:
            await manager.send_personal_message(
                json.dumps({
                    "type": "command_response",
                    "command": "start_movement",
                    "status": "error",
                    "message": str(e)
                }), 
                websocket
            )
    
    elif command == "stop_movement":
        # Cliente solicita parar movimento automático
        try:
            if rede_id in manager.movement_services:
                manager.movement_services[rede_id].stop_automatic_movement()
            
            await manager.send_personal_message(
                json.dumps({
                    "type": "command_response",
                    "command": "stop_movement",
                    "status": "success",
                    "message": "Movimento automático parado"
                }), 
                websocket
            )
        except Exception as e:
            await manager.send_personal_message(
                json.dumps({
                    "type": "command_response",
                    "command": "stop_movement",
                    "status": "error",
                    "message": str(e)
                }), 
                websocket
            )
    
    elif command == "get_movement_stats":
        # Cliente solicita estatísticas de movimento
        try:
            if rede_id in manager.movement_services:
                stats = manager.movement_services[rede_id].get_movement_statistics()
            else:
                stats = {"message": "Movimento automático não iniciado"}
            
            await manager.send_personal_message(
                json.dumps({
                    "type": "command_response",
                    "command": "get_movement_stats",
                    "status": "success",
                    "data": stats
                }), 
                websocket
            )
        except Exception as e:
            await manager.send_personal_message(
                json.dumps({
                    "type": "command_response",
                    "command": "get_movement_stats",
                    "status": "error",
                    "message": str(e)
                }), 
                websocket
            )
    
    else:
        await manager.send_personal_message(
            json.dumps({
                "type": "error",
                "message": f"Comando desconhecido: {command}"
            }), 
            websocket
        )


async def broadcast_real_time_updates(rede_id: str, rede_service: RedeService):
    """Transmite atualizações em tempo real para todos os clientes conectados"""
    
    while manager.broadcasting.get(rede_id, False):
        try:
            # Verificar se ainda há conexões ativas para esta rede
            if rede_id not in manager.active_connections or len(manager.active_connections[rede_id]) == 0:
                print(f"⚠️ Nenhuma conexão ativa para rede {rede_id}, parando broadcast")
                manager.broadcasting[rede_id] = False
                break
            
            # Obter dados atualizados
            current_data = rede_service.obter_dados_websocket(rede_id)
            
            # Verificar se os dados mudaram
            if (rede_id not in manager.last_data or 
                current_data != manager.last_data[rede_id]):
                
                manager.last_data[rede_id] = current_data
                await manager.broadcast_to_network(rede_id, current_data)
            
            # Aguardar antes da próxima atualização (2 segundos)
            await asyncio.sleep(2.0)
            
        except Exception as e:
            print(f"❌ Erro na transmissão em tempo real: {e}")
            await asyncio.sleep(5.0)  # Aguardar mais tempo em caso de erro


async def periodic_cleanup(rede_id: str):
    """Realiza limpeza periódica de conexões inativas"""
    while manager.broadcasting.get(rede_id, False):
        try:
            await asyncio.sleep(30)  # Executar a cada 30 segundos
            manager.cleanup_inactive_connections(rede_id)
        except Exception as e:
            print(f"❌ Erro na limpeza periódica para rede {rede_id}: {e}")
            await asyncio.sleep(60)  # Aguardar mais tempo em caso de erro


@router.get(
    "/status/{rede_id}",
    summary="Status da transmissão WebSocket",
    description="Obtém estatísticas sobre conexões WebSocket ativas para uma rede"
)
async def get_websocket_status(
    rede_id: str,
    current_user: User = Depends(get_current_active_user)
) -> JSONResponse:
    """
    Obtém estatísticas sobre as conexões WebSocket para uma rede específica.
    
    Returns:
        Estatísticas de conexão e status da transmissão
    """
    stats = manager.get_network_stats(rede_id)
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "success",
            "message": "Status WebSocket obtido com sucesso",
            "data": stats
        }
    )


@router.get(
    "/status",
    summary="Status geral do WebSocket",
    description="Obtém estatísticas sobre todas as conexões WebSocket ativas"
)
async def get_all_websocket_status(
    current_user: User = Depends(get_current_active_user)
) -> JSONResponse:
    """
    Obtém estatísticas sobre todas as conexões WebSocket ativas.
    
    Returns:
        Lista com estatísticas de todas as redes com conexões ativas
    """
    all_stats = []
    
    for rede_id in manager.active_connections.keys():
        all_stats.append(manager.get_network_stats(rede_id))
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "success",
            "message": "Status geral WebSocket obtido com sucesso",
            "data": {
                "total_networks": len(all_stats),
                "total_connections": sum(stat["active_connections"] for stat in all_stats),
                "networks": all_stats
            }
        }
    )


@router.post(
    "/simulate/{rede_id}",
    summary="Iniciar simulação de rastreamento",
    description="Inicia simulação de movimento de veículos para demonstração"
)
async def start_vehicle_simulation(
    rede_id: str,
    rede_service: RedeService = Depends(get_rede_service),
    current_user: User = Depends(get_current_active_user)
) -> JSONResponse:
    """
    Inicia simulação de movimento de veículos para demonstração do WebSocket.
    
    A simulação cria veículos virtuais e simula seus movimentos na rede.
    """
    try:
        # Verificar se a rede existe
        if rede_id not in rede_service.redes_cache:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rede não encontrada"
            )
        
        # Iniciar simulação em background
        asyncio.create_task(run_vehicle_simulation(rede_id, rede_service))
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "success",
                "message": f"Simulação iniciada para rede {rede_id}",
                "data": {
                    "rede_id": rede_id,
                    "simulation_started": get_brazilian_timestamp().isoformat()
                }
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao iniciar simulação: {str(e)}"
        )


async def run_vehicle_simulation(rede_id: str, rede_service: RedeService):
    """Executa simulação de movimento de veículos"""
    try:
        # Simular movimento de 3 veículos por 5 minutos
        simulation_duration = 300  # 5 minutos
        start_time = get_brazilian_timestamp()
        
        vehicle_ids = ["sim_vehicle_1", "sim_vehicle_2", "sim_vehicle_3"]
        
        while (get_brazilian_timestamp() - start_time).seconds < simulation_duration:
            for vehicle_id in vehicle_ids:
                # Simular movimento básico de veículo
                try:
                    # Usar coordenadas de Maceió para simulação
                    import random
                    lat = -9.6662 + random.uniform(-0.05, 0.05)  # Centro de Maceió +/- variação
                    lon = -35.7351 + random.uniform(-0.05, 0.05)
                    speed = random.uniform(15.0, 45.0)
                    heading = random.uniform(0, 360)
                    
                    rede_service.atualizar_posicao_veiculo(
                        vehicle_id=vehicle_id,
                        latitude=lat,
                        longitude=lon,
                        speed=speed,
                        heading=heading,
                        status="moving"
                    )
                except Exception as e:
                    print(f"❌ Erro ao simular veículo {vehicle_id}: {e}")
            
            # Aguardar 10 segundos antes da próxima atualização
            await asyncio.sleep(10)
        
        print(f"✓ Simulação de veículos concluída para rede {rede_id}")
        
    except Exception as e:
        print(f"❌ Erro na simulação de veículos: {e}")
