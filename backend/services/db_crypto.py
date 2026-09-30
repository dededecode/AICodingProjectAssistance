"""数据库内敏感字段（大模型 API Key）对称加密。

用 Fernet（AES128-CBC + HMAC）加密，密文带 `enc:v1:` 前缀：
- enc()：已带前缀或空值原样返回（幂等，防二次加密）
- dec()：不带前缀（存量明文/环境变量值）原样返回，因此老数据零迁移兼容

主密钥：优先环境变量 PLATFORM_DB_SECRET，否则从 DJANGO_SECRET_KEY 派生。
注意：主密钥变更后旧密文无法解密（dec 会原样返回密文并打 warning），更换前请先保留旧密钥。
"""
import base64
import hashlib
import logging
import os

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

logger = logging.getLogger(__name__)

_PREFIX = "enc:v1:"
_fernet = None


def is_encrypted(value: str) -> bool:
    return bool(value) and str(value).startswith(_PREFIX)


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        secret = os.getenv("PLATFORM_DB_SECRET") or settings.SECRET_KEY
        raw = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
        _fernet = Fernet(raw)
    return _fernet


def enc(value) -> str:
    """加密敏感值；空值/已加密原样返回。"""
    if not value:
        return value or ""
    s = str(value)
    if is_encrypted(s):
        return s
    return _PREFIX + _get_fernet().encrypt(s.encode("utf-8")).decode("ascii")


def dec(value) -> str:
    """解密敏感值；明文（无前缀）原样返回，兼容存量数据与环境变量兜底。"""
    if not value:
        return value or ""
    s = str(value)
    if not is_encrypted(s):
        return s
    try:
        return _get_fernet().decrypt(s[len(_PREFIX):].encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        logger.warning("敏感字段解密失败（主密钥不匹配或数据损坏），原样返回")
        return s
