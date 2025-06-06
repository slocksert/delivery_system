#!/usr/bin/env python3
"""
Backend API behavior tests following Google's testing best practices.

This file focuses on API functionality excluding authentication (which is tested in test_auth_behaviors.py).
Tests are organized by behavior rather than endpoint and follow DAMP over DRY principles.

Behaviors tested:
- Network Management (CRUD operations)
- Data Integration (import/export)
- API Health and Status
- Permission-based Access Control
- Error Handling and Validation
- Complete Workflow Integration
- Database Operations
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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from backend.main import app
from backend.dependencies import get_rede_service, get_database, override_database_for_testing, reset_database
from backend.services.rede_service import RedeService
from backend.database.sqlite import SQLiteDB


@pytest.fixture(scope="function")
def isolated_client_with_auth():
    """Creates isolated test client with authentication setup."""
    # Create temporary database
    temp_dir = tempfile.mkdtemp(prefix="test_backend_")
    test_db_path = os.path.join(temp_dir, "test_backend.db")
    
    # Setup database
    test_db = SQLiteDB(db_path=test_db_path)
    override_database_for_testing(test_db)
    app.dependency_overrides[get_database] = lambda: test_db
    
    # Setup service
    test_service = RedeService(db=test_db)
    app.dependency_overrides[get_rede_service] = lambda: test_service
    
    client = TestClient(app)
    
    yield client
    
    # Cleanup
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
    """Gets admin authentication headers."""
    response = isolated_client_with_auth.post(
        "/api/v1/auth/login-json",
        json={"username": "admin", "password": "secret"}
    )
    assert response.status_code == 200, "Admin login should succeed for backend tests"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def operator_auth_headers(isolated_client_with_auth):
    """Gets operator authentication headers."""
    response = isolated_client_with_auth.post(
        "/api/v1/auth/login-json",
        json={"username": "operator", "password": "secret"}
    )
    assert response.status_code == 200, "Operator login should succeed for backend tests"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def viewer_auth_headers(isolated_client_with_auth):
    """Gets viewer authentication headers."""
    response = isolated_client_with_auth.post(
        "/api/v1/auth/login-json",
        json={"username": "viewer", "password": "secret"}
    )
    assert response.status_code == 200, "Viewer login should succeed for backend tests"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_network_data():
    """Provides sample network data for testing."""
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
    """Tests API health, status, and basic functionality."""
    
    def test_api_root_endpoint_provides_version_information(self, isolated_client_with_auth):
        """API root should provide service information and version."""
        response = isolated_client_with_auth.get("/")
        
        assert response.status_code == 200, "Root endpoint should be accessible"
        data = response.json()
        assert "message" in data, "Should include service message"
        assert "version" in data, "Should include version information"
        assert data["message"] == "API de Rede de Entrega", "Should have correct service name"
    
    def test_health_check_reports_service_status(self, isolated_client_with_auth):
        """Health endpoint should report operational status of services."""
        response = isolated_client_with_auth.get("/health")
        
        assert response.status_code == 200, "Health check should be accessible"
        data = response.json()
        assert data["status"] == "healthy", "Service should report as healthy"
        assert "services" in data, "Should report status of individual services"
        assert data["services"]["api"] == "operational", "API service should be operational"


class TestNetworkManagement:
    """Tests behaviors related to network creation, modification, and management."""
    
    def test_system_starts_with_empty_network_list(self, isolated_client_with_auth, admin_auth_headers):
        """New system should start with no networks."""
        response = isolated_client_with_auth.get("/api/v1/rede/listar", headers=admin_auth_headers)
        
        assert response.status_code == 200, "Network listing should be accessible"
        networks = response.json()
        assert isinstance(networks, list), "Should return list of networks"
        assert len(networks) == 0, "New system should have no networks"
    
    def test_users_can_create_custom_networks_with_valid_data(self, isolated_client_with_auth, admin_auth_headers, sample_network_data):
        """Users should be able to create custom networks with valid structure."""
        response = isolated_client_with_auth.post(
            "/api/v1/rede/criar",
            json=sample_network_data,
            headers=admin_auth_headers
        )
        
        assert response.status_code == 201, "Valid network data should be accepted"
        data = response.json()
        assert data["status"] == "success", "Creation should report success"
        assert "rede_id" in data["data"], "Should return network ID"
        assert sample_network_data["nome"] in data["message"], "Success message should include network name"
    
    def test_system_generates_complete_maceio_networks_on_demand(self, isolated_client_with_auth, admin_auth_headers):
        """System should generate complete Maceió networks with specified client count."""
        client_count = 50
        response = isolated_client_with_auth.post(
            f"/api/v1/rede/criar-maceio-completo?num_clientes={client_count}",
            headers=admin_auth_headers
        )
        
        assert response.status_code == 201, "Maceió network generation should succeed"
        data = response.json()
        assert data["status"] == "success", "Generation should report success"
        assert "rede_id" in data["data"], "Should return network ID"
        assert f"{client_count} clientes" in data["message"], "Should confirm client count in message"
    
    def test_maceio_networks_can_be_created_with_custom_names(self, isolated_client_with_auth, admin_auth_headers):
        """Users should be able to specify custom names for generated Maceió networks."""
        custom_name = "My Custom Maceió Network"
        response = isolated_client_with_auth.post(
            f"/api/v1/rede/criar-maceio-completo?num_clientes=25&nome_rede={custom_name}",
            headers=admin_auth_headers
        )
        
        assert response.status_code == 201, "Custom named network should be created"
        data = response.json()
        assert data["status"] == "success", "Creation should report success"
        assert "rede_id" in data["data"], "Should return network ID"
    
    def test_created_networks_appear_in_system_listing(self, isolated_client_with_auth, admin_auth_headers, sample_network_data):
        """Networks should appear in system listing after creation."""
        # Create network
        create_response = isolated_client_with_auth.post(
            "/api/v1/rede/criar",
            json=sample_network_data,
            headers=admin_auth_headers
        )
        assert create_response.status_code == 201, "Network creation should succeed"
        
        # Check listing
        list_response = isolated_client_with_auth.get("/api/v1/rede/listar", headers=admin_auth_headers)
        assert list_response.status_code == 200, "Network listing should be accessible"
        
        networks = list_response.json()
        assert len(networks) > 0, "Should have at least one network"
        network_names = [net["nome"] for net in networks]
        assert sample_network_data["nome"] in network_names, "Created network should appear in listing"
    
    def test_network_information_can_be_retrieved_after_creation(self, isolated_client_with_auth, admin_auth_headers, sample_network_data):
        """Users should be able to retrieve detailed information about created networks."""
        # Create network
        create_response = isolated_client_with_auth.post(
            "/api/v1/rede/criar",
            json=sample_network_data,
            headers=admin_auth_headers
        )
        network_id = create_response.json()["data"]["rede_id"]
        
        # Get network info
        info_response = isolated_client_with_auth.get(f"/api/v1/rede/{network_id}/info", headers=admin_auth_headers)
        
        assert info_response.status_code == 200, "Network info should be retrievable"
        info = info_response.json()
        assert info["nome"] == sample_network_data["nome"], "Should return correct network name"
        assert info["total_nodes"] == 3, "Should report correct node count"
        assert info["total_edges"] == 2, "Should report correct edge count"
        assert "nodes_tipo" in info, "Should include node type distribution"
        assert "capacidade_total" in info, "Should include capacity information"
    
    def test_networks_can_be_validated_for_consistency(self, isolated_client_with_auth, admin_auth_headers, sample_network_data):
        """System should validate network structure and report consistency status."""
        # Create network
        create_response = isolated_client_with_auth.post(
            "/api/v1/rede/criar",
            json=sample_network_data,
            headers=admin_auth_headers
        )
        network_id = create_response.json()["data"]["rede_id"]
        
        # Validate network
        validate_response = isolated_client_with_auth.get(f"/api/v1/rede/{network_id}/validar", headers=admin_auth_headers)
        
        assert validate_response.status_code == 200, "Network validation should be accessible"
        validation = validate_response.json()
        assert validation["status"] in ["valid", "invalid"], "Should report validation status"
        assert "data" in validation, "Should include validation details"
    
    def test_flow_calculations_can_be_prepared_for_networks(self, isolated_client_with_auth, admin_auth_headers, sample_network_data):
        """System should prepare flow calculations between network nodes."""
        # Create network
        create_response = isolated_client_with_auth.post(
            "/api/v1/rede/criar",
            json=sample_network_data,
            headers=admin_auth_headers
        )
        network_id = create_response.json()["data"]["rede_id"]
        
        # Prepare flow calculation
        flow_data = {"origem": "depot_test", "destino": "zone_test"}
        flow_response = isolated_client_with_auth.post(
            f"/api/v1/rede/{network_id}/fluxo/preparar",
            json=flow_data,
            headers=admin_auth_headers
        )
        
        assert flow_response.status_code == 200, "Flow preparation should succeed"
        flow_result = flow_response.json()
        assert flow_result["status"] == "prepared", "Flow should be prepared successfully"
    
    def test_network_nodes_can_be_listed_with_type_filtering(self, isolated_client_with_auth, admin_auth_headers, sample_network_data):
        """Users should be able to list network nodes with optional type filtering."""
        # Create network
        create_response = isolated_client_with_auth.post(
            "/api/v1/rede/criar",
            json=sample_network_data,
            headers=admin_auth_headers
        )
        network_id = create_response.json()["data"]["rede_id"]
        
        # List all nodes
        nodes_response = isolated_client_with_auth.get(
            f"/api/v1/rede/{network_id}/nos",
            headers=admin_auth_headers,
            params={"tipo": ""}
        )
        
        assert nodes_response.status_code == 200, "Node listing should be accessible"
        nodes = nodes_response.json()
        assert isinstance(nodes, list), "Should return list of nodes"
        assert len(nodes) == 3, "Should return all nodes"
    
    def test_network_statistics_provide_comprehensive_metrics(self, isolated_client_with_auth, admin_auth_headers, sample_network_data):
        """System should provide comprehensive statistics about network structure and capacity."""
        # Create network
        create_response = isolated_client_with_auth.post(
            "/api/v1/rede/criar",
            json=sample_network_data,
            headers=admin_auth_headers
        )
        network_id = create_response.json()["data"]["rede_id"]
        
        # Get statistics
        stats_response = isolated_client_with_auth.get(f"/api/v1/rede/{network_id}/estatisticas", headers=admin_auth_headers)
        
        assert stats_response.status_code == 200, "Network statistics should be accessible"
        stats = stats_response.json()
        assert stats["status"] == "success", "Statistics generation should succeed"
        assert "data" in stats, "Should include statistical data"
        assert "resumo" in stats["data"], "Should include summary statistics"
        assert "distribuicao" in stats["data"], "Should include distribution data"
        assert "metricas" in stats["data"], "Should include detailed metrics"


class TestDataIntegration:
    """Tests behaviors related to data import/export and integration functionality."""
    
    def test_integration_service_reports_operational_status(self, isolated_client_with_auth, admin_auth_headers):
        """Integration service should report its operational status."""
        response = isolated_client_with_auth.get("/api/v1/integracao/status", headers=admin_auth_headers)
        
        assert response.status_code == 200, "Integration status should be accessible"
        data = response.json()
        assert data["status"] == "operational", "Integration service should be operational"
    
    def test_json_data_can_be_imported_directly(self, isolated_client_with_auth, admin_auth_headers, sample_network_data):
        """System should accept and import JSON network data directly."""
        response = isolated_client_with_auth.post(
            "/api/v1/integracao/importar/json-data",
            json=sample_network_data,
            headers=admin_auth_headers
        )
        
        assert response.status_code == 201, "JSON data import should succeed"
        data = response.json()
        assert data["status"] == "success", "Import should report success"
        assert "rede_id" in data["data"], "Should return network ID"
    
    def test_json_files_can_be_uploaded_and_imported(self, isolated_client_with_auth, admin_auth_headers, sample_network_data, tmp_path):
        """Users should be able to upload and import JSON files."""
        # Create temporary JSON file
        json_file = tmp_path / "test_network.json"
        with open(json_file, "w") as f:
            json.dump(sample_network_data, f)
        
        # Upload and import
        with open(json_file, "rb") as f:
            response = isolated_client_with_auth.post(
                "/api/v1/integracao/importar/json",
                files={"arquivo": ("network.json", f, "application/json")},
                headers=admin_auth_headers
            )
        
        assert response.status_code == 201, "JSON file import should succeed"
        data = response.json()
        assert data["status"] == "success", "File import should report success"
        assert "rede_id" in data["data"], "Should return network ID"
    
    def test_csv_node_data_can_be_imported(self, isolated_client_with_auth, admin_auth_headers, tmp_path):
        """System should accept and import CSV node data."""
        # Create CSV file with node data
        csv_content = "id,nome,tipo,latitude,longitude\n"
        csv_content += "depot1,Central Depot,deposito,-23.5505,-46.6333\n"
        csv_content += "hub1,Logistics Hub,hub,-23.5305,-46.6233\n"
        
        csv_file = tmp_path / "nodes.csv"
        with open(csv_file, "w") as f:
            f.write(csv_content)
        
        # Import CSV
        with open(csv_file, "r", encoding="utf-8") as f:
            response = isolated_client_with_auth.post(
                "/api/v1/integracao/importar/csv-nodes",
                files={"arquivo": ("nodes.csv", f.read(), "text/csv")},
                headers=admin_auth_headers
            )
        
        assert response.status_code == 200, "CSV import should succeed"
        data = response.json()
        assert data["status"] == "success", "CSV import should report success"
        assert "total_nodes" in data["data"], "Should report imported node count"
        assert data["data"]["total_nodes"] == 2, "Should import correct number of nodes"
        
        # Verify type distribution
        assert "tipos_importados" in data["data"], "Should report type distribution"
        assert data["data"]["tipos_importados"]["deposito"] == 1, "Should count depot nodes"
        assert data["data"]["tipos_importados"]["hub"] == 1, "Should count hub nodes"
    
    def test_json_format_examples_are_provided(self, isolated_client_with_auth, admin_auth_headers):
        """System should provide JSON format examples for users."""
        response = isolated_client_with_auth.get("/api/v1/integracao/exemplo/json", headers=admin_auth_headers)
        
        assert response.status_code == 200, "JSON example should be accessible"
        data = response.json()
        assert "exemplo" in data, "Should provide example data"
        assert "nome" in data["exemplo"], "Example should include network name"
        assert "nodes" in data["exemplo"], "Example should include nodes"
        assert "edges" in data["exemplo"], "Example should include edges"
    
    def test_csv_format_examples_are_provided(self, isolated_client_with_auth, admin_auth_headers):
        """System should provide CSV format examples and instructions."""
        response = isolated_client_with_auth.get("/api/v1/integracao/exemplo/csv", headers=admin_auth_headers)
        
        assert response.status_code == 200, "CSV example should be accessible"
        data = response.json()
        assert "exemplo_csv" in data, "Should provide CSV example"
        assert "instrucoes" in data, "Should provide instructions"


class TestPermissionBasedAccess:
    """Tests behaviors related to permission-based access control for different user roles."""
    
    def test_viewers_can_read_network_data_but_cannot_modify(self, isolated_client_with_auth, admin_auth_headers, viewer_auth_headers, sample_network_data):
        """Viewers should have read access but no modification permissions."""
        # Admin creates network
        create_response = isolated_client_with_auth.post(
            "/api/v1/rede/criar",
            json=sample_network_data,
            headers=admin_auth_headers
        )
        assert create_response.status_code == 201, "Admin should be able to create networks"
        
        # Viewer can read
        list_response = isolated_client_with_auth.get("/api/v1/rede/listar", headers=viewer_auth_headers)
        assert list_response.status_code == 200, "Viewer should be able to read network list"
        
        # Viewer cannot create
        create_attempt = isolated_client_with_auth.post(
            "/api/v1/rede/criar",
            json={"nome": "Unauthorized", "nodes": [], "edges": []},
            headers=viewer_auth_headers
        )
        assert create_attempt.status_code == 403, "Viewer should be denied create permission"
        assert "Permissão" in create_attempt.json()["detail"] or "write" in create_attempt.json()["detail"]
    
    def test_operators_can_create_and_modify_networks(self, isolated_client_with_auth, operator_auth_headers, sample_network_data):
        """Operators should have create and modify permissions for networks."""
        response = isolated_client_with_auth.post(
            "/api/v1/rede/criar",
            json=sample_network_data,
            headers=operator_auth_headers
        )
        
        assert response.status_code == 201, "Operator should be able to create networks"
        data = response.json()
        assert data["status"] == "success", "Network creation should succeed"
    
    def test_all_authenticated_users_can_read_network_data(self, isolated_client_with_auth, admin_auth_headers, sample_network_data):
        """All authenticated users should have read access to network data."""
        # Create network as admin
        create_response = isolated_client_with_auth.post(
            "/api/v1/rede/criar",
            json=sample_network_data,
            headers=admin_auth_headers
        )
        assert create_response.status_code == 201, "Network creation should succeed"
        
        # Test read access for all user types
        for username in ["admin", "operator", "viewer"]:
            # Get auth token
            login_response = isolated_client_with_auth.post(
                "/api/v1/auth/login-json",
                json={"username": username, "password": "secret"}
            )
            token = login_response.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            
            # Test read access
            read_response = isolated_client_with_auth.get("/api/v1/rede/listar", headers=headers)
            assert read_response.status_code == 200, f"{username} should have read access"


class TestErrorHandlingAndValidation:
    """Tests system behavior when handling errors and invalid input."""
    
    def test_system_handles_requests_for_nonexistent_networks(self, isolated_client_with_auth, admin_auth_headers):
        """System should gracefully handle requests for networks that don't exist."""
        response = isolated_client_with_auth.get("/api/v1/rede/nonexistent_id/info", headers=admin_auth_headers)
        
        assert response.status_code == 404, "Nonexistent network should return 404"
    
    def test_system_validates_json_format_in_requests(self, isolated_client_with_auth, admin_auth_headers):
        """System should validate JSON format and reject malformed requests."""
        response = isolated_client_with_auth.post(
            "/api/v1/rede/criar",
            data="invalid json content",
            headers={**admin_auth_headers, "Content-Type": "application/json"}
        )
        
        assert response.status_code == 422, "Invalid JSON should be rejected"
    
    def test_system_validates_required_fields_in_network_data(self, isolated_client_with_auth, admin_auth_headers):
        """System should validate presence of required fields in network data."""
        incomplete_data = {"nome": "Incomplete Network"}  # Missing nodes and edges
        
        response = isolated_client_with_auth.post(
            "/api/v1/rede/criar",
            json=incomplete_data,
            headers=admin_auth_headers
        )
        
        assert response.status_code == 422, "Incomplete network data should be rejected"
    
    def test_system_handles_invalid_json_file_uploads(self, isolated_client_with_auth, admin_auth_headers, tmp_path):
        """System should handle malformed JSON files gracefully."""
        # Create file with invalid JSON
        invalid_json_file = tmp_path / "invalid.json"
        with open(invalid_json_file, "w") as f:
            f.write("{invalid json content")
        
        with open(invalid_json_file, "rb") as f:
            response = isolated_client_with_auth.post(
                "/api/v1/integracao/importar/json",
                files={"arquivo": ("invalid.json", f, "application/json")},
                headers=admin_auth_headers
            )
        
        assert response.status_code == 422, "Invalid JSON file should be rejected"
        assert "detail" in response.json(), "Should provide error details"
    
    def test_system_handles_invalid_json_data_imports(self, isolated_client_with_auth, admin_auth_headers):
        """System should validate JSON data structure during direct import."""
        invalid_data = {"nome": "Invalid Network"}  # Missing required elements
        
        response = isolated_client_with_auth.post(
            "/api/v1/integracao/importar/json-data",
            json=invalid_data,
            headers=admin_auth_headers
        )
        
        assert response.status_code == 422, "Invalid network structure should be rejected"
        assert "detail" in response.json(), "Should provide validation error details"


