#!/usr/bin/env python3
"""
Testes de comportamento da API Backend seguindo as melhores práticas de teste do Google.

Este arquivo foca na funcionalidade da API excluindo autenticação (que é testada em test_auth_behaviors.py).
Os testes são organizados por comportamento em vez de endpoint e seguem princípios DAMP em vez de DRY.

Comportamentos testados:
- Gerenciamento de Rede (operações CRUD)
- Integração de Dados (importação/exportação)
- Saúde e Status da API
- Controle de Acesso Baseado em Permissões
- Tratamento de Erros e Validação
- Integração de Fluxo de Trabalho Completo
- Operações de Banco de Dados
"""

import pytest
from fastapi.testclient import TestClient
import sys
import os
import tempfile
import shutil
import time
import json
from typing import Dict, Any, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.backend.main import app
from src.backend.dependencies import get_rede_service, get_database, override_database_for_testing, reset_database
from src.backend.services.rede_service import RedeService
from src.backend.database.sqlite import SQLiteDB


@pytest.fixture(scope="function")
def isolated_client_with_auth():
    """Cria cliente de teste isolado com configuração de autenticação."""
    # Cria banco de dados temporário
    temp_dir = tempfile.mkdtemp(prefix="test_backend_")
    test_db_path = os.path.join(temp_dir, "test_backend.db")
    
    # Configura banco de dados
    test_db = SQLiteDB(db_path=test_db_path)
    override_database_for_testing(test_db)
    app.dependency_overrides[get_database] = lambda: test_db
    
    # Configura serviço
    test_service = RedeService(db=test_db)
    app.dependency_overrides[get_rede_service] = lambda: test_service
    
    client = TestClient(app)
    
    yield client
    
    # Limpeza
    app.dependency_overrides.clear()
    reset_database()
    if os.path.exists(test_db_path):
        try:
            os.remove(test_db_path)
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass


@pytest.fixture
def admin_auth_headers(isolated_client_with_auth):
    """Obtém os cabeçalhos de autenticação do admin."""
    response = isolated_client_with_auth.post(
        "/api/v1/auth/login-json",
        json={"username": "admin", "password": "secret"}
    )
    assert response.status_code == 200, "Login do admin deve ter sucesso para testes de backend"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def operator_auth_headers(isolated_client_with_auth):
    """Obtém os cabeçalhos de autenticação do operador."""
    response = isolated_client_with_auth.post(
        "/api/v1/auth/login-json",
        json={"username": "operator", "password": "secret"}
    )
    assert response.status_code == 200, "Login do operador deve ter sucesso para testes de backend"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def viewer_auth_headers(isolated_client_with_auth):
    """Obtém os cabeçalhos de autenticação do visualizador."""
    response = isolated_client_with_auth.post(
        "/api/v1/auth/login-json",
        json={"username": "viewer", "password": "secret"}
    )
    assert response.status_code == 200, "Login do visualizador deve ter sucesso para testes de backend"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_network_data():
    """Fornece dados de rede de exemplo para testes."""
    return {
        "nome": "Test Network Sample",
        "descricao": "Network created for behavior testing",
        "nodes": [
            {
                "id": "depot_test",
                "nome": "Test Depot",
                "tipo": "deposito",
                "latitude": -23.550520,
                "longitude": -46.633308,
                "capacidade_maxima": 1000
            },
            {
                "id": "hub_test",
                "nome": "Test Hub",
                "tipo": "hub", 
                "latitude": -23.530520,
                "longitude": -46.623308,
                "capacidade": 500
            },
            {
                "id": "zone_test",
                "nome": "Test Zone",
                "tipo": "zona",
                "latitude": -23.560520,
                "longitude": -46.653308
            }
        ],
        "edges": [
            {
                "origem": "depot_test",
                "destino": "hub_test",
                "capacidade": 300,
                "distancia": 5.2,
                "custo": 10.5
            },
            {
                "origem": "hub_test", 
                "destino": "zone_test",
                "capacidade": 150,
                "distancia": 3.1,
                "custo": 8.0
            }
        ]
    }


