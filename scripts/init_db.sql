-- CrateDB schema 初始化腳本（climate-monitor 專用）
-- 此程式在容器首次啟動時自動執行

CREATE TABLE IF NOT EXISTS sensor_readings (
    -- 分區鍵（使用月份分區，由 ts 自動產生對應月份）
    ts TIMESTAMP WITH TIME ZONE NOT NULL,
    month_ts TIMESTAMP WITH TIME ZONE GENERATED ALWAYS AS date_trunc('month', ts),
    
    -- 主鍵組成
    device_id TEXT NOT NULL,
    
    -- 感測器中繼資料
    device_name TEXT,
    
    -- 量測資料
    temperature DOUBLE PRECISION,  -- 單位：°C
    humidity DOUBLE PRECISION,     -- 單位：%RH
    
    -- 設備狀態
    battery_level INTEGER,         -- 單位：0-100%
    rssi INTEGER,                  -- 單位：dBm
    
    PRIMARY KEY (device_id, ts, month_ts)
) CLUSTERED BY (device_id) INTO 4 SHARDS
  PARTITIONED BY (month_ts);

-- -----------------------------------------------------------------------------
-- Views（時區：Asia/Taipei，排序：DESC）
-- -----------------------------------------------------------------------------

-- 1. 最新狀態視圖：顯示每個設備的最後一筆資料
CREATE OR REPLACE VIEW latest_readings AS
SELECT 
    device_name,
    device_id,
    max(ts) AT TIME ZONE 'Asia/Taipei' as last_seen_asia_taipei,
    max_by(temperature, ts) as temperature,
    max_by(humidity, ts) as humidity,
    max_by(battery_level, ts) as battery_level,
    max_by(rssi, ts) as rssi
FROM sensor_readings
GROUP BY device_name, device_id
ORDER BY last_seen_asia_taipei DESC, device_name;

-- 1.1 設備清單視圖：快速查詢所有設備名稱
CREATE OR REPLACE VIEW device_list AS
SELECT device_name, device_id
FROM latest_readings
ORDER BY device_name;

-- 2. 每分鐘統計視圖：適合高解析度近即時圖表
CREATE OR REPLACE VIEW minute_metrics AS
SELECT 
    date_trunc('minute', ts AT TIME ZONE 'Asia/Taipei') as minute_asia_taipei,
    device_name,
    device_id,
    avg(temperature) as avg_temp,
    avg(humidity) as avg_hum,
    count(*) as samples_count
FROM sensor_readings
GROUP BY 1, 2, 3
ORDER BY minute_asia_taipei DESC, device_name;

-- 3. 每小時統計視圖：適合 24 小時趨勢
CREATE OR REPLACE VIEW hourly_metrics AS
SELECT 
    date_trunc('hour', ts AT TIME ZONE 'Asia/Taipei') as hour_asia_taipei,
    device_name,
    device_id,
    avg(temperature) as avg_temp,
    min(temperature) as min_temp,
    max(temperature) as max_temp,
    avg(humidity) as avg_hum,
    count(*) as samples_count
FROM sensor_readings
GROUP BY 1, 2, 3
ORDER BY hour_asia_taipei DESC, device_name;

-- 4. 每日統計視圖：適合月報表
CREATE OR REPLACE VIEW daily_stats AS
SELECT 
    date_trunc('day', ts AT TIME ZONE 'Asia/Taipei') as day_asia_taipei,
    device_name,
    device_id,
    avg(temperature) as avg_temp,
    max(temperature) as max_temp,
    min(temperature) as min_temp,
    avg(humidity) as avg_hum,
    min(battery_level) as min_battery
FROM sensor_readings
GROUP BY 1, 2, 3
ORDER BY day_asia_taipei DESC, device_name;

-- 5. 每週統計視圖：適合長期趨勢觀察
CREATE OR REPLACE VIEW weekly_stats AS
SELECT 
    date_trunc('week', ts AT TIME ZONE 'Asia/Taipei') as week_asia_taipei,
    device_name,
    device_id,
    avg(temperature) as avg_temp,
    max(temperature) as max_temp,
    min(temperature) as min_temp,
    avg(humidity) as avg_hum
FROM sensor_readings
GROUP BY 1, 2, 3
ORDER BY week_asia_taipei DESC, device_name;

-- 6. 每月統計視圖：適合年度總結
CREATE OR REPLACE VIEW monthly_stats AS
SELECT 
    date_trunc('month', ts AT TIME ZONE 'Asia/Taipei') as month_asia_taipei,
    device_name,
    device_id,
    avg(temperature) as avg_temp,
    max(temperature) as max_temp,
    min(temperature) as min_temp,
    avg(humidity) as avg_hum,
    min(battery_level) as min_battery
FROM sensor_readings
GROUP BY 1, 2, 3
ORDER BY month_asia_taipei DESC, device_name;

-- -----------------------------------------------------------------------------
-- 常用查詢範例 (Query Usage Examples)
-- -----------------------------------------------------------------------------

-- 範例 1: 查詢特定設備的詳細記錄 (Query specific device)
-- SELECT * FROM minute_metrics 
-- WHERE device_name = 'Tapo-T315-a' 
-- ORDER BY minute_asia_taipei DESC LIMIT 100;

-- 範例 2: 多設備比較 (Compare multiple devices)
-- SELECT hour_asia_taipei, device_name, avg_temp 
-- FROM hourly_metrics 
-- WHERE device_name IN ('Tapo-T315-a', 'Living Room')
-- ORDER BY hour_asia_taipei DESC, device_name;
