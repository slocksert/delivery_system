"""
Algoritmos de Fluxo Máximo para Otimização de Entregas.

Este módulo implementa os algoritmos Ford-Fulkerson e Edmonds-Karp para
calcular o fluxo máximo em redes de entrega, utilizando estruturas de dados
compatíveis com o sistema existente.
"""

from typing import Dict, List, Set, Tuple, Optional, Any
from collections import defaultdict, deque
import networkx as nx
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class FlowResult:
    """Resultado do cálculo de fluxo máximo."""
    max_flow_value: float
    flow_dict: Dict[str, Dict[str, float]]
    cut_edges: List[Tuple[str, str]]
    paths_used: List[List[str]]
    algorithm_used: str
    execution_time: float
    
    
class MaxFlowCalculator:
    """Classe base para algoritmos de fluxo máximo."""
    
    def __init__(self, graph: nx.DiGraph):
        """
        Inicializa o calculador de fluxo.
        
        Args:
            graph: Grafo direcionado NetworkX com capacidades nas arestas
        """
        self.graph = graph.copy()
        self.original_graph = graph.copy()
        
    def _validate_graph(self, source: str, sink: str) -> bool:
        """Valida se o grafo e os nós são válidos para cálculo de fluxo."""
        if source not in self.graph:
            raise ValueError(f"Nó fonte '{source}' não encontrado no grafo")
        if sink not in self.graph:
            raise ValueError(f"Nó destino '{sink}' não encontrado no grafo")
        if source == sink:
            raise ValueError("Nó fonte e destino não podem ser iguais")
        return True
    
    def _get_capacity(self, u: str, v: str) -> float:
        """Obtém a capacidade da aresta entre dois nós."""
        if self.graph.has_edge(u, v):
            return self.graph[u][v].get('capacity', 0.0)
        return 0.0
    
    def _set_flow(self, u: str, v: str, flow: float):
        """Define o fluxo em uma aresta."""
        if not self.graph.has_edge(u, v):
            self.graph.add_edge(u, v, flow=0.0)
        self.graph[u][v]['flow'] = flow
        
    def _get_flow(self, u: str, v: str) -> float:
        """Obtém o fluxo atual em uma aresta."""
        if self.graph.has_edge(u, v):
            return self.graph[u][v].get('flow', 0.0)
        return 0.0


