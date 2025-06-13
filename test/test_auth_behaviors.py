#!/usr/bin/env python3
"""
Testes de comportamento de autenticação seguindo as melhores práticas de teste do Google.

Este arquivo consolida testes de autenticação de test_backend.py e test_user_system.py,
organizando-os por comportamento ao invés de método/endpoint e seguindo o princípio DAMP ao invés de DRY.

Comportamentos testados:
- Autenticação de Usuário (login, validação de token)
- Registro de Usuário (criação, validação)
- Gerenciamento de Usuário (operações CRUD)
- Controle de Acesso (permissões, autorização)
- Segurança (entradas inválidas, casos extremos)
"""

import pytest
import tempfile
import shutil
import os
import time
from typing import Dict, Any
from fastapi.testclient import TestClient

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.backend.main import app
from src.backend.database.sqlite import SQLiteDB
from src.backend.dependencies import get_database, override_database_for_testing, reset_database


@pytest.fixture(scope="function") 
def isolated_client():
    """Cria um cliente de teste isolado com banco de dados temporário para cada teste."""
    # Cria banco de dados temporário
    temp_dir = tempfile.mkdtemp(prefix="test_auth_behavior_")
    test_db_path = os.path.join(temp_dir, "test_auth.db")
    
    # Injeta banco de dados
    test_db = SQLiteDB(db_path=test_db_path)
    override_database_for_testing(test_db)
    app.dependency_overrides[get_database] = lambda: test_db
    
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
def admin_token(isolated_client):
    """Obtém token de autenticação do admin."""
    response = isolated_client.post(
        "/api/v1/auth/login-json",
        json={"username": "admin", "password": "secret"}
    )
    assert response.status_code == 200, "Login do admin deve ter sucesso"
    return response.json()["access_token"]


@pytest.fixture  
def operator_token(isolated_client):
    """Obtém token de autenticação do operador."""
    response = isolated_client.post(
        "/api/v1/auth/login-json", 
        json={"username": "operator", "password": "secret"}
    )
    assert response.status_code == 200, "Login do operador deve ter sucesso"
    return response.json()["access_token"]


@pytest.fixture
def viewer_token(isolated_client):
    """Obtém token de autenticação do visualizador."""
    response = isolated_client.post(
        "/api/v1/auth/login-json",
        json={"username": "viewer", "password": "secret"}
    )
    assert response.status_code == 200, "Login do visualizador deve ter sucesso"
    return response.json()["access_token"]


