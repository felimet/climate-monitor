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

### 連線狀態驗證設定

| 變數 | 必填 | 預設值 | 說明 |
|------|------|--------|------|
| `VALIDATOR_RSSI_THRESHOLD` | ❌ | `-75` | RSSI 門檻 (dBm)，低於此值視為訊號過弱 |
| `VALIDATOR_FROZEN_WINDOW` | ❌ | `300` | 凍結判定時間窗口 (秒) |
| `VALIDATOR_HISTORY_WINDOW` | ❌ | `1200` | 歷史記錄時間窗口 (秒) |
| `VALIDATOR_MIN_FAILED_CHECKS` | ❌ | `2` | 至少幾項檢查同時失敗才判定為 stale (1-4) |
| `STALE_LOG_PATH` | ❌ | `/app/logs/stale.log` | Stale 事件日誌檔案路徑 |

#### 驗證器預設值設計考量

**`VALIDATOR_RSSI_THRESHOLD = -95 dBm`**

T315 使用 Sub-1GHz 無線協定與 H200 通訊。在一般室內環境中，正常連線的 RSSI 通常在 -30 ~ -80 dBm 範圍內。低於 -95 dBm 時訊號已極度微弱，封包遺失率大幅上升。此門檻設定為較寬鬆的值，避免在中等距離的合法連線中產生誤判；若感測器與 Hub 距離較短（< 5m），可調高至 -70 dBm 以提早偵測異常。

**`VALIDATOR_FROZEN_WINDOW = 900 秒（15 分鐘）`**

此值決定連續多少次取樣 RSSI/溫溼度不變時視為「凍結」。在預設 `COLLECTION_INTERVAL=60` 秒下，等同於 15 次連續不變才觸發（`900 / 60 = 15`）。選擇 15 分鐘是因為短期環境穩定（如夜間空調恆溫）可能導致溫溼度暫時不變，但超過 15 分鐘完全不變（含 RSSI 小數位 jitter）在物理上極不可能。若環境極度穩定（如恆溫恆濕實驗室），建議調高至 1800 秒以避免誤判。

**`VALIDATOR_HISTORY_WINDOW = 1800 秒（30 分鐘）`**

定義每裝置保留的歷史快照時間範圍，用於凍結趨勢分析。設為 `FROZEN_WINDOW` 的 2 倍（1800 / 900 = 2x），確保歷史紀錄涵蓋足夠的樣本來判斷凍結模式。過短的歷史窗口可能無法累積足夠數據點，過長則增加記憶體使用。在預設設定下，每裝置最多保留 30 筆快照（`1800 / 60 = 30`），記憶體開銷可忽略。

**`VALIDATOR_MIN_FAILED_CHECKS = 3（共 4 項中至少 3 項）`**

交叉驗證的核心參數。每項檢查都可能因合法原因單獨失敗（如 RSSI 在門檻邊緣暫時震盪、恆溫環境下溫度暫時不變），因此要求多項同時失敗才判定為 stale。預設為 3/4，意味著僅在大多數指標都顯示異常時才標記資料不可信，是高可靠性的保守設定。若需要更敏感的偵測（接受較多誤判），可降至 2。

#### 調校指南：靈敏度與誤判率

| 場景 | 調整方式 | 影響 |
|------|----------|------|
| 誤判太多（有效資料被標記為 stale） | `MIN_FAILED_CHECKS=3` 或 `4`；`FROZEN_WINDOW=1800` | 降低誤判率，但可能漏判真實斷線 |
| 遺漏真實斷線 | `MIN_FAILED_CHECKS=2`；`FROZEN_WINDOW=300` | 提高偵測靈敏度，但誤判率上升 |
| RF 環境嘈雜（多干擾源） | `FROZEN_WINDOW=1800`；`HISTORY_WINDOW=3600` | 需要更長時間的凍結才觸發，容忍暫態干擾 |
| 高採樣率（`INTERVAL=10s`） | `FROZEN_WINDOW=300`（= 30 次）；注意 CPU 負荷 | 保持合理的凍結判定次數 |

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

修改 `.env` 中的 `LOG_LEVEL`：

```env
LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR
```

### Stale 事件日誌

驗證失敗事件會寫入獨立檔案（預設 `/app/logs/stale.log`），Docker 掛載於 `./data/monitor_logs/`。

```bash
# 查看 stale 日誌
cat docker/data/monitor_logs/stale.log
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
