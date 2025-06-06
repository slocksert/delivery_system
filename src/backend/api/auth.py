from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Dict, Any, Optional, List

from ..auth.auth import (
    authenticate_user,
    create_access_token,
    get_current_active_user,
    create_user,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    Token,
    User,
    UserCreate,
    UserUpdate
)
from ..dependencies import get_database

router = APIRouter(
    prefix="/auth",
    tags=["Autenticação"],
    responses={
        401: {"description": "Não autorizado"},
        403: {"description": "Acesso negado"}
    }
)

class LoginRequest(BaseModel):
    username: str
    password: str

class UserInfo(BaseModel):
    username: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    permissions: list = []
    is_active: bool = True

@router.post(
    "/login",
    response_model=Token,
    summary="Login do usuário",
    description="Autentica usuário e retorna token JWT"
)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db = Depends(get_database)
) -> Token:
    """
    **Login de Usuário**
    
    Autentica o usuário e retorna um token JWT para acesso à API.
    
    **Usuários disponíveis para teste:**
    - `admin` / `secret` - Acesso total (admin, read, write, delete)
    - `operator` / `secret` - Operador (read, write)  
    - `viewer` / `secret` - Apenas visualização (read)
    """
    user = authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "permissions": user.permissions},
        expires_delta=access_token_expires
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60  # em segundos
    )

@router.post(
    "/login-json",
    response_model=Token,
    summary="Login via JSON",
    description="Alternativa ao login usando JSON no body"
)
async def login_json(
    login_data: LoginRequest,
    db = Depends(get_database)
) -> Token:
    """
    **Login via JSON**
    
    Alternativa ao endpoint de login usando JSON no request body
    em vez de form data.
    """
    user = authenticate_user(login_data.username, login_data.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha incorretos",
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "permissions": user.permissions},
        expires_delta=access_token_expires
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )

@router.get(
    "/me",
    response_model=UserInfo,
    summary="Informações do usuário",
    description="Retorna informações do usuário autenticado"
)
async def get_user_info(current_user: User = Depends(get_current_active_user)) -> UserInfo:
    """
    **Informações do Usuário Autenticado**
    
    Retorna as informações do usuário atual, incluindo permissões.
    Requer token JWT válido no header Authorization.
    """
    return UserInfo(
        username=current_user.username,
        full_name=current_user.full_name,
        email=current_user.email,
        permissions=current_user.permissions,
        is_active=current_user.is_active
    )

@router.get(
    "/verify-token",
    summary="Verificar token",
    description="Verifica se o token JWT é válido"
)
async def verify_token(current_user: User = Depends(get_current_active_user)) -> Dict[str, Any]:
    """
    **Verificar Token**
    
    Endpoint para verificar se um token JWT é válido.
    Útil para validação em frontend/outras aplicações.
    """
    return {
        "valid": True,
        "username": current_user.username,
        "permissions": current_user.permissions,
        "message": "Token válido"
    }

@router.get(
    "/permissions",
    summary="Listar permissões disponíveis",
    description="Lista todas as permissões disponíveis no sistema"
)
async def list_permissions() -> Dict[str, Any]:
    """
    **Permissões Disponíveis**
    
    Lista todas as permissões disponíveis no sistema e sua descrição.
    """
    return {
        "permissions": {
            "admin": "Acesso administrativo completo",
            "read": "Leitura de dados (listar, visualizar)",
            "write": "Escrita de dados (criar, atualizar)",
            "delete": "Exclusão de dados"
        },
        "users": {
            "admin": ["admin", "read", "write", "delete"],
            "operator": ["read", "write"],
            "viewer": ["read"]
        },
        "usage": "Inclua o token no header: Authorization: Bearer <token>"
    }