class FordFulkerson(MaxFlowCalculator):
    """
    Implementação do algoritmo Ford-Fulkerson para fluxo máximo.
    
    Utiliza busca em profundidade (DFS) para encontrar caminhos aumentantes
    no grafo residual.
    """
    
    def __init__(self, graph: nx.DiGraph):
        super().__init__(graph)
        self.paths_found = []
        
    def _build_residual_graph(self) -> nx.DiGraph:
        """Constrói o grafo residual com capacidades residuais."""
        residual = nx.DiGraph()
        
        # Adiciona arestas diretas
        for u, v, data in self.graph.edges(data=True):
            capacity = data.get('capacity', 0.0)
            flow = data.get('flow', 0.0)
            residual_capacity = capacity - flow
            
            if residual_capacity > 0:
                residual.add_edge(u, v, capacity=residual_capacity)
                
        # Adiciona arestas reversas para fluxo existente
        for u, v, data in self.graph.edges(data=True):
            flow = data.get('flow', 0.0)
            if flow > 0:
                residual.add_edge(v, u, capacity=flow)
                
        return residual
    
    def _find_augmenting_path_dfs(self, source: str, sink: str, 
                                 residual: nx.DiGraph, 
                                 visited: Set[str], 
                                 path: List[str]) -> Optional[List[str]]:
        """
        Encontra um caminho aumentante usando DFS.
        
        Returns:
            Lista de nós representando o caminho, ou None se não encontrado
        """
        if source == sink:
            return path + [sink]
            
        visited.add(source)
        
        for neighbor in residual.neighbors(source):
            if neighbor not in visited:
                capacity = residual[source][neighbor]['capacity']
                if capacity > 0:
                    result = self._find_augmenting_path_dfs(
                        neighbor, sink, residual, visited, path + [source]
                    )
                    if result:
                        return result
        
        return None
    
    def _find_path_bottleneck(self, path: List[str], residual: nx.DiGraph) -> float:
        """Encontra a capacidade mínima (gargalo) ao longo do caminho."""
        bottleneck = float('inf')
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            capacity = residual[u][v]['capacity']
            bottleneck = min(bottleneck, capacity)
        return bottleneck
    
    def _update_flow_along_path(self, path: List[str], flow_value: float):
        """Atualiza o fluxo ao longo do caminho encontrado."""
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            
            # Verifica se é aresta direta ou reversa
            if self.original_graph.has_edge(u, v):
                # Aresta direta: aumenta fluxo
                current_flow = self._get_flow(u, v)
                self._set_flow(u, v, current_flow + flow_value)
            else:
                # Aresta reversa: diminui fluxo
                current_flow = self._get_flow(v, u)
                self._set_flow(v, u, current_flow - flow_value)
    
    def calculate_max_flow(self, source: str, sink: str) -> FlowResult:
        """
        Calcula o fluxo máximo usando o algoritmo Ford-Fulkerson.
        
        Args:
            source: Nó fonte
            sink: Nó destino
            
        Returns:
            FlowResult com os resultados do cálculo
        """
        import time
        start_time = time.time()
        
        self._validate_graph(source, sink)
        
        # Inicializa fluxos como zero
        for u, v in self.graph.edges():
            self._set_flow(u, v, 0.0)
        
        max_flow_value = 0.0
        self.paths_found = []
        
        while True:
            # Constrói grafo residual
            residual = self._build_residual_graph()
            
            # Encontra caminho aumentante
            visited = set()
            path = self._find_augmenting_path_dfs(source, sink, residual, visited, [])
            
            if not path:
                break  # Não há mais caminhos aumentantes
                
            # Calcula fluxo que pode ser enviado
            bottleneck = self._find_path_bottleneck(path, residual)
            
            # Atualiza fluxo
            self._update_flow_along_path(path, bottleneck)
            max_flow_value += bottleneck
            
            self.paths_found.append(path.copy())
            
            logger.debug(f"Caminho encontrado: {' -> '.join(path)}, fluxo: {bottleneck}")
        
        # Calcula corte mínimo
        cut_edges = self._find_min_cut(source, sink)
        
        # Monta dicionário de fluxos
        flow_dict = self._build_flow_dict()
        
        execution_time = time.time() - start_time
        
        return FlowResult(
            max_flow_value=max_flow_value,
            flow_dict=flow_dict,
            cut_edges=cut_edges,
            paths_used=self.paths_found.copy(),
            algorithm_used="Ford-Fulkerson",
            execution_time=execution_time
        )
    
    def _find_min_cut(self, source: str, sink: str) -> List[Tuple[str, str]]:
        """Encontra as arestas do corte mínimo."""
        residual = self._build_residual_graph()
        
        # Encontra nós alcançáveis a partir da fonte
        reachable = set()
        stack = [source]
        
        while stack:
            node = stack.pop()
            if node not in reachable:
                reachable.add(node)
                for neighbor in residual.neighbors(node):
                    if residual[node][neighbor]['capacity'] > 0:
                        stack.append(neighbor)
        
        # Arestas do corte são aquelas que saem do conjunto alcançável
        cut_edges = []
        for u in reachable:
            for v in self.original_graph.neighbors(u):
                if v not in reachable:
                    cut_edges.append((u, v))
        
        return cut_edges
    
    def _build_flow_dict(self) -> Dict[str, Dict[str, float]]:
        """Constrói dicionário com fluxos em cada aresta."""
        flow_dict = defaultdict(dict)
        
        for u, v, data in self.graph.edges(data=True):
            flow = data.get('flow', 0.0)
            if flow > 0:
                flow_dict[u][v] = flow
                
        return dict(flow_dict)