class TestAPIHealthAndStatus:
    """Testa saúde, status e funcionalidade básica da API."""
    
    def test_api_root_endpoint_provides_version_information(self, isolated_client_with_auth):
        """Endpoint da API deve fornecer informações de versão do serviço."""
        # O endpoint raiz redireciona, então vamos testar o endpoint /api
        response = isolated_client_with_auth.get("/api")
        
        assert response.status_code == 200, "Endpoint da API deve ser acessível"
        data = response.json()
        assert "message" in data, "Deve incluir mensagem do serviço"
        assert "version" in data, "Deve incluir informações de versão"
        assert data["message"] == "API de Rede de Entrega", "Deve ter o nome correto do serviço"
    
    def test_health_check_reports_service_status(self, isolated_client_with_auth):
        """Endpoint de saúde deve reportar status operacional dos serviços."""
        response = isolated_client_with_auth.get("/health")
        
        assert response.status_code == 200, "Verificação de saúde deve ser acessível"
        data = response.json()
        assert data["status"] == "healthy", "Serviço deve reportar como saudável"
        assert "services" in data, "Deve reportar status de serviços individuais"
        assert data["services"]["api"] == "operational", "Serviço API deve estar operacional"


class TestNetworkManagement:
    """Testa comportamentos relacionados à criação, modificação e gerenciamento de rede."""
    
    def test_system_starts_with_empty_network_list(self, isolated_client_with_auth, admin_auth_headers):
        """Sistema novo deve iniciar sem redes."""
        response = isolated_client_with_auth.get("/api/v1/rede/listar", headers=admin_auth_headers)
        
        assert response.status_code == 200, "Listagem de redes deve ser acessível"
        networks = response.json()
        assert isinstance(networks, list), "Deve retornar lista de redes"
        assert len(networks) == 0, "Sistema novo deve ter zero redes"
    
    def test_users_can_create_custom_networks_with_valid_data(self, isolated_client_with_auth, admin_auth_headers, sample_network_data):
        """Usuários devem poder criar redes personalizadas com estrutura válida."""
        response = isolated_client_with_auth.post(
            "/api/v1/rede/criar",
            json=sample_network_data,
            headers=admin_auth_headers
        )
        
        assert response.status_code == 201, "Dados válidos de rede devem ser aceitos"
        data = response.json()
        assert data["status"] == "success", "Criação deve reportar sucesso"
        assert "rede_id" in data["data"], "Deve retornar ID da rede"
        assert sample_network_data["nome"] in data["message"], "Mensagem de sucesso deve incluir nome da rede"
    
    def test_system_generates_complete_maceio_networks_on_demand(self, isolated_client_with_auth, admin_auth_headers):
        """Sistema deve gerar redes completas de Maceió com quantidade especificada de clientes."""
        client_count = 50
        response = isolated_client_with_auth.post(
            f"/api/v1/rede/criar-maceio-completo?num_clientes={client_count}",
            headers=admin_auth_headers
        )
        
        assert response.status_code == 201, "Geração de rede de Maceió deve ter sucesso"
        data = response.json()
        assert data["status"] == "success", "Geração deve reportar sucesso"
        assert "rede_id" in data["data"], "Deve retornar ID da rede"
        assert f"{client_count} clientes" in data["message"], "Deve confirmar quantidade de clientes na mensagem"
    
    def test_maceio_networks_can_be_created_with_custom_names(self, isolated_client_with_auth, admin_auth_headers):
        """Usuários devem poder especificar nomes personalizados para redes geradas de Maceió."""
        custom_name = "Minha Rede Personalizada de Maceió"
        response = isolated_client_with_auth.post(
            f"/api/v1/rede/criar-maceio-completo?num_clientes=25&nome_rede={custom_name}",
            headers=admin_auth_headers
        )
        
        assert response.status_code == 201, "Rede com nome personalizado deve ser criada"
        data = response.json()
        assert data["status"] == "success", "Criação deve reportar sucesso"
        assert "rede_id" in data["data"], "Deve retornar ID da rede"
    
    def test_created_networks_appear_in_system_listing(self, isolated_client_with_auth, admin_auth_headers, sample_network_data):
        """Redes devem aparecer na listagem do sistema após criação."""
        # Cria rede
        create_response = isolated_client_with_auth.post(
            "/api/v1/rede/criar",
            json=sample_network_data,
            headers=admin_auth_headers
        )
        assert create_response.status_code == 201, "Criação de rede deve ter sucesso"
        
        # Verifica listagem
        list_response = isolated_client_with_auth.get("/api/v1/rede/listar", headers=admin_auth_headers)
        assert list_response.status_code == 200, "Listagem de redes deve ser acessível"
        
        networks = list_response.json()
        assert len(networks) > 0, "Deve ter pelo menos uma rede"
        network_names = [net["nome"] for net in networks]
        assert sample_network_data["nome"] in network_names, "Rede criada deve aparecer na listagem"
    
    def test_network_information_can_be_retrieved_after_creation(self, isolated_client_with_auth, admin_auth_headers, sample_network_data):
        """Usuários devem conseguir recuperar informações detalhadas sobre redes criadas."""
        # Cria rede
        create_response = isolated_client_with_auth.post(
            "/api/v1/rede/criar",
            json=sample_network_data,
            headers=admin_auth_headers
        )
        network_id = create_response.json()["data"]["rede_id"]
        
        # Obtém informações da rede
        info_response = isolated_client_with_auth.get(f"/api/v1/rede/{network_id}/info", headers=admin_auth_headers)
        
        assert info_response.status_code == 200, "Informações da rede devem ser recuperáveis"
        info = info_response.json()
        assert info["nome"] == sample_network_data["nome"], "Deve retornar nome correto da rede"
        assert info["total_nodes"] == 3, "Deve reportar contagem correta de nós"
        assert info["total_edges"] == 2, "Deve reportar contagem correta de arestas"
        assert "nodes_tipo" in info, "Deve incluir distribuição de tipos de nós"
        assert "capacidade_total" in info, "Deve incluir informações de capacidade"
    
    def test_networks_can_be_validated_for_consistency(self, isolated_client_with_auth, admin_auth_headers, sample_network_data):
        """Sistema deve validar estrutura da rede e reportar status de consistência."""
        # Cria rede
        create_response = isolated_client_with_auth.post(
            "/api/v1/rede/criar",
            json=sample_network_data,
            headers=admin_auth_headers
        )
        network_id = create_response.json()["data"]["rede_id"]
        
        # Valida rede
        validate_response = isolated_client_with_auth.get(f"/api/v1/rede/{network_id}/validar", headers=admin_auth_headers)
        
        assert validate_response.status_code == 200, "Validação de rede deve ser acessível"
        validation = validate_response.json()
        assert validation["status"] in ["valid", "invalid"], "Deve reportar status de validação"
        assert "data" in validation, "Deve incluir detalhes de validação"
    
    def test_flow_calculations_can_be_prepared_for_networks(self, isolated_client_with_auth, admin_auth_headers, sample_network_data):
        """Sistema deve preparar cálculos de fluxo entre nós da rede."""
        # Cria rede
        create_response = isolated_client_with_auth.post(
            "/api/v1/rede/criar",
            json=sample_network_data,
            headers=admin_auth_headers
        )
        network_id = create_response.json()["data"]["rede_id"]
        
        # Prepara cálculo de fluxo
        flow_data = {"origem": "depot_test", "destino": "zone_test"}
        flow_response = isolated_client_with_auth.post(
            f"/api/v1/rede/{network_id}/fluxo/preparar",
            json=flow_data,
            headers=admin_auth_headers
        )
        
        assert flow_response.status_code == 200, "Preparação de fluxo deve ter sucesso"
        flow_result = flow_response.json()
        assert flow_result["status"] == "prepared", "Fluxo deve ser preparado com sucesso"
    
    def test_network_nodes_can_be_listed_with_type_filtering(self, isolated_client_with_auth, admin_auth_headers, sample_network_data):
        """Usuários devem conseguir listar nós da rede com filtragem opcional por tipo."""
        # Cria rede
        create_response = isolated_client_with_auth.post(
            "/api/v1/rede/criar",
            json=sample_network_data,
            headers=admin_auth_headers
        )
        network_id = create_response.json()["data"]["rede_id"]
        
        # Lista todos os nós
        nodes_response = isolated_client_with_auth.get(
            f"/api/v1/rede/{network_id}/nos",
            headers=admin_auth_headers,
            params={"tipo": ""}
        )
        
        assert nodes_response.status_code == 200, "Listagem de nós deve ser acessível"
        nodes = nodes_response.json()
        assert isinstance(nodes, list), "Deve retornar lista de nós"
        assert len(nodes) == 3, "Deve retornar todos os nós"
    
    def test_network_statistics_provide_comprehensive_metrics(self, isolated_client_with_auth, admin_auth_headers, sample_network_data):
        """Sistema deve fornecer estatísticas abrangentes sobre estrutura e capacidade da rede."""
        # Cria rede
        create_response = isolated_client_with_auth.post(
            "/api/v1/rede/criar",
            json=sample_network_data,
            headers=admin_auth_headers
        )
        network_id = create_response.json()["data"]["rede_id"]
        
        # Obtém estatísticas
        stats_response = isolated_client_with_auth.get(f"/api/v1/rede/{network_id}/estatisticas", headers=admin_auth_headers)
        
        assert stats_response.status_code == 200, "Estatísticas de rede devem ser acessíveis"
        stats = stats_response.json()
        assert stats["status"] == "success", "Geração de estatísticas deve ter sucesso"
        assert "data" in stats, "Deve incluir dados estatísticos"
        assert "resumo" in stats["data"], "Deve incluir estatísticas resumidas"
        assert "distribuicao" in stats["data"], "Deve incluir dados de distribuição"
        assert "metricas" in stats["data"], "Deve incluir métricas detalhadas"