class TestUserAuthentication:
    """Testa comportamentos relacionados à autenticação de usuário e gerenciamento de token."""
    
    def test_admin_can_authenticate_with_valid_credentials(self, isolated_client):
        """Usuários admin devem conseguir fazer login com usuário e senha corretos."""
        response = isolated_client.post(
            "/api/v1/auth/login-json",
            json={"username": "admin", "password": "secret"}
        )
        
        assert response.status_code == 200, "Credenciais válidas de admin devem ser aceitas"
        data = response.json()
        assert "access_token" in data, "Login deve retornar token de acesso"
        assert data["token_type"] == "bearer", "Tipo de token deve ser bearer"
        assert len(data["access_token"]) > 10, "Token deve ser uma string não vazia"
    
    def test_authentication_fails_with_wrong_password(self, isolated_client):
        """A autenticação deve falhar quando o usuário fornece senha incorreta."""
        response = isolated_client.post(
            "/api/v1/auth/login-json",
            json={"username": "admin", "password": "wrong_password"}
        )
        
        assert response.status_code == 401, "Senha errada deve ser rejeitada"
        assert "detail" in response.json(), "Resposta de erro deve incluir detalhes"
    
    def test_authentication_fails_for_nonexistent_user(self, isolated_client):
        """A autenticação deve falhar quando o usuário não existe."""
        response = isolated_client.post(
            "/api/v1/auth/login-json",
            json={"username": "nonexistent_user", "password": "any_password"}
        )
        
        assert response.status_code == 401, "Usuário inexistente deve ser rejeitado"
    
    def test_form_based_authentication_works(self, isolated_client):
        """Usuários devem conseguir autenticar usando dados de formulário (endpoint legado)."""
        response = isolated_client.post(
            "/api/v1/auth/login",
            data={"username": "admin", "password": "secret"},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        assert response.status_code == 200, "Login via formulário deve funcionar"
        data = response.json()
        assert "access_token" in data, "Login via formulário deve retornar token"
    
    def test_token_provides_access_to_user_information(self, isolated_client, admin_token):
        """Tokens válidos devem permitir acesso às informações do próprio usuário."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = isolated_client.get("/api/v1/auth/me", headers=headers)
        
        assert response.status_code == 200, "Token válido deve permitir acesso"
        data = response.json()
        assert data["username"] == "admin", "Deve retornar informações corretas do usuário"
        assert "admin" in data["permissions"], "Deve incluir permissões do usuário"
        assert data["is_active"] is True, "Deve mostrar status do usuário"
    
    def test_token_validation_confirms_token_validity(self, isolated_client, admin_token):
        """Token validation endpoint deve confirmar tokens válidos."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = isolated_client.get("/api/v1/auth/verify-token", headers=headers)
        
        assert response.status_code == 200, "Validação de token deve ter sucesso"
        data = response.json()
        assert data["valid"] is True, "Token válido deve ser confirmado como válido"
        assert data["username"] == "admin", "Deve retornar dono do token"
        assert "permissions" in data, "Deve incluir permissões"
    
    def test_access_denied_without_authentication_token(self, isolated_client):
        """Endpoints protegidos devem negar acesso sem token de autenticação."""
        response = isolated_client.get("/api/v1/auth/me")
        
        assert response.status_code == 403, "No token should result in access denied"


class TestUserRegistration:
    """Testa comportamentos relacionados ao registro de usuário e criação de conta."""
    
    def test_new_user_can_be_registered_with_valid_data(self, isolated_client):
        """O sistema deve permitir o registro de novos usuários com informações válidas."""
        new_user = {
            "username": "newuser",
            "email": "newuser@example.com",
            "full_name": "New User",
            "password": "secure_password",
            "permissions": ["read", "write"]
        }
        
        response = isolated_client.post("/api/v1/auth/register", json=new_user)
        
        assert response.status_code == 201, "Dados válidos de usuário devem ser aceitos"
        data = response.json()
        assert data["status"] == "success", "Registro deve indicar sucesso"
        assert "newuser" in data["message"], "Mensagem de sucesso deve incluir o nome de usuário"
        assert data["user"]["username"] == "newuser", "Deve retornar informações do usuário"
        assert "password" not in data["user"], "Senha não deve ser retornada"
    
    def test_newly_registered_user_can_authenticate(self, isolated_client):
        """Usuários devem conseguir fazer login imediatamente após o registro."""
        # Registra usuário
        new_user = {
            "username": "logintest",
            "email": "logintest@example.com", 
            "full_name": "Login Test User",
            "password": "test_password_123",
            "permissions": ["read"]
        }
        
        register_response = isolated_client.post("/api/v1/auth/register", json=new_user)
        assert register_response.status_code == 201, "Registro deve ter sucesso"
        
        # Tenta login
        login_response = isolated_client.post(
            "/api/v1/auth/login-json",
            json={"username": "logintest", "password": "test_password_123"}
        )
        
        assert login_response.status_code == 200, "Novo usuário deve conseguir fazer login"
        assert "access_token" in login_response.json(), "Login deve retornar token"
    
    def test_duplicate_username_registration_is_rejected(self, isolated_client):
        """O sistema deve impedir o registro de nomes de usuário duplicados."""
        user_data = {
            "username": "duplicate_test",
            "email": "test1@example.com",
            "full_name": "First User",
            "password": "password123",
            "permissions": ["read"]
        }
        
        # Primeiro registro
        first_response = isolated_client.post("/api/v1/auth/register", json=user_data)
        assert first_response.status_code == 201, "Primeiro registro deve ter sucesso"
        
        # Segundo registro com mesmo username
        user_data["email"] = "test2@example.com"  # Email diferente, mesmo username
        second_response = isolated_client.post("/api/v1/auth/register", json=user_data)
        
        assert second_response.status_code == 400, "Username duplicado deve ser rejeitado"
    
    def test_cannot_register_with_existing_system_username(self, isolated_client):
        """Registro deve falhar ao tentar usar nomes de usuário do sistema já existentes."""
        admin_duplicate = {
            "username": "admin",  # Usuário do sistema
            "email": "fake_admin@example.com",
            "full_name": "Fake Admin",
            "password": "new_password",
            "permissions": ["read"]
        }
        
        response = isolated_client.post("/api/v1/auth/register", json=admin_duplicate)
        
        assert response.status_code == 400, "Nomes de usuário do sistema devem ser protegidos"


class TestUserManagement:
    """Testa comportamentos relacionados às operações de gerenciamento de usuário (CRUD)."""
    
    def test_admin_can_view_all_users_in_system(self, isolated_client, admin_token):
        """Administradores devem conseguir visualizar a lista completa de usuários."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = isolated_client.get("/api/v1/auth/users", headers=headers)
        
        assert response.status_code == 200, "Admin deve acessar a lista de usuários"
        users = response.json()
        assert isinstance(users, list), "Deve retornar lista de usuários"
        assert len(users) >= 3, "Deve incluir usuários do sistema (admin, operator, viewer)"
        
        usernames = [user["username"] for user in users]
        assert "admin" in usernames, "Deve incluir usuário admin"
        assert "operator" in usernames, "Deve incluir usuário operator"
        assert "viewer" in usernames, "Deve incluir usuário viewer"
    
    def test_admin_can_update_user_information(self, isolated_client, admin_token):
        """Administradores devem conseguir modificar detalhes de contas de usuário."""
        # Cria usuário de teste
        test_user = {
            "username": "updateable_user",
            "email": "original@example.com",
            "full_name": "Original Name",
            "password": "password123",
            "permissions": ["read"]
        }
        
        register_response = isolated_client.post("/api/v1/auth/register", json=test_user)
        assert register_response.status_code == 201, "Criação de usuário de teste deve ter sucesso"
        
        # Atualiza usuário
        headers = {"Authorization": f"Bearer {admin_token}"}
        update_data = {
            "email": "updated@example.com",
            "full_name": "Updated Name",
            "permissions": ["read", "write"]
        }
        
        update_response = isolated_client.put(
            "/api/v1/auth/users/updateable_user",
            json=update_data,
            headers=headers
        )
        
        assert update_response.status_code == 200, "Atualização de usuário deve ter sucesso"
        data = update_response.json()
        assert data["status"] == "success", "Atualização deve indicar sucesso"
        
        # Verifica alterações
        users_response = isolated_client.get("/api/v1/auth/users", headers=headers)
        users = users_response.json()
        updated_user = next((u for u in users if u["username"] == "updateable_user"), None)
        
        assert updated_user is not None, "Usuário atualizado deve existir"
        assert updated_user["email"] == "updated@example.com", "Email deve ser atualizado"
        assert updated_user["full_name"] == "Updated Name", "Nome completo deve ser atualizado"
        assert sorted(updated_user["permissions"]) == ["read", "write"], "Permissões devem ser atualizadas"
    
    def test_admin_can_delete_user_accounts(self, isolated_client, admin_token):
        """Administradores devem conseguir remover contas de usuário."""
        # Cria usuário de teste
        test_user = {
            "username": "deletable_user",
            "email": "delete@example.com",
            "full_name": "Delete Test",
            "password": "password123",
            "permissions": ["read"]
        }
        
        register_response = isolated_client.post("/api/v1/auth/register", json=test_user)
        assert register_response.status_code == 201, "Criação de usuário de teste deve ter sucesso"
        
        # Deleta usuário
        headers = {"Authorization": f"Bearer {admin_token}"}
        delete_response = isolated_client.delete(
            "/api/v1/auth/users/deletable_user",
            headers=headers
        )
        
        assert delete_response.status_code == 200, "Exclusão de usuário deve ter sucesso"
        data = delete_response.json()
        assert data["status"] == "success", "Exclusão deve indicar sucesso"
        
        # Verifica exclusão
        users_response = isolated_client.get("/api/v1/auth/users", headers=headers)
        users = users_response.json()
        usernames = [u["username"] for u in users]
        assert "deletable_user" not in usernames, "Usuário deletado não deve aparecer na lista"
    
    def test_updating_nonexistent_user_fails_gracefully(self, isolated_client, admin_token):
        """O sistema deve lidar com tentativas de atualizar usuários inexistentes."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        update_data = {"full_name": "Should Not Work"}
        
        response = isolated_client.put(
            "/api/v1/auth/users/nonexistent_user",
            json=update_data,
            headers=headers
        )
        
        assert response.status_code == 404, "Atualização de usuário inexistente deve falhar"
    
    def test_deleting_nonexistent_user_fails_gracefully(self, isolated_client, admin_token):
        """O sistema deve lidar com tentativas de deletar usuários inexistentes."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = isolated_client.delete(
            "/api/v1/auth/users/nonexistent_user",
            headers=headers
        )
        
        assert response.status_code == 404, "Exclusão de usuário inexistente deve falhar"
    
    def test_admin_cannot_delete_own_account(self, isolated_client, admin_token):
        """O sistema deve impedir que usuários deletam suas próprias contas."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = isolated_client.delete(
            "/api/v1/auth/users/admin",
            headers=headers
        )
        
        assert response.status_code == 400, "Auto-exclusão deve ser impedida"
        assert "Não é possível deletar seu próprio usuário" in response.json()["detail"]


