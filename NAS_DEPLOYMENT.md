# Synology NAS 部署指南

本指南專為 Synology NAS (DSM 7.0+) 使用 Container Manager 部署 Climate Monitor 系統而設計。

---

## 目錄

- [前置準備](#前置準備)
- [部署步驟](#部署步驟)
- [健康檢查與驗證](#健康檢查與驗證)
- [服務管理](#服務管理)
- [故障排除](#故障排除)
- [安全性建議](#安全性建議)
- [效能最佳化](#效能最佳化)
- [備份與還原](#備份與還原)

---

## 前置準備

### 硬體需求

| 項目         | 最低需求         | 建議配置               |
|--------------|------------------|------------------------|
| **記憶體**   | 4GB              | 8GB+                   |
| **儲存空間** | 10GB             | 50GB+ (依資料量)       |
| **CPU**      | 雙核心           | 四核心+                |
| **網路**     | 1Gbps            | 1Gbps+                 |

### 軟體需求

- **DSM 版本**：7.0 或更新
- **Container Manager**：已安裝並啟用
- **SSH 存取**：啟用 SSH 服務（控制台 → 終端機和 SNMP → 啟動 SSH 功能）
- **防火牆**：允許必要端口（見下方）

### 網路端口規劃

| 端口 | 服務            | 用途                   | 對外開放 |
|------|-----------------|------------------------|----------|
| 4200 | CrateDB (HTTP)  | 資料庫管理介面         | ❌       |
| 4500 | CrateDB (PSQL)  | PostgreSQL 協議        | ❌       |
| 8088 | Superset        | 視覺化儀表板           | ✅       |
| 5432 | PostgreSQL      | Superset 元資料庫      | ❌       |
| 6379 | Redis           | Superset 快取          | ❌       |

### 檔案準備檢查清單

- [ ] 已準備 `.env` 檔案（從 `.env.example` 複製並填入實際資訊）
- [ ] 已確認 Tapo H200 的 IP 位址
- [ ] 已產生 Superset Secret Key（`openssl rand -base64 42`）
- [ ] （選用）已準備 Cloudflare Tunnel Token

---

## 部署步驟

### 步驟 1：準備部署檔案

#### 方式 A：透過 Git (推薦)

```bash
# SSH 登入 NAS
ssh admin@<NAS-IP>

# 安裝 Git (若未安裝)
sudo synopkg install Git

# Clone 專案
cd /volume1/docker/
git clone <repository-url> climate-monitor
cd climate-monitor
```

#### 方式 B：手動上傳

1. 在本地電腦整理部署檔案：

   ```powershell
   # Windows PowerShell
   mkdir deploy_package
   
   # 複製必要檔案
   Copy-Item -Path "docker\docker-compose.prod.yml" -Destination "deploy_package\docker-compose.yml"
   Copy-Item -Path "docker\Dockerfile" -Destination "deploy_package\"
   Copy-Item -Path ".env.example" -Destination "deploy_package\.env"
   
   # 複製目錄
   Copy-Item -Recurse -Path "src" -Destination "deploy_package\"
   Copy-Item -Recurse -Path "scripts" -Destination "deploy_package\"
   Copy-Item -Recurse -Path "docker\superset" -Destination "deploy_package\docker\"
   ```

2. 透過 File Station 或 SFTP 上傳至 NAS：
   - **建議路徑**：`/volume1/docker/climate-monitor/`

### 步驟 2：設定環境變數

```bash
# SSH 登入 NAS
ssh admin@<NAS-IP>

# 切換到專案目錄
cd /volume1/docker/climate-monitor

# 編輯環境變數
sudo nano .env
```

**必填項目**：

```env
# Tapo H200 設定 (必填)
TAPO_HOST=192.168.1.XXX          # 填入實際 IP
TAPO_USERNAME=your@email.com     # Tapo App 帳號
TAPO_PASSWORD=your_password      # Tapo App 密碼

# Superset 管理員 (必填)
SUPERSET_SECRET_KEY=<產生的 Secret Key>
SUPERSET_ADMIN_USERNAME=admin
SUPERSET_ADMIN_PASSWORD=<強密碼>
SUPERSET_ADMIN_EMAIL=admin@example.com

# Superset PostgreSQL (建議修改)
SUPERSET_POSTGRES_PASSWORD=<資料庫密碼>
```

**選填項目**：

```env
# Cloudflare Tunnel (選填)
TUNNEL_TOKEN=<your_tunnel_token>

# 資料收集頻率 (選填，預設 60 秒)
COLLECTION_INTERVAL=60
```

### 步驟 3：啟動服務

```bash
# 確認在專案目錄
cd /volume1/docker/climate-monitor

# 啟動所有服務 (會自動建構映像檔)
sudo docker compose up -d --build

# 查看服務狀態
sudo docker compose ps
```

**預期輸出** (所有服務應顯示 `Up`):

```text
NAME                STATUS          PORTS
climate-monitor     Up              
cratedb             Up              0.0.0.0:4200->4200/tcp, 0.0.0.0:4500->4500/tcp
db                  Up              5432/tcp
redis               Up              6379/tcp
superset            Up              0.0.0.0:8088->8088/tcp
cloudflared         Up (若有設定 Tunnel)
```

### 步驟 4：初始化 CrateDB

1. **開啟 CrateDB Admin UI**：

   - URL: `http://<NAS-IP>:4200`

2. **執行初始化 SQL**：

   - 點選左側 **Console** 分頁
   - 複製 `scripts/init_db.sql` 的內容並貼上
   - 點選 **Execute Query** 或按 `Ctrl+Enter`

3. **驗證資料表建立**：

   ```sql
   SHOW TABLES;
   ```

   應顯示：
   - `climate_data` (主資料表)
   - `latest_readings` (最新讀數 View)
   - `minute_metrics`, `hourly_metrics`, `daily_stats`, `weekly_stats`, `monthly_stats` (統計 Views)

### 步驟 5：初始化 Superset

```bash
# 等待所有服務啟動完成 (約 30 秒)
sleep 30

# 執行初始化
sudo docker compose up superset-init
```

**注意事項**：

- 此步驟會建立 Superset 管理員帳號、設定資料源、匯入儀表板
- 執行完成後，`superset-init` 容器會自動停止（正常現象）
- 若失敗，請檢查 `db` 與 `redis` 是否正常運行

### 步驟 6：驗證部署

詳見 [健康檢查與驗證](#健康檢查與驗證) 章節。

---

## 健康檢查與驗證

### 檢查點 1：容器狀態

```bash
sudo docker compose ps
```

**期望結果**：所有服務狀態為 `Up`，無 `Restarting` 或 `Exit` 狀態。

### 檢查點 2：CrateDB 連線

```bash
# 測試 HTTP 端口
curl http://localhost:4200

# 測試 PostgreSQL 端口
docker exec -it cratedb crash --command "SELECT 1;"
```

**期望結果**：HTTP 回傳 JSON，SQL 查詢成功。

### 檢查點 3：Superset 登入

1. 開啟瀏覽器：`http://<NAS-IP>:8088`
2. 使用 `.env` 中設定的帳號密碼登入
3. 確認首頁顯示「Climate Monitor」儀表板

### 檢查點 4：資料採集

```bash
# 查看 Climate Monitor 日誌
sudo docker compose logs -f climate-monitor
```

**期望結果**：

```text
INFO - Discovered H200 hub: <device_name>
INFO - Found 3 sensors: T315_1, T315_2, T315_3
INFO - Collected data for T315_1: temp=24.5°C, humidity=65%
INFO - Successfully inserted data into CrateDB
```

### 檢查點 5：資料庫寫入

在 CrateDB Admin UI 執行：

```sql
SELECT COUNT(*) FROM climate_data;
SELECT * FROM climate_data ORDER BY timestamp DESC LIMIT 5;
```

**期望結果**：至少有幾筆資料（等待 1-2 個採集週期後檢查）。

---

## 服務管理

### 常用指令

```bash
# 查看所有服務狀態
sudo docker compose ps

# 查看特定服務日誌
sudo docker compose logs -f <service_name>
# 例如: sudo docker compose logs -f climate-monitor

# 重啟特定服務
sudo docker compose restart <service_name>

# 重啟所有服務
sudo docker compose restart

# 停止所有服務
sudo docker compose down

# 停止並刪除 Volume (謹慎使用，會清除資料)
sudo docker compose down -v

# 更新程式碼後重新部署
sudo docker compose up -d --build

# 清理未使用的 Docker 資源
sudo docker system prune -a -f
```

### 更新應用程式

```bash
# 拉取最新程式碼 (若使用 Git)
cd /volume1/docker/climate-monitor
sudo git pull

# 重新建構並啟動
sudo docker compose up -d --build climate-monitor

# 查看日誌確認正常運行
sudo docker compose logs -f climate-monitor
```

---

## 故障排除

### 問題 1：容器無法啟動

**症狀**：`docker compose ps` 顯示服務 `Exit` 或持續 `Restarting`

**解決方案**：

1. **查看日誌**：

   ```bash
   sudo docker compose logs <service_name>
   ```

2. **常見錯誤**：

   - **端口衝突**：檢查 4200, 4500, 8088 等端口是否被佔用

     ```bash
     sudo netstat -tulpn | grep -E '4200|4500|8088'
     ```

   - **權限問題**：

     ```bash
     # 修正 cratedb_data 權限
     sudo chown -R 1000:1000 cratedb_data/
     ```

   - **記憶體不足**：調整 `docker-compose.yml` 中的 `mem_limit`

### 問題 2：無法連接 Tapo H200

**症狀**：Climate Monitor 日誌顯示 `Failed to discover H200 hub`

**解決方案**：

1. **網路連通性測試**：

   ```bash
   docker exec climate-monitor ping <TAPO_HOST> -c 4
   ```

2. **檢查 `.env` 設定**：

   - `TAPO_HOST` 必須是 IP 位址，不是主機名稱
   - 確認帳號密碼正確（與 Tapo App 相同）

3. **防火牆檢查**：

   - DSM 控制台 → 安全性 → 防火牆
   - 確認允許對 Tapo 設備的連線

### 問題 3：Superset 初始化失敗

**症狀**：`superset-init` 容器錯誤退出

**解決方案**：

1. **檢查依賴服務**：

   ```bash
   sudo docker compose ps db redis
   # 確認兩者都處於 Up 狀態
   ```

2. **重新初始化**：

   ```bash
   # 清除舊的 Superset 元資料
   sudo docker compose down -v
   
   # 重新啟動
   sudo docker compose up -d
   
   # 等待 30 秒後初始化
   sleep 30
   sudo docker compose up superset-init
   ```

3. **查看詳細錯誤**：

   ```bash
   sudo docker compose logs superset-init | tail -50
   ```

### 問題 4：CrateDB 資料遺失

**症狀**：重啟後查詢不到歷史資料

**解決方案**：

1. **檢查 Volume 掛載**：

   ```bash
   # 確認 docker-compose.yml 中 cratedb 的 volumes 設定
   sudo docker compose config | grep -A 5 'cratedb:'
   ```

2. **權限修復**：

   ```bash
   sudo chown -R 1000:1000 /volume1/docker/climate-monitor/cratedb_data/
   sudo chmod -R 755 /volume1/docker/climate-monitor/cratedb_data/
   ```

3. **磁碟空間**：

   ```bash
   df -h | grep volume1
   ```

### 問題 5：重建 CrateDB 資料庫（清除所有資料）

**症狀**：需要完全重置 CrateDB（例如：shard 數量超限、資料損壞、架構變更）

**⚠️ 警告**：此操作將**永久刪除**所有歷史資料，請先備份！

**解決方案**：

#### 步驟 1：確認 Docker Compose 專案路徑

```bash
# 切換到專案目錄
cd /volume1/docker/JiaMing/climate-monitor/docker

# 確認 Docker Compose 檔案存在
ls -lah docker-compose*.yml

# 查看當前運行的容器
sudo docker compose ps
```

#### 步驟 2：停止所有服務

```bash
# 使用正確的 compose 檔案（根據實際情況選擇）
sudo docker compose -f docker-compose.yml down
# 或
sudo docker compose down
```

#### 步驟 3：刪除 CrateDB Volume

```bash
# 列出所有 volumes，確認實際名稱
sudo docker volume ls | grep crate

# 刪除 CrateDB volume（常見名稱）
sudo docker volume rm climate-monitor_cratedb_data

# 如果名稱不同，請使用實際顯示的名稱
# sudo docker volume rm <實際_volume_名稱>
```

**注意**：Volume 名稱取決於 Docker Compose 專案名稱：
- 如果 `docker-compose.yml` 中有 `name: climate-tapo-monitor`：
  - Volume 名稱為 `climate-tapo-monitor_cratedb_data`
- 如果沒有指定專案名稱：
  - Volume 名稱為 `<目錄名稱>_cratedb_data`（如 `climate-monitor_cratedb_data`）

#### 步驟 4：重新啟動 CrateDB

```bash
# 僅啟動 CrateDB（其他服務可稍後啟動）
sudo docker compose up -d cratedb

# 等待啟動完成（約 40 秒）
sleep 40
```

#### 步驟 5：設定 Shard 上限（重要！）

```bash
# 提高 shard 上限至 3000（避免單節點環境達到預設上限）
curl -s -X POST "http://localhost:4500/_sql" \
  -H "Content-Type: application/json" \
  -d '{"stmt":"SET GLOBAL PERSISTENT cluster.max_shards_per_node = 3000"}' | python3 -m json.tool

# 驗證設定
curl -s -X POST "http://localhost:4500/_sql" \
  -H "Content-Type: application/json" \
  -d '{"stmt":"SELECT settings['"'"'cluster'"'"']['"'"'max_shards_per_node'"'"'] as max_shards FROM sys.cluster"}' | python3 -m json.tool
```

#### 步驟 6：初始化資料庫 Schema

```bash
# 方法 A：使用 crash 命令（推薦）
sudo docker exec climate-cratedb crash < /volume1/docker/JiaMing/climate-monitor/scripts/init_db.sql

# 方法 B：如果找不到 crash，使用預設容器名稱
sudo docker exec cratedb crash < /volume1/docker/JiaMing/climate-monitor/scripts/init_db.sql

# 方法 C：使用 HTTP API（如果上述失敗）
curl -X POST "http://localhost:4500/_sql" \
  -H "Content-Type: application/json" \
  -d "@/volume1/docker/JiaMing/climate-monitor/scripts/init_db.sql"
```

#### 步驟 7：驗證資料表已建立

```bash
# 確認表已建立
curl -s -X POST "http://localhost:4500/_sql" \
  -H "Content-Type: application/json" \
  -d '{"stmt":"SHOW TABLES"}' | python3 -m json.tool

# 預期輸出應包含：
# - sensor_readings
# - latest_readings
# - minute_metrics
# - hourly_metrics
# - daily_stats
# - weekly_stats
# - monthly_stats
```

#### 步驟 8：啟動所有服務

```bash
# 啟動所有服務
sudo docker compose up -d

# 查看服務狀態
sudo docker compose ps

# 監控應用程式日誌，確認資料開始寫入
sudo docker compose logs -f climate-monitor
```

#### 步驟 9：驗證資料寫入

```bash
# 等待 2-3 分鐘後查詢
curl -s -X POST "http://localhost:4500/_sql" \
  -H "Content-Type: application/json" \
  -d '{"stmt":"SELECT count(*) as total FROM sensor_readings"}' | python3 -m json.tool

# 確認分割區正常（應該只有 1 個，對應當前月份）
curl -s -X POST "http://localhost:4500/_sql" \
  -H "Content-Type: application/json" \
  -d '{"stmt":"SELECT partition_ident, values['"'"'month_ts'"'"'] as month, number_of_shards FROM information_schema.table_partitions WHERE table_schema = '"'"'doc'"'"' ORDER BY values['"'"'month_ts'"'"'] DESC"}' | python3 -m json.tool
```

**預期結果**：
- `total` > 0（有新資料）
- 僅 1 個分割區，對應當前月份
- `number_of_shards = 1`（單節點最佳化配置）

---

### 問題 6：Synology Container Manager GUI 問題

**症狀**：透過 Container Manager 介面無法看到或管理容器

**解決方案**：

- **使用 SSH + Docker Compose CLI**：Synology Container Manager 對 Docker Compose 支援有限，建議透過 SSH 使用命令列管理
- **重新整理介面**：有時需要手動重新整理 Container Manager 頁面
- **檢查 Docker Socket 權限**：

  ```bash
  sudo chmod 666 /var/run/docker.sock
  ```

---

## 安全性建議

### 1. 變更預設密碼

**務必修改 `.env` 中的以下項目**：

```env
SUPERSET_ADMIN_PASSWORD=<使用強密碼>
SUPERSET_SECRET_KEY=<使用 openssl rand -base64 42 產生>
SUPERSET_POSTGRES_PASSWORD=<資料庫密碼>
```

### 2. 網路隔離

**DSM 防火牆設定**：

1. 控制台 → 安全性 → 防火牆
2. 編輯規則，僅允許：
   - **8088** (Superset)：來源限制為信任的 IP 範圍
   - **4200, 4500**：僅允許本地存取 (127.0.0.1)

### 3. 使用 Cloudflare Tunnel

**優點**：

- 無需開放 NAS 端口至公網
- 自動 HTTPS 加密
- DDoS 防護

**設定步驟**：

1. 在 Cloudflare Zero Trust Dashboard 建立 Tunnel
2. 取得 Token 並填入 `.env` 的 `TUNNEL_TOKEN`
3. 設定 Public Hostname 指向 `http://superset:8088`

### 4. 定期更新

```bash
# 定期拉取最新程式碼與映像檔
cd /volume1/docker/climate-monitor
sudo git pull
sudo docker compose pull
sudo docker compose up -d --build
```

---

## 效能最佳化

### 1. 調整 CrateDB 記憶體

編輯 `docker-compose.yml`：

```yaml
services:
  cratedb:
    environment:
      - CRATE_HEAP_SIZE=4g  # 預設 2g，建議為實體記憶體的 1/4 到 1/2
```

### 2. 啟用 SSD 快取 (若 NAS 有 SSD)

1. DSM 控制台 → 儲存空間管理員 → SSD 快取
2. 為 `/volume1/docker/` 啟用讀寫快取

### 3. 調整資料收集頻率

修改 `.env`：

```env
# 降低採集頻率以節省資源
COLLECTION_INTERVAL=120  # 改為 2 分鐘
```

---

## 備份與還原

### 備份策略

#### 1. 完整備份 (含資料)

```bash
# 停止服務
cd /volume1/docker/climate-monitor
sudo docker compose down

# 備份整個專案目錄
sudo tar -czf /volume1/backups/climate-monitor_$(date +%Y%m%d).tar.gz \
  --exclude='cratedb_data/nodes' \
  /volume1/docker/climate-monitor/

# 重新啟動
sudo docker compose up -d
```

#### 2. 僅備份 CrateDB 資料

```bash
# 方法 A：備份 Volume
sudo tar -czf cratedb_backup_$(date +%Y%m%d).tar.gz cratedb_data/

# 方法 B：使用 CrateDB Snapshot (進階)
docker exec -it cratedb crash --command \
  "CREATE SNAPSHOT backup_repo.snapshot_$(date +%Y%m%d) ALL WITH (wait_for_completion=true);"
```

### 還原資料

```bash
# 停止服務
sudo docker compose down

# 解壓縮備份
sudo tar -xzf /volume1/backups/climate-monitor_YYYYMMDD.tar.gz -C /

# 修正權限
sudo chown -R 1000:1000 /volume1/docker/climate-monitor/cratedb_data/

# 重新啟動
cd /volume1/docker/climate-monitor
sudo docker compose up -d
```

---

## 附錄

### 資源使用參考

| 服務              | 記憶體限制 | CPU 使用   | 儲存空間 (初期) |
|-------------------|------------|------------|-----------------|
| CrateDB           | 2GB        | 0.5-2核    | 5GB             |
| Superset          | 1GB        | 0.2-0.5核  | 500MB           |
| PostgreSQL        | 512MB      | 0.1-0.2核  | 200MB           |
| Redis             | 512MB      | 0.1核      | 100MB           |
| Climate Monitor   | 256MB      | 0.1核      | 50MB            |
| Cloudflare Tunnel | 128MB      | 0.05核     | 20MB            |
| **總計**          | **~4.5GB** | **~3核**   | **~6GB**        |

### 自動啟動設定

在 Synology Task Scheduler 設定開機自動啟動：

1. DSM 控制台 → 任務排程器 → 新增 → 觸發的任務 → 使用者定義的指令碼
2. **一般**：名稱 `Start Climate Monitor`，使用者 `root`
3. **任務設定**：
   - 執行指令：

     ```bash
     sleep 60 && cd /volume1/docker/climate-monitor && docker compose up -d
     ```

4. **排程**：選擇「開機」

---

## 支援與社群

若遇到問題，請參考：

- **專案 README**：[README.md](README.md)
- **Issue Tracker**：GitHub Issues
- **日誌查詢**：`sudo docker compose logs -f`

---

**版本**：1.0  
**更新日期**：2026-01-24