class TestDataIntegration:
    """Testa comportamentos relacionados à importação/exportação de dados e funcionalidade de integração."""
    
    def test_integration_service_reports_operational_status(self, isolated_client_with_auth, admin_auth_headers):
        """Serviço de integração deve reportar seu status operacional."""
        response = isolated_client_with_auth.get("/api/v1/integracao/status", headers=admin_auth_headers)
        
        assert response.status_code == 200, "Status de integração deve ser acessível"
        data = response.json()
        assert data["status"] == "operational", "Serviço de integração deve estar operacional"
    
    def test_json_data_can_be_imported_directly(self, isolated_client_with_auth, admin_auth_headers, sample_network_data):
        """Sistema deve aceitar e importar dados JSON de rede diretamente."""
        response = isolated_client_with_auth.post(
            "/api/v1/integracao/importar/json-data",
            json=sample_network_data,
            headers=admin_auth_headers
        )
        
        assert response.status_code == 201, "Importação de dados JSON deve ter sucesso"
        data = response.json()
        assert data["status"] == "success", "Importação deve reportar sucesso"
        assert "rede_id" in data["data"], "Deve retornar ID da rede"
    
    def test_json_files_can_be_uploaded_and_imported(self, isolated_client_with_auth, admin_auth_headers, sample_network_data, tmp_path):
        """Usuários devem conseguir fazer upload e importar arquivos JSON."""
        # Cria arquivo JSON temporário
        json_file = tmp_path / "test_network.json"
        with open(json_file, "w") as f:
            json.dump(sample_network_data, f)
        
        # Faz upload e importa
        with open(json_file, "rb") as f:
            response = isolated_client_with_auth.post(
                "/api/v1/integracao/importar/json",
                files={"arquivo": ("network.json", f, "application/json")},
                headers=admin_auth_headers
            )
        
        assert response.status_code == 201, "Importação de arquivo JSON deve ter sucesso"
        data = response.json()
        assert data["status"] == "success", "Importação de arquivo deve reportar sucesso"
        assert "rede_id" in data["data"], "Deve retornar ID da rede"
    
    def test_csv_node_data_can_be_imported(self, isolated_client_with_auth, admin_auth_headers, tmp_path):
        """Sistema deve aceitar e importar dados de nós em formato CSV."""
        # Cria arquivo CSV com dados de nós
        csv_content = "id,nome,tipo,latitude,longitude\n"
        csv_content += "depot1,Depósito Central,deposito,-23.5505,-46.6333\n"
        csv_content += "hub1,Hub Logístico,hub,-23.5305,-46.6233\n"
        
        csv_file = tmp_path / "nodes.csv"
        with open(csv_file, "w") as f:
            f.write(csv_content)
        
        # Importa CSV
        with open(csv_file, "r", encoding="utf-8") as f:
            response = isolated_client_with_auth.post(
                "/api/v1/integracao/importar/csv-nodes",
                files={"arquivo": ("nodes.csv", f.read(), "text/csv")},
                headers=admin_auth_headers
            )
        
        assert response.status_code == 200, "Importação CSV deve ter sucesso"
        data = response.json()
        assert data["status"] == "success", "Importação CSV deve reportar sucesso"
        assert "total_nodes" in data["data"], "Deve reportar contagem de nós importados"
        assert data["data"]["total_nodes"] == 2, "Deve importar número correto de nós"
        
        # Verifica distribuição de tipos
        assert "tipos_importados" in data["data"], "Deve reportar distribuição de tipos"
        assert data["data"]["tipos_importados"]["deposito"] == 1, "Deve contar nós de depósito"
        assert data["data"]["tipos_importados"]["hub"] == 1, "Deve contar nós de hub"
    
    def test_json_format_examples_are_provided(self, isolated_client_with_auth, admin_auth_headers):
        """Sistema deve fornecer exemplos de formato JSON para usuários."""
        response = isolated_client_with_auth.get("/api/v1/integracao/exemplo/json", headers=admin_auth_headers)
        
        assert response.status_code == 200, "Exemplo JSON deve ser acessível"
        data = response.json()
        assert "exemplo" in data, "Deve fornecer dados de exemplo"
        assert "nome" in data["exemplo"], "Exemplo deve incluir nome da rede"
        assert "nodes" in data["exemplo"], "Exemplo deve incluir nós"
        assert "edges" in data["exemplo"], "Exemplo deve incluir arestas"
    
    def test_csv_format_examples_are_provided(self, isolated_client_with_auth, admin_auth_headers):
        """Sistema deve fornecer exemplos de formato CSV e instruções."""
        response = isolated_client_with_auth.get("/api/v1/integracao/exemplo/csv", headers=admin_auth_headers)
        
        assert response.status_code == 200, "Exemplo CSV deve ser acessível"
        data = response.json()
        assert "exemplo_csv" in data, "Deve fornecer exemplo CSV"
        assert "instrucoes" in data, "Deve fornecer instruções"


