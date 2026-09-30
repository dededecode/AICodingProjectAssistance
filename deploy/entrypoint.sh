#!/bin/sh
# 后端容器入口：准备数据 -> 修正嵌入模型 -> 迁移/静态文件 -> 启动 gunicorn
set -e
cd /app

echo "[entrypoint] 准备数据目录..."
mkdir -p /app/data
for item in db.sqlite3 chroma media; do
    if [ ! -e "/app/data/$item" ] && [ -e "/app/data_initial/$item" ]; then
        echo "[entrypoint] 拷贝初始数据 $item -> /app/data/$item"
        cp -a "/app/data_initial/$item" "/app/data/$item"
    fi
done

# 修正嵌入模型：库里若是旧版 Windows 绝对路径（如 <模型目录>/...），重置为镜像内置模型名
if [ -f /app/data/db.sqlite3 ]; then
    echo "[entrypoint] 检查嵌入模型配置..."
    python - <<'PY'
import sqlite3
con = sqlite3.connect("/app/data/db.sqlite3")
try:
    row = con.execute("select embedding_model from ai_config_aiconfig where id=1").fetchone()
    if row:
        v = (row[0] or "").strip()
        # 只修正“看起来是路径”的值，避免误改用户后续自定义的模型名
        if v and v != "BAAI/bge-small-zh-v1.5" and ("\\" in v or ":" in v or v.startswith("/")):
            con.execute("update ai_config_aiconfig set embedding_model='BAAI/bge-small-zh-v1.5' where id=1")
            con.commit()
            print("[entrypoint] 已重置 embedding_model -> BAAI/bge-small-zh-v1.5")
finally:
    con.close()
PY
fi

echo "[entrypoint] 迁移与静态文件..."
python manage.py migrate --noinput
python manage.py collectstatic --noinput

echo "[entrypoint] 启动 gunicorn..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-3}" \
    --timeout "${GUNICORN_TIMEOUT:-600}" \
    --access-logfile - --error-logfile -
