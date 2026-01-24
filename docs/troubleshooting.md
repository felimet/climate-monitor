# 故障排除指南

本文件整理 Climate Monitor 常見問題與解決方案。

---

## 目錄

- [容器無法啟動](#問題-1容器無法啟動)
- [無法連接 Tapo H200](#問題-2無法連接-tapo-h200)
- [Superset 初始化失敗](#問題-3superset-初始化失敗)
- [CrateDB 無法啟動或資料遺失](#問題-4cratedb-無法啟動或資料遺失)
- [資料未自動寫入 CrateDB](#問題-5資料未自動寫入-cratedb)
- [Superset 圖表顯示時間不正確](#問題-6superset-圖表顯示時間不正確)
- [重建 CrateDB 資料庫](#問題-7重建-cratedb-資料庫清除所有資料)
- [Synology Container Manager GUI 問題](#問題-8synology-container-manager-gui-問題)

---

## 問題 1：容器無法啟動

**症狀**：`docker compose ps` 顯示服務 `Exit` 或持續 `Restarting`

**解決方案**：

1. **查看日誌**：

   ```bash
   sudo docker compose logs <service_name>
   ```

2. **常見錯誤**：

   - **端口衝突**：

     ```bash
     sudo netstat -tulpn | grep -E '4200|4500|8088'
     ```

   - **權限問題**：

     ```bash
     sudo chown -R 1000:1000 cratedb_data/
     ```

   - **記憶體不足**：調整 `docker-compose.yml` 中的 `mem_limit`

---

## 問題 2：無法連接 Tapo H200

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
   - DSM 控制台 → 安全性 → 防火牆

---

## 問題 3：Superset 初始化失敗

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
   sleep 30
   docker compose up superset-init
   ```

3. **檢查日誌**：

   ```bash
   docker compose logs superset-init | tail -50
   ```

---

## 問題 4：CrateDB 無法啟動或資料遺失

**症狀**：CrateDB 容器啟動失敗或查詢不到歷史資料

**解決方案**：

1. **權限問題** (常見於 Linux/NAS)：

   ```bash
   sudo chown -R 1000:1000 cratedb_data/
   sudo chmod -R 755 cratedb_data/
   ```

2. **磁碟空間**：

   ```bash
   df -h
   # 確認儲存路徑有足夠空間
   ```

3. **記憶體不足**：
   - 編輯 `docker-compose.yml`，調整 `CRATE_HEAP_SIZE` 環境變數（預設 2g）

4. **檢查 Volume 掛載**：

   ```bash
   sudo docker compose config | grep -A 5 'cratedb:'
   ```

---

## 問題 5：資料未自動寫入 CrateDB

**症狀**：應用程式運行正常，但資料庫無新資料

**解決方案**：

1. **確認資料表已建立**：
   - 開啟 CrateDB Admin UI: `http://NAS-IP:4200`
   - 執行 `SELECT * FROM sensor_readings LIMIT 10;`
   - 若提示 "Relation unknown"，表示未執行 `scripts/init_db.sql`

2. **檢查應用程式日誌**：

   ```bash
   docker compose logs -f climate-monitor
   # 查看是否有錯誤訊息
   ```

3. **網路隔離問題**：
   - 確認 Docker Compose 中 `climate-monitor` 與 `cratedb` 在同一網路下
   - 檢查 `.env` 中 `CRATEDB_HOST=cratedb`（容器名稱，非 IP）

---

## 問題 6：Superset 圖表顯示時間不正確

**症狀**：圖表中的時間與台灣時間差 8 小時

**解決方案**：

參考 [Superset 設定與時區技巧](superset-setup.md) 中的「時區設定」章節，在 Dataset 中新增 Calculated Column 轉換時區。

---

## 問題 7：重建 CrateDB 資料庫（清除所有資料）

**狀況**：需要完全重置 CrateDB（例如：shard 數量超限、資料損壞、架構變更）

**⚠️ 警告**：此操作將**永久刪除**所有歷史資料，請先備份！

### 步驟 1：確認 Docker Compose 專案路徑

```bash
cd /volume1/docker/climate-monitor/docker
ls -lah docker-compose*.yml
sudo docker compose ps
```

### 步驟 2：停止所有服務

```bash
sudo docker compose down
```

### 步驟 3：刪除 CrateDB Volume

```bash
# 列出所有 volumes，確認實際名稱
sudo docker volume ls | grep crate

# 刪除 CrateDB volume
sudo docker volume rm climate-monitor_cratedb_data
```

> **Volume 名稱說明**：名稱取決於 Docker Compose 專案名稱。若 `docker-compose.yml` 中有 `name: climate-tapo-monitor`，則為 `climate-tapo-monitor_cratedb_data`。

### 步驟 4：重新啟動 CrateDB

```bash
sudo docker compose up -d cratedb
sleep 40
```

### 步驟 5：設定 Shard 上限（重要！）

```bash
curl -s -X POST "http://localhost:4500/_sql" \
  -H "Content-Type: application/json" \
  -d '{"stmt":"SET GLOBAL PERSISTENT cluster.max_shards_per_node = 3000"}' | python3 -m json.tool
```

### 步驟 6：初始化資料庫 Schema

```bash
sudo docker exec cratedb crash < /volume1/docker/climate-monitor/scripts/init_db.sql
```

### 步驟 7：驗證資料表已建立

```bash
curl -s -X POST "http://localhost:4500/_sql" \
  -H "Content-Type: application/json" \
  -d '{"stmt":"SHOW TABLES"}' | python3 -m json.tool
```

### 步驟 8：啟動所有服務

```bash
sudo docker compose up -d
sudo docker compose logs -f climate-monitor
```

---

## 問題 8：Synology Container Manager GUI 問題

**狀況**：透過 Container Manager 介面無法看到或管理容器

**解決方案**：

- **使用 SSH + Docker Compose CLI**：Synology Container Manager 對 Docker Compose 支援有限，建議透過 SSH 使用命令列管理
- **重新整理介面**：有時需要手動重新整理 Container Manager 頁面
- **檢查 Docker Socket 權限**：

  ```bash
  sudo chmod 666 /var/run/docker.sock
  ```

---

## 日誌查詢技巧

### 即時追蹤單一服務

```bash
sudo docker compose logs -f <service_name>
```

### 查看最近 100 行

```bash
sudo docker compose logs --tail=100 <service_name>
```

### 查看特定時間範圍

```bash
sudo docker compose logs --since="2026-01-24T00:00:00" <service_name>
```

### 匯出日誌至檔案

```bash
sudo docker compose logs > logs_$(date +%Y%m%d).txt
```