class TestPermissionBasedAccess:
    """Testa comportamentos relacionados ao controle de acesso baseado em permissões para diferentes funções de usuário."""
    
    def test_viewers_can_read_network_data_but_cannot_modify(self, isolated_client_with_auth, admin_auth_headers, viewer_auth_headers, sample_network_data):
        """Visualizadores devem ter acesso de leitura mas nenhuma permissão de modificação."""
        # Admin cria rede
        create_response = isolated_client_with_auth.post(
            "/api/v1/rede/criar",
            json=sample_network_data,
            headers=admin_auth_headers
        )
        assert create_response.status_code == 201, "Admin deve conseguir criar redes"
        
        # Visualizador pode ler
        list_response = isolated_client_with_auth.get("/api/v1/rede/listar", headers=viewer_auth_headers)
        assert list_response.status_code == 200, "Visualizador deve conseguir ler lista de redes"
        
        # Visualizador não pode criar
        create_attempt = isolated_client_with_auth.post(
            "/api/v1/rede/criar",
            json={"nome": "Não Autorizada", "nodes": [], "edges": []},
            headers=viewer_auth_headers
        )
        assert create_attempt.status_code == 403, "Visualizador deve ter criação negada"
        assert "Permissão" in create_attempt.json()["detail"] or "write" in create_attempt.json()["detail"]
    
    def test_operators_can_create_and_modify_networks(self, isolated_client_with_auth, operator_auth_headers, sample_network_data):
        """Operadores devem ter permissões de criação e modificação para redes."""
        response = isolated_client_with_auth.post(
            "/api/v1/rede/criar",
            json=sample_network_data,
            headers=operator_auth_headers
        )
        
        assert response.status_code == 201, "Operador deve conseguir criar redes"
        data = response.json()
        assert data["status"] == "success", "Criação de rede deve ter sucesso"
    
    def test_all_authenticated_users_can_read_network_data(self, isolated_client_with_auth, admin_auth_headers, sample_network_data):
        """Todos os usuários autenticados devem ter acesso de leitura aos dados de rede."""
        # Cria rede como admin
        create_response = isolated_client_with_auth.post(
            "/api/v1/rede/criar",
            json=sample_network_data,
            headers=admin_auth_headers
        )
        assert create_response.status_code == 201, "Criação de rede deve ter sucesso"
        
        # Testa acesso de leitura para todos os tipos de usuário
        for username in ["admin", "operator", "viewer"]:
            # Obtém token de autenticação
            login_response = isolated_client_with_auth.post(
                "/api/v1/auth/login-json",
                json={"username": username, "password": "secret"}
            )
            token = login_response.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            
            # Testa acesso de leitura
            read_response = isolated_client_with_auth.get("/api/v1/rede/listar", headers=headers)
            assert read_response.status_code == 200, f"{username} deve ter acesso de leitura"


