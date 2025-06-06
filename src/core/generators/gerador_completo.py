"""
Gerador expandido de rede de entregas para Maceió
Inclui clientes finais e rotas completas para o sistema de delivery
"""

import json
import math
import random
from typing import List, Tuple, Optional
from itertools import combinations
from datetime import datetime

from ..entities.models import (
    Deposito, Hub, Cliente, ZonaEntrega, Veiculo, Rota, RedeEntrega,
    TipoVeiculo, PrioridadeCliente
)


class GeradorMaceioCompleto:
    """Gerador completo de rede de entregas para Maceió com clientes finais"""
    
    def __init__(self, seed: int = 42):
        """Inicializa o gerador com seed para reprodutibilidade"""
        random.seed(seed)
        self.seed = seed
    
    def gerar_rede_completa(self, num_clientes: int = 100, num_entregadores: Optional[int] = None) -> RedeEntrega:
        """Gera uma rede completa de entregas para Maceió"""
        print(f"Gerando rede completa para Maceió com {num_clientes} clientes...")
        
        # 1. Gerar componentes básicos
        depositos = self._gerar_depositos()
        hubs = self._gerar_hubs()
        clientes = self._gerar_clientes(num_clientes)
        zonas = self._gerar_zonas(hubs, clientes)
        veiculos = self._gerar_veiculos(hubs, num_entregadores)
        
        # 2. Gerar todas as rotas
        rotas = self._gerar_rotas_completas(depositos, hubs, clientes, zonas)
        
        # 3. Criar rede
        rede = RedeEntrega(
            depositos=depositos,
            hubs=hubs,
            clientes=clientes,
            zonas=zonas,
            veiculos=veiculos,
            rotas=rotas
        )
        
        print(f"Rede criada: {len(depositos)} depósitos, {len(hubs)} hubs, "
              f"{len(clientes)} clientes, {len(zonas)} zonas, {len(veiculos)} veículos, "
              f"{len(rotas)} rotas")
        
        return rede
    
    def _gerar_depositos(self) -> List[Deposito]:
        """Gera depósitos estratégicos em Maceió"""
        depositos_data = [
            ("DEP_01", -9.6658, -35.7350, "Depósito Central", "Centro de Maceió"),
            ("DEP_02", -9.6200, -35.6800, "Depósito Leste", "Zona Leste"),
        ]
        
        return [
            Deposito(id=id, latitude=lat, longitude=lon, nome=nome, endereco=endereco)
            for id, lat, lon, nome, endereco in depositos_data
        ]
    
    def _gerar_hubs(self) -> List[Hub]:
        """Gera hubs logísticos em pontos estratégicos"""
        hubs_data = [
            # Centro e adjacências
            ("HUB_01", -9.6500, -35.7200, 120, "Hub Centro", "Centro"),
            ("HUB_02", -9.6400, -35.7100, 100, "Hub Farol", "Farol"),
            ("HUB_03", -9.6700, -35.7300, 100, "Hub Ponta Verde", "Ponta Verde"),
            
            # Zona Norte
            ("HUB_04", -9.6200, -35.7000, 80, "Hub Jatiúca", "Jatiúca"),
            ("HUB_05", -9.6000, -35.6900, 90, "Hub Pajuçara", "Pajuçara"),
            
            # Zona Sul
            ("HUB_06", -9.6900, -35.7400, 85, "Hub Ponta da Terra", "Ponta da Terra"),
            ("HUB_07", -9.7100, -35.7200, 75, "Hub Ponta Grossa", "Ponta Grossa"),
            
            # Zona Oeste
            ("HUB_08", -9.6600, -35.7600, 95, "Hub Gruta de Lourdes", "Gruta de Lourdes"),
            ("HUB_09", -9.6800, -35.7800, 85, "Hub Feitosa", "Feitosa"),
            
            # Zona Periférica
            ("HUB_10", -9.6300, -35.7800, 70, "Hub Benedito Bentes", "Benedito Bentes"),
            ("HUB_11", -9.7000, -35.6800, 65, "Hub Cidade Universitária", "Cidade Universitária"),
            ("HUB_12", -9.6100, -35.7400, 75, "Hub Cruz das Almas", "Cruz das Almas"),
        ]
        
        return [
            Hub(id=id, latitude=lat, longitude=lon, capacidade=cap, nome=nome, endereco=endereco)
            for id, lat, lon, cap, nome, endereco in hubs_data
        ]
    
    def _gerar_clientes(self, num_clientes: int) -> List[Cliente]:
        """Gera clientes distribuídos pela cidade"""
        clientes = []
        
        # Definir áreas de concentração de clientes (bairros populosos)
        areas_clientes = [
            # (lat_centro, lon_centro, raio_km, num_clientes_area, zona_id)
            (-9.6500, -35.7200, 0.02, int(num_clientes * 0.15), "ZONA_CENTRO"),  # Centro
            (-9.6300, -35.7000, 0.015, int(num_clientes * 0.12), "ZONA_NORTE"),   # Jatiúca
            (-9.6000, -35.6900, 0.015, int(num_clientes * 0.10), "ZONA_NORTE"),   # Pajuçara
            (-9.6800, -35.7400, 0.02, int(num_clientes * 0.13), "ZONA_SUL"),      # Ponta da Terra
            (-9.7000, -35.7200, 0.02, int(num_clientes * 0.11), "ZONA_SUL"),      # Ponta Grossa
            (-9.6700, -35.7600, 0.025, int(num_clientes * 0.14), "ZONA_OESTE"),   # Gruta de Lourdes
            (-9.6800, -35.7800, 0.02, int(num_clientes * 0.12), "ZONA_OESTE"),    # Feitosa
            (-9.7000, -35.6800, 0.02, int(num_clientes * 0.08), "ZONA_LESTE"),    # Cidade Universitária
            (-9.6100, -35.7400, 0.02, int(num_clientes * 0.05), "ZONA_LESTE"),    # Cruz das Almas
        ]
        
        cliente_id = 1
        
        for lat_centro, lon_centro, raio, num_area, zona_id in areas_clientes:
            for _ in range(num_area):
                # Gerar coordenadas aleatórias dentro da área
                angle = random.uniform(0, 2 * math.pi)
                radius = random.uniform(0, raio)
                
                lat = lat_centro + (radius * math.cos(angle))
                lon = lon_centro + (radius * math.sin(angle))
                
                # Gerar características do cliente
                demanda = random.choice([1, 1, 2, 2, 3, 4, 5])  # Mais peso para demandas baixas
                prioridade = random.choices(
                    list(PrioridadeCliente),
                    weights=[5, 70, 20, 4, 1],  # Maioria normal
                    k=1
                )[0]
                
                cliente = Cliente(
                    id=f"CLI_{cliente_id:04d}",
                    latitude=lat,
                    longitude=lon,
                    demanda_media=demanda,
                    prioridade=prioridade,
                    endereco=f"Endereço {cliente_id}, {zona_id.replace('ZONA_', '')}",
                    zona_id=zona_id
                )
                
                clientes.append(cliente)
                cliente_id += 1
        
        # Completar com clientes restantes se necessário
        while len(clientes) < num_clientes:
            area = random.choice(areas_clientes)
            lat_centro, lon_centro, raio, _, zona_id = area
            
            angle = random.uniform(0, 2 * math.pi)
            radius = random.uniform(0, raio)
            
            lat = lat_centro + (radius * math.cos(angle))
            lon = lon_centro + (radius * math.sin(angle))
            
            cliente = Cliente(
                id=f"CLI_{cliente_id:04d}",
                latitude=lat,
                longitude=lon,
                demanda_media=random.choice([1, 2, 3]),
                prioridade=PrioridadeCliente.NORMAL,
                endereco=f"Endereço {cliente_id}, {zona_id.replace('ZONA_', '')}",
                zona_id=zona_id
            )
            
            clientes.append(cliente)
            cliente_id += 1
        
        return clientes[:num_clientes]
    
    def _gerar_zonas(self, hubs: List[Hub], clientes: List[Cliente]) -> List[ZonaEntrega]:
        """Gera zonas de entrega associando hubs e clientes"""
        zonas_config = [
            ("ZONA_CENTRO", "Centro", [0, 1, 2]),     # HUB_01, HUB_02, HUB_03
            ("ZONA_NORTE", "Zona Norte", [3, 4]),     # HUB_04, HUB_05
            ("ZONA_SUL", "Zona Sul", [5, 6]),         # HUB_06, HUB_07
            ("ZONA_OESTE", "Zona Oeste", [7, 8, 9]),  # HUB_08, HUB_09, HUB_10
            ("ZONA_LESTE", "Zona Leste", [10, 11]),   # HUB_11, HUB_12
        ]
        
        zonas = []
        
        for zona_id, nome, hub_indices in zonas_config:
            # Associar hubs
            hubs_zona = [hubs[i] for i in hub_indices if i < len(hubs)]
            
            # Associar clientes da zona
            clientes_zona = [c for c in clientes if c.zona_id == zona_id]
            
            # Calcular demanda total
            demanda_total = sum(c.demanda_media for c in clientes_zona)
            
            zona = ZonaEntrega(
                id=zona_id,
                nome=nome,
                hubs=hubs_zona,
                clientes=clientes_zona,
                demanda_total=demanda_total
            )
            
            zonas.append(zona)
        
        return zonas
    
    def _gerar_veiculos(self, hubs: List[Hub], num_entregadores: Optional[int] = None) -> List[Veiculo]:
        """Gera frota de veículos distribuída pelos hubs"""
        veiculos = []
        veiculo_id = 1
        
        if num_entregadores is not None:
            # Se número específico foi fornecido, distribuir pelos hubs
            if num_entregadores < len(hubs):
                # Se temos menos entregadores que hubs, alguns hubs ficarão sem veículos
                veiculos_por_hub = 0
                veiculos_extras = num_entregadores
            else:
                # Se temos mais entregadores que hubs, distribuir uniformemente
                veiculos_por_hub = num_entregadores // len(hubs)
                veiculos_extras = num_entregadores % len(hubs)
            
            for i, hub in enumerate(hubs):
                # Distribuir veículos extras nos primeiros hubs
                num_veiculos = veiculos_por_hub + (1 if i < veiculos_extras else 0)
                
                for _ in range(num_veiculos):
                    # Distribuição de tipos de veículo
                    tipo = random.choices(
                        list(TipoVeiculo),
                        weights=[50, 30, 15, 5],  # Mais motos, menos caminhões
                        k=1
                    )[0]
                    
                    # Capacidade baseada no tipo
                    capacidades = {
                        TipoVeiculo.MOTO: random.randint(3, 8),
                        TipoVeiculo.CARRO: random.randint(8, 15),
                        TipoVeiculo.VAN: random.randint(15, 25),
                        TipoVeiculo.CAMINHAO: random.randint(25, 40)
                    }
                    
                    velocidades = {
                        TipoVeiculo.MOTO: random.uniform(25, 35),
                        TipoVeiculo.CARRO: random.uniform(20, 30),
                        TipoVeiculo.VAN: random.uniform(18, 25),
                        TipoVeiculo.CAMINHAO: random.uniform(15, 20)
                    }
                    
                    veiculo = Veiculo(
                        id=f"VEI_{veiculo_id:03d}",
                        tipo=tipo,
                        capacidade=capacidades[tipo],
                        velocidade_media=velocidades[tipo],
                        hub_base=hub.id,
                        condutor=f"Condutor {veiculo_id}"
                    )
                    veiculos.append(veiculo)
                    veiculo_id += 1
        else:
            # Comportamento original: distribuir por capacidade do hub
            for hub in hubs:
                # Número de veículos proporcional à capacidade do hub
                num_veiculos = max(2, hub.capacidade // 25)
                
                for _ in range(num_veiculos):
                    # Distribuição de tipos de veículo
                    tipo = random.choices(
                        list(TipoVeiculo),
                        weights=[50, 30, 15, 5],  # Mais motos, menos caminhões
                        k=1
                    )[0]
                    
                    # Capacidade baseada no tipo
                    capacidades = {
                        TipoVeiculo.MOTO: random.randint(3, 8),
                        TipoVeiculo.CARRO: random.randint(8, 15),
                        TipoVeiculo.VAN: random.randint(15, 25),
                        TipoVeiculo.CAMINHAO: random.randint(25, 40)
                    }
                    
                    velocidades = {
                        TipoVeiculo.MOTO: random.uniform(25, 35),
                        TipoVeiculo.CARRO: random.uniform(20, 30),
                        TipoVeiculo.VAN: random.uniform(18, 25),
                        TipoVeiculo.CAMINHAO: random.uniform(15, 20)
                    }
                    
                    veiculo = Veiculo(
                        id=f"VEI_{veiculo_id:03d}",
                        tipo=tipo,
                        capacidade=capacidades[tipo],
                        velocidade_media=velocidades[tipo],
                        hub_base=hub.id,
                        condutor=f"Condutor {veiculo_id}"
                    )
                    
                    veiculos.append(veiculo)
                    veiculo_id += 1
        
        return veiculos
    
    def _gerar_rotas_completas(self, depositos: List[Deposito], hubs: List[Hub],
                               clientes: List[Cliente], zonas: List[ZonaEntrega]) -> List[Rota]:
        """Gera todas as rotas necessárias para o sistema completo"""
        rotas = []
        
        # 1. Rotas: Depósitos → Hubs
        rotas.extend(self._rotas_depositos_hubs(depositos, hubs))
        
        # 2. Rotas: Hubs ↔ Hubs (redistribuição)
        rotas.extend(self._rotas_hubs_hubs(hubs))
        
        # 3. Rotas: Hubs → Clientes (NOVA - essencial para delivery)
        rotas.extend(self._rotas_hubs_clientes(hubs, clientes))
        
        # 4. Rotas: Hubs → Zonas (agregação)
        rotas.extend(self._rotas_hubs_zonas(hubs, zonas))
        
        return rotas
    
    def _rotas_depositos_hubs(self, depositos: List[Deposito], hubs: List[Hub]) -> List[Rota]:
        """Gera rotas entre depósitos e hubs"""
        rotas = []
        
        for deposito in depositos:
            for hub in hubs:
                dist = self._calcular_distancia(
                    deposito.latitude, deposito.longitude,
                    hub.latitude, hub.longitude
                )
                
                # Conectar hubs próximos (≈6km)
                if dist < 0.06:
                    cap = self._calcular_capacidade_deposito_hub(dist)
                    tempo = self._calcular_tempo_rota(dist, 25)  # Velocidade caminhão
                    
                    rota = Rota(
                        origem=deposito.id,
                        destino=hub.id,
                        peso=dist,
                        capacidade=cap,
                        tipo_rota="abastecimento",
                        tempo_medio=tempo
                    )
                    rotas.append(rota)
        
        return rotas
    
    def _rotas_hubs_hubs(self, hubs: List[Hub]) -> List[Rota]:
        """Gera rotas entre hubs para redistribuição"""
        rotas = []
        
        for hub1, hub2 in combinations(hubs, 2):
            dist = self._calcular_distancia(
                hub1.latitude, hub1.longitude,
                hub2.latitude, hub2.longitude
            )
            
            # Conectar hubs próximos (≈4km) - bidirecional
            if dist < 0.04:
                cap = self._calcular_capacidade_hub_hub(dist)
                tempo = self._calcular_tempo_rota(dist, 20)  # Velocidade van
                
                rotas.extend([
                    Rota(
                        origem=hub1.id,
                        destino=hub2.id,
                        peso=dist,
                        capacidade=cap,
                        tipo_rota="redistribuicao",
                        tempo_medio=tempo
                    ),
                    Rota(
                        origem=hub2.id,
                        destino=hub1.id,
                        peso=dist,
                        capacidade=cap,
                        tipo_rota="redistribuicao",
                        tempo_medio=tempo
                    )
                ])
        
        return rotas
    
    def _rotas_hubs_clientes(self, hubs: List[Hub], clientes: List[Cliente]) -> List[Rota]:
        """Gera rotas diretas entre hubs e clientes (ESSENCIAL para delivery)"""
        rotas = []
        
        for hub in hubs:
            for cliente in clientes:
                dist = self._calcular_distancia(
                    hub.latitude, hub.longitude,
                    cliente.latitude, cliente.longitude
                )
                
                # Conectar clientes dentro do raio de atendimento (≈3km)
                if dist < 0.03:
                    cap = self._calcular_capacidade_hub_cliente(dist, cliente.demanda_media)
                    tempo = self._calcular_tempo_rota(dist, 30)  # Velocidade moto
                    
                    # Ajustar custo baseado na prioridade do cliente
                    custo = self._calcular_custo_entrega(dist, cliente.prioridade)
                    
                    rota = Rota(
                        origem=hub.id,
                        destino=cliente.id,
                        peso=dist,
                        capacidade=cap,
                        tipo_rota="entrega_final",
                        tempo_medio=tempo,
                        custo=custo
                    )
                    rotas.append(rota)
        
        return rotas
    
    def _rotas_hubs_zonas(self, hubs: List[Hub], zonas: List[ZonaEntrega]) -> List[Rota]:
        """Gera rotas agregadas entre hubs e zonas"""
        rotas = []
        
        for zona in zonas:
            for hub in zona.hubs:
                # Usar centroide da zona
                if zona.clientes:
                    zona_lat = sum(c.latitude for c in zona.clientes) / len(zona.clientes)
                    zona_lon = sum(c.longitude for c in zona.clientes) / len(zona.clientes)
                else:
                    zona_lat = sum(h.latitude for h in zona.hubs) / len(zona.hubs)
                    zona_lon = sum(h.longitude for h in zona.hubs) / len(zona.hubs)
                
                dist = self._calcular_distancia(
                    hub.latitude, hub.longitude,
                    zona_lat, zona_lon
                )
                
                cap = self._calcular_capacidade_hub_zona(dist, zona.demanda_total)
                tempo = self._calcular_tempo_rota(dist, 25)
                
                rota = Rota(
                    origem=hub.id,
                    destino=zona.id,
                    peso=dist,
                    capacidade=cap,
                    tipo_rota="zona_agregada",
                    tempo_medio=tempo
                )
                rotas.append(rota)
        
        return rotas
    
    def _calcular_distancia(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calcula distância euclidiana entre dois pontos"""
        return math.sqrt((lat2 - lat1)**2 + (lon2 - lon1)**2)
    
    def _calcular_tempo_rota(self, distancia: float, velocidade_kmh: float) -> float:
        """Calcula tempo de percurso em minutos"""
        distancia_km = distancia * 111  # Conversão aproximada graus → km
        return (distancia_km / velocidade_kmh) * 60
    
    def _calcular_capacidade_deposito_hub(self, distancia: float) -> int:
        """Calcula capacidade para rotas depósito → hub"""
        base = 60
        fator = max(0.3, 1.0 - distancia * 30)
        return int(base * fator)
    
    def _calcular_capacidade_hub_hub(self, distancia: float) -> int:
        """Calcula capacidade para rotas hub ↔ hub"""
        base = 40
        fator = max(0.4, 1.0 - distancia * 25)
        return int(base * fator)
    
    def _calcular_capacidade_hub_cliente(self, distancia: float, demanda_cliente: int) -> int:
        """Calcula capacidade para rotas hub → cliente"""
        base = 10 + (demanda_cliente * 2)  # Baseado na demanda do cliente
        fator = max(0.5, 1.0 - distancia * 20)
        return max(1, int(base * fator))
    
    def _calcular_capacidade_hub_zona(self, distancia: float, demanda_zona: int) -> int:
        """Calcula capacidade para rotas hub → zona"""
        base = min(100, demanda_zona * 5)  # Baseado na demanda total da zona
        fator = max(0.4, 1.0 - distancia * 15)
        return int(base * fator)
    
    def _calcular_custo_entrega(self, distancia: float, prioridade: PrioridadeCliente) -> float:
        """Calcula custo operacional da entrega"""
        custo_base = distancia * 100  # Custo por distância
        
        # Multiplicador por prioridade
        multiplicadores = {
            PrioridadeCliente.BAIXA: 0.8,
            PrioridadeCliente.NORMAL: 1.0,
            PrioridadeCliente.ALTA: 1.2,
            PrioridadeCliente.URGENTE: 1.5,
            PrioridadeCliente.CRITICA: 2.0
        }
        
        return custo_base * multiplicadores[prioridade]
    
    def salvar_json(self, rede: RedeEntrega, arquivo: str):
        """Salva a rede completa em arquivo JSON"""
        dados = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "gerador": "GeradorMaceioCompleto",
                "seed": self.seed,
                "versao": "2.0"
            },
            "depositos": [
                {
                    "id": d.id,
                    "latitude": d.latitude,
                    "longitude": d.longitude,
                    "nome": d.nome,
                    "capacidade_maxima": d.capacidade_maxima,
                    "endereco": d.endereco
                }
                for d in rede.depositos
            ],
            "hubs": [
                {
                    "id": h.id,
                    "latitude": h.latitude,
                    "longitude": h.longitude,
                    "capacidade": h.capacidade,
                    "nome": h.nome,
                    "endereco": h.endereco,
                    "operacional": h.operacional
                }
                for h in rede.hubs
            ],
            "clientes": [
                {
                    "id": c.id,
                    "latitude": c.latitude,
                    "longitude": c.longitude,
                    "demanda_media": c.demanda_media,
                    "prioridade": c.prioridade.value,
                    "endereco": c.endereco,
                    "zona_id": c.zona_id,
                    "ativo": c.ativo
                }
                for c in rede.clientes
            ],
            "zonas": [
                {
                    "id": z.id,
                    "nome": z.nome,
                    "hubs": [h.id for h in z.hubs],
                    "clientes": [c.id for c in z.clientes],
                    "demanda_total": z.demanda_total,
                    "area_cobertura": z.area_cobertura
                }
                for z in rede.zonas
            ],
            "veiculos": [
                {
                    "id": v.id,
                    "tipo": v.tipo.value,
                    "capacidade": v.capacidade,
                    "velocidade_media": v.velocidade_media,
                    "hub_base": v.hub_base,
                    "disponivel": v.disponivel,
                    "condutor": v.condutor
                }
                for v in rede.veiculos
            ],
            "rotas": [
                {
                    "origem": r.origem,
                    "destino": r.destino,
                    "peso": r.peso,
                    "capacidade": r.capacidade,
                    "tipo_rota": r.tipo_rota,
                    "tempo_medio": r.tempo_medio,
                    "custo": r.custo,
                    "ativa": r.ativa
                }
                for r in rede.rotas
            ],
            "estatisticas": rede.obter_estatisticas()
        }
        
        with open(arquivo, 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
        
        print(f"Rede completa salva em: {arquivo}")


# Função de conveniência
def gerar_rede_maceio_completa(num_clientes: int = 100, seed: int = 42) -> RedeEntrega:
    """Função de conveniência para gerar rede completa"""
    gerador = GeradorMaceioCompleto(seed=seed)
    return gerador.gerar_rede_completa(num_clientes=num_clientes)
