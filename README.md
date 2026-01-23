# Climate Monitor

![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)
![CrateDB](https://img.shields.io/badge/database-CrateDB-4bc51d.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

**Climate Monitor** 是一個專為環境設計的溫溼度監控系統。它透過 Python 與 Tapo H200 網關通訊，自動收集 T315 感測器的資料，並將其儲存於高效能的時序資料庫 CrateDB 中。本系統整合 Apache Superset 進行資料視覺化，適合部署於 Synology NAS 或任何 Docker 環境。

## 主要功能

- **自動發現**：啟動後自動搜尋並連接 H200 網關下的所有 T315 感測器。
- **即時監控**：定時（預設 60 秒）收集溫度、濕度、電池電量及訊號強度。
- **高效儲存**：使用 CrateDB 處理時序資料，支援數千萬筆資料的快速查詢。
- **資料視覺化**：內建 Apache Superset，提供專業的儀表板與圖表分析功能。
- **統計視圖**：預建每分鐘、每小時、每日、每週、每月的統計報表。
- **安全存取**：整合 Cloudflare Tunnel，支援免開 Port 的安全遠端存取。

## 快速開始

### 環境需求

- Python 3.11+ (建議使用 [uv](https://github.com/astral-sh/uv) 管理)
- Docker & Docker Compose
- Tapo H200 網關 (Gateway) + T315 感測器 (Sensor)

### 1. 安裝與設定

```bash
# 1. 初始化專案環境
uv sync

# 2. 建立環境變數檔
cp .env.example .env

# 3. 編輯 .env 填入以下資訊：
# - Tapo 帳號資訊 (TAPO_HOST, TAPO_USERNAME, TAPO_PASSWORD)
# - Cloudflare Tunnel Token (選填)
# - Superset 管理員帳號設定 (選填，預設為 admin/admin)
```

### 2. 本地開發 (Windows/Linux)

使用 `docker-compose.pc.yml` 進行本地開發測試：

```bash
cd docker

# 啟動服務 (包含 CrateDB 和 Cloudflare Tunnel)
docker compose -f docker-compose.pc.yml up -d

# 本地執行 Python 程式開發
uv run climate-monitor
```

### 3. 資料庫初始化 (首次執行)

CrateDB 啟動後，請至 Admin UI (`http://localhost:4200`) 執行 `scripts/init_db.sql` 中的 SQL 語句以建立資料表與統計視圖。

## Synology NAS 部署指南

本專案針對 Synology Container Manager 最佳化，支援**自動建構 (Auto-Build)**。

詳細部署步驟請參閱 [NAS_DEPLOYMENT.md](NAS_DEPLOYMENT.md) 文件。

### 部署簡述

1. **準備檔案**：將專案上傳至 NAS。
2. **設定環境**：填寫 `.env` 檔案。
3. **啟動服務**：透過 Docker Compose 啟動所有容器。
4. **初始化 Superset**：執行初始化指令以設定儀表板與資料源。

## 資料查詢與統計

系統透過 CrateDB View 提供不同時間粒度的統計資料，您可以使用 Apache Superset 直接連接這些 View 進行視覺化。

| View名稱 | 描述 | 範例用途 |
|----------|------|----------|
| `latest_readings` | 每個設備的最新狀態 | 即時儀表板 |
| `minute_metrics` | 每分鐘統計 | 高解析度圖表 |
| `hourly_metrics` | 每小時統計 | 24小時趨勢 |
| `daily_stats` | 每日統計 | 長期歷史回顧 |
| `weekly_stats` | 每週統計 | 週報表 |
| `monthly_stats` | 每月統計 | 年度分析 |

### Superset 時區設定技巧 (Calculated Columns)

由於 Superset 預設顯示 UTC 時間，為了正確顯示台北時間 (Asia/Taipei)，建議在 Dataset 中新增 **Calculated Column**，而不僅依賴資料庫 View 的轉換。

**設定方式**：

1. 進入 Edit Dataset -> **Calculated Columns** 分頁。
2. 新增一個欄位（例如命名為 `ts` 或 `ts_taiwan`）。
3. **SQL Expression** 輸入：

   ```sql
   timezone('Asia/Taipei', ts)
   ```

4. 設定 **Data type** 為 `TIMESTAMP` or `DATETIME`，並將 **Datetime format** 設為 `epoch_ms`。
5. 勾選 **Is temporal**。
6. 在製作圖表時，將此欄位選為 Time Column。

> **註**：系統預設的 `datasources.yaml` 已自動為您設定好此計算欄位 (Label: `Time`)。

**查詢範例：查看過去 24 小時的溫度趨勢（台北時間）**

```sql
SELECT 
    hour AT TIME ZONE 'Asia/Taipei' AS hour_taipei,
    device_name,
    avg_temp,
    min_temp,
    max_temp
FROM hourly_metrics 
WHERE hour >= NOW() - INTERVAL '24 hours' 
ORDER BY hour DESC;
```

## 專案結構

```
climate-monitor/
├── src/climate_monitor/
│   ├── core/             # 核心邏輯 (Collector, TapoClient)
│   ├── infra/            # 基礎設施 (CrateDB Client)
│   └── main.py           # 程式入口
├── docker/
│   ├── superset/         # Superset 設定與初始化腳本
│   ├── Dockerfile        # 應用程式建構檔
│   ├── docker-compose.pc.yml   # 本地開發用
│   └── docker-compose.prod.yml # NAS 生產用
├── scripts/              # 資料庫初始化 SQL
└── pyproject.toml        # 專案依賴設定 (uv)
```

## License

MIT
