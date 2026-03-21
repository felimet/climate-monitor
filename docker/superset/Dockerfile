FROM apache/superset:latest

USER root

# Install CrateDB driver, PostgreSQL driver, and dependencies
RUN uv pip install crate sqlalchemy-cratedb==0.40.1 psycopg2-binary

# 複製自訂設定檔
COPY docker/superset/superset_config.py /app/pythonpath/superset_config.py

# 確保 superset_home 目錄權限正確
RUN mkdir -p /app/superset_home && chown -R superset:superset /app/superset_home

USER superset