class TestAccessControl:
    """Testa comportamentos relacionados a permissões e autorização."""
    
    def test_non_admin_users_cannot_view_user_list(self, isolated_client, operator_token):
        """Apenas administradores devem conseguir acessar funções de gerenciamento de usuários."""
        headers = {"Authorization": f"Bearer {operator_token}"}
        response = isolated_client.get("/api/v1/auth/users", headers=headers)
        
        assert response.status_code == 403, "Usuário não admin deve ser negado acesso à lista de usuários"
        assert "Acesso negado" in response.json()["detail"]
    
    def test_non_admin_users_cannot_update_other_users(self, isolated_client, viewer_token):
        """Não-administradores não devem conseguir modificar contas de outros usuários."""
        headers = {"Authorization": f"Bearer {viewer_token}"}
        update_data = {"email": "hacker@example.com"}
        
        response = isolated_client.put(
            "/api/v1/auth/users/admin",
            json=update_data,
            headers=headers
        )
        
        assert response.status_code == 403, "Usuário não admin deve ser negado acesso à atualização"
    
    def test_non_admin_users_cannot_delete_other_users(self, isolated_client, viewer_token):
        """Não-administradores não devem conseguir deletar outras contas de usuário."""
        headers = {"Authorization": f"Bearer {viewer_token}"}
        
        response = isolated_client.delete(
            "/api/v1/auth/users/operator",
            headers=headers
        )
        
        assert response.status_code == 403, "Usuário não admin deve ser negado acesso à exclusão"
    
    def test_permissions_endpoint_lists_available_permissions(self, isolated_client):
        """O sistema deve fornecer informações sobre permissões disponíveis."""
        response = isolated_client.get("/api/v1/auth/permissions")
        
        assert response.status_code == 200, "Endpoint de permissões deve ser acessível"
        data = response.json()
        assert "permissions" in data, "Deve listar permissões disponíveis"
        
        expected_permissions = ["admin", "read", "write", "delete"]
        for permission in expected_permissions:
            assert permission in data["permissions"], f"Deve incluir permissão {permission}"


