"""
Utilitários para manipulação de dados
Suporte para todas as entidades do sistema
"""

import json
import networkx as nx
from typing import Dict, List, Any, Optional
from datetime import datetime

from ..entities.models import (
    Deposito, Hub, Cliente, ZonaEntrega, Veiculo, Pedido, Rota, RedeEntrega,
    TipoVeiculo, StatusPedido, PrioridadeCliente
)


def carregar_rede_completa(path: str) -> RedeEntrega:
    """Carrega rede completa de arquivo JSON"""
    with open(path, "r", encoding='utf-8') as f:
        data = json.load(f)
    
    # Carregar depósitos
    depositos = []
    for d in data.get("depositos", []):
        deposito = Deposito(
            id=d["id"],
            latitude=d["latitude"],
            longitude=d["longitude"],
            nome=d.get("nome", ""),
            capacidade_maxima=d.get("capacidade_maxima", 1000),
            endereco=d.get("endereco", "")
        )
        depositos.append(deposito)
    
    # Carregar hubs
    hubs = []
    hubs_dict = {}  # Para referência rápida
    for h in data.get("hubs", []):
        hub = Hub(
            id=h["id"],
            latitude=h["latitude"],
            longitude=h["longitude"],
            capacidade=h["capacidade"],
            nome=h.get("nome", ""),
            endereco=h.get("endereco", ""),
            operacional=h.get("operacional", True)
        )
        hubs.append(hub)
        hubs_dict[hub.id] = hub
    
    # Carregar clientes
    clientes = []
    clientes_dict = {}  # Para referência rápida
    for c in data.get("clientes", []):
        prioridade = PrioridadeCliente(c.get("prioridade", 2))
        
        cliente = Cliente(
            id=c["id"],
            latitude=c["latitude"],
            longitude=c["longitude"],
            demanda_media=c.get("demanda_media", 1),
            prioridade=prioridade,
            endereco=c.get("endereco", ""),
            zona_id=c.get("zona_id", ""),
            ativo=c.get("ativo", True)
        )
        clientes.append(cliente)
        clientes_dict[cliente.id] = cliente
    
    # Carregar zonas
    zonas = []
    for z in data.get("zonas", []):
        # Associar hubs da zona
        hubs_zona = [hubs_dict[hub_id] for hub_id in z.get("hubs", []) 
                    if hub_id in hubs_dict]
        
        # Associar clientes da zona
        clientes_zona = [clientes_dict[cliente_id] for cliente_id in z.get("clientes", [])
                        if cliente_id in clientes_dict]
        
        zona = ZonaEntrega(
            id=z["id"],
            nome=z.get("nome", ""),
            hubs=hubs_zona,
            clientes=clientes_zona,
            demanda_total=z.get("demanda_total", 0),
            area_cobertura=z.get("area_cobertura", 0.0)
        )
        zonas.append(zona)
    
    # Carregar veículos
    veiculos = []
    for v in data.get("veiculos", []):
        tipo = TipoVeiculo(v.get("tipo", "moto"))
        
        veiculo = Veiculo(
            id=v["id"],
            tipo=tipo,
            capacidade=v["capacidade"],
            velocidade_media=v["velocidade_media"],
            hub_base=v["hub_base"],
            disponivel=v.get("disponivel", True),
            condutor=v.get("condutor", "")
        )
        veiculos.append(veiculo)
    
    # Carregar rotas
    rotas = []
    for r in data.get("rotas", []):
        rota = Rota(
            origem=r["origem"],
            destino=r["destino"],
            peso=r.get("peso", 1.0),
            capacidade=r["capacidade"],
            tipo_rota=r.get("tipo_rota", "terrestre"),
            tempo_medio=r.get("tempo_medio", 0.0),
            custo=r.get("custo", 0.0),
            ativa=r.get("ativa", True)
        )
        rotas.append(rota)
    
    # Carregar pedidos (se existirem)
    pedidos = []
    for p in data.get("pedidos", []):
        status = StatusPedido(p.get("status", "pendente"))
        prioridade = PrioridadeCliente(p.get("prioridade", 2))
        
        # Tratar timestamp
        timestamp_criacao = datetime.now()
        if "timestamp_criacao" in p:
            timestamp_criacao = datetime.fromisoformat(p["timestamp_criacao"])
        
        timestamp_entrega = None
        if "timestamp_entrega" in p and p["timestamp_entrega"]:
            timestamp_entrega = datetime.fromisoformat(p["timestamp_entrega"])
        
        pedido = Pedido(
            id=p["id"],
            cliente_id=p["cliente_id"],
            origem_hub=p.get("origem_hub", ""),
            veiculo_id=p.get("veiculo_id", ""),
            timestamp_criacao=timestamp_criacao,
            timestamp_entrega=timestamp_entrega,
            prioridade=prioridade,
            peso=p.get("peso", 1.0),
            volume=p.get("volume", 1.0),
            status=status,
            observacoes=p.get("observacoes", "")
        )
        pedidos.append(pedido)
    
    # Criar rede
    rede = RedeEntrega(
        depositos=depositos,
        hubs=hubs,
        clientes=clientes,
        zonas=zonas,
        veiculos=veiculos,
        rotas=rotas,
        pedidos=pedidos
    )
    
    return rede


