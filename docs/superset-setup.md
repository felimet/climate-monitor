# Superset 設定與時區技巧

本文件說明 Apache Superset 的設定方式與時區處理技巧。

---

## 目錄

- [資料源設定](#資料源設定)
- [時區設定技巧](#時區設定技巧)
- [建立儀表板](#建立儀表板)
- [常用查詢範例](#常用查詢範例)

---

## 資料源設定

系統預設的 `datasources.yaml` 已自動配置 CrateDB 資料源。

### 可用的 Views

| View 名稱           | 描述                | 範例用途        |
|---------------------|---------------------|-----------------|
| `latest_readings`   | 每個設備的最新狀態  | 即時儀表板      |
| `minute_metrics`    | 每分鐘統計          | 高解析度圖表    |
| `hourly_metrics`    | 每小時統計          | 24 小時趨勢     |
| `daily_stats`       | 每日統計            | 長期歷史回顧    |
| `weekly_stats`      | 每週統計            | 週報表          |
| `monthly_stats`     | 每月統計            | 年度分析        |

### 手動新增資料源

1. 登入 Superset
2. Settings → Database Connections → + Database
3. 選擇 PostgreSQL
4. 填入連線資訊：
   - Host: `cratedb`
   - Port: `5432`
   - Database: `doc`
   - Username: `crate`
   - Password: (留空)

---

## 時區設定技巧

### 問題說明

Superset 預設顯示 UTC 時間。由於資料庫儲存的是 `TIMESTAMP WITH TIME ZONE`，需要透過 Calculated Column 將時間轉換為台北時間 (Asia/Taipei)。

### 設定方式

1. 進入 Datasets → 選擇目標 Dataset → Edit
2. 點選 **Calculated Columns** 分頁
3. 點選 **+ Add Calculated Column**
4. 填入以下資訊：

| 欄位 | 值 |
|------|-----|
| **Column Name** | `ts` |
| **Label** | `Time` |
| **SQL Expression** | `timezone('Asia/Taipei', ts)` |
| **Data Type** | `DATETIME`、`TIMESTAMP` |
| **Datetime Format** | `epoch_ms` |
| **Is Temporal** | ✅ 勾選 |

5. 儲存後，在製作圖表時將此欄位選為 **Time Column**

> **注意**：系統預設的 `datasources.yaml` 已為您設定好此計算欄位。

---

## 建立儀表板

### 即時監控儀表板

1. Charts → + Chart
2. 選擇 Dataset: `latest_readings`
3. Chart Type: Big Number with Trendline
4. Metric: `temperature` (AVG)
5. Time Column: `ts`

### 24 小時趨勢圖

1. Charts → + Chart
2. 選擇 Dataset: `hourly_metrics`
3. Chart Type: Time-series Line Chart
4. Metrics: `avg_temp`, `avg_humidity`
5. Time Column: `hour`
6. Time Range: Last 24 hours

### 設備比較圖

1. Charts → + Chart
2. 選擇 Dataset: `hourly_metrics`
3. Chart Type: Time-series Line Chart
4. Metrics: `avg_temp`
5. Dimensions: `device_name`
6. Time Column: `hour`

---

## 常用查詢範例 SQLLab (參考 [Superset 官方文件](https://superset.apache.org/docs/))

### 時間格式化：`date_format` 函數

CrateDB 預設以 epoch 毫秒回傳時間欄位，使用 `date_format` 函數可轉換為可讀格式：

```sql
date_format('%Y-%m-%d %H:%i', hour_asia_taipei) AS hour_taipei
```

**常用格式符號**：

| 符號 | 說明               | 範例 |
|------|--------------------|------|
| `%Y` | 四位年份           | 2026 |
| `%m` | 月份 (01-12)       | 01   |
| `%d` | 日期 (01-31)       | 24   |
| `%H` | 小時 24 制 (00-23) | 09   |
| `%i` | 分鐘 (00-59)       | 27   |
| `%s` | 秒數 (00-59)       | 36   |

### 過去 24 小時的溫度趨勢（台北時間）

```sql
SELECT 
    date_format('%Y-%m-%d %H:%i', hour_asia_taipei) AS hour_taipei,
    device_name,
    avg_temp,
    min_temp,
    max_temp
FROM hourly_metrics 
WHERE hour_asia_taipei >= NOW() - INTERVAL '24' HOUR
ORDER BY hour_asia_taipei DESC;
```

### 每日最高最低溫度

```sql
SELECT 
    date_format('%Y-%m-%d', day_asia_taipei) AS day_taipei,
    device_name,
    max_temp,
    min_temp,
    max_temp - min_temp AS temp_range
FROM daily_stats 
WHERE day_asia_taipei >= NOW() - INTERVAL '7' DAY
ORDER BY day_asia_taipei DESC, device_name;
```

### 低電量警示（電量低於 20%）

```sql
SELECT 
    device_name,
    battery_level,
    date_format('%Y-%m-%d %H:%i', last_seen_asia_taipei) AS last_update
FROM latest_readings 
WHERE battery_level < 20
ORDER BY battery_level ASC;
```

---

## 下一步

- [進階配置](configuration.md)
- [故障排除](troubleshooting.md)
