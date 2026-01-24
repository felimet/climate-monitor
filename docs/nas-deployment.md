# Synology NAS 部署指南

本指南專為 Synology NAS (DSM 7.0+) 使用 Container Manager 部署 Climate Monitor 系統而設計。

---

## 目錄

- [前置準備](#前置準備)
- [部署步驟](#部署步驟)
- [健康檢查與驗證](#健康檢查與驗證)
- [服務管理](#服務管理)
- [自動啟動設定](#自動啟動設定)

---

## 前置準備

### 硬體需求 (依實際硬體需求調整)

| 項目         | 最低需求         | 建議配置               |
|--------------|------------------|------------------------|
| **記憶體**   | 4GB              | 8GB+                   |
| **儲存空間** | 10GB             | 50GB+ (依資料量)       |
| **CPU**      | 雙核心           | 四核心+                |
| **網路**     | 1Gbps            | 1Gbps+                 |

### 軟體需求

- **DSM 版本**：7.0 或更新
- **Container Manager**：已安裝並啟用
- **SSH 存取** (需熟悉 Linux 指令與環境架構)：啟用 SSH 服務（控制台 → 終端機和 SNMP → 啟動 SSH 功能）
- **防火牆**：允許必要端口
> 註記：若熟悉部署環境架構，可直接使用 `Container Manager` UI 進行操作，無需 SSH。

### 檔案準備檢查清單

- [ ] 已準備 `.env` 檔案（從 `.env.example` 複製並填入實際資訊）
- [ ] 已確認 Tapo H200 的 IP 位址
- [ ] 已產生 Superset Secret Key（`openssl rand -base64 42`）
- [ ] （選用）已準備 Cloudflare Tunnel Token。若無，可使用 `ngrok` 進行存取或配置 `nginx` 反向代理。

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
> **注意**：`/volume1/@docker/volumes` 是 Synology NAS 的預設儲存位置 (為隱藏目錄，請在終端機中輸入 `ls -la` 查看)，請根據實際情況進行調整。 參考 [Synology 官方文件](https://kb.synology.com/en-global/DSM/help/ContainerManager/docker_container?version=7)與各大論壇討論。

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

**預期輸出** (所有服務應顯示 `Up`)：

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

1. **開啟 CrateDB Admin UI**：`http://<NAS-IP>:4200`

2. **執行初始化 SQL**：
   - 點選左側 **Console** 分頁
   - 複製 `scripts/init_db.sql` 的內容並貼上
   - 點選 **Execute Query** 或按 `Ctrl+Enter`

3. **驗證資料表建立**：

   ```sql
   SHOW TABLES;
   ```

   應顯示：`sensor_readings`、`latest_readings`、`minute_metrics`、`hourly_metrics`、`daily_stats`、`weekly_stats`、`monthly_stats`

### 步驟 5：初始化 Superset

```bash
# 等待所有服務啟動完成 (約 30 秒)
sleep 30

# 執行初始化
sudo docker compose up superset-init
```

> **注意**：執行完成後，`superset-init` 容器會自動停止（正常現象）。若失敗，請檢查 `db` 與 `redis` 是否正常運行。

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

### 檢查點 3：Superset 登入

1. 開啟瀏覽器：`http://<NAS-IP>:8088`
2. 使用 `.env` 中設定的帳號密碼登入
3. 確認首頁顯示「Climate Monitor」儀表板

### 檢查點 4：資料採集

```bash
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

```sql
SELECT COUNT(*) FROM sensor_readings;
SELECT * FROM sensor_readings ORDER BY ts DESC LIMIT 5;
```

---

## 服務管理

### 常用指令

```bash
# 查看所有服務狀態
sudo docker compose ps

# 查看特定服務日誌
sudo docker compose logs -f <service_name>

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

## 自動啟動設定

在 Synology Task Scheduler 設定開機自動啟動：

1. DSM 控制台 → 任務排程器 → 新增 → 觸發的任務 → 使用者定義的指令碼
2. **一般**：名稱 `Start Climate Monitor`，使用者 `root`
3. **任務設定**：

   ```bash
   sleep 60 && cd /volume1/docker/climate-monitor && docker compose up -d
   ```

4. **排程**：選擇「開機」

---

## 下一步

- [Superset 設定與時區技巧](superset-setup.md)
- [故障排除](troubleshooting.md)
- [安全性建議](security.md)
- [備份與還原](backup-restore.md)
