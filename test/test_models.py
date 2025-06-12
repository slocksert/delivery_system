"""
Testes para verificar a implementação do módulo de modelagem da rede de entrega.
Verifica entidades, funcionalidades da rede, gerador de dados e validações.
"""

import pytest
import json
import os
import tempfile
from datetime import datetime

from src.core.entities.models import (
    Deposito, Hub, Cliente, ZonaEntrega, Veiculo, Pedido, Rota, RedeEntrega,
    TipoVeiculo, StatusPedido, PrioridadeCliente
)
from src.core.generators.gerador_completo import GeradorMaceioCompleto
from src.core.data.loader import carregar_rede_completa


class TestEntidades:
    """Testa criação e funcionamento das entidades básicas"""
    
    def test_deposito_criacao(self):
        deposito = Deposito(
            id="dep_001",
            latitude=-9.6498,
            longitude=-35.7089,
            nome="Depósito Central",
            capacidade_maxima=500
        )
        assert deposito.id == "dep_001"
        assert deposito.capacidade_maxima == 500
        assert deposito.latitude == -9.6498
    
    def test_hub_criacao(self):
        hub = Hub(
            id="hub_001",
            latitude=-9.6658,
            longitude=-35.7350,
            capacidade=100,
            nome="Hub Pajuçara"
        )
        assert hub.capacidade == 100
        assert hub.operacional == True
        assert hub.nome == "Hub Pajuçara"
    
    def test_cliente_criacao(self):
        cliente = Cliente(
            id="cli_001",
            latitude=-9.6400,
            longitude=-35.7300,
            demanda_media=2,
            prioridade=PrioridadeCliente.NORMAL,
            zona_id="zona_01"
        )
        assert cliente.demanda_media == 2
        assert cliente.ativo == True
        assert cliente.prioridade == PrioridadeCliente.NORMAL
    
    def test_rota_criacao(self):
        rota = Rota(
            origem="dep_001",
            destino="hub_001", 
            peso=5.2,
            capacidade=50,
            tempo_medio=15.0
        )
        assert rota.capacidade == 50
        assert rota.ativa == True
        assert rota.peso == 5.2
    
    def test_veiculo_criacao(self):
        veiculo = Veiculo(
            id="vei_001",
            tipo=TipoVeiculo.VAN,
            capacidade=15,
            velocidade_media=45.0,
            hub_base="hub_001",
            condutor="João Silva"
        )
        assert veiculo.tipo == TipoVeiculo.VAN
        assert veiculo.disponivel == True
        assert veiculo.condutor == "João Silva"
    
    def test_pedido_criacao(self):
        pedido = Pedido(
            id="ped_001",
            cliente_id="cli_001",
            prioridade=PrioridadeCliente.ALTA,
            peso=2.5,
            volume=1.2
        )
        assert pedido.prioridade == PrioridadeCliente.ALTA
        assert pedido.status == StatusPedido.PENDENTE
        assert pedido.peso == 2.5


class TestEnums:
    """Testa funcionamento dos enums"""
    
    def test_tipo_veiculo(self):
        assert TipoVeiculo.MOTO.value == "moto"
        assert TipoVeiculo.CAMINHAO.value == "caminhao"
        assert TipoVeiculo.VAN.value == "van"
    
    def test_prioridade_cliente(self):
        assert PrioridadeCliente.URGENTE.value == 4
        assert PrioridadeCliente.CRITICA.value == 5
        assert PrioridadeCliente.NORMAL.value == 2
    
    def test_status_pedido(self):
        assert StatusPedido.PENDENTE.value == "pendente"
        assert StatusPedido.ENTREGUE.value == "entregue"
        assert StatusPedido.EM_ROTA.value == "em_rota"


