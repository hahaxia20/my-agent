# ═══════════════════════════════════════
# 构建阶段：安装依赖
# ═══════════════════════════════════════
FROM python:3.12-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ═══════════════════════════════════════
# 运行阶段：生产镜像
# ═══════════════════════════════════════
FROM python:3.12-slim

WORKDIR /app

# 从构建阶段复制已安装的依赖
COPY --from=builder /install /usr/local

# 复制应用代码
COPY src/ src/
COPY static/ static/
COPY index.html login.html ./

EXPOSE 8001

# 生产环境使用 uvicorn（可替换为 gunicorn + uvicorn workers）
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2"]
