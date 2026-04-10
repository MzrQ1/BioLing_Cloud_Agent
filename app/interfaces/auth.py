"""用户认证模块 - 简单的用户管理"""
import hashlib
import secrets
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import os

from app.database.database import get_db_context
from sqlalchemy import text


class UserAuth:
    """简单用户认证（基于SQLite）"""
    
    def __init__(self):
        self._sessions: Dict[str, Dict] = {}
        self._init_db()
    
    def _init_db(self):
        """初始化用户表"""
        with get_db_context() as db:
            db.execute(text('''
                CREATE TABLE IF NOT EXISTS user_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now')),
                    expires_at TEXT
                )
            '''))
    
    def _hash_password(self, password: str) -> str:
        """密码哈希"""
        salt = secrets.token_hex(16)
        hash_val = hashlib.sha256((password + salt).encode()).hexdigest()
        return f"{salt}:{hash_val}"
    
    def _verify_password(self, password: str, stored_hash: str) -> bool:
        """验证密码"""
        try:
            salt, hash_val = stored_hash.split(':')
            computed = hashlib.sha256((password + salt).encode()).hexdigest()
            return computed == hash_val
        except:
            return False
    
    def register(self, username: str, password: str, 
                 nickname: str = None) -> Dict:
        """
        注册新用户
        
        Returns:
            {success: bool, user_id: str, error: str}
        """
        with get_db_context() as db:
            existing = db.execute(
                text('SELECT user_id FROM users WHERE username = :username'), 
                {'username': username}
            ).fetchone()
            
            if existing:
                return {"success": False, "error": "用户名已存在"}
            
            user_id = f"user_{secrets.token_hex(8)}"
            password_hash = self._hash_password(password)
            
            db.execute(text('''
                INSERT INTO users (user_id, username, password_hash, nickname, is_active)
                VALUES (:user_id, :username, :password_hash, :nickname, 1)
            '''), {
                'user_id': user_id,
                'username': username,
                'password_hash': password_hash,
                'nickname': nickname or username
            })
            
            return {
                "success": True,
                "user_id": user_id,
                "username": username,
                "message": "注册成功"
            }
    
    def login(self, username: str, password: str) -> Dict:
        """
        用户登录
        
        Returns:
            {success: bool, session_id: str, user_id: str, error: str}
        """
        with get_db_context() as db:
            user = db.execute(
                text('SELECT user_id, username, password_hash, is_active FROM users WHERE username = :username'),
                {'username': username}
            ).fetchone()
            
            if not user:
                return {"success": False, "error": "用户名或密码错误"}
            
            if not user[3]:
                return {"success": False, "error": "账户已被禁用"}
            
            if not self._verify_password(password, user[2]):
                return {"success": False, "error": "用户名或密码错误"}
            
            session_id = f"sess_{secrets.token_hex(16)}"
            expires = datetime.now() + timedelta(days=7)
            
            db.execute(text('''
                INSERT INTO user_sessions (session_id, user_id, expires_at)
                VALUES (:session_id, :user_id, :expires_at)
            '''), {
                'session_id': session_id,
                'user_id': user[0],
                'expires_at': expires.isoformat()
            })
            
            db.execute(text('''
                UPDATE users SET last_login = datetime('now') WHERE user_id = :user_id
            '''), {'user_id': user[0]})
            
            self._sessions[session_id] = {
                "user_id": user[0],
                "username": user[1],
                "expires_at": expires.isoformat()
            }
            
            return {
                "success": True,
                "session_id": session_id,
                "user_id": user[0],
                "username": user[1],
                "message": "登录成功"
            }
    
    def logout(self, session_id: str) -> bool:
        """登出"""
        with get_db_context() as db:
            db.execute(
                text('DELETE FROM user_sessions WHERE session_id = :session_id'),
                {'session_id': session_id}
            )
        
        self._sessions.pop(session_id, None)
        return True
    
    def verify_session(self, session_id: str) -> Optional[Dict]:
        """
        验证会话
        
        Returns:
            用户信息字典 或 None（无效会话）
        """
        if session_id in self._sessions:
            session = self._sessions[session_id]
            try:
                if datetime.fromisoformat(session["expires_at"]) > datetime.now():
                    return session
                else:
                    del self._sessions[session_id]
                    return None
            except:
                del self._sessions[session_id]
                return None
        
        with get_db_context() as db:
            result = db.execute(text('''
                SELECT s.user_id, u.username, s.expires_at
                FROM user_sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.session_id = :session_id
            '''), {'session_id': session_id}).fetchone()
            
            if not result:
                return None
            
            try:
                if datetime.fromisoformat(result[2]) < datetime.now():
                    db.execute(
                        text('DELETE FROM user_sessions WHERE session_id = :session_id'),
                        {'session_id': session_id}
                    )
                    return None
                
                user_info = {
                    "user_id": result[0],
                    "username": result[1],
                    "expires_at": result[2]
                }
                self._sessions[session_id] = user_info
                return user_info
            except:
                return None
    
    def get_user_info(self, user_id: str) -> Optional[Dict]:
        """获取用户信息"""
        with get_db_context() as db:
            user = db.execute(text('''
                SELECT user_id, username, nickname, created_at, last_login, is_active
                FROM users WHERE user_id = :user_id
            '''), {'user_id': user_id}).fetchone()
            
            if not user:
                return None
            
            return {
                "user_id": user[0],
                "username": user[1],
                "nickname": user[2],
                "created_at": user[3],
                "last_login": user[4],
                "is_active": bool(user[5])
            }
    
    def list_users(self) -> List[Dict]:
        """列出所有用户（管理员功能）"""
        with get_db_context() as db:
            rows = db.execute(text('''
                SELECT user_id, username, nickname, created_at, last_login, is_active
                FROM users ORDER BY created_at DESC
            ''')).fetchall()
            
            return [{
                "user_id": r[0],
                "username": r[1],
                "nickname": r[2],
                "created_at": r[3],
                "last_login": r[4],
                "is_active": bool(r[5])
            } for r in rows]


_auth_instance: Optional[UserAuth] = None

def get_auth() -> UserAuth:
    """获取全局认证实例（单例）"""
    global _auth_instance
    if _auth_instance is None:
        _auth_instance = UserAuth()
    return _auth_instance
