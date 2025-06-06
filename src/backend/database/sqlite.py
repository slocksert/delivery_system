import sqlite3
import json
import os
from typing import Optional, Dict, Any, List
import threading

DB_PATH_PROD = 'redes_entregas.db'
DB_PATH_TEST = 'redes_entregas_test.db'

class SQLiteDB:
    _lock = threading.Lock()

    def __init__(self, db_path: Optional[str] = None, is_test: bool = False):
        if db_path:
            self.db_path = db_path
        elif is_test:
            self.db_path = DB_PATH_TEST
        else:
            self.db_path = DB_PATH_PROD
            
        self.is_test = is_test
        self._ensure_tables()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _ensure_tables(self):
        with self._get_conn() as conn:
            # Tabela de redes
            conn.execute('''
                CREATE TABLE IF NOT EXISTS redes (
                    id TEXT PRIMARY KEY,
                    nome TEXT,
                    descricao TEXT,
                    json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Tabela de usuários
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    full_name TEXT,
                    hashed_password TEXT NOT NULL,
                    permissions TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor = conn.execute("PRAGMA table_info(redes)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if 'created_at' not in columns:
                print("Adding created_at column to existing redes table")
                conn.execute('ALTER TABLE redes ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
            
            # Inserir usuários padrão se a tabela estiver vazia
            cursor = conn.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            
            if user_count == 0:
                print("Inserindo usuários padrão...")
                self._insert_default_users(conn)
            
            conn.commit()

    def _insert_default_users(self, conn):
        """Insere usuários padrão na tabela"""
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        default_users = [
            {
                "username": "admin",
                "email": "admin@rede-entregas.com",
                "full_name": "Administrador Sistema",
                "password": "secret",
                "permissions": '["admin", "read", "write", "delete"]'
            },
            {
                "username": "operator",
                "email": "operator@rede-entregas.com", 
                "full_name": "Operador Logística",
                "password": "secret",
                "permissions": '["read", "write"]'
            },
            {
                "username": "viewer",
                "email": "viewer@rede-entregas.com",
                "full_name": "Visualizador",
                "password": "secret", 
                "permissions": '["read"]'
            }
        ]
        
        for user in default_users:
            hashed_password = pwd_context.hash(user["password"])
            conn.execute('''
                INSERT INTO users (username, email, full_name, hashed_password, permissions)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                user["username"],
                user["email"], 
                user["full_name"],
                hashed_password,
                user["permissions"]
            ))

    def cleanup_test_db(self):
        """Remove o arquivo de banco de teste se existir"""
        if self.is_test and os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
                print(f"Banco de teste removido: {self.db_path}")
            except Exception as e:
                print(f"Erro ao remover banco de teste: {e}")

    @classmethod
    def create_test_instance(cls):
        """Cria uma instância para testes"""
        return cls(is_test=True)

    @classmethod 
    def create_production_instance(cls):
        """Cria uma instância para produção"""
        return cls(is_test=False)

    def salvar_rede(self, rede_id: str, nome: str, descricao: str, dados: Dict[str, Any]):
        with self._lock, self._get_conn() as conn:
            cur = conn.execute('SELECT created_at FROM redes WHERE id = ?', (rede_id,))
            existing = cur.fetchone()
            
            if existing:
                conn.execute(
                    'UPDATE redes SET nome = ?, descricao = ?, json = ? WHERE id = ?',
                    (nome, descricao, json.dumps(dados), rede_id)
                )
            else:
                conn.execute(
                    'INSERT INTO redes (id, nome, descricao, json) VALUES (?, ?, ?, ?)',
                    (rede_id, nome, descricao, json.dumps(dados))
                )
            conn.commit()

    def remover_rede(self, rede_id: str):
        with self._lock, self._get_conn() as conn:
            conn.execute('DELETE FROM redes WHERE id = ?', (rede_id,))
            conn.commit()

    def carregar_rede(self, rede_id: str) -> Optional[Dict[str, Any]]:
        with self._lock, self._get_conn() as conn:
            cur = conn.execute('SELECT json FROM redes WHERE id = ?', (rede_id,))
            row = cur.fetchone()
            if row:
                return json.loads(row[0])
            return None

    def listar_redes(self) -> List[Dict[str, Any]]:
        with self._lock, self._get_conn() as conn:
            cur = conn.execute('SELECT id, nome, descricao, json, created_at FROM redes')
            return [
                {
                    "id": row[0], 
                    "nome": row[1], 
                    "descricao": row[2], 
                    "created_at": row[4],
                    **json.loads(row[3])
                }
                for row in cur.fetchall()
            ]

    def carregar_todas_redes(self) -> Dict[str, Dict[str, Any]]:
        redes = {}
        with self._lock, self._get_conn() as conn:
            cur = conn.execute('SELECT id, json FROM redes')
            for row in cur.fetchall():
                redes[row[0]] = json.loads(row[1])
        return redes

    # Métodos para gerenciamento de usuários
    def criar_usuario(self, username: str, email: str, full_name: str, hashed_password: str, permissions: List[str]) -> bool:
        """Cria um novo usuário no banco de dados"""
        try:
            with self._lock, self._get_conn() as conn:
                conn.execute('''
                    INSERT INTO users (username, email, full_name, hashed_password, permissions)
                    VALUES (?, ?, ?, ?, ?)
                ''', (username, email, full_name, hashed_password, json.dumps(permissions)))
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False  # Username ou email já existe

    def buscar_usuario_por_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Busca usuário por username"""
        with self._lock, self._get_conn() as conn:
            cur = conn.execute('''
                SELECT id, username, email, full_name, hashed_password, permissions, is_active, created_at
                FROM users WHERE username = ?
            ''', (username,))
            row = cur.fetchone()
            if row:
                return {
                    "id": row[0],
                    "username": row[1],
                    "email": row[2],
                    "full_name": row[3],
                    "hashed_password": row[4],
                    "permissions": json.loads(row[5]),
                    "is_active": bool(row[6]),
                    "created_at": row[7]
                }
            return None

    def buscar_usuario_por_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Busca usuário por email"""
        with self._lock, self._get_conn() as conn:
            cur = conn.execute('''
                SELECT id, username, email, full_name, hashed_password, permissions, is_active, created_at
                FROM users WHERE email = ?
            ''', (email,))
            row = cur.fetchone()
            if row:
                return {
                    "id": row[0],
                    "username": row[1],
                    "email": row[2],
                    "full_name": row[3],
                    "hashed_password": row[4],
                    "permissions": json.loads(row[5]),
                    "is_active": bool(row[6]),
                    "created_at": row[7]
                }
            return None

    def listar_usuarios(self) -> List[Dict[str, Any]]:
        """Lista todos os usuários (sem senhas)"""
        with self._lock, self._get_conn() as conn:
            cur = conn.execute('''
                SELECT id, username, email, full_name, permissions, is_active, created_at
                FROM users ORDER BY created_at DESC
            ''')
            return [
                {
                    "id": row[0],
                    "username": row[1],
                    "email": row[2],
                    "full_name": row[3],
                    "permissions": json.loads(row[4]),
                    "is_active": bool(row[5]),
                    "created_at": row[6]
                }
                for row in cur.fetchall()
            ]

    def atualizar_usuario(self, username: str, email: Optional[str] = None, full_name: Optional[str] = None, 
                         hashed_password: Optional[str] = None, permissions: Optional[List[str]] = None, 
                         is_active: Optional[bool] = None) -> bool:
        """Atualiza dados do usuário"""
        updates = []
        params = []
        
        if email is not None:
            updates.append("email = ?")
            params.append(email)
        if full_name is not None:
            updates.append("full_name = ?")
            params.append(full_name)
        if hashed_password is not None:
            updates.append("hashed_password = ?")
            params.append(hashed_password)
        if permissions is not None:
            updates.append("permissions = ?")
            params.append(json.dumps(permissions))
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(is_active)
        
        if not updates:
            return False
            
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(username)
        
        try:
            with self._lock, self._get_conn() as conn:
                conn.execute(f'''
                    UPDATE users SET {", ".join(updates)}
                    WHERE username = ?
                ''', params)
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False

    def deletar_usuario(self, username: str) -> bool:
        """Deleta um usuário"""
        with self._lock, self._get_conn() as conn:
            cursor = conn.execute('DELETE FROM users WHERE username = ?', (username,))
            conn.commit()
            return cursor.rowcount > 0
