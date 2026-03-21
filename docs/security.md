# 安全性建議

本文件說明 Climate Monitor 的安全性配置與最佳實踐。

---

## 目錄

- [密碼安全](#密碼安全)
- [網路隔離](#網路隔離)
- [Cloudflare Tunnel 設定](#cloudflare-tunnel-設定)
- [Cloudflare Access 進階防護](#cloudflare-access-進階防護)
- [定期更新](#定期更新)

---

## 密碼安全

### 1. 變更所有預設密碼

**務必修改 `.env` 中的以下項目**：

```env
SUPERSET_ADMIN_PASSWORD=<使用強密碼>
SUPERSET_SECRET_KEY=<使用 openssl rand -base64 42 產生>
SUPERSET_POSTGRES_PASSWORD=<資料庫密碼>
```

### 2. 產生安全的 Secret Key

```bash
# Linux/macOS
openssl rand -base64 42

# Windows (PowerShell)
[Convert]::ToBase64String((1..42 | ForEach-Object { Get-Random -Maximum 256 }) -as [byte[]])
```

### 3. 密碼強度建議

- 至少 16 個字元
- 包含大小寫字母、數字與特殊符號
- 不使用字典單字或個人資訊

---

## 網路隔離

### 端口開放策略

| 服務                | 內部端口 | 外部開放 | 說明                        |
|---------------------|----------|----------|-----------------------------| 
| climate-monitor     | -        | ❌       | 無需對外                    |
| cratedb (HTTP)      | 4200     | ❌       | 僅內部管理使用              |
| cratedb (PSQL)      | 4500     | ❌       | Superset 內部連線           |
| superset            | 8088     | ✅       | 透過 Cloudflare Tunnel      |
| db (PostgreSQL)     | 5432     | ❌       | 僅 Superset 使用            |
| redis               | 6379     | ❌       | 僅 Superset 使用            |

### DSM 防火牆設定 (Synology NAS)

1. 控制台 → 安全性 → 防火牆
2. 編輯規則，建議配置：

| 端口 | 來源 | 動作 |
|------|------|------|
| 8088 | 信任的 IP 範圍 | 允許 |
| 4200, 4500 | 127.0.0.1 | 允許 |
| 4200, 4500 | 其他 | 拒絕 |

### Docker 網路隔離

在 `docker-compose.yml` 中，服務預設在同一個 Docker 網路內通訊。若需進一步隔離：

```yaml
networks:
  frontend:
  backend:

services:
  superset:
    networks:
      - frontend
      - backend
  
  cratedb:
    networks:
      - backend  # 不暴露至 frontend
```

---

## Cloudflare Tunnel 設定

### 優點

- **無需開放 NAS 端口至公網**
- **自動 HTTPS 加密**
- **DDoS 防護**
- **Zero Trust 架構**

### 設定步驟

1. 登入 [Cloudflare Zero Trust Dashboard](https://one.dash.cloudflare.com/)

2. 建立 Tunnel：
   - 前往 Networks → Tunnels
   - 點選 Create a tunnel
   - 選擇 Cloudflared
   - 複製 Token

3. 設定環境變數：

   ```env
   TUNNEL_TOKEN=<your_tunnel_token>
   ```

4. 設定 Public Hostname：
   - 新增 Hostname（例如：`superset.your-domain.com`）
   - Type: HTTP
   - URL: `superset:8088`

5. 重新啟動服務：

   ```bash
   sudo docker compose up -d cloudflared
   ```

### 存取方式

- **Superset**: `https://superset.your-domain.com`
- **CrateDB** (選填，不建議對外開放): `https://climate-db.your-domain.com`

> **安全提醒**：CrateDB Admin UI 對外開放有安全風險，建議僅開放 Superset 或使用 Cloudflare Access 進行身份驗證。

---

## Cloudflare Access 進階防護

為 Superset 設定額外的身份驗證層：

### 步驟 1：建立 Access Policy

1. Cloudflare Zero Trust Dashboard → Access → Applications
2. Add an application → Self-hosted
3. 填入 Subdomain（例如：`superset`）與 Domain

### 步驟 2：設定驗證規則

| 規則類型 | 設定 |
|----------|------|
| **Email** | 允許特定 Email（例如：`admin@example.com`）|
| **Email Domain** | 允許整個網域（例如：`@example.com`）|
| **IP Range** | 允許特定 IP 範圍 |

### 步驟 3：套用至 Tunnel

在 Tunnel 的 Public Hostname 設定中，啟用 Access Policy。

---

## 定期更新

### 拉取最新程式碼與映像檔

```bash
cd /volume1/docker/climate-monitor
sudo git pull
sudo docker compose pull
sudo docker compose up -d --build
```

### 自動更新程式碼

建立 `/volume1/docker/climate-monitor/scripts/update.sh`：

```bash
#!/bin/bash
cd /volume1/docker/climate-monitor
git pull
docker compose pull
docker compose up -d --build
docker system prune -f
```

### 設定定期執行 (Synology Task Scheduler)

1. DSM 控制台 → 任務排程器
2. 新增 → 排程的任務 → 使用者定義的指令碼
3. 排程：每週執行
4. 執行指令：`/volume1/docker/climate-monitor/scripts/update.sh`

---

## 連線驗證器安全考量

### Stale 日誌檔案權限

驗證器將 stale 事件寫入 `/app/logs/stale.log`（Docker 掛載於 `./data/monitor_logs/`）。此日誌包含感測器 ID、RSSI 值、溫溼度讀數等設備資訊。雖然這些資料本身不屬於高敏感資訊，仍應注意：

- **檔案權限**：確保 `./data/monitor_logs/` 目錄僅限管理者存取（`chmod 750`），避免同一台 NAS 上的其他使用者讀取設備拓撲資訊
- **日誌輪替**：日誌檔案會持續增長，建議搭配 Docker 的 `json-file` logging driver 限制（已在 `docker-compose.yml` 中設定 `max-size: 10m, max-file: 3`）

### stale_reasons 欄位資訊揭露

`stale_reasons` 欄位記錄了驗證失敗的具體原因，包含 RSSI 數值、溫溼度值、凍結次數等。若 Superset 儀表板對外開放（透過 Cloudflare Tunnel），需考量：

- **設備拓撲推斷**：持續觀察 RSSI 值與凍結模式，可推斷感測器的物理位置與 Hub 的距離關係
- **建議**：對外公開的 Dashboard 應使用 `WHERE is_valid = TRUE` 過濾，僅顯示有效資料。將含有 `stale_reasons` 的診斷用 Dashboard 限制於管理員角色

### 驗證器資源消耗

驗證器為每個 device_id 維護獨立的歷史紀錄（`deque(maxlen=history_size)`）。在正常設定下（`history_size=20`，3-5 個感測器），記憶體開銷可忽略。但若：

- **大量感測器**：歷史紀錄隨裝置數線性增長。100 個感測器 × 20 筆快照 ≈ 2000 個 `SensorSnapshot` 物件，仍在合理範圍內
- **極短採樣間隔**：`COLLECTION_INTERVAL=10` 搭配 `FROZEN_WINDOW=300` 需要 30 筆歷史，增加每次驗證的迴圈比對開銷。在 NAS 等低效能環境中，建議監控 CPU 使用率

---

## 安全性檢查清單

- [ ] 已變更所有預設密碼
- [ ] 已產生強 Secret Key
- [ ] 已設定防火牆規則
- [ ] 已啟用 Cloudflare Tunnel
- [ ] 已設定 Cloudflare Access（選用）
- [ ] 已設定定期更新排程
- [ ] 已備份 `.env` 檔案至安全位置

---

## 下一步

- [備份與還原](backup-restore.md)
- [故障排除](troubleshooting.md)
