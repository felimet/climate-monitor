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