class TestSecurityBehaviors:
    """Testa comportamentos relacionados à segurança e casos extremos."""
    
    def test_system_handles_malformed_authentication_requests(self, isolated_client):
        """O sistema deve lidar graciosamente com dados de autenticação malformados."""
        # Falta senha
        response1 = isolated_client.post(
            "/api/v1/auth/login-json",
            json={"username": "admin"}
        )
        assert response1.status_code in [400, 422], "Falta de senha deve ser rejeitada"
        
        # Falta nome de usuário  
        response2 = isolated_client.post(
            "/api/v1/auth/login-json",
            json={"password": "secret"}
        )
        assert response2.status_code in [400, 422], "Falta de nome de usuário deve ser rejeitada"
        
        # Payload vazio
        response3 = isolated_client.post(
            "/api/v1/auth/login-json",
            json={}
        )
        assert response3.status_code in [400, 422], "Payload vazio deve ser rejeitado"
    
    def test_system_handles_malformed_registration_requests(self, isolated_client):
        """O sistema deve validar dados de registro e rejeitar requisições inválidas."""
        # Campos obrigatórios faltando
        invalid_user = {
            "username": "incomplete"
            # Falta email, senha, permissões
        }
        
        response = isolated_client.post("/api/v1/auth/register", json=invalid_user)
        assert response.status_code in [400, 422], "Dados de registro incompletos devem ser rejeitados"
    
    def test_database_isolation_prevents_cross_test_contamination(self):
        """Cada teste deve ser executado em isolamento, sem afetar outros."""
        # Este teste verifica a infraestrutura de teste em si
        # Cria duas instâncias de teste separadas
        
        temp_dir1 = tempfile.mkdtemp(prefix="test_isolation_1_")
        temp_dir2 = tempfile.mkdtemp(prefix="test_isolation_2_")
        
        try:
            # Banco de dados 1
            test_db_path1 = os.path.join(temp_dir1, "test1.db")
            test_db1 = SQLiteDB(db_path=test_db_path1)
            override_database_for_testing(test_db1)
            app.dependency_overrides[get_database] = lambda: test_db1
            
            client1 = TestClient(app)
            
            # Cria usuário no banco de dados 1
            new_user = {
                "username": "isolation_test_user",
                "email": "isolation@test.com",
                "full_name": "Isolation Test",
                "password": "password123",
                "permissions": ["read"]
            }
            
            response1 = client1.post("/api/v1/auth/register", json=new_user)
            assert response1.status_code == 201, "Criação de usuário no db1 deve ter sucesso"
            
            # Troca para banco de dados 2
            app.dependency_overrides.clear()
            reset_database()
            
            test_db_path2 = os.path.join(temp_dir2, "test2.db")
            test_db2 = SQLiteDB(db_path=test_db_path2)
            override_database_for_testing(test_db2)
            app.dependency_overrides[get_database] = lambda: test_db2
            
            client2 = TestClient(app)
            
            # Obtém token de admin para banco de dados 2
            login_response = client2.post(
                "/api/v1/auth/login-json",
                json={"username": "admin", "password": "secret"}
            )
            admin_token = login_response.json()["access_token"]
            headers = {"Authorization": f"Bearer {admin_token}"}
            
            # Verifica se usuário do db1 não existe no db2
            users_response = client2.get("/api/v1/auth/users", headers=headers)
            users = users_response.json()
            usernames = [u["username"] for u in users]
            
            assert "isolation_test_user" not in usernames, "Isolamento de banco de dados deve prevenir contaminação cruzada"
            assert "admin" in usernames, "Usuários padrão devem existir no novo banco de dados"
            
        finally:
            # Limpeza
            app.dependency_overrides.clear()
            reset_database()
            for temp_dir in [temp_dir1, temp_dir2]:
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except:
                    pass


if __name__ == "__main__":
    print("Authentication Behavior Tests")
    print("Run with: pytest test_auth_behaviors.py -v")
