# 進階配置

本文件說明 Climate Monitor 的進階配置選項與效能調校參數。

---

## 目錄

- [環境變數參考](#環境變數參考)
- [效能調校](#效能調校)
- [CrateDB 配置](#cratedb-配置)
- [Superset 配置](#superset-配置)

---

## 環境變數參考

### Tapo H200 設定

| 變數 | 必填 | 預設值 | 說明 |
|------|------|--------|------|
| `TAPO_HOST` | ✅ | - | H200 網關 IP 位址 |
| `TAPO_USERNAME` | ✅ | - | Tapo App 帳號 |
| `TAPO_PASSWORD` | ✅ | - | Tapo App 密碼 |

### 資料採集設定

| 變數 | 必填 | 預設值 | 說明 |
|------|------|--------|------|
| `COLLECTION_INTERVAL` | ❌ | `60` | 資料收集間隔（秒） |

### CrateDB 設定

| 變數 | 必填 | 預設值 | 說明 |
|------|------|--------|------|
| `CRATEDB_HOST` | ❌ | `cratedb` | CrateDB 主機名稱 |
| `CRATEDB_PORT` | ❌ | `4200` | CrateDB HTTP 端口 |

### Superset 設定

| 變數 | 必填 | 預設值 | 說明 |
|------|------|--------|------|
| `SUPERSET_SECRET_KEY` | ✅ | - | 加密金鑰（`openssl rand -base64 42`） |
| `SUPERSET_ADMIN_USERNAME` | ✅ | - | 管理員帳號 |
| `SUPERSET_ADMIN_PASSWORD` | ✅ | - | 管理員密碼 |
| `SUPERSET_ADMIN_EMAIL` | ✅ | - | 管理員 Email |
| `SUPERSET_POSTGRES_PASSWORD` | ✅ | - | PostgreSQL 資料庫密碼 |

### Cloudflare Tunnel 設定

| 變數 | 必填 | 預設值 | 說明 |
|------|------|--------|------|
| `TUNNEL_TOKEN` | ❌ | - | Cloudflare Tunnel Token |

---

## 效能調校

### 調整資料收集頻率

修改 `.env` 中的 `COLLECTION_INTERVAL`：

```env
# 預設 60 秒，可根據需求調整
COLLECTION_INTERVAL=30   # 增加採樣頻率（更高解析度）
COLLECTION_INTERVAL=300  # 降低採樣頻率（節省資源）
```

**權衡考量**：

| 間隔 | 優點 | 缺點 |
|------|------|------|
| 30 秒 | 更細緻的資料趨勢 | 資料量增加、儲存成本提高 |
| 60 秒 | 平衡點 | - |
| 300 秒 | 節省儲存空間與 CPU | 可能錯過短期變化 |

---

## CrateDB 配置

### 記憶體最佳化

在 `docker-compose.yml` 中調整 Java Heap Size：

```yaml
services:
  cratedb:
    environment:
      - CRATE_HEAP_SIZE=4g  # 預設 2g
```

**建議**：設定為實體記憶體的 1/4 到 1/2，但不超過 32GB。

### Shard 上限設定

在單節點環境中，可能需要提高 shard 上限：

```bash
curl -s -X POST "http://localhost:4500/_sql" \
  -H "Content-Type: application/json" \
  -d '{"stmt":"SET GLOBAL PERSISTENT cluster.max_shards_per_node = 3000"}'
```

### 查詢快取

CrateDB 預設啟用查詢快取。若需要調整，可設定：

```sql
SET GLOBAL PERSISTENT indices.queries.cache.size = '10%';
```

---

## Superset 配置

### 查詢快取設定

Superset 使用 Redis 進行查詢快取。可在 `docker/superset/datasources.yaml` 中調整 TTL：

```yaml
databases:
  - database_name: Climate CrateDB
    cache_timeout: 3600  # 快取保留時間（秒）
```

### 效能相關設定

編輯 `docker/superset/superset_config.py`（若存在）：

```python
# 查詢逾時設定
SUPERSET_WEBSERVER_TIMEOUT = 120

# 並行查詢數
SUPERSET_MAX_CONCURRENT_QUERIES = 10

# 結果列數上限
ROW_LIMIT = 10000
```

### SSD 快取 (Synology NAS)

若 NAS 配有 SSD，建議啟用讀寫快取：

1. DSM 控制台 → 儲存空間管理員 → SSD 快取
2. 為 `/volume1/docker/` 啟用讀寫快取

---

## Docker 資源限制

在 `docker-compose.yml` 中可設定容器資源上限：

```yaml
services:
  cratedb:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '0.5'
          memory: 1G
```

**各服務建議配置**：

| 服務 | 記憶體上限 | CPU 上限 |
|------|------------|----------|
| CrateDB | 2-4GB | 2.0 |
| Superset | 1-2GB | 1.0 |
| PostgreSQL | 512MB | 0.5 |
| Redis | 512MB | 0.2 |
| Climate Monitor | 256MB | 0.2 |

---

## 日誌等級調整

### Climate Monitor

修改 `src/climate_monitor/main.py` 中的日誌等級：

```python
import logging
logging.basicConfig(level=logging.DEBUG)  # DEBUG, INFO, WARNING, ERROR
```

### Docker Compose 日誌

```yaml
services:
  climate-monitor:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

---

## 下一步

- [Superset 設定與時區技巧](superset-setup.md)
- [安全性建議](security.md)
- [備份與還原](backup-restore.md)
