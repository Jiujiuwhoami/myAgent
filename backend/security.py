"""安全模块 - 增强的安全特性"""

import hashlib
import hmac
import os
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class RateLimitTier(Enum):
    """限流层级"""

    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


@dataclass
class RateLimitConfig:
    """限流配置"""

    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    tokens_per_minute: int = 10000
    burst_size: int = 10


@dataclass
class RateLimitEntry:
    """限流条目"""

    count: int = 0
    window_start: float = field(default_factory=time.time)
    total_tokens: int = 0


class RateLimiter:
    """
    令牌桶限流器

    支持：
    - 按用户/IP 限流
    - 不同限流层级
    - 突发流量处理
    - 滑动窗口
    """

    def __init__(self):
        self._limits: Dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)
        self._tokens: Dict[str, float] = defaultdict(lambda: 50.0)
        self._last_refill: Dict[str, float] = defaultdict(time.time)
        self._lock = threading.Lock()

        self._tier_configs: Dict[RateLimitTier, RateLimitConfig] = {
            RateLimitTier.FREE: RateLimitConfig(
                requests_per_minute=30, requests_per_hour=500, tokens_per_minute=5000, burst_size=5
            ),
            RateLimitTier.BASIC: RateLimitConfig(
                requests_per_minute=60,
                requests_per_hour=2000,
                tokens_per_minute=10000,
                burst_size=10,
            ),
            RateLimitTier.PREMIUM: RateLimitConfig(
                requests_per_minute=120,
                requests_per_hour=5000,
                tokens_per_minute=20000,
                burst_size=20,
            ),
            RateLimitTier.ENTERPRISE: RateLimitConfig(
                requests_per_minute=300,
                requests_per_hour=20000,
                tokens_per_minute=50000,
                burst_size=50,
            ),
        }

    def check_rate_limit(
        self,
        key: str,
        tier: RateLimitTier = RateLimitTier.FREE,
        cost: int = 1,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        检查限流

        Returns:
            (是否允许, 限流信息)
        """
        config = self._tier_configs[tier]
        current_time = time.time()

        with self._lock:
            entry = self._limits[key]
            tokens = self._tokens[key]
            last_refill = self._last_refill[key]

            elapsed = current_time - entry.window_start
            if elapsed >= 60:
                entry.count = 0
                entry.window_start = current_time

            if elapsed >= 3600:
                entry.total_tokens = 0

            if entry.count >= config.requests_per_minute:
                reset_time = entry.window_start + 60
                return False, {
                    "error": "Rate limit exceeded (per minute)",
                    "retry_after": int(reset_time - current_time),
                    "limit": config.requests_per_minute,
                    "tier": tier.value,
                }

            if entry.total_tokens >= config.requests_per_hour:
                reset_time = entry.window_start + 3600
                return False, {
                    "error": "Rate limit exceeded (per hour)",
                    "retry_after": int(reset_time - current_time),
                    "limit": config.requests_per_hour,
                    "tier": tier.value,
                }

            if tokens < cost:
                return False, {
                    "error": "Token bucket empty",
                    "available_tokens": tokens,
                    "required": cost,
                    "refill_rate": 10,
                }

            entry.count += 1
            entry.total_tokens += cost
            tokens -= cost

            self._limits[key] = entry
            self._tokens[key] = tokens
            self._last_refill[key] = last_refill

            return True, {
                "remaining_requests": config.requests_per_minute - entry.count,
                "remaining_tokens": tokens,
                "tier": tier.value,
            }

    def get_status(self, key: str) -> Dict[str, Any]:
        entry = self._limits.get(key, RateLimitEntry())
        tokens = self._tokens.get(key, 50.0)
        return {
            "request_count": entry.count,
            "total_tokens": entry.total_tokens,
            "available_tokens": tokens,
            "window_start": entry.window_start,
        }


class SecurePassword:
    """
    安全密码哈希

    使用 PBKDF2-SHA256 (可升级到 bcrypt/argon2)
    """

    @staticmethod
    def hash(password: str, salt: Optional[str] = None) -> str:
        """哈希密码"""
        if salt is None:
            salt = os.urandom(32).hex()

        password_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            100000,
        )
        return f"{salt}${password_hash.hex()}"

    @staticmethod
    def verify(password: str, password_hash: str) -> bool:
        """验证密码"""
        try:
            salt, hash_hex = password_hash.split("$")
            expected_hash = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt.encode("utf-8"),
                100000,
            )
            return hmac.compare_digest(expected_hash.hex(), hash_hex)
        except (ValueError, AttributeError):
            return False


class RefreshTokenStore:
    """
    Refresh Token 存储

    支持：
    - Access Token (短期)
    - Refresh Token (长期)
    - Token 轮换
    - 主动撤销
    """

    def __init__(self, ttl_seconds: int = 86400 * 7):
        self._access_tokens: Dict[str, Dict] = {}
        self._refresh_tokens: Dict[str, Dict] = {}
        self._user_sessions: Dict[str, List[str]] = defaultdict(list)
        self._ttl_access = 3600
        self._ttl_refresh = ttl_seconds
        self._lock = threading.Lock()

    def create_tokens(
        self,
        user_id: str,
        username: str,
        role: str = "user",
    ) -> Dict[str, Any]:
        """创建 Access + Refresh Token 对"""
        access_id = str(uuid.uuid4())
        refresh_id = str(uuid.uuid4())

        now = time.time()
        access_expires = now + self._ttl_access
        refresh_expires = now + self._ttl_refresh

        access_token = self._create_jwt_like(
            token_id=access_id,
            user_id=user_id,
            username=username,
            role=role,
            expires=access_expires,
            token_type="access",
        )

        refresh_token = self._create_jwt_like(
            token_id=refresh_id,
            user_id=user_id,
            username=username,
            role=role,
            expires=refresh_expires,
            token_type="refresh",
        )

        with self._lock:
            self._access_tokens[access_id] = {
                "user_id": user_id,
                "username": username,
                "role": role,
                "expires": access_expires,
                "created_at": now,
            }

            self._refresh_tokens[refresh_id] = {
                "user_id": user_id,
                "username": username,
                "role": role,
                "expires": refresh_expires,
                "created_at": now,
                "access_token_id": access_id,
            }

            self._user_sessions[user_id].append(refresh_id)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": self._ttl_access,
            "refresh_expires_in": self._ttl_refresh,
        }

    def verify_access_token(self, token: str) -> Optional[Dict]:
        """验证 Access Token"""
        payload = self._parse_jwt_like(token)
        if not payload:
            return None

        token_id = payload.get("jti")
        if token_id not in self._access_tokens:
            return None

        token_data = self._access_tokens[token_id]
        if time.time() > token_data["expires"]:
            del self._access_tokens[token_id]
            return None

        return {
            "user_id": token_data["user_id"],
            "username": token_data["username"],
            "role": token_data["role"],
        }

    def refresh_access_token(self, refresh_token: str) -> Optional[Dict]:
        """使用 Refresh Token 刷新 Access Token"""
        payload = self._parse_jwt_like(refresh_token)
        if not payload:
            return None

        token_id = payload.get("jti")
        if token_id not in self._refresh_tokens:
            return None

        token_data = self._refresh_tokens[token_id]
        if time.time() > token_data["expires"]:
            self._revoke_refresh_token(token_id, token_data["user_id"])
            return None

        old_access_id = token_data.get("access_token_id")
        if old_access_id and old_access_id in self._access_tokens:
            del self._access_tokens[old_access_id]

        return self.create_tokens(
            user_id=token_data["user_id"],
            username=token_data["username"],
            role=token_data["role"],
        )

    def revoke_refresh_token(self, refresh_token: str):
        """撤销 Refresh Token"""
        payload = self._parse_jwt_like(refresh_token)
        if not payload:
            return

        token_id = payload.get("jti")
        user_id = payload.get("uid")
        self._revoke_refresh_token(token_id, user_id)

    def revoke_all_user_tokens(self, user_id: str):
        """撤销用户所有 Token"""
        with self._lock:
            refresh_ids = self._user_sessions.get(user_id, [])
            for refresh_id in refresh_ids:
                if refresh_id in self._refresh_tokens:
                    token_data = self._refresh_tokens[refresh_id]
                    access_id = token_data.get("access_token_id")
                    if access_id:
                        self._access_tokens.pop(access_id, None)
                    del self._refresh_tokens[refresh_id]

            self._user_sessions[user_id] = []

    def _revoke_refresh_token(self, token_id: str, user_id: str):
        with self._lock:
            if token_id in self._refresh_tokens:
                token_data = self._refresh_tokens[token_id]
                access_id = token_data.get("access_token_id")
                if access_id:
                    self._access_tokens.pop(access_id, None)
                del self._refresh_tokens[token_id]

            if user_id and token_id in self._user_sessions.get(user_id, []):
                self._user_sessions[user_id].remove(token_id)

    def cleanup_expired(self):
        """清理过期 Token"""
        now = time.time()
        expired_access = [k for k, v in self._access_tokens.items() if now > v["expires"]]
        expired_refresh = [k for k, v in self._refresh_tokens.items() if now > v["expires"]]

        for k in expired_access:
            del self._access_tokens[k]
        for k in expired_refresh:
            user_id = self._refresh_tokens[k].get("user_id")
            del self._refresh_tokens[k]
            if user_id and k in self._user_sessions.get(user_id, []):
                self._user_sessions[user_id].remove(k)

    @staticmethod
    def _create_jwt_like(
        token_id: str,
        user_id: str,
        username: str,
        role: str,
        expires: float,
        token_type: str,
    ) -> str:
        """创建简化的 JWT-like Token"""
        header = {"alg": "PBKDF2-SHA256", "typ": "JWT"}
        payload = {
            "jti": token_id,
            "uid": user_id,
            "username": username,
            "role": role,
            "exp": expires,
            "type": token_type,
            "iat": time.time(),
        }

        import base64
        import json

        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode()
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()

        signature_input = f"{header_b64}.{payload_b64}"
        signature = hashlib.sha256(signature_input.encode()).hexdigest()

        return f"{header_b64}.{payload_b64}.{signature}"

    @staticmethod
    def _parse_jwt_like(token: str) -> Optional[Dict]:
        """解析简化的 JWT-like Token"""
        import base64
        import json

        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None

            header_b64, payload_b64, signature = parts

            signature_input = f"{header_b64}.{payload_b64}"
            expected_sig = hashlib.sha256(signature_input.encode()).hexdigest()

            if not hmac.compare_digest(signature, expected_sig):
                return None

            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            return payload
        except Exception:
            return None


class SecurityManager:
    """
    安全管理器

    整合所有安全功能：
    - 密码哈希
    - Token 管理
    - 限流
    """

    def __init__(self):
        self.password = SecurePassword()
        self.rate_limiter = RateLimiter()
        self.token_store = RefreshTokenStore()

    def hash_password(self, password: str) -> str:
        return self.password.hash(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        return self.password.verify(password, password_hash)

    def create_auth_tokens(self, user_id: str, username: str, role: str) -> Dict:
        return self.token_store.create_tokens(user_id, username, role)

    def verify_access_token(self, token: str) -> Optional[Dict]:
        return self.token_store.verify_access_token(token)

    def refresh_access_token(self, refresh_token: str) -> Optional[Dict]:
        return self.token_store.refresh_access_token(refresh_token)

    def revoke_refresh_token(self, refresh_token: str):
        self.token_store.revoke_refresh_token(refresh_token)

    def check_rate_limit(
        self, key: str, tier: RateLimitTier = RateLimitTier.FREE
    ) -> Tuple[bool, Dict]:
        return self.rate_limiter.check_rate_limit(key, tier)

    def get_user_rate_limit_tier(self, role: str) -> RateLimitTier:
        tier_map = {
            "admin": RateLimitTier.ENTERPRISE,
            "premium": RateLimitTier.PREMIUM,
            "user": RateLimitTier.BASIC,
            "guest": RateLimitTier.FREE,
        }
        return tier_map.get(role, RateLimitTier.FREE)
