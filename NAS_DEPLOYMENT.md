# NAS 部署指南

## 檔案結構

部署到 NAS 時，請確保以下檔案及資料夾位於專案根目錄：

```
climate-monitor/                      # NAS 專案根目錄 (例如：/volume1/docker/climate-monitor/)
├── docker-compose.prod.yml           # 重要：建議將 docker/docker-compose.prod.yml 複製並改名為 docker-compose.yml
├── Dockerfile                        # 應用程式建構檔 (從 docker/Dockerfile 複製)
├── .env                              # 環境變數設定檔 (必須包含帳號密碼)
├── scripts/
│   └── init_db.sql                   # 資料庫初始化腳本
├── docker/
│   ├── superset/                     # Superset 相關設定
│   │   ├── Dockerfile
│   │   ├── superset-init.sh
│   │   └── datasources.yaml
│   └── ...
└── src/                              # Python 原始程式碼
    └── climate_monitor/
```

## 部署步驟

### 1. 準備檔案

在您的電腦上整理好檔案結構，然後上傳至 NAS。

建議操作方式：
```bash
# 1. 建立部署專用目錄
mkdir deploy_package

# 2. 複製必要檔案 (Windows cmd 範例)
copy docker\docker-compose.prod.yml deploy_package\docker-compose.yml
copy docker\Dockerfile deploy_package\Dockerfile
copy .env.example deploy_package\.env
xcopy /E /I src deploy_package\src
xcopy /E /I scripts deploy_package\scripts
xcopy /E /I docker\superset deploy_package\docker\superset

# 3. 編輯 .env 填入實際設定
```

### 2. 上傳到 NAS

將整理好的資料夾上傳至 Synology NAS。
- 建議路徑：`/volume1/docker/climate-monitor/`

### 3. SSH 登入 NAS 並部署

```bash
# SSH 登入 NAS (請將 your-nas-ip 替換為實際 IP)
ssh admin@your-nas-ip

# 切換到專案目錄
cd /volume1/docker/climate-monitor

# 啟動服務 (會自動建構映像檔)
sudo docker compose up -d --build

# 檢查服務狀態
sudo docker compose ps
```

### 4. 初始化 Superset

服務啟動後，必須執行初始化腳本以設定 Superset 的管理者帳號與資料源。

```bash
# 等待所有服務 (尤其是 db 和 redis) 啟動完成後執行
sudo docker compose up superset-init
```

此步驟完成後，`superset-init` 容器會自動停止，這是正常現象。

### 5. 初始化 CrateDB

1. 開啟瀏覽器存取 CrateDB Admin UI: `http://NAS-IP:4500`
2. 進入 Console (主控台) 分頁。
3. 複製 `scripts/init_db.sql` 的內容並執行，以建立資料表與 View。

## 服務訪問

- **CrateDB UI**: `http://NAS-IP:4500`
- **Superset**: `http://NAS-IP:8088`
  - 預設帳號：`admin` (或參照 .env 設定)
  - 預設密碼：`admin` (或參照 .env 設定)

## Cloudflare Tunnel 配置

若需設定外部存取，請在 Cloudflare Zero Trust Dashboard 添加 Public Hostname：

1. **Superset (儀表板)**
   - Subdomain: `superset`
   - Service: `http://superset:8088`

2. **CrateDB (資料庫管理)** (選填)
   - Subdomain: `climate-db`
   - Service: `http://cratedb:4200`

## 資源使用估算

建議 NAS 配置至少 8GB 記憶體。

**總記憶體需求：約 4.5GB**

| 服務 | 記憶體限制 | 說明 |
|------|------------|------|
| CrateDB | 2GB | 資料庫核心，依資料量調整 |
| Superset | 1GB | 視覺化網頁伺服器 |
| PostgreSQL | 512MB | Superset 元資料儲存 |
| Redis | 512MB | Superset 快取 |
| Climate Monitor | 256MB | Python 收集器 |
| Cloudflare Tunnel | 128MB | 安全連線通道 |

## 常用指令

```bash
# 停止所有服務
sudo docker compose down

# 重新啟動所有服務
sudo docker compose restart

# 更新程式碼後重新建構並啟動
sudo docker compose up -d --build

# 查看特定服務日誌 (例如 superset)
sudo docker compose logs -f superset

# 清理未使用的 Docker 資源 (謹慎使用)
sudo docker system prune -a
```
