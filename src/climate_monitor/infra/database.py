"""CrateDB 資料庫操作模組。"""

from contextlib import contextmanager
from typing import Any, Generator

from crate import client

from climate_monitor.config import Settings
from climate_monitor.models import SensorReading
from climate_monitor.utils.logging import get_logger

logger = get_logger(__name__)

# 感測器讀取資料表 Schema
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS sensor_readings (
    ts TIMESTAMP WITH TIME ZONE NOT NULL,
    device_id TEXT NOT NULL,
    device_name TEXT,
    temperature DOUBLE PRECISION,
    humidity DOUBLE PRECISION,
    battery_level INTEGER,
    rssi INTEGER,
    report_interval INTEGER,
    device_time TEXT,
    is_valid BOOLEAN,
    stale_reasons TEXT,
    failed_checks INTEGER DEFAULT 0,
    check_rssi_weak BOOLEAN DEFAULT FALSE,
    check_rssi_frozen BOOLEAN DEFAULT FALSE,
    check_temp_frozen BOOLEAN DEFAULT FALSE,
    check_time_frozen BOOLEAN DEFAULT FALSE,
    month_ts TIMESTAMP WITH TIME ZONE GENERATED ALWAYS AS date_trunc('month', ts),
    PRIMARY KEY (device_id, ts, month_ts)
) CLUSTERED BY (device_id) INTO 1 SHARDS
  PARTITIONED BY (month_ts)
