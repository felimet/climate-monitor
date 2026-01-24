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
| `temperature` | `DOUBLE PRECISION` | 溫度 (°C) |
| `humidity` | `DOUBLE PRECISION` | 相對濕度 (%) |
| `battery_level` | `INTEGER` | 電池電量 (%) |
| `rssi` | `INTEGER` | Wi-Fi 訊號強度 (dBm) |

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