class EdmondsKarp(MaxFlowCalculator):
    """
    Implementação do algoritmo Edmonds-Karp para fluxo máximo.
    
    É uma especialização do Ford-Fulkerson que usa busca em largura (BFS)
    para encontrar o caminho aumentante mais curto, garantindo complexidade O(VE²).
    """
    
    def __init__(self, graph: nx.DiGraph):
        super().__init__(graph)
        self.paths_found = []
        
    def _build_residual_graph(self) -> nx.DiGraph:
        """Constrói o grafo residual com capacidades residuais."""
        residual = nx.DiGraph()
        
        # Adiciona arestas diretas
        for u, v, data in self.graph.edges(data=True):
            capacity = data.get('capacity', 0.0)
            flow = data.get('flow', 0.0)
            residual_capacity = capacity - flow
            
            if residual_capacity > 0:
                residual.add_edge(u, v, capacity=residual_capacity)
                
        # Adiciona arestas reversas para fluxo existente
        for u, v, data in self.graph.edges(data=True):
            flow = data.get('flow', 0.0)
            if flow > 0:
                residual.add_edge(v, u, capacity=flow)
                
        return residual
    
    def _find_augmenting_path_bfs(self, source: str, sink: str, 
                                 residual: nx.DiGraph) -> Optional[List[str]]:
        """
        Encontra o caminho aumentante mais curto usando BFS.
        
        Returns:
            Lista de nós representando o caminho, ou None se não encontrado
        """
        if source == sink:
            return [source]
            
        visited = {source}
        queue = deque([(source, [source])])
        
        while queue:
            current, path = queue.popleft()
            
            for neighbor in residual.neighbors(current):
                if neighbor not in visited:
                    capacity = residual[current][neighbor]['capacity']
                    if capacity > 0:
                        new_path = path + [neighbor]
                        
                        if neighbor == sink:
                            return new_path
                            
                        visited.add(neighbor)
                        queue.append((neighbor, new_path))
        
        return None
    
    def _find_path_bottleneck(self, path: List[str], residual: nx.DiGraph) -> float:
        """Encontra a capacidade mínima (gargalo) ao longo do caminho."""
        bottleneck = float('inf')
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            capacity = residual[u][v]['capacity']
            bottleneck = min(bottleneck, capacity)
        return bottleneck
    
    def _update_flow_along_path(self, path: List[str], flow_value: float):
        """Atualiza o fluxo ao longo do caminho encontrado."""
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            
            # Verifica se é aresta direta ou reversa
            if self.original_graph.has_edge(u, v):
                # Aresta direta: aumenta fluxo
                current_flow = self._get_flow(u, v)
                self._set_flow(u, v, current_flow + flow_value)
            else:
                # Aresta reversa: diminui fluxo
                current_flow = self._get_flow(v, u)
                self._set_flow(v, u, current_flow - flow_value)
    
    def calculate_max_flow(self, source: str, sink: str) -> FlowResult:
        """
        Calcula o fluxo máximo usando o algoritmo Edmonds-Karp.
        
        Args:
            source: Nó fonte
            sink: Nó destino
            
        Returns:
            FlowResult com os resultados do cálculo
        """
        import time
        start_time = time.time()
        
        self._validate_graph(source, sink)
        
        # Inicializa fluxos como zero
        for u, v in self.graph.edges():
            self._set_flow(u, v, 0.0)
        
        max_flow_value = 0.0
        self.paths_found = []
        iteration = 0
        
        while True:
            iteration += 1
            # Constrói grafo residual
            residual = self._build_residual_graph()
            
            # Encontra caminho aumentante mais curto (BFS)
            path = self._find_augmenting_path_bfs(source, sink, residual)
            
            if not path:
                break  # Não há mais caminhos aumentantes
                
            # Calcula fluxo que pode ser enviado
            bottleneck = self._find_path_bottleneck(path, residual)
            
            # Atualiza fluxo
            self._update_flow_along_path(path, bottleneck)
            max_flow_value += bottleneck
            
            self.paths_found.append(path.copy())
            
            logger.debug(f"Iteração {iteration}: Caminho {' -> '.join(path)}, fluxo: {bottleneck}")
        
        # Calcula corte mínimo
        cut_edges = self._find_min_cut(source, sink)
        
        # Monta dicionário de fluxos
        flow_dict = self._build_flow_dict()
        
        execution_time = time.time() - start_time
        
        logger.info(f"Edmonds-Karp completado em {iteration} iterações, tempo: {execution_time:.4f}s")
        
        return FlowResult(
            max_flow_value=max_flow_value,
            flow_dict=flow_dict,
            cut_edges=cut_edges,
            paths_used=self.paths_found.copy(),
            algorithm_used="Edmonds-Karp",
            execution_time=execution_time
        )
    
    def _find_min_cut(self, source: str, sink: str) -> List[Tuple[str, str]]:
        """Encontra as arestas do corte mínimo."""
        residual = self._build_residual_graph()
        
        # Encontra nós alcançáveis a partir da fonte
        reachable = {source}
        queue = deque([source])
        
        while queue:
            node = queue.popleft()
            for neighbor in residual.neighbors(node):
                if neighbor not in reachable and residual[node][neighbor]['capacity'] > 0:
                    reachable.add(neighbor)
                    queue.append(neighbor)
        
        # Arestas do corte são aquelas que saem do conjunto alcançável
        cut_edges = []
        for u in reachable:
            for v in self.original_graph.neighbors(u):
                if v not in reachable:
                    cut_edges.append((u, v))
        
        return cut_edges
    
    def _build_flow_dict(self) -> Dict[str, Dict[str, float]]:
        """Constrói dicionário com fluxos em cada aresta."""
        flow_dict = defaultdict(dict)
        
        for u, v, data in self.graph.edges(data=True):
            flow = data.get('flow', 0.0)
            if flow > 0:
                flow_dict[u][v] = flow
                
        return dict(flow_dict)


