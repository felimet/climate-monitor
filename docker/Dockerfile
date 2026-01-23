# 階段 1：建構依賴項
FROM python:3.11-slim AS builder

WORKDIR /build

# 安裝 uv 以加速依賴解析
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 複製依賴檔案
COPY pyproject.toml README.md ./
COPY src/ ./src/

# 建構 wheel
RUN uv pip compile pyproject.toml -o requirements.txt && \
    uv pip install --system --target /deps -r requirements.txt && \
    uv pip install --system --target /deps .


# 階段 2：執行環境
FROM python:3.11-slim AS runtime

# 安全性：以非 root 使用者執行
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# 從 builder 複製依賴項
COPY --from=builder /deps /usr/local/lib/python3.11/site-packages/

# 複製應用程式程式碼
COPY --chown=appuser:appuser src/ ./src/

# 設定 Python 路徑
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

USER appuser

# 健康檢查 - 驗證 Python 可以匯入模組
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "from climate_monitor.config import Settings; print('OK')" || exit 1

CMD ["python", "-m", "climate_monitor.main"]
