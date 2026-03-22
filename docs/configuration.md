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
| `VALIDATOR_RSSI_THRESHOLD` | ❌ | `-85` | RSSI 門檻 (dBm)，低於此值視為訊號過弱 |
| `VALIDATOR_FROZEN_WINDOW` | ❌ | `600` | RSSI / 溫溼度凍結判定時間窗口 (秒) |
| `VALIDATOR_HISTORY_WINDOW` | ❌ | `1800` | 歷史記錄時間窗口 (秒) |
| `VALIDATOR_TIME_FROZEN_THRESHOLD` | ❌ | `3` | device_time 連續相同幾次即判定凍結 (2-10) |
| `VALIDATOR_MIN_FAILED_CHECKS` | ❌ | `3` | 至少幾項檢查同時失敗才判定為 stale (1-4) |
| `STALE_LOG_PATH` | ❌ | `/app/logs/stale.log` | Stale 事件日誌檔案路徑 |

#### 什麼是「凍結」？

在本系統中，**凍結 = 數值連續多次完全不變**。

正常的感測器即使環境穩定，每次讀數也會有微小浮動（例如溫度 25.8 → 25.9 → 25.8、RSSI -88 → -90 → -87）。如果某個數值連續 N 次完全一樣，代表 H200 Hub 很可能不是回傳即時資料，而是在**重複回傳快取中的舊資料**——這是因為 H200 Hub 的 API 不提供子裝置連線狀態，感測器斷線後 Hub 仍持續回傳最後一筆快取。

凍結 ≠ 數值太低或太高，而是「數值不動了」。

#### 四項檢查說明

驗證器透過四項獨立訊號交叉比對，偵測 T315 是否仍與 Hub 保持有效連線：

| # | 檢查項目 | 判定條件 | 為何可疑 |
|---|----------|----------|----------|
| 1 | **RSSI 弱** | RSSI ≤ 門檻值 | 訊號過弱，封包遺失率高 |
| 2 | **RSSI 凍結** | RSSI 連續 N 次完全相同 | 無線訊號強度在物理上不可能完全靜止 |
| 3 | **溫溼度凍結** | 溫度+溼度連續 N 次完全相同（含小數位） | 真實環境至少會有 ±0.1 的自然波動 |
| 4 | **device_time 凍結** | 裝置時間戳停止遞增 | T315 每次回報應帶遞增的時間，停止代表裝置已離線 |

#### 各檢查的掃描次數差異

RSSI 凍結和溫溼度凍結使用 `VALIDATOR_FROZEN_WINDOW` 計算掃描次數，而 device_time 凍結使用獨立的 `VALIDATOR_TIME_FROZEN_THRESHOLD`。兩者的門檻不同是因為**訊號的確定性不同**：

| 檢查 | 掃描範圍 | 預設次數 | 為何不同 |
|------|----------|----------|----------|
| RSSI 凍結 | `FROZEN_WINDOW / INTERVAL` | 10 次（10 分鐘） | RSSI 短期碰巧相同有可能，需較多樣本排除巧合 |
| 溫溼度凍結 | `FROZEN_WINDOW / INTERVAL` | 10 次（10 分鐘） | 恆溫環境下短期不變是可能的，需較多樣本 |
| device_time 凍結 | `TIME_FROZEN_THRESHOLD` | 3 次（3 分鐘） | 裝置時鐘必定遞增，不動就是確定性的斷線證據 |

**比喻**：溫溼度不變像一個人 10 分鐘沒眨眼（大概有問題）；device_time 不變像心跳停了 3 拍（肯定有問題）。風險越確定的訊號，需要的觀察次數越少。

#### 為何需要多重交叉比對？

雖然 device_time 停止是最強的斷線訊號，但**單一訊號不足以做決策**：

- **device_time 可能本身就是空值**：部分情況下 H200 回傳的 device_time 為空字串，此時「凍結」不代表斷線，只代表韌體沒正確回報時間。
- **Hub 快取可能「部分更新」**：Hub 的快取行為非全有全無——有時 device_time 還在更新但溫溼度已是舊值（Hub 更新了時間戳但沒拿到新的感測資料）；有時 device_time 停了但 RSSI 還在變（RSSI 是 Hub 自己量測的，不依賴 T315 回報）。

因此需要 `MIN_FAILED_CHECKS` 門檻做交叉比對，在「不漏報」和「不誤報」之間取得平衡：

| 情境 | RSSI弱 | RSSI凍結 | 溫溼度凍結 | time凍結 | 失敗數 | 判定 |
|------|--------|----------|-----------|----------|--------|------|
| 真正斷線 | ✗ | ✗ | ✗ | ✗ | 4 | **stale** |
| 韌體時間異常 | ✗ | ✓ | ✓ | ✗ | 2 | valid（僅 2 項失敗） |
| Hub 部分快取 | ✓ | ✗ | ✗ | ✓ | 2 | valid（僅 2 項失敗） |

#### `MIN_FAILED_CHECKS` 各值影響分析

