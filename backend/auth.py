# -*- coding: utf-8 -*-
"""
简单Token认证系统
"""
import os
import hashlib
import secrets
import bcrypt
from datetime import datetime, timedelta
from typing import Optional
import logging
from pydantic import BaseModel

from config.config import get_config

logger = logging.getLogger(__name__)

# 配置文件路径（使用绝对路径）
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
AUTH_CONFIG_FILE = os.path.join(BACKEND_DIR, "config", "auth.json")

# 默认管理员账号（从 config.yaml 读取）
_cfg = get_config()
DEFAULT_USERNAME = _cfg.AUTH_USERNAME
DEFAULT_PASSWORD_HASH = _cfg.AUTH_PASSWORD_HASH

# Token有效期（小时）
TOKEN_EXPIRE_HOURS = 24


class UserInfo(BaseModel):
    """用户信息"""
    password_hash: str
    display_name: str = "用户"


class TokenInfo(BaseModel):
    """Token信息"""
    user_id: str
    expires_at: str


class AuthConfig(BaseModel):
    """认证配置"""
    users: dict[str, UserInfo] = {}
    tokens: dict[str, TokenInfo] = {}  # token -> TokenInfo


class LoginRequest(BaseModel):
    """登录请求"""
    username: str
    password: str


class LoginResponse(BaseModel):
    """登录响应"""
    success: bool
    token: Optional[str] = None
    user_id: Optional[str] = None
    display_name: Optional[str] = None
    message: str


def hash_password(password: str) -> str:
    """使用 bcrypt 密码哈希"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def load_auth_config() -> AuthConfig:
    """加载认证配置"""
    config_dir = os.path.dirname(AUTH_CONFIG_FILE)
    if config_dir and not os.path.exists(config_dir):
        os.makedirs(config_dir)
    
    if os.path.exists(AUTH_CONFIG_FILE):
        import json
        with open(AUTH_CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 检查是否需要从旧格式迁移（单用户 -> 多用户）
        if "username" in data and "password_hash" in data:
            config = AuthConfig(
                users={
                    data["username"]: UserInfo(
                        password_hash=data["password_hash"],
                        display_name=data["username"]
                    )
                }
            )
            # 如果旧格式有 tokens，也迁移
            if "tokens" in data:
                for token, expiry_str in data["tokens"].items():
                    config.tokens[token] = TokenInfo(user_id=data["username"], expires_at=expiry_str)
            save_auth_config(config)
            logger.info(f"[Auth] 已从旧格式迁移: {data['username']}")
            return config
        
        return AuthConfig(**data)
    else:
        # 创建默认配置（使用 config.yaml 中的哈希）
        if not DEFAULT_PASSWORD_HASH:
            raise RuntimeError(
                "请在 config.yaml 中设置 AUTH_PASSWORD_HASH "
                "（使用 'python -c \"import hashlib; print(hashlib.sha256(b\\\"your_password\\\").hexdigest())\"' 生成）"
            )
        config = AuthConfig(
            users={
                DEFAULT_USERNAME: UserInfo(
                    password_hash=DEFAULT_PASSWORD_HASH,
                    display_name=DEFAULT_USERNAME
                )
            }
        )
        save_auth_config(config)
        logger.info(f"[Auth] 创建默认账号: {DEFAULT_USERNAME}")
        logger.info("[Auth] 请修改默认密码!")
        return config


def save_auth_config(config: AuthConfig):
    """保存认证配置"""
    import json
    config_dir = os.path.dirname(AUTH_CONFIG_FILE)
    if config_dir and not os.path.exists(config_dir):
        os.makedirs(config_dir)
    
    with open(AUTH_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config.model_dump(), f, indent=2, ensure_ascii=False)


# 全局配置实例
_auth_config: Optional[AuthConfig] = None


def get_auth_config() -> AuthConfig:
    """获取认证配置"""
    global _auth_config
    if _auth_config is None:
        _auth_config = load_auth_config()
    return _auth_config


def _check_password(plain_password: str, hashed_password: str) -> bool:
    """检查密码是否匹配哈希（支持 bcrypt 和旧版 SHA256）"""
    if hashed_password.startswith('$2b$') or hashed_password.startswith('$2a$'):
        try:
            return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
        except Exception:
            return False
    # 旧版 SHA256（向后兼容）
    return hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password


def verify_password(username: str, password: str) -> tuple[bool, Optional[str]]:
    """验证密码，返回 (是否成功, user_id)"""
    config = get_auth_config()
    if username in config.users:
        if _check_password(password, config.users[username].password_hash):
            return True, username
    return False, None


def generate_token() -> str:
    """生成Token"""
    return secrets.token_urlsafe(32)


def create_token(username: str) -> str:
    """创建登录Token，关联 user_id"""
    config = get_auth_config()
    token = generate_token()
    expiry = datetime.now() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    config.tokens[token] = TokenInfo(user_id=username, expires_at=expiry.isoformat())
    
    # 清理过期token
    clean_expired_tokens(config)
    
    save_auth_config(config)
    return token


def verify_token(token: str) -> tuple[bool, Optional[str]]:
    """验证Token，返回 (是否有效, user_id)"""
    if not token:
        return False, None
    
    config = get_auth_config()
    if token not in config.tokens:
        return False, None
    
    # 检查是否过期
    token_info = config.tokens[token]
    try:
        expiry = datetime.fromisoformat(token_info.expires_at)
        if datetime.now() > expiry:
            # Token已过期
            del config.tokens[token]
            save_auth_config(config)
            return False, None
        return True, token_info.user_id
    except:
        return False, None


def clean_expired_tokens(config: AuthConfig):
    """清理过期Token"""
    now = datetime.now()
    expired = []
    for token, token_info in config.tokens.items():
        try:
            expiry = datetime.fromisoformat(token_info.expires_at)
            if now > expiry:
                expired.append(token)
        except:
            expired.append(token)
    
    for token in expired:
        del config.tokens[token]


def logout(token: str):
    """登出"""
    config = get_auth_config()
    if token in config.tokens:
        del config.tokens[token]
        save_auth_config(config)


def change_password(user_id: str, old_password: str, new_password: str) -> tuple[bool, str]:
    """修改密码"""
    config = get_auth_config()
    
    if user_id not in config.users:
        return False, "用户不存在"
    
    if not _check_password(old_password, config.users[user_id].password_hash):
        return False, "原密码错误"
    
    if len(new_password) < 6:
        return False, "新密码至少6位"
    
    config.users[user_id].password_hash = hash_password(new_password)
    # 清除所有token，强制重新登录
    config.tokens = {}
    save_auth_config(config)
    
    return True, "密码修改成功，请重新登录"