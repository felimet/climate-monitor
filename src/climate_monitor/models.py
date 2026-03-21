"""感測器資料模型定義。"""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class SensorReading:
    """表示單筆溫溼度感測器讀取資料。

    屬性:
        timestamp: 讀取時間（UTC）。
        device_id: 感測器裝置唯一識別碼。
        device_name: 人類可讀的感測器名稱。
        temperature: 溫度（攝氏度）。
        humidity: 相對濕度百分比。
        battery_level: 電池電量百分比（0-100）。
        rssi: Wi-Fi 訊號強度（dBm）。
    """

    timestamp: datetime
    device_id: str
    device_name: str
    temperature: float | None
    humidity: float | None
    battery_level: int
    rssi: int
    report_interval: int = 0
    device_time: str = ""
    is_valid: bool = True
    stale_reasons: str = ""
    failed_checks: int = 0
    check_rssi_weak: bool = False
    check_rssi_frozen: bool = False
    check_temp_frozen: bool = False
    check_time_frozen: bool = False

    @classmethod
    def create(
        cls,
        device_id: str,
        device_name: str,
        temperature: float | None,
        humidity: float | None,
        battery_level: int,
        rssi: int,
        report_interval: int = 0,
        device_time: str = "",
        is_valid: bool = True,
        stale_reasons: str = "",
        failed_checks: int = 0,
        check_rssi_weak: bool = False,
        check_rssi_frozen: bool = False,
        check_temp_frozen: bool = False,
        check_time_frozen: bool = False,
    ) -> "SensorReading":
        """建立帶有當前 UTC 時間戳記的讀取資料。"""
        return cls(
            timestamp=datetime.now(timezone.utc),
            device_id=device_id,
            device_name=device_name,
            temperature=temperature,
            humidity=humidity,
            battery_level=battery_level,
            rssi=rssi,
            report_interval=report_interval,
            device_time=device_time,
            is_valid=is_valid,
            stale_reasons=stale_reasons,
            failed_checks=failed_checks,
            check_rssi_weak=check_rssi_weak,
            check_rssi_frozen=check_rssi_frozen,
            check_temp_frozen=check_temp_frozen,
            check_time_frozen=check_time_frozen,
        )

    def to_dict(self) -> dict:
        """轉換為字典格式，用於資料庫插入。"""
        return {
            "ts": self.timestamp.isoformat(),
            "device_id": self.device_id,
            "device_name": self.device_name,
            "temperature": self.temperature,
            "humidity": self.humidity,
            "battery_level": self.battery_level,
            "rssi": self.rssi,
            "report_interval": self.report_interval,
            "device_time": self.device_time,
            "is_valid": self.is_valid,
            "stale_reasons": self.stale_reasons,
            "failed_checks": self.failed_checks,
            "check_rssi_weak": self.check_rssi_weak,
            "check_rssi_frozen": self.check_rssi_frozen,
            "check_temp_frozen": self.check_temp_frozen,
            "check_time_frozen": self.check_time_frozen,
        }


@dataclass
class CollectorStats:
    """資料收集器服務統計資訊。"""

    readings_collected: int = 0
    readings_saved: int = 0
    errors: int = 0
    last_collection: datetime | None = None
    sensors_discovered: list[str] = field(default_factory=list)