class TestErrorHandlingAndValidation:
    """Testa comportamentos relacionados ao tratamento de erros e validação de entrada."""
    
    def test_system_handles_requests_for_nonexistent_networks(self, isolated_client_with_auth, admin_auth_headers):
        """Sistema deve lidar graciosamente com requisições para redes que não existem."""
        response = isolated_client_with_auth.get("/api/v1/rede/nonexistent_id/info", headers=admin_auth_headers)
        
        assert response.status_code == 404, "Rede inexistente deve retornar 404"
    
    def test_system_validates_json_format_in_requests(self, isolated_client_with_auth, admin_auth_headers):
        """Sistema deve validar formato JSON e rejeitar requisições malformadas."""
        response = isolated_client_with_auth.post(
            "/api/v1/rede/criar",
            data="conteúdo json inválido",
            headers={**admin_auth_headers, "Content-Type": "application/json"}
        )
        
        assert response.status_code == 422, "JSON inválido deve ser rejeitado"
    
    def test_system_validates_required_fields_in_network_data(self, isolated_client_with_auth, admin_auth_headers):
        """Sistema deve validar presença de campos obrigatórios nos dados de rede."""
        incomplete_data = {"nome": "Rede Incompleta"}  # Faltam nodes e edges
        
        response = isolated_client_with_auth.post(
            "/api/v1/rede/criar",
            json=incomplete_data,
            headers=admin_auth_headers
        )
        
        assert response.status_code == 422, "Dados de rede incompletos devem ser rejeitados"
    
    def test_system_handles_invalid_json_file_uploads(self, isolated_client_with_auth, admin_auth_headers, tmp_path):
        """Sistema deve lidar com arquivos JSON malformados graciosamente."""
        # Cria arquivo com JSON inválido
        invalid_json_file = tmp_path / "invalid.json"
        with open(invalid_json_file, "w") as f:
            f.write("{conteúdo json inválido")
        
        with open(invalid_json_file, "rb") as f:
            response = isolated_client_with_auth.post(
                "/api/v1/integracao/importar/json",
                files={"arquivo": ("invalid.json", f, "application/json")},
                headers=admin_auth_headers
            )
        
        assert response.status_code == 422, "Arquivo JSON inválido deve ser rejeitado"
        assert "detail" in response.json(), "Deve fornecer detalhes do erro"
    
    def test_system_handles_invalid_json_data_imports(self, isolated_client_with_auth, admin_auth_headers):
        """Sistema deve validar estrutura de dados JSON durante importação direta."""
        invalid_data = {"nome": "Rede Inválida"}  # Faltam elementos obrigatórios
        
        response = isolated_client_with_auth.post(
            "/api/v1/integracao/importar/json-data",
            json=invalid_data,
            headers=admin_auth_headers
        )
        
        assert response.status_code == 422, "Estrutura de rede inválida deve ser rejeitada"
        assert "detail" in response.json(), "Deve fornecer detalhes de erro de validação"


