from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr

from ..dependencies import get_database
from ..database.sqlite import SQLiteDB

SECRET_KEY = "sistema-otimizacao-rede-entregas-2025-dev5-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    full_name: str
    password: str
    permissions: List[str] = ["read"]

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    permissions: Optional[List[str]] = None
    is_active: Optional[bool] = None

class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int

class TokenData(BaseModel):
    username: Optional[str] = None
    permissions: list = []

class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    permissions: list = []
    is_active: bool = True

class UserInDB(User):
    hashed_password: str

# Removido fake_users_db - agora usamos o banco de dados

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def get_user(username: str, db: Optional[SQLiteDB] = None) -> Optional[UserInDB]:
    """Busca usuário no banco de dados"""
    if db is None:
        from ..dependencies import get_database
        db = get_database()
    user_data = db.buscar_usuario_por_username(username)
    if user_data and user_data.get("is_active", False):
        return UserInDB(**user_data)
    return None

def authenticate_user(username: str, password: str, db: Optional[SQLiteDB] = None) -> Optional[UserInDB]:
    """Autentica usuário verificando senha"""
    user = get_user(username, db)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

def create_user(user_data: UserCreate, db: Optional[SQLiteDB] = None) -> bool:
    """Cria um novo usuário no banco de dados"""
    if db is None:
        from ..dependencies import get_database
        db = get_database()
    
    # Verificar se username ou email já existem
    if db.buscar_usuario_por_username(user_data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username já existe"
        )
    
    if db.buscar_usuario_por_email(str(user_data.email)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email já está em uso"
        )
    
    # Hash da senha
    hashed_password = get_password_hash(user_data.password)
    
    # Criar usuário
    success = db.criar_usuario(
        username=user_data.username,
        email=str(user_data.email),
        full_name=user_data.full_name,
        hashed_password=hashed_password,
        permissions=user_data.permissions
    )
    
    return success

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> TokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido ou expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        permissions: list = payload.get("permissions", [])
        if not username:
            raise credentials_exception
        token_data = TokenData(username=username, permissions=permissions)
        return token_data
    except JWTError:
        raise credentials_exception

def get_current_user(
    token_data: TokenData = Depends(verify_token),
    db = Depends(lambda: get_database())
) -> User:
    if not token_data.username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado"
        )
    user = get_user(username=token_data.username, db=db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado"
        )
    return User(**user.model_dump())

def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuário inativo"
        )
    return current_user

def require_permission(required_permission: str):
    def permission_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if required_permission not in current_user.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permissão '{required_permission}' necessária"
            )
        return current_user
    return permission_checker

def require_read_permission(current_user: User = Depends(require_permission("read"))):
    return current_user

def require_write_permission(current_user: User = Depends(require_permission("write"))):
    return current_user

def require_admin_permission(current_user: User = Depends(require_permission("admin"))):
    return current_user