def calculate_network_flow(graph: nx.DiGraph, 
                          source: str, 
                          sink: str,
                          algorithm: str = "edmonds_karp") -> FlowResult:
    """
    Função utilitária para calcular fluxo máximo em uma rede.
    
    Args:
        graph: Grafo NetworkX com capacidades
        source: Nó fonte
        sink: Nó destino
        algorithm: Algoritmo a usar ("ford_fulkerson" ou "edmonds_karp")
        
    Returns:
        FlowResult com os resultados do cálculo
    """
    if algorithm.lower() == "ford_fulkerson":
        calculator = FordFulkerson(graph)
    elif algorithm.lower() == "edmonds_karp":
        calculator = EdmondsKarp(graph)
    else:
        raise ValueError(f"Algoritmo '{algorithm}' não suportado. Use 'ford_fulkerson' ou 'edmonds_karp'")
    
    return calculator.calculate_max_flow(source, sink)


def validate_flow_conservation(graph: nx.DiGraph, flow_dict: Dict[str, Dict[str, float]], 
                              source: Optional[str], sink: Optional[str]) -> bool:
    """
    Valida se o fluxo satisfaz a conservação em todos os nós (exceto fonte e destino).
    
    Args:
        graph: Grafo original
        flow_dict: Dicionário com fluxos nas arestas
        source: Nó fonte (será ignorado na validação)
        sink: Nó destino (será ignorado na validação)
        
    Returns:
    Valida se o fluxo satisfaz a conservação em todos os nós (exceto fonte e destino).
    
    Args:
        graph: Grafo original
        flow_dict: Dicionário com fluxos nas arestas
        source: Nó fonte (será ignorado na validação)
        sink: Nó destino (será ignorado na validação)
        
    Returns:
        True se o fluxo é válido, False caso contrário
    """
    for node in graph.nodes():
        # Pula validação para fonte e destino
        if node == source or node == sink:
            continue
            
        inflow = sum(flow_dict.get(pred, {}).get(node, 0) 
                    for pred in graph.predecessors(node))
        outflow = sum(flow_dict.get(node, {}).get(succ, 0) 
                     for succ in graph.successors(node))
        
        # Para nós intermediários, entrada deve ser igual à saída
        if abs(inflow - outflow) > 1e-6:  # Tolerância para erros de ponto flutuante
            logger.warning(f"Violação de conservação no nó {node}: entrada={inflow}, saída={outflow}")
            return False
    
    return True