def carregar_dados_legado(path: str) -> RedeEntrega:
    """Carrega dados do formato antigo e converte para o novo formato"""
    with open(path, "r", encoding='utf-8') as f:
        data = json.load(f)
    
    # Converter formato antigo
    depositos = [Deposito(**d) for d in data.get("depositos", [])]
    
    hubs = []
    hubs_dict = {}
    for h in data.get("hubs", []):
        hub = Hub(**h, nome="", endereco="")
        hubs.append(hub)
        hubs_dict[hub.id] = hub
    
    # No formato antigo, não há clientes - criar zona sem clientes
    zonas = []
    for z in data.get("zonas", []):
        hubs_zona = [hubs_dict[h] for h in z["hubs"] if h in hubs_dict]
        zona = ZonaEntrega(
            id=z["id"],
            nome=z["id"].replace("ZONA_", "").title(),
            hubs=hubs_zona,
            clientes=[],  # Vazio no formato antigo
            demanda_total=0
        )
        zonas.append(zona)
    
    # Converter rotas
    rotas = []
    for r in data.get("rotas", []):
        rota = Rota(
            origem=r["origem"],
            destino=r["destino"],
            peso=r.get("peso", 1.0),
            capacidade=r["capacidade"],
            tipo_rota="legado"
        )
        rotas.append(rota)
    
    rede = RedeEntrega(
        depositos=depositos,
        hubs=hubs,
        clientes=[],  # Vazio no formato antigo
        zonas=zonas,
        veiculos=[],  # Vazio no formato antigo
        rotas=rotas,
        pedidos=[]   # Vazio no formato antigo
    )
    
    return rede


