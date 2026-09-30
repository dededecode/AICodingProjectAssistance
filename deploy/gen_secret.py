"""生成随机主密钥（用于 docker-compose 的 PLATFORM_DB_SECRET 等环境变量）。

用法：python deploy/gen_secret.py（可重复运行，每次生成新的随机值）
"""
import secrets

print(secrets.token_urlsafe(48))