class TestCompleteWorkflows:
    """Testa fluxos de trabalho completos e cenários de integração."""
    
    def test_complete_network_creation_and_analysis_workflow(self, isolated_client_with_auth, sample_network_data):
        """Usuários devem conseguir completar ciclo completo de vida da rede desde criação até análise."""
        # 1. Autentica
        login_response = isolated_client_with_auth.post(
            "/api/v1/auth/login-json",
            json={"username": "admin", "password": "secret"}
        )
        assert login_response.status_code == 200, "Autenticação deve ter sucesso"
        
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 2. Cria rede
        create_response = isolated_client_with_auth.post(
            "/api/v1/rede/criar",
            json=sample_network_data,
            headers=headers
        )
        assert create_response.status_code == 201, "Criação de rede deve ter sucesso"
        network_id = create_response.json()["data"]["rede_id"]
        
        # 3. Verifica se rede aparece na listagem
        list_response = isolated_client_with_auth.get("/api/v1/rede/listar", headers=headers)
        assert list_response.status_code == 200, "Listagem de redes deve ser acessível"
        assert len(list_response.json()) > 0, "Deve ter pelo menos uma rede"
        
        # 4. Obtém informações detalhadas da rede
        info_response = isolated_client_with_auth.get(f"/api/v1/rede/{network_id}/info", headers=headers)
        assert info_response.status_code == 200, "Informações da rede devem ser acessíveis"
        info = info_response.json()
        assert info["nome"] == sample_network_data["nome"], "Deve retornar detalhes corretos da rede"
        
        # 5. Valida estrutura da rede
        validate_response = isolated_client_with_auth.get(f"/api/v1/rede/{network_id}/validar", headers=headers)
        assert validate_response.status_code == 200, "Validação de rede deve ser acessível"
        
        # 6. Prepara cálculos de fluxo
        flow_data = {"origem": "depot_test", "destino": "zone_test"}
        flow_response = isolated_client_with_auth.post(
            f"/api/v1/rede/{network_id}/fluxo/preparar",
            json=flow_data,
            headers=headers
        )
        assert flow_response.status_code == 200, "Preparação de fluxo deve ter sucesso"
        
        # 7. Obtém estatísticas da rede
        stats_response = isolated_client_with_auth.get(f"/api/v1/rede/{network_id}/estatisticas", headers=headers)
        assert stats_response.status_code == 200, "Estatísticas devem ser acessíveis"
    
    @pytest.mark.parametrize("client_count", [10, 50, 100])
    def test_maceio_network_generation_and_validation_workflow(self, isolated_client_with_auth, admin_auth_headers, client_count):
        """Sistema deve lidar com geração e validação completa de rede de Maceió para vários tamanhos."""
        # 1. Gera rede de Maceió
        network_name = f"Teste Maceió {client_count} Clientes - {int(time.time())}"
        create_response = isolated_client_with_auth.post(
            "/api/v1/rede/criar-maceio-completo",
            json={"num_clientes": client_count, "nome_rede": network_name},
            headers=admin_auth_headers
        )
        
        assert create_response.status_code == 201, f"Criação de rede de Maceió deve ter sucesso para {client_count} clientes"
        data = create_response.json()
        assert data["status"] == "success", "Criação deve reportar sucesso"
        network_id = data["data"]["rede_id"]
        
        # 2. Valida rede gerada
        validate_response = isolated_client_with_auth.get(f"/api/v1/rede/{network_id}/validar", headers=admin_auth_headers)
        assert validate_response.status_code == 200, "Validação deve ser acessível"
        
        validation = validate_response.json()
        assert validation["status"] == "valid", f"Rede gerada com {client_count} clientes deve ser válida"
        
        # 3. Verifica estrutura de dados de validação
        assert "data" in validation, "Validação deve incluir dados detalhados"
        val_data = validation["data"]
        assert "resumo" in val_data, "Deve incluir informações resumidas"
        assert "problemas" in val_data, "Deve incluir lista de problemas"
        assert len(val_data["problemas"]) == 0, f"Rede válida não deve ter problemas: {val_data.get('problemas', [])}"
        
        # 4. Verifica se rede tem estrutura esperada
        resumo = val_data["resumo"]
        assert "total_clientes" in resumo, "Resumo deve incluir contagem de clientes"
        assert resumo["total_clientes"] > 0, "Rede deve ter clientes"
        assert "total_rotas" in resumo, "Resumo deve incluir contagem de rotas"
        assert resumo["total_rotas"] > 0, "Rede deve ter rotas"
    
    def test_data_import_and_network_analysis_workflow(self, isolated_client_with_auth, admin_auth_headers, sample_network_data):
        """Usuários devem conseguir importar dados e analisar imediatamente a rede resultante."""
        # 1. Importa dados de rede
        import_response = isolated_client_with_auth.post(
            "/api/v1/integracao/importar/json-data",
            json=sample_network_data,
            headers=admin_auth_headers
        )
        assert import_response.status_code == 201, "Importação de dados deve ter sucesso"
        network_id = import_response.json()["data"]["rede_id"]
        
        # 2. Analisa imediatamente rede importada
        info_response = isolated_client_with_auth.get(f"/api/v1/rede/{network_id}/info", headers=admin_auth_headers)
        assert info_response.status_code == 200, "Informações da rede importada devem ser acessíveis"
        
        info = info_response.json()
        assert info["nome"] == sample_network_data["nome"], "Deve preservar nome da rede importada"
        assert info["total_nodes"] == len(sample_network_data["nodes"]), "Deve preservar contagem de nós"
        assert info["total_edges"] == len(sample_network_data["edges"]), "Deve preservar contagem de arestas"
        
        # 3. Valida estrutura da rede importada
        validate_response = isolated_client_with_auth.get(f"/api/v1/rede/{network_id}/validar", headers=admin_auth_headers)
        assert validate_response.status_code == 200, "Validação de rede importada deve funcionar"