class TestRedeEntrega:
    """Testa funcionalidades da classe RedeEntrega"""
    
    def setup_method(self):
        """Configura rede básica para testes"""
        self.rede = RedeEntrega()
        
        self.deposito = Deposito("dep_001", -9.6498, -35.7089, "Depósito Central")
        self.hub1 = Hub("hub_001", -9.6658, -35.7350, 100, "Hub Pajuçara")
        self.hub2 = Hub("hub_002", -9.6400, -35.7100, 80, "Hub Centro")
        
        self.cliente1 = Cliente("cli_001", -9.6400, -35.7300, 2, zona_id="zona_01")
        self.cliente2 = Cliente("cli_002", -9.6500, -35.7200, 1, zona_id="zona_01")
        
        self.rede.depositos.append(self.deposito)
        self.rede.hubs.extend([self.hub1, self.hub2])
        self.rede.clientes.extend([self.cliente1, self.cliente2])
    
    def test_obter_vertices(self):
        vertices = self.rede.obter_vertices()
        assert "dep_001" in vertices
        assert "hub_001" in vertices
        assert "cli_001" in vertices
        assert len(vertices) == 5
    
    def test_demanda_total(self):
        demanda = self.rede.obter_demanda_total()
        assert demanda == 3  # 2 + 1
    
    def test_capacidade_total(self):
        capacidade = self.rede.obter_capacidade_total()
        assert capacidade == 180  # 100 + 80
    
    def test_estatisticas(self):
        stats = self.rede.obter_estatisticas()
        assert stats['total_depositos'] == 1
        assert stats['total_hubs'] == 2
        assert stats['total_clientes'] == 2
        assert stats['demanda_total'] == 3
        assert stats['capacidade_total'] == 180
    
    def test_adicionar_cliente(self):
        zona = ZonaEntrega("zona_01", "Zona Teste")
        self.rede.zonas.append(zona)
        
        cliente = Cliente("cli_test", -9.6400, -35.7300, 5, zona_id="zona_01")
        self.rede.adicionar_cliente(cliente)
        
        assert len(self.rede.clientes) == 3  # 2 originais + 1 novo
        assert self.rede.zonas[0].demanda_total == 5
    
    def test_cliente_duplicado_nao_adicionado(self):
        cliente = Cliente("cli_test", -9.6400, -35.7300, 5, zona_id="zona_01")
        self.rede.adicionar_cliente(cliente)
        self.rede.adicionar_cliente(cliente)  # Mesmo cliente
        
        assert len([c for c in self.rede.clientes if c.id == "cli_test"]) == 1


class TestRotasCapacidade:
    """Testa sistema de rotas e capacidades"""
    
    def setup_method(self):
        self.rede = RedeEntrega()
        
        self.rota1 = Rota("dep_001", "hub_001", 5.2, 50)
        self.rota2 = Rota("hub_001", "cli_001", 2.1, 30)
        self.rota3 = Rota("hub_001", "cli_002", 1.8, 20)
        
        self.rede.rotas.extend([self.rota1, self.rota2, self.rota3])
    
    def test_capacidade_rota_especifica(self):
        cap1 = self.rede.obter_capacidade_rota("dep_001", "hub_001")
        assert cap1 == 50
        
        cap2 = self.rede.obter_capacidade_rota("hub_001", "cli_001")
        assert cap2 == 30
    
    def test_rota_inexistente(self):
        cap_zero = self.rede.obter_capacidade_rota("nao_existe", "tambem_nao")
        assert cap_zero == 0


class TestMetodosEspecificos:
    """Testa métodos específicos da RedeEntrega com filtros"""
    
    def setup_method(self):
        self.rede = RedeEntrega()
        
        # Hubs com diferentes status
        hub1 = Hub("hub_001", -9.6658, -35.7350, 100, "Hub 1")
        hub2 = Hub("hub_002", -9.6400, -35.7100, 80, "Hub 2", operacional=False)
        
        # Veículos com diferentes status
        veiculo1 = Veiculo("vei_001", TipoVeiculo.MOTO, 5, 60.0, "hub_001")
        veiculo2 = Veiculo("vei_002", TipoVeiculo.VAN, 15, 50.0, "hub_001", disponivel=False)
        veiculo3 = Veiculo("vei_003", TipoVeiculo.CARRO, 8, 55.0, "hub_002")
        
        # Clientes com diferentes status
        cliente1 = Cliente("cli_001", -9.6400, -35.7300, 3, zona_id="zona_01", ativo=False)
        cliente2 = Cliente("cli_002", -9.6500, -35.7200, 2, zona_id="zona_01")
        
        # Pedidos com diferentes status
        pedido1 = Pedido("ped_001", "cli_001", status=StatusPedido.PENDENTE)
        pedido2 = Pedido("ped_002", "cli_002", status=StatusPedido.ENTREGUE)
        
        self.rede.hubs.extend([hub1, hub2])
        self.rede.veiculos.extend([veiculo1, veiculo2, veiculo3])
        self.rede.clientes.extend([cliente1, cliente2])
        self.rede.pedidos.extend([pedido1, pedido2])
    
    def test_capacidade_hubs_operacionais(self):
        cap_total = self.rede.obter_capacidade_total()
        assert cap_total == 100  # Só hub1 está operacional
    
    def test_demanda_clientes_ativos(self):
        demanda = self.rede.obter_demanda_total()
        assert demanda == 2  # Só cliente2 está ativo
    
    def test_veiculos_disponiveis(self):
        veiculos_disp = self.rede.obter_veiculos_disponiveis()
        assert len(veiculos_disp) == 2  # vei_001 e vei_003
    
    def test_veiculos_hub_especifico(self):
        veiculos_hub1 = self.rede.obter_veiculos_disponiveis("hub_001")
        assert len(veiculos_hub1) == 1  # Só vei_001
    
    def test_pedidos_pendentes(self):
        pendentes = self.rede.obter_pedidos_pendentes()
        assert len(pendentes) == 1  # Só ped_001


