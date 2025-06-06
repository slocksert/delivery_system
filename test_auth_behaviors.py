#!/usr/bin/env python3
"""
Authentication behavior tests following Google's testing best practices.

This file consolidates authentication tests from test_backend.py and test_user_system.py,
organizing them by behavior rather than method/endpoint and following DAMP over DRY principles.

Behaviors tested:
- User Authentication (login, token validation)  
- User Registration (creation, validation)
- User Management (CRUD operations)
- Access Control (permissions, authorization)
- Security (invalid inputs, edge cases)
"""

import pytest
import tempfile
import shutil
import os
import time
from typing import Dict, Any
from fastapi.testclient import TestClient

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from backend.main import app
from backend.database.sqlite import SQLiteDB
from backend.dependencies import get_database, override_database_for_testing, reset_database


@pytest.fixture(scope="function") 
def isolated_client():
    """Creates an isolated test client with temporary database for each test."""
    # Create temporary database
    temp_dir = tempfile.mkdtemp(prefix="test_auth_behavior_")
    test_db_path = os.path.join(temp_dir, "test_auth.db")
    
    # Setup database injection
    test_db = SQLiteDB(db_path=test_db_path)
    override_database_for_testing(test_db)
    app.dependency_overrides[get_database] = lambda: test_db
    
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
def admin_token(isolated_client):
    """Gets admin authentication token."""
    response = isolated_client.post(
        "/api/v1/auth/login-json",
        json={"username": "admin", "password": "secret"}
    )
    assert response.status_code == 200, "Admin login should succeed"
    return response.json()["access_token"]


@pytest.fixture  
def operator_token(isolated_client):
    """Gets operator authentication token."""
    response = isolated_client.post(
        "/api/v1/auth/login-json", 
        json={"username": "operator", "password": "secret"}
    )
    assert response.status_code == 200, "Operator login should succeed"
    return response.json()["access_token"]


@pytest.fixture
def viewer_token(isolated_client):
    """Gets viewer authentication token."""
    response = isolated_client.post(
        "/api/v1/auth/login-json",
        json={"username": "viewer", "password": "secret"}
    )
    assert response.status_code == 200, "Viewer login should succeed"
    return response.json()["access_token"]


