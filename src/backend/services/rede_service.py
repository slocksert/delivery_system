import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from core.entities.models import RedeEntrega, Deposito, Hub, ZonaEntrega, Rota, Cliente, PrioridadeCliente, Veiculo, TipoVeiculo
from core.generators.gerador_completo import GeradorMaceioCompleto
from typing import List, Dict, Any, Optional
import time
from ..database.sqlite import SQLiteDB

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
        self._carregar_redes_do_banco()

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
                    nome=node["nome"]
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
            rede.rotas.append(Rota(
                origem=edge["origem"],
                destino=edge["destino"],
                peso=edge.get("peso", edge.get("distancia", 1.0)),
                capacidade=edge["capacidade"]
            ))
        return rede

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
                    nome=node_data['nome']
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
        
        todos_nos = []
        
        for deposito in rede.depositos:
            todos_nos.append({
                "id": deposito.id,
                "nome": deposito.nome,
                "tipo": "deposito"
            })
        
        for hub in rede.hubs:
            todos_nos.append({
                "id": hub.id,
                "nome": hub.nome,
                "tipo": "hub"
            })
        
        for zona in rede.zonas:
            todos_nos.append({
                "id": zona.id,
                "nome": zona.nome,
                "tipo": "zona"
            })
        
        return {
            'nome': metadata.get('nome', 'Rede sem nome'),
            'total_nodes': len(todos_nos),
            'total_edges': len(rede.rotas),
            'nodes_por_tipo': self._contar_nodes_por_tipo(rede),
            'capacidade_total': sum(rota.capacidade for rota in rede.rotas),
            'nodes': todos_nos
        }
    
    def preparar_para_calculo_fluxo(self, rede_id: str, origem: str, destino: str) -> Dict[str, Any]:
        if rede_id not in self.redes_cache:
            raise ValueError("Rede não encontrada")
        
        rede = self.redes_cache[rede_id]
        
        todos_ids = []
        todos_ids.extend([d.id for d in rede.depositos])
        todos_ids.extend([h.id for h in rede.hubs])
        todos_ids.extend([z.id for z in rede.zonas])
        
        if origem not in todos_ids:
            raise ValueError(f"Nó origem '{origem}' não encontrado")
        if destino not in todos_ids:
            raise ValueError(f"Nó destino '{destino}' não encontrado")
        
        return {
            'rede_preparada': True,
            'origem': origem,
            'destino': destino,
            'grafo_info': {
                'total_nodes': len(todos_ids),
                'total_edges': len(rede.rotas),
                'nodes_disponiveis': todos_ids
            },
            'status': 'Aguardando implementação do Dev 2 (Algoritmos de Fluxo)',
            'proximos_passos': [
                '1. Dev 2 implementar Ford-Fulkerson/Edmonds-Karp',
                '2. Integrar algoritmos neste service',
                '3. Retornar fluxo máximo calculado'
            ]
        }
    
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