"""

# 確保舊表補齊新欄位（CREATE TABLE IF NOT EXISTS 不會自動新增欄位）
MIGRATE_COLUMNS_SQL = [
    "ALTER TABLE sensor_readings ADD COLUMN IF NOT EXISTS is_valid BOOLEAN",
    "ALTER TABLE sensor_readings ADD COLUMN IF NOT EXISTS stale_reasons TEXT",
    "ALTER TABLE sensor_readings ADD COLUMN IF NOT EXISTS failed_checks INTEGER DEFAULT 0",
    "ALTER TABLE sensor_readings ADD COLUMN IF NOT EXISTS check_rssi_weak BOOLEAN DEFAULT FALSE",
    "ALTER TABLE sensor_readings ADD COLUMN IF NOT EXISTS check_rssi_frozen BOOLEAN DEFAULT FALSE",
    "ALTER TABLE sensor_readings ADD COLUMN IF NOT EXISTS check_temp_frozen BOOLEAN DEFAULT FALSE",
    "ALTER TABLE sensor_readings ADD COLUMN IF NOT EXISTS check_time_frozen BOOLEAN DEFAULT FALSE",
]

CREATE_VIEWS_SQL = [
    """
    CREATE OR REPLACE VIEW latest_readings AS
    SELECT
        device_name,
        device_id,
        timezone('Asia/Taipei', max(ts)) as last_seen_asia_taipei,
        max_by(temperature, ts) as temperature,
        max_by(humidity, ts) as humidity,
        max_by(battery_level, ts) as battery_level,
        max_by(rssi, ts) as rssi,
        max_by(is_valid, ts) as is_valid,
        max_by(failed_checks, ts) as failed_checks,
        max_by(check_rssi_weak, ts) as check_rssi_weak,
        max_by(check_rssi_frozen, ts) as check_rssi_frozen,
        max_by(check_temp_frozen, ts) as check_temp_frozen,
        max_by(check_time_frozen, ts) as check_time_frozen
    FROM sensor_readings
    GROUP BY device_name, device_id
    ORDER BY last_seen_asia_taipei DESC, device_name
    """,
    """
    CREATE OR REPLACE VIEW device_list AS
    SELECT device_name, device_id
    FROM latest_readings
    ORDER BY device_name
    """,
    """
    CREATE OR REPLACE VIEW minute_metrics AS
    SELECT
        date_trunc('minute', 'Asia/Taipei', ts) as minute_asia_taipei,
        device_name,
        device_id,
        avg(temperature) as avg_temp,
        avg(humidity) as avg_hum,
        count(*) as samples_count,
        count(*) FILTER (WHERE is_valid = FALSE) as stale_count
    FROM sensor_readings
    GROUP BY 1, 2, 3
    ORDER BY minute_asia_taipei DESC, device_name
    """,
    """
    CREATE OR REPLACE VIEW hourly_metrics AS
    SELECT
        date_trunc('hour', 'Asia/Taipei', ts) as hour_asia_taipei,
        device_name,
        device_id,
        avg(temperature) as avg_temp,
        min(temperature) as min_temp,
        max(temperature) as max_temp,
        avg(humidity) as avg_hum,
        count(*) as samples_count,
        count(*) FILTER (WHERE is_valid = FALSE) as stale_count
    FROM sensor_readings
    GROUP BY 1, 2, 3
    ORDER BY hour_asia_taipei DESC, device_name
    """,
    """
    CREATE OR REPLACE VIEW daily_stats AS
    SELECT
        date_trunc('day', 'Asia/Taipei', ts) as day_asia_taipei,
        device_name,
        device_id,
        avg(temperature) as avg_temp,
        max(temperature) as max_temp,
        min(temperature) as min_temp,
        avg(humidity) as avg_hum,
        min(battery_level) as min_battery,
        count(*) as samples_count,
        count(*) FILTER (WHERE is_valid = FALSE) as stale_count
    FROM sensor_readings
    GROUP BY 1, 2, 3
    ORDER BY day_asia_taipei DESC, device_name
    """,
    """
    CREATE OR REPLACE VIEW weekly_stats AS
    SELECT
        date_trunc('week', 'Asia/Taipei', ts) as week_asia_taipei,
        device_name,
        device_id,
        avg(temperature) as avg_temp,
        max(temperature) as max_temp,
        min(temperature) as min_temp,
        avg(humidity) as avg_hum,
        count(*) as samples_count,
        count(*) FILTER (WHERE is_valid = FALSE) as stale_count
    FROM sensor_readings
    GROUP BY 1, 2, 3
    ORDER BY week_asia_taipei DESC, device_name
    """,
    """
    CREATE OR REPLACE VIEW monthly_stats AS
    SELECT
        date_trunc('month', 'Asia/Taipei', ts) as month_asia_taipei,
        device_name,
        device_id,
        avg(temperature) as avg_temp,
        max(temperature) as max_temp,
        min(temperature) as min_temp,
        avg(humidity) as avg_hum,
        min(battery_level) as min_battery,
        count(*) as samples_count,
        count(*) FILTER (WHERE is_valid = FALSE) as stale_count
    FROM sensor_readings
    GROUP BY 1, 2, 3
    ORDER BY month_asia_taipei DESC, device_name
    """,
    """
    CREATE OR REPLACE VIEW stale_events AS
    SELECT
        timezone('Asia/Taipei', ts) as event_time_asia_taipei,
        device_name,
        device_id,
        stale_reasons,
        failed_checks,
        check_rssi_weak,
        check_rssi_frozen,
        check_temp_frozen,
        check_time_frozen,
        rssi,
        battery_level
    FROM sensor_readings
    WHERE is_valid = FALSE
    ORDER BY ts DESC
    """,
]

INSERT_SQL = """
INSERT INTO sensor_readings (ts, device_id, device_name, temperature, humidity, battery_level, rssi, report_interval, device_time, is_valid, stale_reasons, failed_checks, check_rssi_weak, check_rssi_frozen, check_temp_frozen, check_time_frozen)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


class DatabaseError(Exception):
    """資料庫操作錯誤。"""


