# 系統架構

本文件說明 Climate Monitor 的系統架構、技術選型與資料流程。

---

## 系統架構圖

```
┌───────────────────────────────────────────────────┐
│                   Tapo H200 Gateway               │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐   │
│  │ T315 #1    │  │ T315 #2    │  │ T315 #3    │   │
│  │ (Sensor)   │  │ (Sensor)   │  │ (Sensor)   │   │
│  └────────────┘  └────────────┘  └────────────┘   │
└──────────────────────┬────────────────────────────┘
                       │ Kasa Protocol (python-kasa)
                       ▼
          ┌───────────────────────────┐
          │  Climate Monitor App      │
          │  (Python Container)       │
          │  - Auto Discovery         │
          │  - Data Collector         │
          │  - Connection Validator   │
          │  - Error Handling         │
          └───────────┬───────────────┘
                      │ HTTP (Port 4200)
                      ▼
          ┌───────────────────────────┐
          │  CrateDB (Time-Series DB) │
          │  - Raw Data Table         │
          │  - Aggregation Views      │
          │  - Admin UI (Port 4500)   │
          └───────────┬───────────────┘
                      │ PostgreSQL Wire Protocol
                      ▼
          ┌───────────────────────────┐
          │  Apache Superset          │
          │  (Visualization Layer)    │
          │  - Dashboards             │
          │  - Charts                 │
          │  - Web UI (Port 8088)     │
          └───────────────────────────┘
                      │
                      ▼
          ┌───────────────────────────┐
          │  Cloudflare Tunnel        │
          │  (Secure Remote Access)   │
          └───────────────────────────┘
```

---

## 技術棧

