#!/usr/bin/env python3
"""
Test script to verify WebSocket connection state handling fixes
"""

import asyncio
import websockets
import json
import time
import sys
import pytest
from concurrent.futures import ThreadPoolExecutor

@pytest.mark.asyncio 
async def test_websocket_connection(network_id="test_network", duration=10):
    """Test WebSocket connection with simulated disconnection"""
    uri = f"ws://localhost:8000/tracking/{network_id}?token=test_token"
    
    try:
        print(f"🔌 Conectando ao WebSocket: {uri}")
        async with websockets.connect(uri) as websocket:
            print("✓ Conectado com sucesso")
            
            # Aguardar algumas mensagens
            await asyncio.sleep(duration)
            
            print("📤 Enviando comando de teste...")
            test_command = {
                "command": "get_traffic_stats"
            }
            await websocket.send(json.dumps(test_command))
            
            # Aguardar resposta
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                print(f"📨 Resposta recebida: {response[:100]}...")
            except asyncio.TimeoutError:
                print("⏰ Timeout aguardando resposta")
            
            print("🔌 Fechando conexão...")
            
    except Exception as e:
        print(f"❌ Erro na conexão WebSocket: {e}")

@pytest.mark.asyncio
async def test_multiple_connections():
    """Test multiple connections to simulate production load"""
    print("🚀 Testando múltiplas conexões WebSocket...")
    
    tasks = []
    for i in range(3):
        task = asyncio.create_task(
            test_websocket_connection(f"test_network_{i}", duration=5)
        )
        tasks.append(task)
        await asyncio.sleep(1)  # Aguardar 1 segundo entre conexões
    
    # Aguardar todas as tarefas
    await asyncio.gather(*tasks, return_exceptions=True)
    
    print("✓ Teste de múltiplas conexões concluído")

@pytest.mark.asyncio
async def test_abrupt_disconnection():
    """Test abrupt disconnection to verify error handling"""
    uri = "ws://localhost:8000/tracking/test_abrupt?token=test_token"
    
    try:
        print("🔌 Testando desconexão abrupta...")
        websocket = await websockets.connect(uri)
        print("✓ Conectado")
        
        # Aguardar um pouco
        await asyncio.sleep(2)
        
        # Fechar abruptamente sem seguir protocolo
        await websocket.close()
        print("💥 Conexão fechada abruptamente")
        
        # Aguardar para ver se há erros no servidor
        await asyncio.sleep(5)
        
    except Exception as e:
        print(f"❌ Erro esperado: {e}")

async def main():
    """Execute all tests"""
    print("🧪 Iniciando testes de WebSocket...")
    
    # Teste 1: Conexão única
    print("\n=== Teste 1: Conexão única ===")
    await test_websocket_connection("single_test", 8)
    
    # Aguardar um pouco
    await asyncio.sleep(3)
    
    # Teste 2: Múltiplas conexões
    print("\n=== Teste 2: Múltiplas conexões ===")
    await test_multiple_connections()
    
    # Aguardar um pouco
    await asyncio.sleep(3)
    
    # Teste 3: Desconexão abrupta
    print("\n=== Teste 3: Desconexão abrupta ===")
    await test_abrupt_disconnection()
    
    print("\n✅ Todos os testes concluídos!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Testes interrompidos pelo usuário")
    except Exception as e:
        print(f"\n❌ Erro durante os testes: {e}")
