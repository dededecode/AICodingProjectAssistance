# 后端镜像：Django + gunicorn + 内置本地 embedding 模型
# 构建上下文：AICodingProjectAssistance/ 仓库根目录
#   docker build -f deploy/backend.Dockerfile -t aicodingprojectassistance-backend ..
FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/opt/hf

WORKDIR /app

# 1) 安装依赖（gunicorn 仅用于容器，不写入 requirements.txt，避免影响本地 Windows 开发）。
#    pip 默认走官方 PyPI，国内服务器很慢，加国内镜像源提速；海外可 --build-arg PIP_INDEX_URL=https://pypi.org/simple
#    默认 false = 轻量远程版：用 requirements.noembed.txt（不装 sentence-transformers/torch），
#    embedding 走远程 OpenAI 兼容接口（配合 EMBEDDING_MODE=remote）；
#    置 true 则内置本地模型（离线可用，需下载 torch，镜像大）。
#    注意：docker-compose.yml 的 build.args 默认值也是 false，二者必须保持一致，
#    否则直接 docker build 与 docker compose build 会走不同 pip 分支、缓存互相失效。
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG INSTALL_LOCAL_EMBEDDING=false
COPY backend/requirements*.txt ./
RUN if [ "$INSTALL_LOCAL_EMBEDDING" = "true" ]; then \
        pip install --no-cache-dir -r requirements.txt gunicorn -i ${PIP_INDEX_URL}; \
    else \
        pip install --no-cache-dir -r requirements.noembed.txt gunicorn -i ${PIP_INDEX_URL}; \
    fi

# 2) 本地 embedding：构建时把模型下载进镜像（运行时离线可用）。远程版（false）跳过本步。
#    服务器无法访问 HuggingFace 时用国内镜像；海外可 --build-arg HF_ENDPOINT=https://huggingface.co
ARG HF_ENDPOINT=https://hf-mirror.com
ENV HF_ENDPOINT=${HF_ENDPOINT}
RUN if [ "$INSTALL_LOCAL_EMBEDDING" = "true" ]; then \
        python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-zh-v1.5')"; \
    fi

# 3) 应用代码
COPY backend/ ./

# 4) 初始数据快照（数据库 / 向量库 / 上传文件），由 deploy/prepare_data.ps1 生成
COPY deploy/data_initial/ /app/data_initial/

COPY deploy/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