class TestDatabaseOperations:
    """Testa operações de banco de dados e comportamentos de persistência de dados."""
    
    def test_database_initializes_with_required_tables(self):
        """Banco de dados deve criar todas as tabelas necessárias na inicialização."""
        temp_dir = tempfile.mkdtemp(prefix="test_db_init_")
        try:
            db_path = os.path.join(temp_dir, "test_init.db")
            db = SQLiteDB(db_path=db_path)
            
            # Verifica se tabelas necessárias existem
            with db._get_conn() as conn:
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
            
            assert "redes" in tables, "Deve criar tabela de redes"
            assert "users" in tables, "Deve criar tabela de usuários"
            
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_networks_persist_correctly_in_database(self):
        """Dados de rede devem ser salvos e recuperados com precisão do banco de dados."""
        temp_dir = tempfile.mkdtemp(prefix="test_db_persist_")
        try:
            db_path = os.path.join(temp_dir, "test_persist.db")
            db = SQLiteDB(db_path=db_path)
            
            # Salva rede
            network_id = f"persist_test_{int(time.time())}"
            name = "Rede de Teste de Persistência"
            description = "Rede de teste para validação de persistência"
            data = {
                "nome": name,
                "descricao": description,
                "nodes": [{"id": "test_node", "tipo": "deposito", "latitude": 10.0, "longitude": 20.0}],
                "edges": [{"origem": "node1", "destino": "node2", "distancia": 5.0, "capacidade": 100}]
            }
            
            db.salvar_rede(network_id, name, description, data)
            
            # Recupera rede
            retrieved = db.carregar_rede(network_id)
            
            assert retrieved is not None, "Rede salva deve ser recuperável"
            assert retrieved["nome"] == name, "Nome da rede deve ser preservado"
            assert retrieved["descricao"] == description, "Descrição da rede deve ser preservada"
            assert "nodes" in retrieved, "Nós da rede devem ser preservados"
            assert "edges" in retrieved, "Arestas da rede devem ser preservadas"
            
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_network_listing_includes_metadata(self):
        """Listagem de redes deve incluir metadados como horário de criação."""
        temp_dir = tempfile.mkdtemp(prefix="test_db_metadata_")
        try:
            db_path = os.path.join(temp_dir, "test_metadata.db")
            db = SQLiteDB(db_path=db_path)
            
            # Salva múltiplas redes
            for i in range(3):
                network_id = f"metadata_test_{i}_{int(time.time())}"
                db.salvar_rede(
                    network_id,
                    f"Rede de Teste {i}",
                    f"Descrição {i}",
                    {"nome": f"Rede {i}", "nodes": [], "edges": []}
                )
            
            # Lista redes
            networks = db.listar_redes()
            
            assert len(networks) >= 3, "Deve listar todas as redes salvas"
            for network in networks:
                assert "id" in network, "Deve incluir ID da rede"
                assert "nome" in network, "Deve incluir nome da rede"
                assert "descricao" in network, "Deve incluir descrição"
                assert "created_at" in network, "Deve incluir timestamp de criação"
                
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_network_removal_works_correctly(self):
        """Redes devem ser completamente removidas do banco de dados quando deletadas."""
        temp_dir = tempfile.mkdtemp(prefix="test_db_removal_")
        try:
            db_path = os.path.join(temp_dir, "test_removal.db")
            db = SQLiteDB(db_path=db_path)
            
            # Cria rede
            network_id = f"removal_test_{int(time.time())}"
            db.salvar_rede(
                network_id,
                "Rede para Remover",
                "Será deletada",
                {"nome": "Rede Removível", "nodes": [], "edges": []}
            )
            
            # Verifica existência
            before_removal = db.carregar_rede(network_id)
            assert before_removal is not None, "Rede deve existir antes da remoção"
            
            # Remove rede
            db.remover_rede(network_id)
            
            # Verifica remoção
            after_removal = db.carregar_rede(network_id)
            assert after_removal is None, "Rede não deve existir após remoção"
            
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_user_data_operations_work_correctly(self):
        """Operações CRUD de usuário devem funcionar corretamente no banco de dados."""
        temp_dir = tempfile.mkdtemp(prefix="test_db_users_")
        try:
            db_path = os.path.join(temp_dir, "test_users.db")
            db = SQLiteDB(db_path=db_path)
            
            # Usuários padrão devem existir
            users = db.listar_usuarios()
            assert len(users) >= 3, "Deve ter usuários padrão"
            
            usernames = [u["username"] for u in users]
            assert "admin" in usernames, "Deve incluir usuário admin"
            assert "operator" in usernames, "Deve incluir usuário operator"  
            assert "viewer" in usernames, "Deve incluir usuário viewer"
            
            # Testa criação de usuário
            username = f"test_user_{int(time.time())}"
            success = db.criar_usuario(
                username=username,
                email=f"{username}@test.com",
                full_name="Usuário de Teste",
                hashed_password="senha_hash_placeholder",
                permissions=["read", "write"]
            )
            assert success is True, "Criação de usuário deve ter sucesso"
            
            # Testa recuperação de usuário
            user = db.buscar_usuario_por_username(username)
            assert user is not None, "Usuário criado deve ser recuperável"
            assert user["username"] == username, "Deve retornar nome de usuário correto"
            assert user["email"] == f"{username}@test.com", "Deve retornar email correto"
            
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    print("Testes de Comportamento da API Backend")
    print("Execute com: pytest test_backend_behaviors.py -v")
