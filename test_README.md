# Test Suite Organization

This project's test suite has been reorganized following Google's unit testing best practices.

## Test Files

### Behavior-Focused Tests

- **test_auth_behaviors.py**: Authentication and user management tests organized by behavior
  - `TestUserAuthentication`: Login, token validation
  - `TestUserRegistration`: User creation, registration validation
  - `TestUserManagement`: User CRUD operations
  - `TestAccessControl`: Permission-based access
  - `TestSecurityBehaviors`: Security edge cases

- **test_backend_behaviors.py**: Backend API tests organized by behavior
  - `TestAPIHealthAndStatus`: API health and status checks
  - `TestNetworkManagement`: Network CRUD operations
  - `TestDataIntegration`: Import/export functionality
  - `TestPermissionBasedAccess`: Role-based access control
  - `TestErrorHandlingAndValidation`: Error handling and input validation
  - `TestCompleteWorkflows`: End-to-end workflows
  - `TestDatabaseOperations`: Database operations

### Original Tests (Kept for Compatibility)

- **test_backend.py**: Original backend tests, now with deprecation notices directing to behavior-focused tests
- **test_user_system.py**: Original user system tests, now with deprecation notices directing to behavior-focused tests
- **test_models.py**: Tests for the core domain models

## Google Testing Best Practices

The new tests follow these best practices:

1. **Strive for unchanging tests**: Tests are isolated and don't depend on external state
2. **Test via public APIs**: Tests interact with the system through its public interface
3. **Test state, not interactions**: Tests verify results, not implementation details
4. **Make tests complete and concise**: Each test covers a specific behavior completely
5. **Test behaviors, not methods**: Tests are organized by behavior rather than by method
6. **Structure tests to emphasize behaviors**: Test classes and methods clearly indicate what's being tested
7. **Name tests after the behavior being tested**: Test names describe the behavior, not the implementation
8. **Don't put logic in tests**: Tests are straightforward and readable
9. **Write clear failure messages**: Assertions provide clear failure messages
10. **Follow DAMP over DRY**: Tests prefer clarity (Descriptive And Meaningful Phrases) over avoiding repetition (Don't Repeat Yourself)

## Database Isolation

Tests use a temporary database with automatic cleanup to ensure complete isolation between test runs:
- No test data contamination of the production database
- Each test runs in a clean environment
- Automatic cleanup after tests complete

## Running Tests

```bash
# Run behavior-focused tests
pytest test_auth_behaviors.py test_backend_behaviors.py -v

# Run all tests (including legacy tests)
pytest -v
```