def validar_rede_completa(rede: RedeEntrega) -> Dict[str, Any]:
    """Validação completa da integridade da rede expandida"""
    problemas = []
    warnings = []
    
    # Validações básicas
    if not rede.depositos:
        problemas.append("Rede sem depósitos")
    
    if not rede.hubs:
        problemas.append("Rede sem hubs")
    
    if not rede.rotas:
        problemas.append("Rede sem rotas")
    
    # Validar capacidades
    for hub in rede.hubs:
        if hub.capacidade <= 0:
            problemas.append(f"Hub {hub.id} com capacidade inválida: {hub.capacidade}")
    
    for rota in rede.rotas:
        if rota.capacidade <= 0:
            problemas.append(f"Rota {rota.origem}->{rota.destino} com capacidade inválida")
    
    # Validar conectividade básica
    try:
        vertices = rede.obter_vertices()
        grafo = nx.DiGraph()
        grafo.add_nodes_from(vertices)
        
        for rota in rede.rotas:
            if rota.ativa:
                grafo.add_edge(rota.origem, rota.destino)
        
        # Verificar conectividade depósitos → hubs
        depositos_ids = [d.id for d in rede.depositos]
        hubs_ids = [h.id for h in rede.hubs if h.operacional]
        
        for dep_id in depositos_ids:
            conectado = False
            for hub_id in hubs_ids:
                if nx.has_path(grafo, dep_id, hub_id):
                    conectado = True
                    break
            if not conectado:
                problemas.append(f"Depósito {dep_id} não conectado a nenhum hub")
        
        # Verificar conectividade hubs → clientes (se existirem)
        if rede.clientes:
            clientes_conectados = 0
            for cliente in rede.clientes:
                if cliente.ativo:
                    conectado = False
                    for hub_id in hubs_ids:
                        if nx.has_path(grafo, hub_id, cliente.id):
                            conectado = True
                            clientes_conectados += 1
                            break
                    if not conectado:
                        warnings.append(f"Cliente {cliente.id} não conectado a nenhum hub")
            
            if clientes_conectados == 0 and len(rede.clientes) > 0:
                problemas.append("Nenhum cliente conectado aos hubs")
    
    except Exception as e:
        problemas.append(f"Erro na validação de conectividade: {str(e)}")
    
    # Validar consistência de zonas
    for zona in rede.zonas:
        # Verificar se clientes da zona estão na lista principal
        for cliente in zona.clientes:
            if cliente not in rede.clientes:
                problemas.append(f"Cliente {cliente.id} da zona {zona.id} não está na lista principal")
        
        # Verificar se hubs da zona estão na lista principal
        for hub in zona.hubs:
            if hub not in rede.hubs:
                problemas.append(f"Hub {hub.id} da zona {zona.id} não está na lista principal")
    
    # Validar veículos
    hub_ids = {h.id for h in rede.hubs}
    for veiculo in rede.veiculos:
        if veiculo.hub_base not in hub_ids:
            problemas.append(f"Veículo {veiculo.id} tem hub_base inválido: {veiculo.hub_base}")
    
    # Validar pedidos
    cliente_ids = {c.id for c in rede.clientes}
    veiculo_ids = {v.id for v in rede.veiculos}
    
    for pedido in rede.pedidos:
        if pedido.cliente_id not in cliente_ids:
            problemas.append(f"Pedido {pedido.id} tem cliente_id inválido: {pedido.cliente_id}")
        
        if pedido.veiculo_id and pedido.veiculo_id not in veiculo_ids:
            warnings.append(f"Pedido {pedido.id} tem veiculo_id inválido: {pedido.veiculo_id}")
        
        if pedido.origem_hub and pedido.origem_hub not in hub_ids:
            warnings.append(f"Pedido {pedido.id} tem origem_hub inválido: {pedido.origem_hub}")
    
    # Análise de capacidade vs demanda
    if rede.clientes:
        demanda_total = rede.obter_demanda_total()
        capacidade_total = rede.obter_capacidade_total()
        
        if demanda_total > capacidade_total:
            warnings.append(f"Demanda total ({demanda_total}) excede capacidade total ({capacidade_total})")
        elif capacidade_total > demanda_total * 2:
            warnings.append(f"Capacidade excessiva: {capacidade_total} vs demanda {demanda_total}")
    
    return {
        'rede_valida': len(problemas) == 0,
        'problemas': problemas,
        'warnings': warnings,
        'total_problemas': len(problemas),
        'total_warnings': len(warnings),
        'estatisticas': rede.obter_estatisticas()
    }


def construir_grafo_networkx_completo(rede: RedeEntrega) -> nx.DiGraph:
    """Constrói um grafo NetworkX completo a partir da rede"""
    grafo = nx.DiGraph()
    
    # Adicionar todos os vértices com atributos
    for deposito in rede.depositos:
        grafo.add_node(deposito.id, 
                      tipo='deposito',
                      latitude=deposito.latitude,
                      longitude=deposito.longitude,
                      capacidade=deposito.capacidade_maxima,
                      nome=deposito.nome)
    
    for hub in rede.hubs:
        grafo.add_node(hub.id,
                      tipo='hub',
                      latitude=hub.latitude,
                      longitude=hub.longitude,
                      capacidade=hub.capacidade,
                      nome=hub.nome,
                      operacional=hub.operacional)
    
    for cliente in rede.clientes:
        grafo.add_node(cliente.id,
                      tipo='cliente',
                      latitude=cliente.latitude,
                      longitude=cliente.longitude,
                      demanda=cliente.demanda_media,
                      prioridade=cliente.prioridade.value,
                      zona_id=cliente.zona_id,
                      ativo=cliente.ativo)
    
    for zona in rede.zonas:
        grafo.add_node(zona.id,
                      tipo='zona',
                      nome=zona.nome,
                      demanda_total=zona.demanda_total,
                      num_clientes=len(zona.clientes),
                      num_hubs=len(zona.hubs))
    
    # Adicionar arestas com atributos
    for rota in rede.rotas:
        if rota.ativa:
            grafo.add_edge(rota.origem, rota.destino,
                          peso=rota.peso,
                          capacidade=rota.capacidade,
                          tipo_rota=rota.tipo_rota,
                          tempo_medio=rota.tempo_medio,
                          custo=rota.custo)
    
    return grafo