class CrateDBClient:
    """CrateDB 操作客戶端。

    管理連線池並提供感測器資料儲存方法。
    """

    def __init__(self, settings: Settings) -> None:
        """初始化資料庫客戶端。

        參數:
            settings: 包含 CrateDB 設定的應用程式設定。
        """
        self._settings = settings
        self._connection: Any = None

    @contextmanager
    def _get_cursor(self) -> Generator[Any, None, None]:
        """取得資料庫游標並自動清理。

        產出:
            資料庫游標。
        """
        if self._connection is None:
            raise DatabaseError("資料庫未連接。請先呼叫 connect()。")

        cursor = self._connection.cursor()
        try:
            yield cursor
        finally:
            cursor.close()

    def connect(self) -> None:
        """建立與 CrateDB 的連線。"""
        if self._connection is not None:
            return

        url = f"{self._settings.cratedb_host}:{self._settings.cratedb_port}"
        logger.info("正在連接 CrateDB：%s", url)

        try:
            self._connection = client.connect(url)
            logger.info("已連接 CrateDB")
        except Exception as e:
            logger.error("連接 CrateDB 失敗：%s", e)
            raise DatabaseError(f"連接 CrateDB 失敗：{e}") from e

    def disconnect(self) -> None:
        """關閉資料庫連線。"""
        if self._connection is not None:
            logger.info("正在中斷 CrateDB 連線")
            self._connection.close()
            self._connection = None

    def initialize_schema(self) -> None:
        """建立 sensor_readings 資料表與 Views（如不存在）。

        若資料表已存在但缺少新版欄位，會自動透過 ALTER TABLE 補齊。
        """
        logger.info("正在初始化資料庫 Schema")
        with self._get_cursor() as cursor:
            # 建立資料表
            cursor.execute(CREATE_TABLE_SQL)

            # 補齊舊表可能缺少的欄位
            for alter_sql in MIGRATE_COLUMNS_SQL:
                try:
                    cursor.execute(alter_sql)
                except Exception:
                    # 欄位已存在時 CrateDB 會拋出異常，安全忽略
                    pass

            # 建立 Views
            for view_sql in CREATE_VIEWS_SQL:
                cursor.execute(view_sql)

        logger.info("Schema 初始化完成")

    def insert_reading(self, reading: SensorReading) -> None:
        """插入單筆感測器讀取資料。

        參數:
            reading: 要插入的感測器讀取資料。
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                INSERT_SQL,
                (
                    reading.timestamp.isoformat(),
                    reading.device_id,
                    reading.device_name,
                    reading.temperature,
                    reading.humidity,
                    reading.battery_level,
                    reading.rssi,
                    reading.report_interval,
                    reading.device_time,
                    reading.is_valid,
                    reading.stale_reasons,
                    reading.failed_checks,
                    reading.check_rssi_weak,
                    reading.check_rssi_frozen,
                    reading.check_temp_frozen,
                    reading.check_time_frozen,
                ),
            )

    def insert_readings(self, readings: list[SensorReading]) -> int:
        """批次插入多筆感測器讀取資料。

        參數:
            readings: 要插入的感測器讀取資料清單。

        回傳:
            已插入的資料筆數。
        """
        if not readings:
            return 0

        with self._get_cursor() as cursor:
            values = [
                (
                    r.timestamp.isoformat(),
                    r.device_id,
                    r.device_name,
                    r.temperature,
                    r.humidity,
                    r.battery_level,
                    r.rssi,
                    r.report_interval,
                    r.device_time,
                    r.is_valid,
                    r.stale_reasons,
                    r.failed_checks,
                    r.check_rssi_weak,
                    r.check_rssi_frozen,
                    r.check_temp_frozen,
                    r.check_time_frozen,
                )
                for r in readings
            ]
            cursor.executemany(INSERT_SQL, values)

        logger.debug("已插入 %d 筆資料", len(readings))
        return len(readings)

    def health_check(self) -> bool:
        """檢查資料庫連線狀態。

        回傳:
            資料庫可達時回傳 True。
        """
        try:
            with self._get_cursor() as cursor:
                cursor.execute("SELECT 1")
                return True
        except Exception as e:
            logger.warning("健康檢查失敗：%s", e)
            return False

    def get_latest_readings(self, limit: int = 10) -> list[dict]:
        """取得最近的感測器讀取資料。

        參數:
            limit: 回傳的最大資料筆數。

        回傳:
            讀取資料字典清單。
        """
        query = """
        SELECT ts, device_id, device_name, temperature, humidity, battery_level, rssi
        FROM sensor_readings
        ORDER BY ts DESC
        LIMIT ?
        """
        with self._get_cursor() as cursor:
            cursor.execute(query, (limit,))
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