class TestCompleteWorkflows:
    """Tests complete end-to-end workflows and integration scenarios."""
    
    def test_complete_network_creation_and_analysis_workflow(self, isolated_client_with_auth, sample_network_data):
        """Users should be able to complete full network lifecycle from creation to analysis."""
        # 1. Authenticate
        login_response = isolated_client_with_auth.post(
            "/api/v1/auth/login-json",
            json={"username": "admin", "password": "secret"}
        )
        assert login_response.status_code == 200, "Authentication should succeed"
        
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 2. Create network
        create_response = isolated_client_with_auth.post(
            "/api/v1/rede/criar",
            json=sample_network_data,
            headers=headers
        )
        assert create_response.status_code == 201, "Network creation should succeed"
        network_id = create_response.json()["data"]["rede_id"]
        
        # 3. Verify network appears in listing
        list_response = isolated_client_with_auth.get("/api/v1/rede/listar", headers=headers)
        assert list_response.status_code == 200, "Network listing should be accessible"
        assert len(list_response.json()) > 0, "Should have at least one network"
        
        # 4. Get detailed network information
        info_response = isolated_client_with_auth.get(f"/api/v1/rede/{network_id}/info", headers=headers)
        assert info_response.status_code == 200, "Network info should be accessible"
        info = info_response.json()
        assert info["nome"] == sample_network_data["nome"], "Should return correct network details"
        
        # 5. Validate network structure
        validate_response = isolated_client_with_auth.get(f"/api/v1/rede/{network_id}/validar", headers=headers)
        assert validate_response.status_code == 200, "Network validation should be accessible"
        
        # 6. Prepare flow calculations
        flow_data = {"origem": "depot_test", "destino": "zone_test"}
        flow_response = isolated_client_with_auth.post(
            f"/api/v1/rede/{network_id}/fluxo/preparar",
            json=flow_data,
            headers=headers
        )
        assert flow_response.status_code == 200, "Flow preparation should succeed"
        
        # 7. Get network statistics
        stats_response = isolated_client_with_auth.get(f"/api/v1/rede/{network_id}/estatisticas", headers=headers)
        assert stats_response.status_code == 200, "Statistics should be accessible"
    
    @pytest.mark.parametrize("client_count", [10, 50, 100])
    def test_maceio_network_generation_and_validation_workflow(self, isolated_client_with_auth, admin_auth_headers, client_count):
        """System should handle complete Maceió network generation and validation for various sizes."""
        # 1. Generate Maceió network
        network_name = f"Maceió Test {client_count} Clients - {int(time.time())}"
        create_response = isolated_client_with_auth.post(
            "/api/v1/rede/criar-maceio-completo",
            json={"num_clientes": client_count, "nome_rede": network_name},
            headers=admin_auth_headers
        )
        
        assert create_response.status_code == 201, f"Maceió network creation should succeed for {client_count} clients"
        data = create_response.json()
        assert data["status"] == "success", "Creation should report success"
        network_id = data["data"]["rede_id"]
        
        # 2. Validate generated network
        validate_response = isolated_client_with_auth.get(f"/api/v1/rede/{network_id}/validar", headers=admin_auth_headers)
        assert validate_response.status_code == 200, "Validation should be accessible"
        
        validation = validate_response.json()
        assert validation["status"] == "valid", f"Generated network with {client_count} clients should be valid"
        
        # 3. Verify validation data structure
        assert "data" in validation, "Validation should include detailed data"
        val_data = validation["data"]
        assert "resumo" in val_data, "Should include summary information"
        assert "problemas" in val_data, "Should include problems list"
        assert len(val_data["problemas"]) == 0, f"Valid network should have no problems: {val_data.get('problemas', [])}"
        
        # 4. Verify network has expected structure
        resumo = val_data["resumo"]
        assert "total_clientes" in resumo, "Summary should include client count"
        assert resumo["total_clientes"] > 0, "Network should have clients"
        assert "total_rotas" in resumo, "Summary should include route count"
        assert resumo["total_rotas"] > 0, "Network should have routes"
    
    def test_data_import_and_network_analysis_workflow(self, isolated_client_with_auth, admin_auth_headers, sample_network_data):
        """Users should be able to import data and immediately analyze the resulting network."""
        # 1. Import network data
        import_response = isolated_client_with_auth.post(
            "/api/v1/integracao/importar/json-data",
            json=sample_network_data,
            headers=admin_auth_headers
        )
        assert import_response.status_code == 201, "Data import should succeed"
        network_id = import_response.json()["data"]["rede_id"]
        
        # 2. Immediately analyze imported network
        info_response = isolated_client_with_auth.get(f"/api/v1/rede/{network_id}/info", headers=admin_auth_headers)
        assert info_response.status_code == 200, "Imported network info should be accessible"
        
        info = info_response.json()
        assert info["nome"] == sample_network_data["nome"], "Should preserve imported network name"
        assert info["total_nodes"] == len(sample_network_data["nodes"]), "Should preserve node count"
        assert info["total_edges"] == len(sample_network_data["edges"]), "Should preserve edge count"
        
        # 3. Validate imported network structure
        validate_response = isolated_client_with_auth.get(f"/api/v1/rede/{network_id}/validar", headers=admin_auth_headers)
        assert validate_response.status_code == 200, "Imported network validation should work"