def exportar_para_diversos_formatos(rede: RedeEntrega, prefixo_arquivo: str):
    """Exporta a rede para diversos formatos úteis"""
    import pandas as pd
    
    # 1. CSV das entidades
    # Depósitos
    df_depositos = pd.DataFrame([
        {
            'id': d.id,
            'latitude': d.latitude,
            'longitude': d.longitude,
            'nome': d.nome,
            'capacidade_maxima': d.capacidade_maxima,
            'endereco': d.endereco
        }
        for d in rede.depositos
    ])
    df_depositos.to_csv(f"{prefixo_arquivo}_depositos.csv", index=False)
    
    # Hubs
    df_hubs = pd.DataFrame([
        {
            'id': h.id,
            'latitude': h.latitude,
            'longitude': h.longitude,
            'capacidade': h.capacidade,
            'nome': h.nome,
            'endereco': h.endereco,
            'operacional': h.operacional
        }
        for h in rede.hubs
    ])
    df_hubs.to_csv(f"{prefixo_arquivo}_hubs.csv", index=False)
    
    # Clientes
    if rede.clientes:
        df_clientes = pd.DataFrame([
            {
                'id': c.id,
                'latitude': c.latitude,
                'longitude': c.longitude,
                'demanda_media': c.demanda_media,
                'prioridade': c.prioridade.value,
                'endereco': c.endereco,
                'zona_id': c.zona_id,
                'ativo': c.ativo
            }
            for c in rede.clientes
        ])
        df_clientes.to_csv(f"{prefixo_arquivo}_clientes.csv", index=False)
    
    # Rotas
    df_rotas = pd.DataFrame([
        {
            'origem': r.origem,
            'destino': r.destino,
            'peso': r.peso,
            'capacidade': r.capacidade,
            'tipo_rota': r.tipo_rota,
            'tempo_medio': r.tempo_medio,
            'custo': r.custo,
            'ativa': r.ativa
        }
        for r in rede.rotas
    ])
    df_rotas.to_csv(f"{prefixo_arquivo}_rotas.csv", index=False)
    
    # 2. Grafo para análise
    grafo = construir_grafo_networkx_completo(rede)
    nx.write_gexf(grafo, f"{prefixo_arquivo}_grafo.gexf")
    
    # 3. Resumo estatístico
    stats = rede.obter_estatisticas()
    with open(f"{prefixo_arquivo}_estatisticas.json", 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    
    print(f"Rede exportada para múltiplos formatos com prefixo: {prefixo_arquivo}")


# Função de conveniência para migração
def migrar_formato_antigo_para_novo(arquivo_antigo: str, arquivo_novo: str, 
                                   num_clientes: int = 100):
    """Migra arquivo do formato antigo para o novo formato completo"""
    from ..generators.gerador_completo import GeradorMaceioCompleto
    
    # Carregar dados antigos
    rede_antiga = carregar_dados_legado(arquivo_antigo)
    
    # Gerar dados completos baseados na estrutura antiga
    gerador = GeradorMaceioCompleto()
    rede_nova = gerador.gerar_rede_completa(num_clientes=num_clientes)
    
    # Preservar depósitos e hubs originais se compatíveis
    if len(rede_antiga.depositos) <= len(rede_nova.depositos):
        for i, dep_antigo in enumerate(rede_antiga.depositos):
            rede_nova.depositos[i].latitude = dep_antigo.latitude
            rede_nova.depositos[i].longitude = dep_antigo.longitude
    
    # Salvar nova rede
    gerador.salvar_json(rede_nova, arquivo_novo)
    
    print(f"Migração concluída: {arquivo_antigo} → {arquivo_novo}")
    return rede_nova
