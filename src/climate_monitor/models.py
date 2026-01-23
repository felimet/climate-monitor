"""感測器資料模型定義。"""

from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo


@dataclass(frozen=True, slots=True)
class SensorReading:
    """表示單筆溫溼度感測器讀取資料。

    屬性:
        timestamp: 讀取時間（Asia/Taipei）。
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
    temperature: float
    humidity: float
    battery_level: int
    rssi: int

    @classmethod
    def create(
        cls,
        device_id: str,
        device_name: str,
        temperature: float,
        humidity: float,
        battery_level: int,
        rssi: int,
    ) -> "SensorReading":
        """建立帶有當前 Asia/Taipei 時間戳記的讀取資料。"""
        return cls(
            timestamp=datetime.now(ZoneInfo("Asia/Taipei")),
            device_id=device_id,
            device_name=device_name,
            temperature=temperature,
            humidity=humidity,
            battery_level=battery_level,
            rssi=rssi,
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
        }


@dataclass
class CollectorStats:
    """資料收集器服務統計資訊。"""

    readings_collected: int = 0
    readings_saved: int = 0
    errors: int = 0
    last_collection: datetime | None = None
    sensors_discovered: list[str] = field(default_factory=list)