class TestUserAuthentication:
    """Tests behaviors related to user authentication and token management."""
    
    def test_admin_can_authenticate_with_valid_credentials(self, isolated_client):
        """Admin users should be able to login with correct username and password."""
        response = isolated_client.post(
            "/api/v1/auth/login-json",
            json={"username": "admin", "password": "secret"}
        )
        
        assert response.status_code == 200, "Valid admin credentials should be accepted"
        data = response.json()
        assert "access_token" in data, "Login should return access token"
        assert data["token_type"] == "bearer", "Token type should be bearer"
        assert len(data["access_token"]) > 10, "Token should be non-empty string"
    
    def test_authentication_fails_with_wrong_password(self, isolated_client):
        """Authentication should fail when user provides incorrect password."""
        response = isolated_client.post(
            "/api/v1/auth/login-json",
            json={"username": "admin", "password": "wrong_password"}
        )
        
        assert response.status_code == 401, "Wrong password should be rejected"
        assert "detail" in response.json(), "Error response should include details"
    
    def test_authentication_fails_for_nonexistent_user(self, isolated_client):
        """Authentication should fail when username does not exist."""
        response = isolated_client.post(
            "/api/v1/auth/login-json",
            json={"username": "nonexistent_user", "password": "any_password"}
        )
        
        assert response.status_code == 401, "Nonexistent user should be rejected"
    
    def test_form_based_authentication_works(self, isolated_client):
        """Users should be able to authenticate using form data (legacy endpoint)."""
        response = isolated_client.post(
            "/api/v1/auth/login",
            data={"username": "admin", "password": "secret"},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        assert response.status_code == 200, "Form-based login should work"
        data = response.json()
        assert "access_token" in data, "Form login should return token"
    
    def test_token_provides_access_to_user_information(self, isolated_client, admin_token):
        """Valid tokens should allow access to user's own information."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = isolated_client.get("/api/v1/auth/me", headers=headers)
        
        assert response.status_code == 200, "Valid token should provide access"
        data = response.json()
        assert data["username"] == "admin", "Should return correct user info"
        assert "admin" in data["permissions"], "Should include user permissions"
        assert data["is_active"] is True, "Should show user status"
    
    def test_token_validation_confirms_token_validity(self, isolated_client, admin_token):
        """Token validation endpoint should confirm valid tokens."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = isolated_client.get("/api/v1/auth/verify-token", headers=headers)
        
        assert response.status_code == 200, "Token verification should succeed"
        data = response.json()
        assert data["valid"] is True, "Valid token should be confirmed as valid"
        assert data["username"] == "admin", "Should return token owner"
        assert "permissions" in data, "Should include permissions"
    
    def test_access_denied_without_authentication_token(self, isolated_client):
        """Protected endpoints should deny access without authentication."""
        response = isolated_client.get("/api/v1/auth/me")
        
        assert response.status_code == 403, "No token should result in access denied"


class TestUserRegistration:
    """Tests behaviors related to user registration and account creation."""
    
    def test_new_user_can_be_registered_with_valid_data(self, isolated_client):
        """System should allow registration of new users with valid information."""
        new_user = {
            "username": "newuser",
            "email": "newuser@example.com",
            "full_name": "New User",
            "password": "secure_password",
            "permissions": ["read", "write"]
        }
        
        response = isolated_client.post("/api/v1/auth/register", json=new_user)
        
        assert response.status_code == 201, "Valid user data should be accepted"
        data = response.json()
        assert data["status"] == "success", "Registration should indicate success"
        assert "newuser" in data["message"], "Success message should include username"
        assert data["user"]["username"] == "newuser", "Should return user info"
        assert "password" not in data["user"], "Password should not be returned"
    
    def test_newly_registered_user_can_authenticate(self, isolated_client):
        """Users should be able to login immediately after registration."""
        # Register user
        new_user = {
            "username": "logintest",
            "email": "logintest@example.com", 
            "full_name": "Login Test User",
            "password": "test_password_123",
            "permissions": ["read"]
        }
        
        register_response = isolated_client.post("/api/v1/auth/register", json=new_user)
        assert register_response.status_code == 201, "Registration should succeed"
        
        # Attempt login
        login_response = isolated_client.post(
            "/api/v1/auth/login-json",
            json={"username": "logintest", "password": "test_password_123"}
        )
        
        assert login_response.status_code == 200, "New user should be able to login"
        assert "access_token" in login_response.json(), "Login should return token"
    
    def test_duplicate_username_registration_is_rejected(self, isolated_client):
        """System should prevent registration of duplicate usernames."""
        user_data = {
            "username": "duplicate_test",
            "email": "test1@example.com",
            "full_name": "First User",
            "password": "password123",
            "permissions": ["read"]
        }
        
        # First registration
        first_response = isolated_client.post("/api/v1/auth/register", json=user_data)
        assert first_response.status_code == 201, "First registration should succeed"
        
        # Second registration with same username
        user_data["email"] = "test2@example.com"  # Different email, same username
        second_response = isolated_client.post("/api/v1/auth/register", json=user_data)
        
        assert second_response.status_code == 400, "Duplicate username should be rejected"
    
    def test_cannot_register_with_existing_system_username(self, isolated_client):
        """Registration should fail when trying to use existing system usernames."""
        admin_duplicate = {
            "username": "admin",  # System user
            "email": "fake_admin@example.com",
            "full_name": "Fake Admin",
            "password": "new_password",
            "permissions": ["read"]
        }
        
        response = isolated_client.post("/api/v1/auth/register", json=admin_duplicate)
        
        assert response.status_code == 400, "System usernames should be protected"


class TestUserManagement:
    """Tests behaviors related to user management operations (CRUD)."""
    
    def test_admin_can_view_all_users_in_system(self, isolated_client, admin_token):
        """Administrators should be able to view complete user list."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = isolated_client.get("/api/v1/auth/users", headers=headers)
        
        assert response.status_code == 200, "Admin should access user list"
        users = response.json()
        assert isinstance(users, list), "Should return list of users"
        assert len(users) >= 3, "Should include system users (admin, operator, viewer)"
        
        usernames = [user["username"] for user in users]
        assert "admin" in usernames, "Should include admin user"
        assert "operator" in usernames, "Should include operator user"
        assert "viewer" in usernames, "Should include viewer user"
    
    def test_admin_can_update_user_information(self, isolated_client, admin_token):
        """Administrators should be able to modify user account details."""
        # Create test user
        test_user = {
            "username": "updateable_user",
            "email": "original@example.com",
            "full_name": "Original Name",
            "password": "password123",
            "permissions": ["read"]
        }
        
        register_response = isolated_client.post("/api/v1/auth/register", json=test_user)
        assert register_response.status_code == 201, "Test user creation should succeed"
        
        # Update user
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
        
        assert update_response.status_code == 200, "User update should succeed"
        data = update_response.json()
        assert data["status"] == "success", "Update should indicate success"
        
        # Verify changes
        users_response = isolated_client.get("/api/v1/auth/users", headers=headers)
        users = users_response.json()
        updated_user = next((u for u in users if u["username"] == "updateable_user"), None)
        
        assert updated_user is not None, "Updated user should exist"
        assert updated_user["email"] == "updated@example.com", "Email should be updated"
        assert updated_user["full_name"] == "Updated Name", "Full name should be updated"
        assert sorted(updated_user["permissions"]) == ["read", "write"], "Permissions should be updated"
    
    def test_admin_can_delete_user_accounts(self, isolated_client, admin_token):
        """Administrators should be able to remove user accounts."""
        # Create test user
        test_user = {
            "username": "deletable_user",
            "email": "delete@example.com",
            "full_name": "Delete Test",
            "password": "password123",
            "permissions": ["read"]
        }
        
        register_response = isolated_client.post("/api/v1/auth/register", json=test_user)
        assert register_response.status_code == 201, "Test user creation should succeed"
        
        # Delete user
        headers = {"Authorization": f"Bearer {admin_token}"}
        delete_response = isolated_client.delete(
            "/api/v1/auth/users/deletable_user",
            headers=headers
        )
        
        assert delete_response.status_code == 200, "User deletion should succeed"
        data = delete_response.json()
        assert data["status"] == "success", "Deletion should indicate success"
        
        # Verify deletion
        users_response = isolated_client.get("/api/v1/auth/users", headers=headers)
        users = users_response.json()
        usernames = [u["username"] for u in users]
        assert "deletable_user" not in usernames, "Deleted user should not appear in list"
    
    def test_updating_nonexistent_user_fails_gracefully(self, isolated_client, admin_token):
        """System should handle attempts to update non-existent users."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        update_data = {"full_name": "Should Not Work"}
        
        response = isolated_client.put(
            "/api/v1/auth/users/nonexistent_user",
            json=update_data,
            headers=headers
        )
        
        assert response.status_code == 404, "Nonexistent user update should fail"
    
    def test_deleting_nonexistent_user_fails_gracefully(self, isolated_client, admin_token):
        """System should handle attempts to delete non-existent users."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = isolated_client.delete(
            "/api/v1/auth/users/nonexistent_user",
            headers=headers
        )
        
        assert response.status_code == 404, "Nonexistent user deletion should fail"
    
    def test_admin_cannot_delete_own_account(self, isolated_client, admin_token):
        """System should prevent users from deleting their own accounts."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = isolated_client.delete(
            "/api/v1/auth/users/admin",
            headers=headers
        )
        
        assert response.status_code == 400, "Self-deletion should be prevented"
        assert "Não é possível deletar seu próprio usuário" in response.json()["detail"]