class TestGerador:
    """Testa gerador de dados"""
    
    def test_gerar_rede_pequena(self):
        gerador = GeradorMaceioCompleto(seed=42)
        rede = gerador.gerar_rede_completa(num_clientes=10)
        
        assert len(rede.depositos) > 0
        assert len(rede.hubs) > 0
        assert len(rede.clientes) == 10
        assert len(rede.rotas) > 0
        
        stats = rede.obter_estatisticas()
        assert stats['total_clientes'] == 10
        assert stats['taxa_utilizacao'] >= 0
    
    def test_integridade_rede_gerada(self):
        gerador = GeradorMaceioCompleto(seed=123)
        rede = gerador.gerar_rede_completa(num_clientes=15)
        
        # Verificar clientes têm zona
        clientes_sem_zona = [c for c in rede.clientes if not c.zona_id]
        assert len(clientes_sem_zona) == 0
        
        # Verificar capacidades positivas
        rotas_capacidade_zero = [r for r in rede.rotas if r.capacidade <= 0]
        assert len(rotas_capacidade_zero) == 0
        
        # Verificar coordenadas de Maceió
        for entidade in rede.depositos + rede.hubs + rede.clientes:
            assert -10.0 <= entidade.latitude <= -9.0
            assert -36.0 <= entidade.longitude <= -35.0


class TestCarregamentoJSON:
    """Testa carregamento de dados JSON"""
    
    def test_carregamento_json_basico(self):
        data = {
            "depositos": [
                {
                    "id": "dep_001",
                    "latitude": -9.6498,
                    "longitude": -35.7089,
                    "nome": "Depósito Teste",
                    "capacidade_maxima": 100
                }
            ],
            "hubs": [
                {
                    "id": "hub_001",
                    "latitude": -9.6658,
                    "longitude": -35.7350,
                    "capacidade": 50,
                    "nome": "Hub Teste"
                }
            ],
            "clientes": [
                {
                    "id": "cli_001", 
                    "latitude": -9.6400,
                    "longitude": -35.7300,
                    "demanda_media": 2,
                    "zona_id": "zona_01"
                }
            ],
            "rotas": [
                {
                    "origem": "dep_001",
                    "destino": "hub_001",
                    "capacidade": 30,
                    "peso": 5.2
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(data, f, indent=2)
            temp_path = f.name
        
        try:
            rede = carregar_rede_completa(temp_path)
            assert len(rede.depositos) == 1
            assert len(rede.hubs) == 1
            assert len(rede.clientes) == 1
            assert len(rede.rotas) == 1
            
            assert rede.depositos[0].nome == "Depósito Teste"
            assert rede.hubs[0].capacidade == 50
            assert rede.clientes[0].demanda_media == 2
            assert rede.rotas[0].capacidade == 30
        finally:
            os.unlink(temp_path)


class TestValidacoes:
    """Testa validações e casos limite"""
    
    def test_rede_vazia(self):
        rede = RedeEntrega()
        assert rede.obter_demanda_total() == 0
        assert rede.obter_capacidade_total() == 0
        assert len(rede.obter_pedidos_pendentes()) == 0
    
    def test_zona_entrega_completa(self):
        hub1 = Hub("hub_001", -9.6658, -35.7350, 100, "Hub 1")
        hub2 = Hub("hub_002", -9.6400, -35.7100, 80, "Hub 2")
        
        cliente1 = Cliente("cli_001", -9.6400, -35.7300, 3, zona_id="zona_01")
        cliente2 = Cliente("cli_002", -9.6500, -35.7200, 2, zona_id="zona_01")
        
        zona = ZonaEntrega(
            id="zona_01",
            nome="Zona Pajuçara",
            hubs=[hub1, hub2],
            clientes=[cliente1, cliente2],
            demanda_total=5,
            area_cobertura=2.5
        )
        
        assert len(zona.hubs) == 2
        assert len(zona.clientes) == 2
        assert zona.demanda_total == 5
        assert zona.nome == "Zona Pajuçara"


if __name__ == "__main__":
    pytest.main([__file__])
