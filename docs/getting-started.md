# 快速開始

本文件說明如何在本地開發環境中快速啟動 Climate Monitor 系統。

> **NAS 使用者**：請參閱 [NAS 部署指南](nas-deployment.md)

---

## 環境需求

### 硬體

- **Tapo H200 網關** + **T315 感測器**（一個或多個）
- 開發機與 Tapo 設備需在**同一區域網路**

### 軟體

| 項目 | 版本需求 |
|------|----------|
| Docker | 20.10+ |
| Docker Compose | 2.0+ |
| Python | 3.11+ (選用，本地開發時) |
| [uv](https://github.com/astral-sh/uv) | 最新版 (選用，本地開發時) |

---

## 部署方式選擇

| 方式 | 適用情境 | Docker Compose 檔案 |
|------|----------|---------------------|
| **生產部署** | Synology NAS 或伺服器 | `docker/docker-compose.prod.yml` |
| **本地開發** | Windows/Linux 開發機 | `docker/docker-compose.pc.yml` |

---

## 本地開發流程

### 步驟 1：安裝 uv

```bash
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Linux/macOS
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 步驟 2：初始化 Python 環境

```bash
uv sync
```

### 步驟 3：設定環境變數

```bash
cp .env.example .env
```

編輯 `.env` 檔案，填入以下**必填**項目：

```env
# Tapo H200 設定
TAPO_HOST=192.168.1.XXX          # 填入 H200 的實際 IP
TAPO_USERNAME=your@email.com     # Tapo App 帳號
TAPO_PASSWORD=your_password      # Tapo App 密碼

# Superset 管理員
SUPERSET_SECRET_KEY=<使用 openssl rand -base64 42 產生>
SUPERSET_ADMIN_USERNAME=admin
SUPERSET_ADMIN_PASSWORD=<強密碼>
SUPERSET_ADMIN_EMAIL=admin@example.com

# Superset PostgreSQL
SUPERSET_POSTGRES_PASSWORD=<資料庫密碼>
```

### 步驟 4：啟動 Docker 服務

```bash
cd docker
docker compose -f docker-compose.pc.yml up -d
```

### 步驟 5：初始化 Superset

```bash
# 等待服務啟動完成 (約 30 秒)，首次部署才需執行
docker compose -f docker-compose.pc.yml --profile init up superset-init
```

> **注意**：此步驟會建立 Superset 管理員帳號、設定資料源。僅首次部署時需執行一次，完成後容器會自動停止。

### 步驟 6：初始化 CrateDB

1. 開啟瀏覽器：`http://localhost:4200`
2. 點選左側 **Console** 分頁
3. 複製 `scripts/init_db.sql` 的內容並貼上
4. 點選 **Execute Query** 或按 `Ctrl+Enter`

### 步驟 7：執行 Python 應用程式

```bash
cd ..
uv run climate-monitor
```

---

## 驗證部署

### 檢查容器狀態

```bash
docker compose -f docker-compose.pc.yml ps
```

**期望結果**：所有服務狀態為 `Up`，無 `Restarting` 或 `Exit` 狀態。

### 服務訪問

| 服務               | URL                          | 說明                          |
|--------------------|------------------------------|-------------------------------|
| **CrateDB Admin**  | http://localhost:4200        | 資料庫管理介面                |
| **Superset**       | http://localhost:8088        | 視覺化儀表板                  |

### 確認資料寫入

在 CrateDB Admin UI 執行：

```sql
SELECT COUNT(*) FROM sensor_readings;
SELECT * FROM sensor_readings WHERE is_valid = true ORDER BY ts DESC LIMIT 5;
```

等待 1-2 個採集週期後，應可看到資料。

---

## 下一步

- [Superset 設定與時區技巧](superset-setup.md)
- [進階配置](configuration.md)
- [故障排除](troubleshooting.md)