| 值 | 特性 | 適合場景 |
|----|------|----------|
| **2** | 敏感偵測，2 項失敗即判定 stale | 高價值監控、不容許漏報，但誤判率較高 |
| **3**（推薦） | 平衡設定，需多數訊號一致才判定 | 一般用途，兼顧靈敏度與可靠性 |
| **4** | 極保守，4 項全部失敗才觸發 | 幾乎只能抓到「完美斷線」，大量無效資料將被放行 |

設為 4 的風險：只要任何一項碰巧通過就放行資料。例如 RSSI 是 Hub 自己量測的，即使 T315 已斷線，RSSI 仍可能因環境噪訊而微幅跳動，導致 RSSI 凍結檢查通過，使真正的斷線永遠無法被判定為 stale。

#### 驗證器預設值設計考量

**`VALIDATOR_RSSI_THRESHOLD = -85 dBm`**（半開放牧場環境建議值）

T315 使用 Sub-1GHz 無線協定與 H200 通訊。正常連線的 RSSI 通常在 -30 ~ -80 dBm 範圍內。在半開放牧場環境中，距離遠且有金屬圍欄、鐵皮屋頂等遮蔽物，訊號衰減更嚴重。-85 dBm 可以在「訊號已不穩但 Hub 還在吐快取」的階段就提早偵測，而 -85 到 -95 之間屬於「能收到但不可靠」的灰色地帶，放行這段資料風險較高。若感測器與 Hub 距離較短（< 5m 室內環境），可調低至 -95 dBm 以容忍更弱的訊號。

**`VALIDATOR_FROZEN_WINDOW = 600 秒（10 分鐘）`**（半開放牧場環境建議值）

此值決定連續多少次取樣 RSSI/溫溼度不變時視為「凍結」。在預設 `COLLECTION_INTERVAL=60` 秒下，等同於 10 次連續不變才觸發（`600 / 60 = 10`）。半開放牧場有風、日照變化，溫溼度自然波動頻繁，10 分鐘完全不變已極不自然。若環境極度穩定（如恆溫恆濕實驗室或室內冷氣房），建議調高至 900-1800 秒以避免誤判。

**`VALIDATOR_HISTORY_WINDOW = 1800 秒（30 分鐘）`**

定義每裝置保留的歷史快照時間範圍，用於凍結趨勢分析。設為 `FROZEN_WINDOW` 的 3 倍（1800 / 600 = 3x），確保歷史紀錄涵蓋足夠的樣本來判斷凍結模式。過短的歷史窗口可能無法累積足夠數據點，過長則增加記憶體使用。在預設設定下，每裝置最多保留 30 筆快照（`1800 / 60 = 30`），記憶體開銷可忽略。

**`VALIDATOR_TIME_FROZEN_THRESHOLD = 3`**

device_time 連續相同 3 次即判定凍結。device_time 是裝置內部時鐘，只要 T315 還活著就必定遞增，不像溫溼度或 RSSI 有自然巧合的可能性，因此門檻設定較低。在預設 60 秒間隔下，3 次 = 3 分鐘即可偵測。若裝置韌體偶爾會回報重複時間戳，可調高至 5 以降低誤判。

**`VALIDATOR_MIN_FAILED_CHECKS = 3（共 4 項中至少 3 項）`**

交叉驗證的核心參數。每項檢查都可能因合法原因單獨失敗（如 RSSI 在門檻邊緣暫時震盪、恆溫環境下溫度暫時不變），因此要求多項同時失敗才判定為 stale。預設為 3/4，意味著僅在大多數指標都顯示異常時才標記資料不可信，是高可靠性的平衡設定。若需要更敏感的偵測（接受較多誤判），可降至 2。

#### 調校指南：依部署環境調整

| 部署環境 | 建議設定 | 原因 |
|----------|----------|------|
| 半開放牧場（預設） | `RSSI=-85`、`FROZEN_WINDOW=600`、`TIME_FROZEN=3`、`MIN_CHECKS=3` | 戶外波動大，凍結更可疑；距離遠需提早偵測弱訊號 |
| 室內冷氣房 | `RSSI=-95`、`FROZEN_WINDOW=900`、`TIME_FROZEN=3`、`MIN_CHECKS=3` | 恆溫環境短期不變是正常的，需更長觀察窗口 |
| 恆溫恆濕實驗室 | `RSSI=-95`、`FROZEN_WINDOW=1800`、`TIME_FROZEN=5`、`MIN_CHECKS=3` | 環境極穩定，需大幅放寬以避免誤判 |
| 高價值監控（不容漏報） | `RSSI=-80`、`FROZEN_WINDOW=300`、`TIME_FROZEN=2`、`MIN_CHECKS=2` | 偵測靈敏但誤判率較高 |

#### 調校指南：靈敏度與誤判率

| 場景 | 調整方式 | 影響 |
|------|----------|------|
| 誤判太多（有效資料被標記為 stale） | `MIN_FAILED_CHECKS=3`；`FROZEN_WINDOW=900` 以上 | 降低誤判率，但可能漏判真實斷線 |
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