class TestAccessControl:
    """Tests behaviors related to permissions and authorization."""
    
    def test_non_admin_users_cannot_view_user_list(self, isolated_client, operator_token):
        """Only administrators should be able to access user management functions."""
        headers = {"Authorization": f"Bearer {operator_token}"}
        response = isolated_client.get("/api/v1/auth/users", headers=headers)
        
        assert response.status_code == 403, "Non-admin should be denied user list access"
        assert "Acesso negado" in response.json()["detail"]
    
    def test_non_admin_users_cannot_update_other_users(self, isolated_client, viewer_token):
        """Non-administrators should not be able to modify other user accounts."""
        headers = {"Authorization": f"Bearer {viewer_token}"}
        update_data = {"email": "hacker@example.com"}
        
        response = isolated_client.put(
            "/api/v1/auth/users/admin",
            json=update_data,
            headers=headers
        )
        
        assert response.status_code == 403, "Non-admin should be denied update access"
    
    def test_non_admin_users_cannot_delete_other_users(self, isolated_client, viewer_token):
        """Non-administrators should not be able to delete other user accounts."""
        headers = {"Authorization": f"Bearer {viewer_token}"}
        
        response = isolated_client.delete(
            "/api/v1/auth/users/operator",
            headers=headers
        )
        
        assert response.status_code == 403, "Non-admin should be denied delete access"
    
    def test_permissions_endpoint_lists_available_permissions(self, isolated_client):
        """System should provide information about available permissions."""
        response = isolated_client.get("/api/v1/auth/permissions")
        
        assert response.status_code == 200, "Permissions endpoint should be accessible"
        data = response.json()
        assert "permissions" in data, "Should list available permissions"
        
        expected_permissions = ["admin", "read", "write", "delete"]
        for permission in expected_permissions:
            assert permission in data["permissions"], f"Should include {permission} permission"


