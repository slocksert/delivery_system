"""
Gerador expandido de rede de entregas para Maceió usando dados reais do OpenStreetMap
Inclui clientes finais e rotas completas baseadas na infraestrutura real da cidade
"""

import json
import math
import random
import osmnx as ox
import networkx as nx
from typing import List, Tuple, Optional, Dict
from itertools import combinations
from datetime import datetime, timezone, timedelta

from ..entities.models import (
    Deposito, Hub, Cliente, ZonaEntrega, Veiculo, Rota, RedeEntrega,
    TipoVeiculo, PrioridadeCliente
)

# Função utilitária para timestamps brasileiros
def get_brazilian_timestamp() -> datetime:
    """Retorna timestamp atual no fuso horário brasileiro (UTC-3)"""
    brazilian_tz = timezone(timedelta(hours=-3))
    return datetime.now(brazilian_tz)


class GeradorMaceioCompleto:
    """Gerador completo de rede de entregas para Maceió usando dados reais do OpenStreetMap"""
    
    def __init__(self, seed: int = 42, cache_graph: bool = True):
        """Inicializa o gerador com seed para reprodutibilidade"""
        random.seed(seed)
        self.seed = seed
        self.cache_graph = cache_graph
        self.grafo_maceio = None
        self.boundaries = None
        
    def _carregar_mapa_maceio(self) -> Optional[nx.MultiDiGraph]:
        """Carrega o mapa real de Maceió usando OSMNX"""
        if self.grafo_maceio is None:
            print("Carregando mapa de Maceió do OpenStreetMap...")
            
            # Definir Maceió, Alagoas
            lugar = "Maceió, Alagoas, Brazil"
            
            try:
                # Baixar o grafo da rede viária de Maceió
                # Incluir diferentes tipos de vias para delivery
                network_type = 'drive'  # Vias para veículos
                self.grafo_maceio = ox.graph_from_place(
                    lugar, 
                    network_type=network_type,
                    simplify=True,
                    retain_all=False
                )
                
                # Obter limites geográficos
                self.boundaries = ox.geocode_to_gdf(lugar)
                
                print(f"Mapa carregado: {len(self.grafo_maceio.nodes)} nós, {len(self.grafo_maceio.edges)} arestas")
                
                # Adicionar informações de velocidade e tempo
                self.grafo_maceio = ox.add_edge_speeds(self.grafo_maceio)
                self.grafo_maceio = ox.add_edge_travel_times(self.grafo_maceio)
                
            except Exception as e:
                print(f"Erro ao carregar mapa: {e}")
                print("Usando dados sintéticos como fallback...")
                return None
        
        return self.grafo_maceio
    
    def _obter_pontos_interesse(self) -> Dict[str, List[Tuple[float, float, str]]]:
        """Obtém pontos de interesse reais de Maceió usando OSMNX"""
        if self.grafo_maceio is None:
            return {}
            
        pontos = {
            'centros_comerciais': [],
            'hospitais': [],
            'universidades': [],
            'mercados': [],
            'estacoes_rodoviarias': []
        }
        
        lugar = "Maceió, Alagoas, Brazil"
        
        try:
            # Centros comerciais e shopping centers
            shopping = ox.features_from_place(
                lugar, 
                tags={'shop': 'mall', 'amenity': 'marketplace'}
            )
            for idx, row in shopping.iterrows():
                if hasattr(row.geometry, 'centroid'):
                    lat, lon = row.geometry.centroid.y, row.geometry.centroid.x
                    pontos['centros_comerciais'].append((lat, lon, row.get('name', 'Centro Comercial')))
            
            # Hospitais
            hospitais = ox.features_from_place(
                lugar,
                tags={'amenity': 'hospital'}
            )
            for idx, row in hospitais.iterrows():
                if hasattr(row.geometry, 'centroid'):
                    lat, lon = row.geometry.centroid.y, row.geometry.centroid.x
                    pontos['hospitais'].append((lat, lon, row.get('name', 'Hospital')))
            
            # Universidades
            universidades = ox.features_from_place(
                lugar,
                tags={'amenity': 'university'}
            )
            for idx, row in universidades.iterrows():
                if hasattr(row.geometry, 'centroid'):
                    lat, lon = row.geometry.centroid.y, row.geometry.centroid.x
                    pontos['universidades'].append((lat, lon, row.get('name', 'Universidade')))
            
            # Supermercados
            mercados = ox.features_from_place(
                lugar,
                tags={'shop': 'supermarket'}
            )
            for idx, row in mercados.iterrows():
                if hasattr(row.geometry, 'centroid'):
                    lat, lon = row.geometry.centroid.y, row.geometry.centroid.x
                    pontos['mercados'].append((lat, lon, row.get('name', 'Mercado')))
                    
        except Exception as e:
            print(f"Aviso: Erro ao obter pontos de interesse: {e}")
            
        return pontos
    
    def gerar_rede_completa(self, num_clientes: int = 100, num_entregadores: Optional[int] = None) -> RedeEntrega:
        """Gera uma rede completa de entregas para Maceió usando dados reais"""
        print(f"Gerando rede completa para Maceió com {num_clientes} clientes usando dados reais...")
        
        # 1. Carregar mapa real de Maceió
        self._carregar_mapa_maceio()
        
        # 2. Obter pontos de interesse reais
        pontos_interesse = self._obter_pontos_interesse()
        
        # 3. Gerar componentes baseados em dados reais
        # IMPORTANTE: Gerar clientes primeiro para usar como referência
        clientes = self._gerar_clientes_reais(num_clientes)
        
        # Gerar depósitos e hubs próximos aos clientes
        depositos = self._gerar_depositos_reais(pontos_interesse, clientes)
        hubs = self._gerar_hubs_reais(pontos_interesse, clientes)
        
        zonas = self._gerar_zonas_reais(hubs, clientes)
        veiculos = self._gerar_veiculos(hubs, num_entregadores)
        
        # 4. Gerar rotas baseadas no grafo real de Maceió
        rotas = self._gerar_rotas_reais(depositos, hubs, clientes, zonas)
        
        # 5. Criar rede
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
              f"{len(rotas)} rotas (baseadas em dados reais)")
        
        return rede
    
    def _gerar_depositos_reais(self, pontos_interesse: Dict, clientes: Optional[List[Cliente]] = None) -> List[Deposito]:
        """Gera poucos depósitos em posições estratégicas próximas aos clientes"""
        depositos = []
        
        # ESTRATÉGIA: Apenas 2 depósitos principais em posições estratégicas
        # Posicionados próximos aos clientes, mas não sobrepostos
        depositos_estrategicos = [
            {
                'zona': 'centro',
                'nome': 'Depósito Central',
                'capacidade': 2000,  # Capacidade maior para ser o principal
                'endereco': 'Centro, Maceió - AL'
            },
            {
                'zona': 'oeste', 
                'nome': 'Depósito Industrial',
                'capacidade': 1500,  # Zona industrial, boa para distribuição
                'endereco': 'Zona Industrial Oeste, Maceió - AL'
            }
        ]
        
        for i, config in enumerate(depositos_estrategicos):
            # Gerar coordenadas próximas aos clientes da zona
            lat, lon = self._gerar_coordenada_proxima_clientes(config['zona'], clientes)
            
            deposito = Deposito(
                id=f"DEP_{i+1:02d}",
                latitude=lat,
                longitude=lon,
                nome=config['nome'],
                endereco=config['endereco'],
                capacidade_maxima=config['capacidade']
            )
            depositos.append(deposito)
            print(f"📦 Depósito estratégico criado: {config['nome']} ({lat:.4f}, {lon:.4f})")
        
        return depositos
    
    def _gerar_hubs_reais(self, pontos_interesse: Dict, clientes: Optional[List[Cliente]] = None) -> List[Hub]:
        """Gera poucos hubs estratégicos próximos aos clientes para máxima cobertura"""
        hubs = []
        hub_id = 1
        
        # ESTRATÉGIA: 3 hubs estratégicos cobrindo toda Maceió
        # Posicionados próximos aos clientes, mas não sobrepostos
        hubs_estrategicos = [
            # Hub Central - Cobertura do centro histórico e comercial
            {
                'zona': 'centro',
                'nome': 'Hub Centro',
                'capacidade': 150,
                'endereco': 'Centro Histórico, Maceió - AL'
            },
            # Hub Norte - Cobertura da orla norte (Pajuçara, Jatiúca)
            {
                'zona': 'norte',
                'nome': 'Hub Pajuçara',
                'capacidade': 120,
                'endereco': 'Região da Orla Norte, Maceió - AL'
            },
            # Hub Oeste - Cobertura da zona industrial e bairros internos
            {
                'zona': 'oeste',
                'nome': 'Hub Feitosa',
                'capacidade': 130,
                'endereco': 'Zona Oeste, Maceió - AL'
            }
        ]
        
        for config in hubs_estrategicos:
            # Gerar coordenadas próximas aos clientes da zona
            lat, lon = self._gerar_coordenada_proxima_clientes(config['zona'], clientes)
            
            hub = Hub(
                id=f"HUB_{hub_id:02d}",
                latitude=lat,
                longitude=lon,
                capacidade=config['capacidade'],
                nome=config['nome'],
                endereco=config['endereco']
            )
            hubs.append(hub)
            print(f"🏪 Hub estratégico criado: {config['nome']} ({lat:.4f}, {lon:.4f})")
            hub_id += 1
        
        return hubs
    
    def _gerar_clientes_reais(self, num_clientes: int) -> List[Cliente]:
        """Gera clientes distribuídos em áreas residenciais reais de Maceió"""
        clientes = []
        cliente_id = 1
        
        if self.grafo_maceio is None:
            # Fallback para método sintético se não conseguiu carregar o mapa
            return self._gerar_clientes_sintetico(num_clientes)
        
        # Obter nós do grafo como potenciais localizações de clientes
        nos = list(self.grafo_maceio.nodes(data=True))
        
        # Filtrar nós em áreas residenciais (se possível)
        nos_residenciais = []
        for node_id, data in nos:
            lat, lon = data['y'], data['x']
            # Verificar se está dentro dos limites de Maceió
            if -9.75 <= lat <= -9.50 and -35.85 <= lon <= -35.65:
                nos_residenciais.append((lat, lon, node_id))
        
        # Se não temos nós suficientes, usar amostragem
        if len(nos_residenciais) < num_clientes:
            nos_residenciais = nos_residenciais * (num_clientes // len(nos_residenciais) + 1)
        
        # Selecionar aleatoriamente localizações
        clientes_selecionados = random.sample(nos_residenciais, min(num_clientes, len(nos_residenciais)))
        
        # Definir zonas baseadas em coordenadas
        for lat, lon, node_id in clientes_selecionados:
            zona_id = self._determinar_zona_por_coordenada(lat, lon)
            
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
                endereco=f"Rua {cliente_id}, {zona_id.replace('ZONA_', '')}",
                zona_id=zona_id
            )
            
            clientes.append(cliente)
            cliente_id += 1
        
        return clientes
    
    def _determinar_zona_por_coordenada(self, lat: float, lon: float) -> str:
        """Determina a zona baseada nas coordenadas geográficas"""
        # Centro: região central de Maceió (área terrestre)
        if -9.67 <= lat <= -9.63 and -35.75 <= lon <= -35.72:
            return "ZONA_CENTRO"
        
        # Norte: Jatiúca, Pajuçara, Mangabeiras (mais para dentro da terra)
        elif lat <= -9.60 and -35.72 <= lon <= -35.70:
            return "ZONA_NORTE"
        
        # Sul: Ponta Verde, Ponta da Terra, Ponta Grossa (área terrestre)
        elif lat >= -9.68 and -35.76 <= lon <= -35.72:
            return "ZONA_SUL"
        
        # Oeste: Feitosa, Gruta de Lourdes (área mais interna)
        elif lon >= -35.80:
            return "ZONA_OESTE"
        
        # Leste: Cidade Universitária, áreas internas
        else:
            return "ZONA_LESTE"
    
    def _gerar_clientes_sintetico(self, num_clientes: int) -> List[Cliente]:
        """Gera clientes usando método dinâmico baseado em zonas válidas"""
        clientes = []
        cliente_id = 1
        
        # Definir distribuição por zona
        distribuicao_zonas = [
            ('centro', 0.15),    # 15% no centro
            ('norte', 0.22),     # 22% na zona norte (Jatiúca, Pajuçara)
            ('sul', 0.24),       # 24% na zona sul (Ponta Verde, Ponta da Terra)
            ('oeste', 0.26),     # 26% na zona oeste (Gruta, Feitosa)
            ('leste', 0.13),     # 13% na zona leste (Cidade Universitária)
        ]
        
        for zona_nome, percentual in distribuicao_zonas:
            num_clientes_zona = int(num_clientes * percentual)
            
            for _ in range(num_clientes_zona):
                # Gerar coordenadas baseadas na zona
                if zona_nome == 'centro':
                    lat = -9.6500 + random.uniform(-0.02, 0.02)
                    lon = -35.7350 + random.uniform(-0.02, 0.02)
                elif zona_nome == 'norte':
                    lat = -9.6100 + random.uniform(-0.02, 0.02)
                    lon = -35.7400 + random.uniform(-0.02, 0.02)
                elif zona_nome == 'sul':
                    lat = -9.6900 + random.uniform(-0.02, 0.02)
                    lon = -35.7450 + random.uniform(-0.02, 0.02)
                elif zona_nome == 'oeste':
                    lat = -9.6700 + random.uniform(-0.02, 0.02)
                    lon = -35.7800 + random.uniform(-0.02, 0.02)
                else:  # leste
                    lat = -9.7000 + random.uniform(-0.02, 0.02)
                    lon = -35.7350 + random.uniform(-0.02, 0.02)
                
                # Determinar zona ID
                zona_id = self._determinar_zona_por_coordenada(lat, lon)
                
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
        
        # Completar com clientes restantes se necessário (distribuição aleatória)
        while len(clientes) < num_clientes:
            zona_aleatoria = random.choice([zona for zona, _ in distribuicao_zonas])
            
            # Gerar coordenadas baseadas na zona aleatória
            if zona_aleatoria == 'centro':
                lat = -9.6500 + random.uniform(-0.02, 0.02)
                lon = -35.7350 + random.uniform(-0.02, 0.02)
            elif zona_aleatoria == 'norte':
                lat = -9.6100 + random.uniform(-0.02, 0.02)
                lon = -35.7400 + random.uniform(-0.02, 0.02)
            elif zona_aleatoria == 'sul':
                lat = -9.6900 + random.uniform(-0.02, 0.02)
                lon = -35.7450 + random.uniform(-0.02, 0.02)
            elif zona_aleatoria == 'oeste':
                lat = -9.6700 + random.uniform(-0.02, 0.02)
                lon = -35.7800 + random.uniform(-0.02, 0.02)
            else:  # leste
                lat = -9.7000 + random.uniform(-0.02, 0.02)
                lon = -35.7350 + random.uniform(-0.02, 0.02)
            
            zona_id = self._determinar_zona_por_coordenada(lat, lon)
            
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
    
    def _gerar_zonas_reais(self, hubs: List[Hub], clientes: List[Cliente]) -> List[ZonaEntrega]:
        """Gera zonas de entrega baseadas na geografia real de Maceió"""
        zonas_config = [
            ("ZONA_CENTRO", "Centro", [h for h in hubs if "Centro" in h.nome or "Farol" in h.nome]),
            ("ZONA_NORTE", "Zona Norte", [h for h in hubs if "Jatiúca" in h.nome or "Pajuçara" in h.nome]),
            ("ZONA_SUL", "Zona Sul", [h for h in hubs if "Ponta" in h.nome]),
            ("ZONA_OESTE", "Zona Oeste", [h for h in hubs if "Gruta" in h.nome or "Feitosa" in h.nome or "Benedito" in h.nome]),
            ("ZONA_LESTE", "Zona Leste", [h for h in hubs if "Universitária" in h.nome or "Cruz" in h.nome]),
        ]
        
        zonas = []
        
        for zona_id, nome, hubs_zona in zonas_config:
            # Se não encontrou hubs específicos, distribuir hubs disponíveis
            if not hubs_zona:
                # Associar hubs baseado no índice
                indices_zona = {
                    "ZONA_CENTRO": [0, 1, 2],
                    "ZONA_NORTE": [3, 4],
                    "ZONA_SUL": [5, 6],
                    "ZONA_OESTE": [7, 8, 9],
                    "ZONA_LESTE": [10, 11],
                }.get(zona_id, [])
                
                hubs_zona = [hubs[i] for i in indices_zona if i < len(hubs)]
            
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
    
    def _gerar_rotas_reais(self, depositos: List[Deposito], hubs: List[Hub],
                          clientes: List[Cliente], zonas: List[ZonaEntrega]) -> List[Rota]:
        """Gera rotas baseadas no grafo real de Maceió"""
        rotas = []
        
        if self.grafo_maceio is None:
            # Fallback para método sintético
            return self._gerar_rotas_sinteticas(depositos, hubs, clientes, zonas)
        
        # Por enquanto, usar métodos sintéticos até resolver problemas de compatibilidade OSMNX
        print("Usando rotas sintéticas como fallback devido a problemas de compatibilidade OSMNX")
        return self._gerar_rotas_sinteticas(depositos, hubs, clientes, zonas)
    
    def _gerar_rotas_sinteticas(self, depositos: List[Deposito], hubs: List[Hub],
                               clientes: List[Cliente], zonas: List[ZonaEntrega]) -> List[Rota]:
        """Gera rotas usando método sintético (fallback)"""
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
    
    # Métodos de rota sintéticos (fallback)
    def _rotas_depositos_hubs(self, depositos: List[Deposito], hubs: List[Hub]) -> List[Rota]:
        """Método sintético para gerar rotas depósitos-hubs"""
        rotas = []
        for deposito in depositos:
            for hub in hubs:
                dist = self._calcular_distancia(
                    deposito.latitude, deposito.longitude,
                    hub.latitude, hub.longitude
                )
                if dist < 0.06:  # Aproximadamente 6.6km
                    cap = self._calcular_capacidade_deposito_hub(dist)
                    tempo = self._calcular_tempo_rota(dist, 25)
                    
                    rota = Rota(
                        origem=deposito.id,
                        destino=hub.id,
                        peso=dist * 111,  # Conversão para km
                        capacidade=cap,
                        tipo_rota="abastecimento",
                        tempo_medio=tempo
                    )
                    rotas.append(rota)
        return rotas
    
    def _rotas_hubs_hubs(self, hubs: List[Hub]) -> List[Rota]:
        """Método sintético para gerar rotas hub-hub"""
        rotas = []
        for hub1, hub2 in combinations(hubs, 2):
            dist = self._calcular_distancia(
                hub1.latitude, hub1.longitude,
                hub2.latitude, hub2.longitude
            )
            if dist < 0.04:  # Aproximadamente 4.4km
                cap = self._calcular_capacidade_hub_hub(dist)
                tempo = self._calcular_tempo_rota(dist, 20)
                
                rotas.extend([
                    Rota(
                        origem=hub1.id,
                        destino=hub2.id,
                        peso=dist * 111,
                        capacidade=cap,
                        tipo_rota="redistribuicao",
                        tempo_medio=tempo
                    ),
                    Rota(
                        origem=hub2.id,
                        destino=hub1.id,
                        peso=dist * 111,
                        capacidade=cap,
                        tipo_rota="redistribuicao",
                        tempo_medio=tempo
                    )
                ])
        return rotas
    
    def _rotas_hubs_clientes(self, hubs: List[Hub], clientes: List[Cliente]) -> List[Rota]:
        """Método sintético para gerar rotas hub-cliente"""
        rotas = []
        for hub in hubs:
            for cliente in clientes:
                dist = self._calcular_distancia(
                    hub.latitude, hub.longitude,
                    cliente.latitude, cliente.longitude
                )
                if dist < 0.03:  # Aproximadamente 3.3km
                    cap = self._calcular_capacidade_hub_cliente(dist, cliente.demanda_media)
                    tempo = self._calcular_tempo_rota(dist, 30)
                    custo = self._calcular_custo_entrega(dist, cliente.prioridade)
                    
                    rota = Rota(
                        origem=hub.id,
                        destino=cliente.id,
                        peso=dist * 111,
                        capacidade=cap,
                        tipo_rota="entrega_final",
                        tempo_medio=tempo,
                        custo=custo
                    )
                    rotas.append(rota)
        return rotas
    
    def _rotas_hubs_zonas(self, hubs: List[Hub], zonas: List[ZonaEntrega]) -> List[Rota]:
        """Método sintético para gerar rotas hub-zona"""
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
                
                dist = self._calcular_distancia(hub.latitude, hub.longitude, zona_lat, zona_lon)
                distancia_km = dist * 111
                tempo_minutos = self._calcular_tempo_rota(dist, 25)
                cap = self._calcular_capacidade_hub_zona(distancia_km / 10.0, zona.demanda_total)
                
                rota = Rota(
                    origem=hub.id,
                    destino=zona.id,
                    peso=distancia_km,
                    capacidade=cap,
                    tipo_rota="zona_agregada",
                    tempo_medio=tempo_minutos
                )
                rotas.append(rota)
        return rotas

    def _gerar_veiculos(self, hubs: List[Hub], num_entregadores: Optional[int] = None) -> List[Veiculo]:
        """Gera frota de veículos distribuída pelos hubs"""
        if num_entregadores is None:
            num_entregadores = max(5, len(hubs) * 2)  # 2 veículos por hub mínimo
        
        veiculos = []
        tipos_veiculo = [TipoVeiculo.MOTO, TipoVeiculo.VAN, TipoVeiculo.CAMINHAO]
        pesos_tipos = [60, 30, 10]  # Mais motos para delivery urbano
        
        for i in range(num_entregadores):
            hub_base = hubs[i % len(hubs)]  # Distribuir entre os hubs
            tipo = random.choices(tipos_veiculo, weights=pesos_tipos, k=1)[0]
            
            # Capacidade baseada no tipo
            capacidades = {
                TipoVeiculo.MOTO: random.randint(5, 15),
                TipoVeiculo.VAN: random.randint(20, 50),
                TipoVeiculo.CAMINHAO: random.randint(80, 150)
            }
            
            # Velocidade baseada no tipo
            velocidades = {
                TipoVeiculo.MOTO: random.randint(25, 40),
                TipoVeiculo.VAN: random.randint(20, 35),
                TipoVeiculo.CAMINHAO: random.randint(15, 30)
            }
            
            veiculo = Veiculo(
                id=f"VEI_{i+1:03d}",
                tipo=tipo,
                capacidade=capacidades[tipo],
                velocidade_media=velocidades[tipo],
                hub_base=hub_base.id,
                condutor=f"Entregador {i+1}"
            )
            veiculos.append(veiculo)
        
        return veiculos

    # Métodos auxiliares para cálculos
    def _calcular_distancia(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calcula distância euclidiana entre duas coordenadas (aproximada em graus)"""
        return math.sqrt((lat2 - lat1)**2 + (lon2 - lon1)**2)
    
    def _calcular_tempo_rota(self, distancia_graus: float, velocidade_kmh: float) -> float:
        """Calcula tempo de viagem aproximado em minutos"""
        distancia_km = distancia_graus * 111  # Conversão aproximada graus -> km
        tempo_horas = distancia_km / velocidade_kmh
        return tempo_horas * 60  # Converter para minutos
    
    def _calcular_capacidade_deposito_hub(self, fator_distancia: float) -> int:
        """Calcula capacidade da rota depósito-hub baseada na distância"""
        # Capacidade base diminui com a distância
        capacidade_base = 200
        return max(50, int(capacidade_base * (1 - fator_distancia)))
    
    def _calcular_capacidade_hub_hub(self, fator_distancia: float) -> int:
        """Calcula capacidade da rota hub-hub baseada na distância"""
        capacidade_base = 150
        return max(30, int(capacidade_base * (1 - fator_distancia)))
    
    def _calcular_capacidade_hub_cliente(self, fator_distancia: float, demanda_cliente: int) -> int:
        """Calcula capacidade da rota hub-cliente baseada na distância e demanda"""
        capacidade_base = max(10, demanda_cliente * 5)
        return max(5, int(capacidade_base * (1 - fator_distancia * 0.5)))
    
    def _calcular_capacidade_hub_zona(self, fator_distancia: float, demanda_zona: float) -> int:
        """Calcula capacidade da rota hub-zona baseada na distância e demanda total"""
        capacidade_base = max(50, int(demanda_zona * 2))
        return max(25, int(capacidade_base * (1 - fator_distancia * 0.3)))
    
    def _calcular_custo_entrega(self, fator_distancia: float, prioridade: PrioridadeCliente) -> float:
        """Calcula custo de entrega baseado na distância e prioridade"""
        custo_base = 5.0
        multiplicador_prioridade = {
            PrioridadeCliente.BAIXA: 0.8,
            PrioridadeCliente.NORMAL: 1.0,
            PrioridadeCliente.ALTA: 1.3,
            PrioridadeCliente.URGENTE: 1.8,
            PrioridadeCliente.CRITICA: 2.5
        }
        return custo_base * (1 + fator_distancia) * multiplicador_prioridade[prioridade]

    def _gerar_distribuicao_estrategica(self, num_pontos: int, tipo_ponto: str = "hub") -> List[Tuple[float, float, str]]:
        """
        Gera distribuição estratégica de pontos baseada em características urbanas dinâmicas.
        
        Args:
            num_pontos: Número de pontos a gerar
            tipo_ponto: Tipo do ponto ("hub", "deposito", "cliente")
        
        Returns:
            Lista de tuplas (lat, lon, zona_nome)
        """
        pontos = []
        
        # Estratégias baseadas no tipo de ponto
        if tipo_ponto == "deposito":
            # Depósitos: preferir zonas centrais e oeste (industrial)
            zonas_preferidas = [('centro', 0.3), ('oeste', 0.4), ('norte', 0.15), ('sul', 0.1), ('leste', 0.05)]
        elif tipo_ponto == "hub":
            # Hubs: distribuição mais equilibrada, mas priorizando densidade
            zonas_preferidas = [('centro', 0.2), ('norte', 0.25), ('sul', 0.25), ('oeste', 0.2), ('leste', 0.1)]
        else:  # clientes
            # Clientes: distribuição baseada em densidade populacional estimada
            zonas_preferidas = [('norte', 0.28), ('sul', 0.26), ('oeste', 0.24), ('centro', 0.15), ('leste', 0.07)]
        
        # Gerar pontos baseado na distribuição estratégica
        for zona, percentual in zonas_preferidas:
            num_zona = int(num_pontos * percentual)
            
            for _ in range(num_zona):
                # Gerar coordenadas baseadas na zona
                if zona == 'centro':
                    lat = -9.6500 + random.uniform(-0.02, 0.02)
                    lon = -35.7350 + random.uniform(-0.02, 0.02)
                elif zona == 'norte':
                    lat = -9.6100 + random.uniform(-0.02, 0.02)
                    lon = -35.7400 + random.uniform(-0.02, 0.02)
                elif zona == 'sul':
                    lat = -9.6900 + random.uniform(-0.02, 0.02)
                    lon = -35.7450 + random.uniform(-0.02, 0.02)
                elif zona == 'oeste':
                    lat = -9.6700 + random.uniform(-0.02, 0.02)
                    lon = -35.7800 + random.uniform(-0.02, 0.02)
                else:  # leste
                    lat = -9.7000 + random.uniform(-0.02, 0.02)
                    lon = -35.7350 + random.uniform(-0.02, 0.02)
                pontos.append((lat, lon, zona))
        
        # Completar pontos restantes distribuindo aleatoriamente
        while len(pontos) < num_pontos:
            zona = random.choice([z for z, _ in zonas_preferidas])
            # Gerar coordenadas baseadas na zona aleatória
            if zona == 'centro':
                lat = -9.6500 + random.uniform(-0.02, 0.02)
                lon = -35.7350 + random.uniform(-0.02, 0.02)
            elif zona == 'norte':
                lat = -9.6100 + random.uniform(-0.02, 0.02)
                lon = -35.7400 + random.uniform(-0.02, 0.02)
            elif zona == 'sul':
                lat = -9.6900 + random.uniform(-0.02, 0.02)
                lon = -35.7450 + random.uniform(-0.02, 0.02)
            elif zona == 'oeste':
                lat = -9.6700 + random.uniform(-0.02, 0.02)
                lon = -35.7800 + random.uniform(-0.02, 0.02)
            else:  # leste
                lat = -9.7000 + random.uniform(-0.02, 0.02)
                lon = -35.7350 + random.uniform(-0.02, 0.02)
            pontos.append((lat, lon, zona))
        
        return pontos[:num_pontos]

    def _aplicar_espacamento_minimo(self, pontos: List[Tuple[float, float, str]], 
                                   distancia_min: float = 0.005) -> List[Tuple[float, float, str]]:
        """
        Aplica espaçamento mínimo entre pontos para evitar sobreposição.
        
        Args:
            pontos: Lista de pontos (lat, lon, zona)
            distancia_min: Distância mínima entre pontos em graus
            
        Returns:
            Lista de pontos com espaçamento aplicado
        """
        if not pontos:
            return pontos
        
        pontos_espacados = [pontos[0]]  # Sempre incluir o primeiro ponto
        
        for lat, lon, zona in pontos[1:]:
            # Verificar distância mínima de todos os pontos já adicionados
            muito_proximo = False
            
            for lat_existente, lon_existente, _ in pontos_espacados:
                distancia = math.sqrt((lat - lat_existente)**2 + (lon - lon_existente)**2)
                if distancia < distancia_min:
                    muito_proximo = True
                    break
            
            if not muito_proximo:
                pontos_espacados.append((lat, lon, zona))
            else:
                # Tentar gerar novo ponto na mesma zona
                tentativas = 0
                while tentativas < 5:  # Máximo 5 tentativas
                    # Gerar nova coordenada baseada na zona
                    if zona == 'centro':
                        nova_lat = -9.6500 + random.uniform(-0.02, 0.02)
                        nova_lon = -35.7350 + random.uniform(-0.02, 0.02)
                    elif zona == 'norte':
                        nova_lat = -9.6100 + random.uniform(-0.02, 0.02)
                        nova_lon = -35.7400 + random.uniform(-0.02, 0.02)
                    elif zona == 'sul':
                        nova_lat = -9.6900 + random.uniform(-0.02, 0.02)
                        nova_lon = -35.7450 + random.uniform(-0.02, 0.02)
                    elif zona == 'oeste':
                        nova_lat = -9.6700 + random.uniform(-0.02, 0.02)
                        nova_lon = -35.7800 + random.uniform(-0.02, 0.02)
                    else:  # leste
                        nova_lat = -9.7000 + random.uniform(-0.02, 0.02)
                        nova_lon = -35.7350 + random.uniform(-0.02, 0.02)
                    
                    # Verificar se nova posição tem espaçamento adequado
                    adequado = True
                    for lat_existente, lon_existente, _ in pontos_espacados:
                        distancia = math.sqrt((nova_lat - lat_existente)**2 + (nova_lon - lon_existente)**2)
                        if distancia < distancia_min:
                            adequado = False
                            break
                    
                    if adequado:
                        pontos_espacados.append((nova_lat, nova_lon, zona))
                        break
                    
                    tentativas += 1
        
        return pontos_espacados

    def salvar_json(self, rede: RedeEntrega, arquivo: str):
        """Salva a rede completa em arquivo JSON"""
        dados = {
            "metadata": {
                "timestamp": get_brazilian_timestamp().isoformat(),
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
    
    def _gerar_coordenada_proxima_clientes(self, zona_nome: str, clientes: Optional[List[Cliente]] = None, 
                                          distancia_min: float = 0.002) -> Tuple[float, float]:
        """
        Gera coordenada próxima aos clientes da zona, mas não sobreposta e em área terrestre segura.
        
        Args:
            zona_nome: Nome da zona ('centro', 'norte', 'sul', 'oeste', 'leste')
            clientes: Lista de clientes para usar como referência
            distancia_min: Distância mínima dos clientes em graus
            
        Returns:
            Tupla (latitude, longitude)
        """
        if not clientes:
            # Fallback: usar coordenadas padrão da zona
            return self._obter_coordenada_zona_segura(zona_nome)
        
        # Filtrar clientes da zona específica
        zona_id = f"ZONA_{zona_nome.upper()}"
        clientes_zona = [c for c in clientes if c.zona_id == zona_id]
        
        if not clientes_zona:
            # Se não há clientes na zona, usar coordenadas padrão seguras
            return self._obter_coordenada_zona_segura(zona_nome)
        
        # Calcular centroide dos clientes da zona
        lat_media = sum(c.latitude for c in clientes_zona) / len(clientes_zona)
        lon_media = sum(c.longitude for c in clientes_zona) / len(clientes_zona)
        
        # Tentar gerar coordenada próxima, mas não sobreposta e em área terrestre
        max_tentativas = 30
        for _ in range(max_tentativas):
            # Gerar offset aleatório próximo ao centroide
            offset_lat = random.uniform(-0.003, 0.003)
            offset_lon = random.uniform(-0.003, 0.003)
            
            nova_lat = lat_media + offset_lat
            nova_lon = lon_media + offset_lon
            
            # Verificar se a coordenada está em área terrestre segura
            if not self._eh_coordenada_terrestre_segura(nova_lat, nova_lon):
                continue
            
            # Verificar se está longe o suficiente de todos os clientes
            muito_proximo = False
            for cliente in clientes_zona:
                distancia = math.sqrt((nova_lat - cliente.latitude)**2 + (nova_lon - cliente.longitude)**2)
                if distancia < distancia_min:
                    muito_proximo = True
                    break
            
            if not muito_proximo:
                return nova_lat, nova_lon
        
        # Se não conseguiu encontrar posição adequada, usar coordenada segura da zona
        return self._obter_coordenada_zona_segura(zona_nome)
    
    def _eh_coordenada_terrestre_segura(self, lat: float, lon: float) -> bool:
        """
        Verifica se a coordenada está em área terrestre segura, evitando água/lagoa.
        
        Args:
            lat: Latitude da coordenada
            lon: Longitude da coordenada
            
        Returns:
            True se a coordenada está em área terrestre segura
        """
        # Áreas problemáticas conhecidas em Maceió (água/lagoa)
        areas_problematicas = [
            # Lagoa Mundaú (principal área problemática)
            (-9.670, -35.740, -9.650, -35.710),  # (lat_min, lon_min, lat_max, lon_max)
            # Oceano Atlântico (costa leste)
            (-9.700, -35.710, -9.600, -35.690),
            # Outras áreas aquáticas menores
            (-9.680, -35.720, -9.660, -35.700),
            # Área da barra/canal
            (-9.665, -35.715, -9.645, -35.705),
        ]
        
        # Verificar se a coordenada está em alguma área problemática
        for lat_min, lon_min, lat_max, lon_max in areas_problematicas:
            if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
                return False
        
        # Verificar se está muito próximo da costa (longitude muito a leste)
        if lon > -35.700:  # Muito próximo do oceano
            return False
        
        # Verificar se está em área muito ao sul (pode ser água)
        if lat > -9.600 and lon > -35.720:  # Área norte próxima à lagoa
            return False
            
        # Se passou por todas as verificações, é área terrestre segura
        return True
    
    def _obter_coordenada_zona_segura(self, zona_nome: str) -> Tuple[float, float]:
        """Retorna coordenadas seguras (terrestres) para cada zona, evitando água/lagoa"""
        # Coordenadas seguras mais para o interior, longe da costa e lagoas
        coordenadas_seguras = {
            'centro': (-9.6480, -35.7320),    # Centro mais interno
            'norte': (-9.6080, -35.7380),     # Norte mais interno  
            'sul': (-9.6880, -35.7430),      # Sul mais interno
            'oeste': (-9.6680, -35.7780),    # Oeste área industrial
            'leste': (-9.6980, -35.7330)     # Leste área universitária
        }
        
        if zona_nome in coordenadas_seguras:
            lat_base, lon_base = coordenadas_seguras[zona_nome]
            # Adicionar pequena variação aleatória em área segura
            lat = lat_base + random.uniform(-0.001, 0.001)
            lon = lon_base + random.uniform(-0.001, 0.001)
            return lat, lon
        
        # Fallback para centro seguro
        return -9.6480 + random.uniform(-0.001, 0.001), -35.7320 + random.uniform(-0.001, 0.001)


# Função de conveniência
def gerar_rede_maceio_completa(num_clientes: int = 100, seed: int = 42) -> RedeEntrega:
    """Função de conveniência para gerar rede completa"""
    gerador = GeradorMaceioCompleto(seed=seed)
    return gerador.gerar_rede_completa(num_clientes=num_clientes)