@router.post(
    "/register",
    response_model=Dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Registrar novo usuário",
    description="Cria uma nova conta de usuário no sistema"
)
async def register_user(
    user_data: UserCreate,
    db = Depends(get_database)
) -> Dict[str, Any]:
    """
    **Registrar Novo Usuário**
    
    Cria uma nova conta de usuário no sistema com as informações fornecidas.
    
    **Permissões disponíveis:**
    - `read` - Visualizar dados
    - `write` - Criar e editar dados  
    - `delete` - Excluir dados
    - `admin` - Acesso administrativo completo
    
    **Campos obrigatórios:**
    - username: Nome de usuário único
    - email: Email único válido
    - full_name: Nome completo
    - password: Senha (mínimo 6 caracteres)
    - permissions: Lista de permissões (padrão: ["read"])
    """
    try:
        success = create_user(user_data, db)
        if success:
            return {
                "status": "success",
                "message": f"Usuário '{user_data.username}' criado com sucesso",
                "user": {
                    "username": user_data.username,
                    "email": user_data.email,
                    "full_name": user_data.full_name,
                    "permissions": user_data.permissions
                }
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Erro ao criar usuário"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(e)}"
        )

@router.get(
    "/users",
    response_model=List[Dict[str, Any]],
    summary="Listar usuários",
    description="Lista todos os usuários do sistema (apenas admins)"
)
async def list_users(
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_database)
) -> List[Dict[str, Any]]:
    """
    **Listar Usuários**
    
    Lista todos os usuários cadastrados no sistema.
    Requer permissão de administrador.
    """
    if "admin" not in current_user.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado. Apenas administradores podem listar usuários."
        )
    
    users = db.listar_usuarios()
    
    return users

@router.put(
    "/users/{username}",
    response_model=Dict[str, Any],
    summary="Atualizar usuário", 
    description="Atualiza dados de um usuário existente"
)
async def update_user(
    username: str,
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_database)
) -> Dict[str, Any]:
    """
    **Atualizar Usuário**
    
    Atualiza os dados de um usuário existente.
    Usuários podem atualizar seus próprios dados.
    Apenas admins podem atualizar outros usuários.
    """
    # Verificar se o usuário pode atualizar este perfil
    if current_user.username != username and "admin" not in current_user.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado. Você só pode atualizar seu próprio perfil."
        )
    
    from ..auth.auth import get_password_hash
    
    # Verificar se o usuário existe
    existing_user = db.buscar_usuario_por_username(username)
    if not existing_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    
    # Preparar dados para atualização
    update_data = {}
    if user_update.email is not None:
        update_data["email"] = str(user_update.email)
    if user_update.full_name is not None:
        update_data["full_name"] = user_update.full_name
    if user_update.password is not None:
        update_data["hashed_password"] = get_password_hash(user_update.password)
    if user_update.permissions is not None:
        # Apenas admins podem alterar permissões
        if "admin" not in current_user.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas administradores podem alterar permissões"
            )
        update_data["permissions"] = user_update.permissions
    if user_update.is_active is not None:
        # Apenas admins podem ativar/desativar usuários
        if "admin" not in current_user.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas administradores podem ativar/desativar usuários"
            )
        update_data["is_active"] = user_update.is_active
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhum dado fornecido para atualização"
        )
    
    # Atualizar usuário
    success = db.atualizar_usuario(username, **update_data)
    
    if success:
        return {
            "status": "success",
            "message": f"Usuário '{username}' atualizado com sucesso"
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Erro ao atualizar usuário. Email pode já estar em uso."
        )

@router.delete(
    "/users/{username}",
    response_model=Dict[str, Any],
    summary="Deletar usuário",
    description="Remove um usuário do sistema (apenas admins)"
)
async def delete_user(
    username: str,
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_database)
) -> Dict[str, Any]:
    """
    **Deletar Usuário**
    
    Remove um usuário do sistema permanentemente.
    Requer permissão de administrador.
    Não é possível deletar o próprio usuário.
    """
    if "admin" not in current_user.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado. Apenas administradores podem deletar usuários."
        )
    
    if current_user.username == username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível deletar seu próprio usuário"
        )
    
    success = db.deletar_usuario(username)
    
    if success:
        return {
            "status": "success",
            "message": f"Usuário '{username}' deletado com sucesso"
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
