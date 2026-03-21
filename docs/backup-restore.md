# 備份與還原

本文件說明 Climate Monitor 的資料備份策略與還原程序。

---

## 備份項目

| 項目 | 路徑/位置 | 重要性 | 說明 |
|------|-----------|--------|------|
| **CrateDB 資料** | `data/cratedb/` | 高 | 所有歷史監控資料 |
| **環境變數** | `.env` | 高 | 包含密碼與配置 |
| **Superset 元資料** | `data/postgres/` | 中 | 儀表板與資料源設定 |
| **Stale 日誌** | `data/monitor_logs/` | 低 | 連線驗證失敗事件記錄 |
| **程式碼** | Git Repository | 低 | 可從 Git 重新拉取 |

---

## 備份方法

### 方法 1：完整備份

```bash
cd /volume1/docker/climate-monitor
sudo docker compose down

sudo tar -czf /volume1/backups/climate-monitor_$(date +%Y%m%d).tar.gz \
  /volume1/docker/climate-monitor/

sudo docker compose up -d
```

### 方法 2：僅備份 CrateDB

```bash
cd /volume1/docker/climate-monitor
sudo tar -czf /volume1/backups/cratedb_$(date +%Y%m%d).tar.gz data/cratedb/
```

### 方法 3：匯出為 JSON

```bash
docker exec -it cratedb crash --command \
  "COPY sensor_readings TO DIRECTORY '/tmp/backup' WITH (compression='gzip');"
docker cp cratedb:/tmp/backup ./backup_$(date +%Y%m%d)/
```

---

## 還原程序

### 還原完整備份

```bash
sudo docker compose down
sudo tar -xzf /volume1/backups/climate-monitor_YYYYMMDD.tar.gz -C /
sudo chown -R 1000:1000 /volume1/docker/climate-monitor/data/cratedb/
sudo docker compose up -d
```

### 還原 CrateDB 資料

```bash
sudo docker compose down
sudo rm -rf data/cratedb/*
sudo tar -xzf /volume1/backups/cratedb_YYYYMMDD.tar.gz
sudo chown -R 1000:1000 data/cratedb/
sudo docker compose up -d
```

### 從 JSON 匯入

```bash
docker exec -it cratedb crash --command \
  "COPY sensor_readings FROM '/tmp/backup/*.json.gz' WITH (compression='gzip');"
```

---

## 自動備份設定

### Synology Task Scheduler

1. DSM 控制台 → 任務排程器
2. 新增 → 排程的任務 → 使用者定義的指令碼
3. 排程：每日凌晨 3:00
4. 執行指令：

```bash
#!/bin/bash
BACKUP_DIR="/volume1/backups"
PROJECT_DIR="/volume1/docker/climate-monitor"
DATE=$(date +%Y%m%d)

mkdir -p $BACKUP_DIR
cd $PROJECT_DIR
tar -czf $BACKUP_DIR/cratedb_$DATE.tar.gz data/cratedb/
cp $PROJECT_DIR/.env $BACKUP_DIR/env_$DATE.bak

# 清理 30 天前的備份
find $BACKUP_DIR -name "cratedb_*.tar.gz" -mtime +30 -delete
find $BACKUP_DIR -name "env_*.bak" -mtime +30 -delete
```

---

## 備份檢查清單

- [ ] 已設定自動備份排程
- [ ] 備份包含 `.env` 檔案
- [ ] 備份儲存在獨立磁碟或異地
- [ ] 已測試還原程序
- [ ] 已設定備份保留策略

---

## 下一步

- [故障排除](troubleshooting.md)
- [安全性建議](security.md)
