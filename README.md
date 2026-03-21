# Climate Monitor

![Python Version](https://img.shields.io/badge/python-3.11-blue.svg)
![CrateDB](https://img.shields.io/badge/database-CrateDB-4bc51d.svg)
![Apache Superset](https://img.shields.io/badge/BI-Apache%20Superset-20A6C9.svg)
![Docker](https://img.shields.io/badge/container-Docker-2496ED.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

**Climate Monitor** 是一個 T315 溫溼度感測器監測系統，專為長期穩定運行設計。透過 Python 與 Tapo H200 網關通訊，自動蒐集 T315 感測器資料，並儲存於高效能時序資料庫 CrateDB 中。整合 Apache Superset 提供專業級資料視覺化，適合部署於 Synology NAS 或任何 Docker 環境。

---

## 主要功能

- **自動發現**：啟動後自動搜尋並連接 H200 網關下的所有 T315 感測器
- **即時監控**：定時（預設 60 秒）蒐集溫度、濕度、電池電量及訊號強度
- **連線狀態驗證**：多重訊號交叉比對（RSSI、溫溼度凍結、device_time）偵測 Hub 快取的過時資料，驗證不通過時寫入 NULL 並記錄至 `stale.log`
- **高效儲存**：使用 CrateDB 處理時序資料，支援數千萬筆資料的快速查詢與聚合
- **資料視覺化**：配置 Apache Superset，提供專業的儀表板與圖表分析功能
- **統計視圖**：預建每分鐘、每小時、每日、每週、每月的統計表
- **安全存取**：配置 Cloudflare Tunnel，支援免開 Port 的安全遠端存取
- **容錯機制**：自動重連、錯誤重試、完整日誌記錄

---

## 快速開始

### 環境需求

- **硬體**：Tapo H200 網關 + T315 感測器
- **軟體**：Docker 20.10+ & Docker Compose 2.0+
- **網路**：NAS/開發機與 Tapo 設備需在同一區域網路

### 部署方式

| 方式 | 適用情境 | 文件 |
|------|----------|------|
| **NAS 生產部署** | Synology NAS 或伺服器 | [NAS 部署指南](docs/nas-deployment.md) |
| **本地開發** | Windows/Linux 開發機 | [快速開始](docs/getting-started.md) |

### 快速版本（NAS 部署）

```bash
# 1. 準備環境變數
cp .env.example .env
# 編輯 .env 填入 Tapo 帳號、IP 等資訊

# 2. 啟動所有服務
cd docker
docker compose -f docker-compose.prod.yml up -d --build

# 3. 初始化 Superset（僅首次部署）
docker compose -f docker-compose.prod.yml --profile init up superset-init

# 4. 初始化 CrateDB
# 開啟瀏覽器: http://your-nas-ip:4200
# 執行 scripts/init_db.sql 中的 SQL 語句
# 另可使用 CrateDB Viewer (https://github.com/crate/crate-viewer) 進行管理，點選預建查詢。
```

---

## 連線狀態驗證

H200 Hub 的 API 不提供子裝置的 online/offline 狀態，斷線後仍會回傳最後一筆快取資料。系統透過四項訊號交叉比對偵測過時資料：

| 檢查項目 | 原理 |
|----------|------|
| RSSI 門檻 | 低於 -75 dBm 視為訊號過弱 |
| RSSI 凍結 | 真實 RF 環境 RSSI 一定有 jitter，完全不動代表快取 |
| 溫溼度凍結 | 溫度和濕度不可能同時長時間不變到小數位都一樣 |
| device_time 凍結 | 正常連線下裝置時間一定遞增 |

**判定規則**：至少 2 項（可設定）同時失敗才判定為 stale，避免單一指標誤判。凍結判定次數根據取樣間隔自動計算（`frozen_window / collection_interval`）。

**Stale 處理**：temperature 和 humidity 寫入 NULL，保留 `is_valid` 和 `stale_reasons` 欄位。事件同時記錄至 `data/monitor_logs/stale.log`。

相關環境變數：

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `VALIDATOR_RSSI_THRESHOLD` | -75 | RSSI 門檻（dBm） |
| `VALIDATOR_FROZEN_WINDOW` | 300 | 凍結判定時間窗口（秒） |
| `VALIDATOR_HISTORY_WINDOW` | 1200 | 歷史記錄時間窗口（秒） |
| `VALIDATOR_MIN_FAILED_CHECKS` | 2 | 交叉確認門檻（1-4） |
| `STALE_LOG_PATH` | /app/logs/stale.log | Stale 日誌路徑 |

---

## 文件導覽

| 文件 | 說明 |
|------|------|
| [系統架構](docs/architecture.md) | 架構圖、技術棧、資料模型 |
| [快速開始](docs/getting-started.md) | 本地開發流程 |
| [NAS 部署指南](docs/nas-deployment.md) | Synology NAS 完整部署步驟 |
| [Superset 設定](docs/superset-setup.md) | 時區設定、儀表板建立 |
| [進階配置](docs/configuration.md) | 環境變數、效能調校 |
| [安全性建議](docs/security.md) | 密碼安全、Cloudflare Tunnel |
| [備份與還原](docs/backup-restore.md) | 資料備份策略 |
| [故障排除](docs/troubleshooting.md) | 常見問題與解決方案 |

---

## 專案結構

```text
climate-monitor/
├── src/climate_monitor/
│   ├── core/                       # 核心邏輯
│   │   ├── collector.py            # 資料採集器
│   │   ├── tapo_client.py          # Tapo 通訊客戶端
│   │   └── validator.py            # T315 連線狀態驗證器
│   ├── infra/                      # 基礎設施
│   │   └── database.py             # CrateDB 客戶端
│   ├── utils/                      # 工具模組
│   │   └── logging.py              # 日誌設定（含 stale 檔案日誌）
│   ├── config.py                   # 環境變數設定
│   ├── models.py                   # 資料模型
│   └── main.py                     # 程式入口
│
├── docker/
│   ├── superset/                   # Superset 設定
│   │   ├── Dockerfile              # Superset 客製化映像
│   │   ├── superset-init.sh        # 初始化程式碼
│   │   └── datasources.yaml        # 預設資料源配置
│   ├── Dockerfile                  # Climate Monitor 映像
│   ├── docker-compose.pc.yml       # 本地開發用
│   ├── docker-compose.prod.yml     # NAS 生產部署用
│   └── data/                       # Bind mount 資料（gitignore）
│       ├── cratedb/                # CrateDB 資料庫資料
│       ├── monitor_logs/           # Stale 事件日誌
│       ├── postgres/               # Superset 元資料庫
│       ├── redis/                  # Redis 快取
│       └── superset/               # Superset 設定檔
│
├── scripts/
│   └── init_db.sql                 # CrateDB Schema 初始化
│
├── docs/                           # 說明文件
│   ├── architecture.md
│   ├── getting-started.md
│   ├── nas-deployment.md
│   └── ...
│
├── .env.example                    # 環境變數範本
├── pyproject.toml                  # Python 專案依賴 (uv)
└── README.md                       
```

---

## 服務訪問

### 本地開發環境

| 服務 | URL |
|------|-----|
| CrateDB Admin | http://localhost:4200 |
| Superset | http://localhost:8088 |

### NAS/生產環境

| 服務 | URL |
|------|-----|
| CrateDB Admin | http://NAS-IP:4200 |
| Superset | http://NAS-IP:8088 |

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

---

## License

MIT License - 詳見 [LICENSE](LICENSE) 檔案。
