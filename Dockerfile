FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 只安装主流程必需的依赖，保持镜像体积可控（完整依赖见 requirements.txt）
COPY requirements-core.txt ./
RUN pip install --no-cache-dir -r requirements-core.txt

COPY . .

# 运行期数据（报告 / 状态 / 证据）挂载到卷，避免写进镜像层
RUN mkdir -p /app/output /app/data/state /app/data/logs /app/data/patent_evidence
VOLUME ["/app/output", "/app/data"]

EXPOSE 9090

# 常驻运行：每小时一个分析周期，并暴露 Prometheus 指标端点
CMD ["python", "main.py", "--mode", "production", "--continuous", "--interval", "3600", "--metrics-port", "9090"]