| 層級 | 技術 | 用途 | 備註 |
|------|------|------|------|
| **資料採集** | Python 3.11 + python-kasa | 與 Tapo 設備通訊 | [python-kasa](https://github.com/python-kasa/python-kasa.git) |
| **專案管理** | uv | 快速依賴管理與虛擬環境 | [uv](https://github.com/astral-sh/uv) |
| **資料儲存** | CrateDB 5.9+ | 分散式時序資料庫 | [CrateDB](https://github.com/crate/crate) |
| **資料視覺化** | Apache Superset 4.1+ | BI 儀表板平台 | [Apache Superset](https://github.com/apache/superset) |
| **元資料儲存** | PostgreSQL 16 | Superset 後端資料庫 | [PostgreSQL](https://github.com/postgres/postgres) |
| **快取層** | Redis 7 | Superset 查詢快取 | [Redis](https://github.com/redis/redis) |
| **容器化** | Docker + Docker Compose | 服務編排與部署 | [Docker](https://docs.docker.com/get-started/) |
| **遠端存取** | Cloudflare Tunnel | Zero Trust 安全通道 | [Cloudflare Tunnel](https://github.com/cloudflare/cloudflared) |

---

## 技術選型說明：為什麼選擇 CrateDB？

CrateDB 並非時序資料庫的第一選擇（如 InfluxDB、TimescaleDB 更為常見），但在本專案中，考量以下因素後為相對較佳的做法：

### 優勢

- **PostgreSQL 相容性**：支援標準 SQL 與 PostgreSQL Wire Protocol，降低 BI 工具整合成本（Apache Superset 原生支援）
- **簡易部署**：單一容器即可運行，無需複雜叢集配置，適合 Synology NAS 等資源受限環境
- **彈性查詢**：支援複雜的 JOIN、Aggregation 與 Materialized Views，適合多維度分析
- **資料規模**：本專案資料量級（每分鐘數筆記錄）尚未達專業時序資料庫的效能優勢閾值

### 何時考慮遷移

若未來需要以下功能，建議評估遷移至 InfluxDB、TimescaleDB 或 ClickHouse：

- 毫秒級高頻寫入
- 百萬級感測器規模
- 更細粒度的資料保留策略 (Retention Policy)
- 原生時序壓縮演算法

---

## 資料模型

### 主資料表：`sensor_readings`

| 欄位 | 型別 | 說明 |
|------|------|------|
| `ts` | `TIMESTAMP WITH TIME ZONE` | 資料採集時間 UTC (ISO 8601) |
| `month_ts` | `TIMESTAMP WITH TIME ZONE` | 月份分區鍵 (自動產生) |
| `device_id` | `TEXT` | 感測器唯一識別碼 |
| `device_name` | `TEXT` | 感測器名稱 |
| `temperature` | `DOUBLE PRECISION` | 溫度 (°C)，驗證失敗時為 NULL |
| `humidity` | `DOUBLE PRECISION` | 相對濕度 (%)，驗證失敗時為 NULL |
| `battery_level` | `INTEGER` | 電池電量 (%) |
| `rssi` | `INTEGER` | 訊號強度 (dBm) |
| `report_interval` | `INTEGER` | 裝置回報間隔 (秒) |
| `device_time` | `TEXT` | 裝置回報時間戳 |
| `is_valid` | `BOOLEAN` | 資料是否通過連線驗證 |
| `stale_reasons` | `TEXT` | 驗證失敗原因 |
| `failed_checks` | `INTEGER` | 失敗的檢查項數 |
| `check_rssi_weak` | `BOOLEAN` | RSSI 低於門檻 |
| `check_rssi_frozen` | `BOOLEAN` | RSSI 連續凍結 |
| `check_temp_frozen` | `BOOLEAN` | 溫溼度連續凍結 |
| `check_time_frozen` | `BOOLEAN` | device_time 停止遞增 |

#### 驗證欄位設計原理

H200 Hub 的 API 不提供子裝置的連線狀態，感測器斷線後 Hub 仍持續回傳最後一筆快取資料。上述驗證欄位的設計理念如下：

- **`is_valid` (BOOLEAN)**：明確標記每筆資料的可信度，讓下游查詢和儀表板可透過 `WHERE is_valid = TRUE` 過濾不可信數據，無需知道驗證邏輯的細節。
- **`temperature`/`humidity` 寫入 NULL**：Stale 資料不保留溫溼度值，確保 `AVG(temperature)` 等聚合函式自動排除不可信數據，避免需要額外的 `WHERE` 條件。選擇 NULL 而非哨兵值（如 -999）是為了符合 SQL 語意慣例。
- **`stale_reasons` (TEXT)**：以分號分隔的失敗檢查描述（如 `"RSSI frozen at -80 dBm for 10 consecutive polls; Temperature (25.3) and humidity (62.1) frozen for 10 consecutive polls"`），供運維人員查詢 `SELECT device_name, stale_reasons FROM sensor_readings WHERE is_valid = FALSE` 快速診斷感測器問題（RF 干擾、電池耗盡、距離過遠等）。
- **四項 check 布林旗標**：各自記錄該筆資料在哪些項目上失敗，便於統計分析（例如：「某感測器 80% 的 stale 事件都是 RSSI 凍結觸發的，代表 RF 環境需要改善」）。
- **`report_interval` 和 `device_time` 保留**：即使資料被判定為 stale，這兩個欄位仍保留原始值，提供驗證邏輯的審計軌跡和除錯依據。

#### 連線驗證機制：多重訊號交叉比對

驗證器透過四項獨立訊號偵測 T315 是否仍與 Hub 保持有效連線。「凍結」指數值連續多次完全不變——正常感測器即使環境穩定也會有微小浮動，完全不動代表 Hub 在重播快取舊資料。

**四項檢查與掃描次數：**

| # | 檢查 | 預設掃描次數 | 設定來源 | 確定性 |
|---|------|-------------|----------|--------|
| 1 | RSSI 弱（絕對門檻） | 每次即判 | `VALIDATOR_RSSI_THRESHOLD` | 中（訊號可能在門檻邊緣震盪） |
| 2 | RSSI 凍結 | 10 次（10 分鐘） | `VALIDATOR_FROZEN_WINDOW / COLLECTION_INTERVAL` | 中（短期碰巧相同有可能） |
| 3 | 溫溼度凍結 | 10 次（10 分鐘） | `VALIDATOR_FROZEN_WINDOW / COLLECTION_INTERVAL` | 中（恆溫環境下短期不變是可能的） |
| 4 | device_time 凍結 | 3 次（3 分鐘） | `VALIDATOR_TIME_FROZEN_THRESHOLD` | 高（裝置時鐘必定遞增，不動即斷線） |

device_time 門檻較低的原因：溫溼度和 RSSI 有自然巧合的可能性，需要較長的觀察窗口排除；device_time 是裝置內部時鐘，只要 T315 還活著就必定遞增，因此 3 次即可確認。

**為何不能只看 device_time？** 因為 device_time 可能本身就是空值（韌體未正確回報），且 Hub 快取可能「部分更新」（時間戳更新但感測資料未更新，或反之）。因此需要多項檢查中至少 3 項同時失敗（`MIN_FAILED_CHECKS=3`）才判定為 stale，在「不漏報」和「不誤報」之間取得平衡。

預設值針對半開放牧場環境調校，詳見 [進階配置 — 連線狀態驗證設定](configuration.md#連線狀態驗證設定)。

### 統計 Views

所有 View 的時間欄位已轉換為 **Asia/Taipei** 時區。

| View 名稱           | 時間欄位                | 描述                | 範例用途        |
|---------------------|-------------------------|---------------------|-----------------|
| `latest_readings`   | `last_seen_asia_taipei` | 每個設備的最新狀態  | 即時儀表板      |
| `minute_metrics`    | `minute_asia_taipei`    | 每分鐘統計          | 高解析度圖表    |
| `hourly_metrics`    | `hour_asia_taipei`      | 每小時統計          | 24 小時趨勢     |
| `daily_stats`       | `day_asia_taipei`       | 每日統計            | 長期歷史回顧    |
| `weekly_stats`      | `week_asia_taipei`      | 每週統計            | 週報表          |
| `monthly_stats`     | `month_asia_taipei`     | 每月統計            | 年度分析        |
| `stale_events`      | `event_time_asia_taipei`| 驗證失敗事件        | 連線品質監控    |

所有聚合 View 都包含 `stale_count` 欄位（使用 `FILTER (WHERE is_valid = FALSE)` 統計），方便在 Superset 中建立資料品質趨勢圖表。`stale_events` View 專門彙整所有驗證失敗記錄，包含失敗原因和各項檢查旗標，是連線品質監控和故障排除的核心查詢來源。

---

## 網路端口規劃

| 端口 | 服務            | 用途                   | 對外開放 |
|------|-----------------|------------------------|----------|
| 4200 | CrateDB (HTTP)  | 資料庫管理介面         | ❌       |
| 4500 | CrateDB (PSQL)  | PostgreSQL 協議        | ❌       |
| 8088 | Superset        | 視覺化儀表板           | ✅       |
| 5432 | PostgreSQL      | Superset 元資料庫      | ❌       |
| 6379 | Redis           | Superset 快取          | ❌       |

---

## 容器資源使用參考

| 服務              | 記憶體限制 | CPU 使用   | 儲存空間 (初期) |
|-------------------|------------|------------|-----------------|
| CrateDB           | 2GB        | 0.5-2 core | 5GB             |
| Superset          | 1GB        | 0.2-0.5 core | 500MB           |
| PostgreSQL        | 512MB      | 0.1-0.2 core | 200MB           |
| Redis             | 512MB      | 0.1 core   | 100MB           |
| Climate Monitor   | 256MB      | 0.1 core   | 50MB            |
| Cloudflare Tunnel | 128MB      | 0.05 core  | 20MB            |
| **總計**          | **~4.5GB** | **~3 core**   | **~6GB**        |
