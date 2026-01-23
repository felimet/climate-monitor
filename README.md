# Climate Monitor

![Python Version](https://img.shields.io/badge/python-3.11-blue.svg)
![CrateDB](https://img.shields.io/badge/database-CrateDB-4bc51d.svg)
![Apache Superset](https://img.shields.io/badge/BI-Apache%20Superset-20A6C9.svg)
![Docker](https://img.shields.io/badge/container-Docker-2496ED.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

**Climate Monitor** 是一個生產級的溫溼度監控系統，專為長期穩定運行設計。透過 Python 與 Tapo H200 網關通訊，自動蒐集 T315 感測器資料，並儲存於高效能時序資料庫 CrateDB 中。整合 Apache Superset 提供專業級資料視覺化，適合部署於 Synology NAS 或任何 Docker 環境。

---

## 目錄

- [主要功能](#主要功能)
- [系統架構](#系統架構)
- [快速開始](#快速開始)
- [Synology NAS 部署](#synology-nas-部署指南)
- [資料查詢與統計](#資料查詢與統計)
- [服務訪問](#服務訪問)
- [故障排除](#故障排除)
- [專案結構](#專案結構)
- [進階配置](#進階配置)

---

## 主要功能

- **自動發現**：啟動後自動搜尋並連接 H200 網關下的所有 T315 感測器
- **即時監控**：定時（預設 60 秒）蒐集溫度、濕度、電池電量及訊號強度
- **高效儲存**：使用 CrateDB 處理時序資料，支援數千萬筆資料的快速查詢與聚合
- **資料視覺化**：內建 Apache Superset，提供專業的儀表板與圖表分析功能
- **統計視圖**：預建每分鐘、每小時、每日、每週、每月的統計報表 (Materialized Views)
- **安全存取**：整合 Cloudflare Tunnel，支援免開 Port 的安全遠端存取
- **容錯機制**：自動重連、錯誤重試、完整日誌記錄

---

## 系統架構

```
┌─────────────────────────────────────────────────────────────┐
│                   Tapo H200 Gateway                         │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐             │
│  │ T315 #1    │  │ T315 #2    │  │ T315 #3    │             │
│  │ (Sensor)   │  │ (Sensor)   │  │ (Sensor)   │             │
│  └────────────┘  └────────────┘  └────────────┘             │
└──────────────────────┬──────────────────────────────────────┘
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

### 技術棧

| 層級 | 技術 | 用途 | 備註 |
|------|------|------|------|
| **資料採集** | Python 3.11 + python-kasa | 與 Tapo 設備通訊 | [python-kasa](https://github.com/python-kasa/python-kasa.git) |
| **專案管理** | uv | 快速依賴管理與虛擬環境 | [uv](https://github.com/astral-sh/uv) |
| **資料儲存** | CrateDB 5.9+ | 分散式時序資料庫 | [CrateDB](https://github.com/crate/crate) |
| **資料視覺化** | Apache Superset 4.1+ | BI 儀表板平台 | [Apache Superset](https://github.com/apache/superset) |
| **元資料儲存** | PostgreSQL 16 | Superset 後端資料庫 | [PostgreSQL](https://github.com/postgres/postgres) |
| **快取層** | Redis 7 | Superset 查詢快取 | [Redis](https://github.com/redis/redis) |
| **容器化** | Docker + Docker Compose | 服務編排與部署 | [Docker](https://docs.docker.com/get-started/) + [Docker Compose](https://github.com/docker/compose) |
| **遠端存取** | Cloudflare Tunnel | Zero Trust 安全通道 | [Cloudflare Tunnel](https://github.com/cloudflare/cloudflared) |

> **技術選型說明**：CrateDB 並非時序資料庫的第一選擇（如 InfluxDB、TimescaleDB 更為常見），但在本專案中，考量以下因素後為相對較佳的做法：
>
> - **PostgreSQL 相容性**：支援標準 SQL 與 PostgreSQL Wire Protocol，降低 BI 工具整合成本（Apache Superset 原生支援）
> - **簡易部署**：單一容器即可運行，無需複雜叢集配置，適合 Synology NAS 等資源受限環境
> - **彈性查詢**：支援複雜的 JOIN、Aggregation 與 Materialized Views，適合多維度分析
> - **資料規模**：本專案資料量級（每分鐘數筆記錄）尚未達專業時序資料庫的效能優勢閾值
>
> 若未來需要毫秒級寫入或百萬級感測器，建議評估遷移至 InfluxDB 或 TimescaleDB 或 ClickHouse。

---

## 快速開始

### 環境需求

- **硬體**：Tapo H200 網關 + T315 感測器（一個或多個）

- **軟體**：Docker 20.10+ & Docker Compose 2.0+
- **開發工具**（選用）：Python 3.11+, [uv](https://github.com/astral-sh/uv)
- **網路**：NAS/開發機與 Tapo 設備需在同一區域網路

### 部署方式選擇

| 方式 | 適用情境 | Docker Compose 檔案 |
|------|----------|---------------------|
| **生產部署** | Synology NAS 或伺服器 | `docker/docker-compose.prod.yml` |
| **本地開發** | Windows/Linux 開發機 | `docker/docker-compose.pc.yml` |

---

### 方式 A：生產部署 (推薦給 NAS 使用者)

**詳細步驟請參閱 [NAS_DEPLOYMENT.md](NAS_DEPLOYMENT.md)**

快速版本：

```bash
# 1. 準備環境變數
cp .env.example .env
# 編輯 .env 填入 Tapo 帳號、IP 等資訊

# 2. 切換到 docker 目錄
cd docker

# 3. 啟動所有服務 (自動建構)
docker compose -f docker-compose.prod.yml up -d --build

# 4. 初始化 Superset
docker compose -f docker-compose.prod.yml up superset-init

# 5. 初始化 CrateDB
# 開啟瀏覽器: http://your-nas-ip:4500
# 執行 scripts/init_db.sql 中的 SQL 語句
```

---

### 方式 B：本地開發

此方式適合修改程式碼與測試新功能。

```bash
# 1. 安裝 uv (若未安裝)
# Windows: powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
# Linux/macOS: curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 初始化 Python 環境
uv sync

# 3. 設定環境變數
cp .env.example .env
# 編輯 .env，特別注意 TAPO_HOST 需填入實際 IP

# 4. 啟動 Docker 服務 (CrateDB, Superset, Cloudflare Tunnel)
cd docker
docker compose -f docker-compose.pc.yml up -d

# 5. 初始化 Superset (首次執行)
docker compose -f docker-compose.pc.yml up superset-init

# 6. 初始化 CrateDB (首次執行)
# 開啟: http://localhost:4200
# 在 Console 執行 scripts/init_db.sql

# 7. 本機執行 Python 應用程式
cd ..
uv run climate-monitor
```

---

## Synology NAS 部署指南

本專案針對 Synology Container Manager 最佳化，支援**自動建構 (Auto-Build)**。

📖 **完整部署流程請參閱：[NAS_DEPLOYMENT.md](NAS_DEPLOYMENT.md)**

### 部署簡述

1. **準備檔案**：將專案上傳至 NAS（建議路徑：`/volume1/docker/climate-monitor/`）
2. **設定環境**：填寫 `.env` 檔案（Tapo 帳號、資料庫密碼等）
3. **啟動服務**：透過 Docker Compose 啟動所有容器
4. **初始化**：執行 Superset 初始化與 CrateDB schema 建立
5. **驗證**：確認各服務運行正常並能蒐集資料


## 資料查詢與統計

系統透過 CrateDB View 提供不同時間粒度的統計資料，您可以使用 Apache Superset 直接連接這些 View 進行視覺化。

| View 名稱           | 描述                | 範例用途        |
|---------------------|---------------------|-----------------|
| `latest_readings`   | 每個設備的最新狀態  | 即時儀表板      |
| `minute_metrics`    | 每分鐘統計          | 高解析度圖表    |
| `hourly_metrics`    | 每小時統計          | 24 小時趨勢     |
| `daily_stats`       | 每日統計            | 長期歷史回顧    |
| `weekly_stats`      | 每週統計            | 週報表          |
| `monthly_stats`     | 每月統計            | 年度分析        |

### Superset 時區設定技巧 (Calculated Columns)

由於 Superset 預設顯示 UTC 時間，為了正確顯示台北時間 (Asia/Taipei)，建議在 Dataset 中新增 **Calculated Column**，而不僅依賴資料庫 View 的轉換。

**設定方式**：

1. 進入 Edit Dataset -> **Calculated Columns** 分頁。
2. 新增一個欄位（例如命名為 `ts` 或 `ts_taiwan`）。
3. **SQL Expression** 輸入：

   ```sql
   timezone('Asia/Taipei', ts)
   ```

4. 設定 **Data type** 為 `TIMESTAMP`。
5. 勾選 **Is temporal**。
6. 在製作圖表時，將此欄位選為 Time Column。

> **註**：系統預設的 `datasources.yaml` 已自動為您設定好此計算欄位 (Column Name: `ts`, Label: `Time`)。由於 `ts` 欄位現在儲存為標準 ISO 8601 格式 (`TIMESTAMP WITH TIME ZONE`)，Superset 會自動正確解析時間資料，無需額外格式設定。

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

---

## 服務訪問

部署完成後，可透過以下 URL 訪問各服務：

### 本地開發環境

| 服務               | URL                          | 說明                          |
|--------------------|------------------------------|-------------------------------|
| **CrateDB Admin**  | http://localhost:4200        | 資料庫管理介面（HTTP 協議）   |
| **CrateDB Admin**  | http://localhost:4500        | 資料庫管理介面（PSQL 協議）   |
| **Superset**       | http://localhost:8088        | 視覺化儀表板                  |

### NAS/生產環境

| 服務               | URL                          | 帳密設定                      |
|--------------------|------------------------------|-------------------------------|
| **CrateDB Admin**  | http://NAS-IP:4200           | 無需登入（建議設定防火牆）    |
| **CrateDB Admin**  | http://NAS-IP:4500           | PostgreSQL 協議端口           |
| **Superset**       | http://NAS-IP:8088           | 參照 `.env` 中的 `SUPERSET_ADMIN_*` |

### Cloudflare Tunnel (遠端存取)

若已設定 Cloudflare Tunnel，可透過您的自訂網域存取：

- **Superset**: `https://superset.your-domain.com`
- **CrateDB** (選填): `https://climate-db.your-domain.com`

> **安全提醒**：CrateDB Admin UI 對外開放有安全風險，建議僅開放 Superset 或使用 Cloudflare Access 進行身份驗證。

---

## 故障排除

### 常見問題

#### 1. 應用程式無法連接到 Tapo H200

**症狀**：日誌顯示 `Failed to discover H200 hub` 或 `Connection timeout`

**解決方案**：

1. **確認網路連通性**：
   ```bash
   # Windows
   ping <TAPO_HOST>
   
   # Linux/NAS
   docker exec climate-monitor ping <TAPO_HOST> -c 4
   ```

2. **檢查 `.env` 設定**：
   - `TAPO_HOST` 是否填寫正確的 IP 位址（不是 MAC，不是網域名稱）
   - 確認帳號密碼無誤（使用 Tapo App 登入的帳密）

3. **防火牆檢查**：
   - 確認 NAS/主機防火牆未封鎖對 Tapo 設備的連線

#### 2. Superset 初始化失敗

**症狀**：`superset-init` 容器持續重啟或報錯

**解決方案**：

1. **確認依賴服務已啟動**：
   ```bash
   docker compose ps
   # 確認 db (PostgreSQL) 與 redis 都處於 running 狀態
   ```

2. **手動重新初始化**：
   ```bash
   # 刪除舊的 Superset 元資料庫
   docker compose down -v
   
   # 重新啟動並初始化
   docker compose up -d
   docker compose up superset-init
   ```

3. **檢查日誌**：
   ```bash
   docker compose logs superset-init
   ```

#### 3. CrateDB 無法啟動或資料遺失

**症狀**：CrateDB 容器啟動失敗或查詢不到歷史資料

**解決方案**：

1. **權限問題** (常見於 Linux/NAS)：
   ```bash
   # 確保 cratedb_data 目錄權限正確
   sudo chown -R 1000:1000 cratedb_data/
   ```

2. **磁碟空間**：
   ```bash
   df -h
   # 確認儲存路徑有足夠空間
   ```

3. **記憶體不足**：
   - 編輯 `docker-compose.yml`，調整 CrateDB 的 `mem_limit`
   - 或修改 `CRATE_HEAP_SIZE` 環境變數（預設 2g）

#### 4. 資料未自動寫入 CrateDB

**症狀**：應用程式運行正常，但資料庫無新資料

**解決方案**：

1. **確認資料表已建立**：
   - 開啟 CrateDB Admin UI: `http://NAS-IP:4200`
   - 執行 `SELECT * FROM climate_data LIMIT 10;`
   - 若提示 "Relation unknown"，表示未執行 `scripts/init_db.sql`

2. **檢查應用程式日誌**：
   ```bash
   docker compose logs -f climate-monitor
   # 查看是否有錯誤訊息
   ```

3. **網路隔離問題**：
   - 確認 Docker Compose 中 `climate-monitor` 與 `cratedb` 在同一網路下
   - 檢查 `.env` 中 `CRATEDB_HOST=cratedb`（容器名稱，非 IP）

#### 5. Superset 圖表顯示時間不正確

**症狀**：圖表中的時間與台灣時間差 8 小時

**解決方案**：

參考 [資料查詢與統計](#資料查詢與統計) 章節中的「Superset 時區設定技巧」，在 Dataset 中新增 Calculated Column 轉換時區。

---

## 專案結構

```text
climate-monitor/
├── .agent/                         # Antigravity AI 配置
├── src/climate_monitor/
│   ├── core/                       # 核心邏輯
│   │   ├── collector.py            # 資料採集器
│   │   └── tapo_client.py          # Tapo 通訊客戶端
│   ├── infra/                      # 基礎設施
│   │   └── database.py             # CrateDB 客戶端
│   └── main.py                     # 程式入口
│
├── docker/
│   ├── superset/                   # Superset 設定
│   │   ├── Dockerfile              # Superset 客製化映像
│   │   ├── superset-init.sh        # 初始化腳本
│   │   └── datasources.yaml        # 預設資料源配置
│   ├── Dockerfile                  # Climate Monitor 映像
│   ├── docker-compose.pc.yml       # 本地開發用
│   └── docker-compose.prod.yml     # NAS 生產用
│
├── scripts/
│   └── init_db.sql                 # CrateDB Schema 初始化
│
├── .env.example                    # 環境變數範本
├── .dockerignore                   # Docker 建構排除檔案
├── .gitignore                      # Git 版控排除檔案
├── pyproject.toml                  # Python 專案依賴 (uv)
├── README.md                       # 本文件
└── NAS_DEPLOYMENT.md               # NAS 部署詳細指南
```

---

## 進階配置

### 效能調校

#### 調整資料收集頻率

修改 `.env` 中的 `COLLECTION_INTERVAL`（單位：秒）：

```env
# 預設 60 秒，可根據需求調整
COLLECTION_INTERVAL=30  # 增加採樣頻率
COLLECTION_INTERVAL=300 # 降低採樣頻率以節省資源
```

#### CrateDB 記憶體最佳化

在 `docker-compose.yml` 中調整 Java Heap Size：

```yaml
environment:
  - CRATE_HEAP_SIZE=4g  # 預設 2g，建議不超過實體記憶體的一半
```

#### Superset 查詢快取設定

Superset 預設使用 Redis 進行查詢快取，可調整 TTL（Time-to-Live）：

- 編輯 `docker/superset/datasources.yaml` 中的 `cache_timeout` 參數

### 安全性強化

#### 1. 變更預設密碼

**Superset 管理員**：

修改 `.env`：

```env
SUPERSET_ADMIN_USERNAME=your_username
SUPERSET_ADMIN_PASSWORD=your_strong_password
SUPERSET_ADMIN_EMAIL=your_email@example.com
```

**Superset Secret Key**：

```bash
# 產生安全的 Secret Key
openssl rand -base64 42
```

將結果填入 `.env` 的 `SUPERSET_SECRET_KEY`。

#### 2. 網路隔離

僅開放必要端口至外網，建議配置：

| 服務                | 內部端口 | 外部開放 | 說明                        |
|---------------------|----------|----------|-----------------------------|
| climate-monitor     | -        | ❌       | 無需對外                    |
| cratedb (HTTP)      | 4200     | ❌       | 僅內部管理使用              |
| cratedb (PSQL)      | 4500     | ❌       | Superset 內部連線           |
| superset            | 8088     | ✅       | 透過 Cloudflare Tunnel      |
| db (PostgreSQL)     | 5432     | ❌       | 僅 Superset 使用            |
| redis               | 6379     | ❌       | 僅 Superset 使用            |

#### 3. 使用 Cloudflare Access

在 Cloudflare Zero Trust Dashboard 為 Superset 設定存取策略：

1. 建立 Access Policy
2. 設定允許的 Email 網域或特定使用者
3. 套用至 Superset 的 Public Hostname

### 資料備份與還原

#### 備份 CrateDB 資料

```bash
# 方法 1：備份整個 Docker Volume
docker compose down
tar -czf cratedb_backup_$(date +%Y%m%d).tar.gz cratedb_data/

# 方法 2：透過 SQL 匯出 (適合小型資料集)
docker exec -it cratedb crash --command "COPY climate_data TO DIRECTORY '/tmp/backup' WITH (compression='gzip');"
```

#### 還原資料

```bash
# 方法 1：還原 Volume
docker compose down
tar -xzf cratedb_backup_YYYYMMDD.tar.gz

# 方法 2：透過 SQL 匯入
docker exec -it cratedb crash --command "COPY climate_data FROM '/tmp/backup/*.json.gz' WITH (compression='gzip');"
```

---

## License

MIT License - 詳見 [LICENSE](LICENSE) 檔案。

---

## 貢獻與支援

若有問題或建議，歡迎開啟 Issue 或 Pull Request。

**開發環境設定**：

```bash
# 安裝開發依賴
uv sync --dev

# 執行測試 (若有)
uv run pytest

# 程式碼格式化
uv run ruff format .
uv run ruff check --fix .
```
