# Synology NAS 部署指南

本指南專為 Synology NAS (DSM 7.0+) 使用 Container Manager 部署 Climate Monitor 系統而設計。

提供兩種操作方式：
- **Container Manager UI**：適合不熟悉終端機的使用者
- **SSH 終端機**：適合熟悉 Linux 指令的使用者

---

## 目錄

- [前置準備](#前置準備)
- [部署步驟](#部署步驟)
- [健康檢查與驗證](#健康檢查與驗證)
- [服務管理](#服務管理)
- [自動啟動設定](#自動啟動設定)

---

## 儲存策略：Bind Mount vs Named Volume

本專案選擇 **bind mount**（`./data/cratedb`、`./data/redis` 等）而非 Docker named volume，這是基於 Synology NAS 環境的實際運維需求所做的設計決策。

### 為什麼不使用 Named Volume？

Docker named volume 在一般伺服器環境中是推薦做法——由 Docker 管理、路徑固定、不受主機檔案系統影響。但在 Synology NAS 的 Container Manager 中，named volume 存在以下問題：

- **不可見性**：Named volume 儲存在 `/volume1/@docker/volumes/` 深層目錄中，File Station 無法直接瀏覽，使用者必須透過 SSH 才能存取資料
- **備份困難**：Synology 的 Hyper Backup 無法直接選擇 Docker volume 作為備份來源。使用 bind mount 後，資料目錄位於 `/volume1/docker/climate-monitor/data/`，可直接納入 Hyper Backup 任務
- **遷移不便**：當需要將整個專案遷移至另一台 NAS 時，bind mount 只需複製整個專案目錄；named volume 則需要額外的 `docker volume` 匯出/匯入步驟

### Bind Mount 的權限處理

CrateDB 容器以 `crate` 用戶（UID 1000）運行，但 NAS 上由 `root` 建立的 bind mount 目錄預設權限為 `root:root`。這會導致 CrateDB 無法寫入資料目錄而啟動失敗。

解決方案是在 `docker-compose.yml` 中使用自訂 entrypoint，在容器啟動時先以 root 身份建立並修正目錄權限，再切換至 `crate` 用戶執行主程式：

```yaml
entrypoint: ["/bin/sh", "-c", "mkdir -p /data/data && chown -R crate:crate /data && /docker-entrypoint.sh crate ..."]
```

這個模式確保了首次部署與後續重啟都能正確運作，無需手動在 NAS 上 SSH 設定目錄權限。

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
- **Container Manager**：已安裝並啟用（套件中心 → Container Manager）
- **SSH 存取**（選用）：控制台 → 終端機和 SNMP → 啟動 SSH 功能

### 檔案準備檢查清單

- [ ] 已準備 `.env` 檔案（從 `.env.example` 複製並填入實際資訊）
- [ ] 已確認 Tapo H200 的 IP 位址
- [ ] 已產生 Superset Secret Key（`openssl rand -base64 42`）
- [ ] （選用）已準備 Cloudflare Tunnel Token。若無，可使用 `ngrok` 進行存取或配置 `nginx` 反向代理。

---

## 部署步驟

### 步驟 1：上傳專案檔案

#### 方式 A：透過 File Station（推薦）

1. 開啟 **File Station**
2. 建立資料夾：`/docker/climate-monitor/`
3. 上傳以下檔案與資料夾：

   ```
   climate-monitor/
   ├── docker/
   │   ├── docker-compose.prod.yml  → 重新命名為 docker-compose.yml
   │   ├── Dockerfile
   │   └── superset/
   ├── src/
   ├── scripts/
   ├── .env.example  → 複製並重新命名為 .env
   └── pyproject.toml
   ```

4. 編輯 `.env` 檔案，填入實際設定值（可用 Text Editor 套件）

#### 方式 B：透過 Git（SSH）

```bash
ssh admin@<NAS-IP>

# 安裝 Git (若未安裝)
sudo synopkg install Git

# Clone 專案
cd /volume1/docker/
git clone <repository-url> climate-monitor
cd climate-monitor
cp .env.example .env
nano .env  # 編輯環境變數
```

### 步驟 2：設定環境變數

編輯 `.env` 檔案，填入以下必要設定：

```env
# Tapo H200 設定 (必填)
TAPO_HOST=192.168.xxx.xxx          # H200 的實際 IP
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

### 步驟 3：建立並啟動專案

#### 方式 A：透過 Container Manager UI

1. 開啟 **Container Manager**
2. 左側選單 → **專案**
3. 點選 **建立**
4. 填入專案資訊：
   - **專案名稱**：`climate-monitor`
   - **路徑**：選擇 `/docker/climate-monitor`
   - **來源**：選擇「使用現有的 docker-compose.yml」
5. 點選 **下一步**
6. 確認設定後，點選 **完成**
7. 等待所有容器建構並啟動

#### 方式 B：透過 SSH 終端機

```bash
# 確認在專案目錄
cd /volume1/docker/climate-monitor

# 啟動所有服務 (會自動建構映像檔)
sudo docker compose up -d --build

# 查看服務狀態
sudo docker compose ps
```

**預期結果**：所有服務狀態為 `Up` 或「執行中」

| 容器名稱        | 狀態   | 說明           |
|-----------------|--------|----------------|
| climate-monitor | 執行中 | 資料採集服務   |
| cratedb         | 執行中 | 時序資料庫     |
| superset        | 執行中 | 視覺化平台     |
| db              | 執行中 | Superset 元資料庫 |
| redis           | 執行中 | Superset 快取  |

### 步驟 4：初始化 CrateDB

1. 開啟瀏覽器：`http://<NAS-IP>:4200`
2. 點選左側 **Console** 分頁
3. 複製 `scripts/init_db.sql` 的內容並貼上
4. 點選 **Execute Query** 或按 `Ctrl+Enter`
5. 驗證資料表建立：

   ```sql
   SHOW TABLES;
   ```

   應顯示：`sensor_readings`、`latest_readings`、`minute_metrics`、`hourly_metrics`、`daily_stats`、`weekly_stats`、`monthly_stats`

### 步驟 5：初始化 Superset（僅首次部署）

> **說明**：`superset-init` 是一次性初始化任務，使用 `profiles: ["init"]` 設定，不會隨 `docker compose up -d` 自動啟動，因此不會產生「容器不預期停止」的通知。

#### 方式 A：透過 SSH 終端機（推薦）

```bash
cd /volume1/docker/climate-monitor
sudo docker compose --profile init up superset-init
```

等待約 30-60 秒，容器會自動停止。確認日誌顯示 `Superset initialization complete`。

#### 方式 B：透過 Container Manager UI

1. Container Manager 不直接支援 profile 啟動，建議使用 SSH 方式
2. 或者暫時將 `docker-compose.yml` 中 superset-init 的 `profiles` 段落註解掉，透過 UI 啟動後再恢復

> **重新初始化**：若需重新初始化 Superset，再次執行 `docker compose --profile init up superset-init` 即可。

---

## 健康檢查與驗證

### 檢查點 1：容器狀態

#### 透過 Container Manager UI

1. 開啟 **Container Manager** → **專案** → `climate-monitor`
2. 確認所有容器狀態為「執行中」（綠色圖示）

#### 透過 SSH 終端機

```bash
sudo docker compose ps
```

### 檢查點 2：Superset 登入

1. 開啟瀏覽器：`http://<NAS-IP>:8088`
2. 使用 `.env` 中設定的帳號密碼登入
3. 確認可正常進入儀表板頁面

### 檢查點 3：資料採集

#### 透過 Container Manager UI

1. **Container Manager** → **容器** → `climate-monitor`
2. 右鍵 → **詳細資訊** → **日誌**
3. 確認顯示資料採集訊息

#### 透過 SSH 終端機

```bash
sudo docker compose logs -f climate-monitor
```

**期望結果**：

```text
INFO - Discovered H200 hub: <device_name>
INFO - Found sensors: T315_1, T315_2
INFO - Collected data for T315_1: temp=24.5°C, humidity=65%
INFO - Successfully inserted data into CrateDB
```

### 檢查點 4：資料庫寫入

在 CrateDB Admin UI（`http://<NAS-IP>:4200`）執行：

```sql
SELECT COUNT(*) FROM sensor_readings;
SELECT * FROM sensor_readings ORDER BY ts DESC LIMIT 5;
```

---

## 服務管理

### 透過 Container Manager UI

| 操作 | 步驟 |
|------|------|
| **查看容器狀態** | Container Manager → 專案/容器 |
| **查看日誌** | 容器 → 右鍵 → 詳細資訊 → 日誌 |
| **重啟容器** | 容器 → 右鍵 → 重新啟動 |
| **停止容器** | 容器 → 右鍵 → 停止 |
| **啟動容器** | 容器 → 右鍵 → 啟動 |
| **重建專案** | 專案 → 右鍵 → 建置 |

### 透過 SSH 終端機

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

# 停止服務 (資料保留於 ./data/ 目錄)
sudo docker compose down

# 更新程式碼後重新部署
sudo docker compose up -d --build

# 清理未使用的 Docker 資源
sudo docker system prune -a -f
```

### 更新應用程式

#### 透過 Container Manager UI

1. 更新專案檔案（透過 File Station 上傳新版本）
2. **Container Manager** → **專案** → `climate-monitor`
3. 右鍵 → **建置**
4. 完成後，容器會自動重新啟動

#### 透過 SSH 終端機

```bash
cd /volume1/docker/climate-monitor
sudo git pull
sudo docker compose up -d --build
```

---

## 自動啟動設定

設定 NAS 開機後自動啟動 Climate Monitor：

1. DSM **控制台** → **任務排程器**
2. **新增** → **觸發的任務** → **使用者定義的指令碼**
3. **一般**：
   - 名稱：`Start Climate Monitor`
   - 使用者：`root`
   - 事件：開機
4. **任務設定** → **執行指令**：

   ```bash
   sleep 60 && cd /volume1/docker/climate-monitor && docker compose up -d
   ```

5. 點選 **確定**

> **說明**：`sleep 60` 確保 Docker 服務完全啟動後再執行。

---

## 下一步

- [Superset 設定與時區技巧](superset-setup.md)
- [故障排除](troubleshooting.md)
- [安全性建議](security.md)
- [備份與還原](backup-restore.md)