class TestDatabaseOperations:
    """Tests database operations and data persistence behaviors."""
    
    def test_database_initializes_with_required_tables(self):
        """Database should create all required tables on initialization."""
        temp_dir = tempfile.mkdtemp(prefix="test_db_init_")
        try:
            db_path = os.path.join(temp_dir, "test_init.db")
            db = SQLiteDB(db_path=db_path)
            
            # Check that required tables exist
            with db._get_conn() as conn:
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
            
            assert "redes" in tables, "Should create networks table"
            assert "users" in tables, "Should create users table"
            
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_networks_persist_correctly_in_database(self):
        """Network data should be saved and retrieved accurately from database."""
        temp_dir = tempfile.mkdtemp(prefix="test_db_persist_")
        try:
            db_path = os.path.join(temp_dir, "test_persist.db")
            db = SQLiteDB(db_path=db_path)
            
            # Save network
            network_id = f"persist_test_{int(time.time())}"
            name = "Persistence Test Network"
            description = "Test network for persistence validation"
            data = {
                "nome": name,
                "descricao": description,
                "nodes": [{"id": "test_node", "tipo": "deposito", "latitude": 10.0, "longitude": 20.0}],
                "edges": [{"origem": "node1", "destino": "node2", "distancia": 5.0, "capacidade": 100}]
            }
            
            db.salvar_rede(network_id, name, description, data)
            
            # Retrieve network
            retrieved = db.carregar_rede(network_id)
            
            assert retrieved is not None, "Saved network should be retrievable"
            assert retrieved["nome"] == name, "Network name should be preserved"
            assert retrieved["descricao"] == description, "Network description should be preserved"
            assert "nodes" in retrieved, "Network nodes should be preserved"
            assert "edges" in retrieved, "Network edges should be preserved"
            
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_network_listing_includes_metadata(self):
        """Network listing should include metadata like creation time."""
        temp_dir = tempfile.mkdtemp(prefix="test_db_metadata_")
        try:
            db_path = os.path.join(temp_dir, "test_metadata.db")
            db = SQLiteDB(db_path=db_path)
            
            # Save multiple networks
            for i in range(3):
                network_id = f"metadata_test_{i}_{int(time.time())}"
                db.salvar_rede(
                    network_id,
                    f"Test Network {i}",
                    f"Description {i}",
                    {"nome": f"Network {i}", "nodes": [], "edges": []}
                )
            
            # List networks
            networks = db.listar_redes()
            
            assert len(networks) >= 3, "Should list all saved networks"
            for network in networks:
                assert "id" in network, "Should include network ID"
                assert "nome" in network, "Should include network name"
                assert "descricao" in network, "Should include description"
                assert "created_at" in network, "Should include creation timestamp"
                
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_network_removal_works_correctly(self):
        """Networks should be completely removed from database when deleted."""
        temp_dir = tempfile.mkdtemp(prefix="test_db_removal_")
        try:
            db_path = os.path.join(temp_dir, "test_removal.db")
            db = SQLiteDB(db_path=db_path)
            
            # Create network
            network_id = f"removal_test_{int(time.time())}"
            db.salvar_rede(
                network_id,
                "Network to Remove",
                "Will be deleted",
                {"nome": "Removable Network", "nodes": [], "edges": []}
            )
            
            # Verify existence
            before_removal = db.carregar_rede(network_id)
            assert before_removal is not None, "Network should exist before removal"
            
            # Remove network
            db.remover_rede(network_id)
            
            # Verify removal
            after_removal = db.carregar_rede(network_id)
            assert after_removal is None, "Network should not exist after removal"
            
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_user_data_operations_work_correctly(self):
        """User CRUD operations should work correctly in database."""
        temp_dir = tempfile.mkdtemp(prefix="test_db_users_")
        try:
            db_path = os.path.join(temp_dir, "test_users.db")
            db = SQLiteDB(db_path=db_path)
            
            # Default users should exist
            users = db.listar_usuarios()
            assert len(users) >= 3, "Should have default users"
            
            usernames = [u["username"] for u in users]
            assert "admin" in usernames, "Should include admin user"
            assert "operator" in usernames, "Should include operator user"  
            assert "viewer" in usernames, "Should include viewer user"
            
            # Test user creation
            username = f"test_user_{int(time.time())}"
            success = db.criar_usuario(
                username=username,
                email=f"{username}@test.com",
                full_name="Test User",
                hashed_password="hashed_password_placeholder",
                permissions=["read", "write"]
            )
            assert success is True, "User creation should succeed"
            
            # Test user retrieval
            user = db.buscar_usuario_por_username(username)
            assert user is not None, "Created user should be retrievable"
            assert user["username"] == username, "Should return correct username"
            assert user["email"] == f"{username}@test.com", "Should return correct email"
            
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    print("Backend API Behavior Tests")
    print("Run with: pytest test_backend_behaviors.py -v")
