# 前端镜像：构建 Vue3 产物 + nginx 托管/反代
# 构建上下文：AICodingProjectAssistance/ 仓库根目录
#   docker build -f deploy/frontend.Dockerfile -t aicodingprojectassistance-frontend ..
FROM node:18-alpine AS fe
WORKDIR /fe
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM nginx:1.25-alpine
COPY --from=fe /fe/dist /usr/share/nginx/html
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
