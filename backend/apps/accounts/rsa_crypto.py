"""登录参数 RSA 非对称加密：前端用公钥加密 username/password/验证码，后端私钥解密。

密钥对生成后以 PEM 文件落盘（目录可用环境变量 RSA_KEYS_DIR 指定，生产建议指向持久化
数据卷，如 /app/data/keys）；前端每次登录页加载都会重新拉取公钥，密钥轮换不影响使用。
"""
import base64
import json
import os

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from django.conf import settings

KEY_SIZE = 2048
# PKCS#1 v1.5 单次加密最大明文 = 密钥字节数 - 11
_MAX_PLAIN = KEY_SIZE // 8 - 11


def _keys_dir():
    return os.getenv("RSA_KEYS_DIR", str(settings.BASE_DIR / "rsa_keys"))


def _paths():
    d = _keys_dir()
    return d, os.path.join(d, "rsa_private.pem"), os.path.join(d, "rsa_public.pem")


def _load_private_key():
    d, priv_path, pub_path = _paths()
    os.makedirs(d, exist_ok=True)
    if not (os.path.exists(priv_path) and os.path.exists(pub_path)):
        key = rsa.generate_private_key(public_exponent=65537, key_size=KEY_SIZE)
        with open(priv_path, "wb") as f:
            f.write(
                key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.TraditionalOpenSSL,
                    serialization.NoEncryption(),
                )
            )
        with open(pub_path, "wb") as f:
            f.write(
                key.public_key().public_bytes(
                    serialization.Encoding.PEM,
                    serialization.PublicFormat.SubjectPublicKeyInfo,
                )
            )
    with open(priv_path, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def get_public_key_pem():
    """返回 PEM 格式公钥字符串（供前端 JSEncrypt 加密）。"""
    _, _, pub_path = _paths()
    _load_private_key()  # 确保密钥已生成
    with open(pub_path, "rb") as f:
        return f.read().decode()


def decrypt_payload(encrypted_b64):
    """解密密文为 dict：base64(RSA_PKCS1v15(utf8(json)))。失败抛 ValueError。"""
    try:
        raw = base64.b64decode(encrypted_b64)
    except Exception:
        raise ValueError("加密数据无效")
    if not raw:
        raise ValueError("加密数据无效")
    private_key = _load_private_key()
    try:
        plain = private_key.decrypt(raw, padding.PKCS1v15())
    except Exception:
        raise ValueError("加密数据无法解密，请刷新后重试")
    try:
        data = json.loads(plain.decode("utf-8"))
    except Exception:
        raise ValueError("加密数据格式错误")
    if not isinstance(data, dict):
        raise ValueError("加密数据格式错误")
    return data