class TestSecurityBehaviors:
    """Tests security-related behaviors and edge cases."""
    
    def test_system_handles_malformed_authentication_requests(self, isolated_client):
        """System should gracefully handle malformed authentication data."""
        # Missing password
        response1 = isolated_client.post(
            "/api/v1/auth/login-json",
            json={"username": "admin"}
        )
        assert response1.status_code in [400, 422], "Missing password should be rejected"
        
        # Missing username  
        response2 = isolated_client.post(
            "/api/v1/auth/login-json",
            json={"password": "secret"}
        )
        assert response2.status_code in [400, 422], "Missing username should be rejected"
        
        # Empty payload
        response3 = isolated_client.post(
            "/api/v1/auth/login-json",
            json={}
        )
        assert response3.status_code in [400, 422], "Empty payload should be rejected"
    
    def test_system_handles_malformed_registration_requests(self, isolated_client):
        """System should validate registration data and reject invalid requests."""
        # Missing required fields
        invalid_user = {
            "username": "incomplete"
            # Missing email, password, permissions
        }
        
        response = isolated_client.post("/api/v1/auth/register", json=invalid_user)
        assert response.status_code in [400, 422], "Incomplete registration data should be rejected"
    
    def test_database_isolation_prevents_cross_test_contamination(self):
        """Each test should run in isolation without affecting others."""
        # This test verifies the test infrastructure itself
        # Create two separate test instances
        
        temp_dir1 = tempfile.mkdtemp(prefix="test_isolation_1_")
        temp_dir2 = tempfile.mkdtemp(prefix="test_isolation_2_")
        
        try:
            # Database 1
            test_db_path1 = os.path.join(temp_dir1, "test1.db")
            test_db1 = SQLiteDB(db_path=test_db_path1)
            override_database_for_testing(test_db1)
            app.dependency_overrides[get_database] = lambda: test_db1
            
            client1 = TestClient(app)
            
            # Create user in database 1
            new_user = {
                "username": "isolation_test_user",
                "email": "isolation@test.com",
                "full_name": "Isolation Test",
                "password": "password123",
                "permissions": ["read"]
            }
            
            response1 = client1.post("/api/v1/auth/register", json=new_user)
            assert response1.status_code == 201, "User creation in db1 should succeed"
            
            # Switch to database 2
            app.dependency_overrides.clear()
            reset_database()
            
            test_db_path2 = os.path.join(temp_dir2, "test2.db")
            test_db2 = SQLiteDB(db_path=test_db_path2)
            override_database_for_testing(test_db2)
            app.dependency_overrides[get_database] = lambda: test_db2
            
            client2 = TestClient(app)
            
            # Get admin token for database 2
            login_response = client2.post(
                "/api/v1/auth/login-json",
                json={"username": "admin", "password": "secret"}
            )
            admin_token = login_response.json()["access_token"]
            headers = {"Authorization": f"Bearer {admin_token}"}
            
            # Verify user from db1 doesn't exist in db2
            users_response = client2.get("/api/v1/auth/users", headers=headers)
            users = users_response.json()
            usernames = [u["username"] for u in users]
            
            assert "isolation_test_user" not in usernames, "Database isolation should prevent cross-contamination"
            assert "admin" in usernames, "Default users should exist in new database"
            
        finally:
            # Cleanup
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
