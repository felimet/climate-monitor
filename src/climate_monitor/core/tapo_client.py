"""Tapo 設備整合模組，使用 python-kasa。"""

import asyncio
from typing import TYPE_CHECKING

from kasa import Credentials, Device, Discover

from climate_monitor.config import Settings
from climate_monitor.models import SensorReading
from climate_monitor.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class TapoClientError(Exception):
    """與 Tapo 設備通訊時發生錯誤。"""


class TapoClient:
    """Tapo H200 網關與 T315 感測器通訊客戶端。

    使用 python-kasa 發現並讀取連接至 Tapo H200 網關的
    溫溼度感測器資料。
    """

    def __init__(self, settings: Settings) -> None:
        """初始化 Tapo 客戶端。

        參數:
            settings: 包含 Tapo 認證資訊的應用程式設定。
        """
        self._settings = settings
        self._credentials = Credentials(
            username=settings.tapo_username,
            password=settings.tapo_password,
        )
        self._hub: Device | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """連接至 Tapo H200 網關。"""
        async with self._lock:
            if self._hub is not None:
                return

            logger.info("正在連接 Tapo H200 網關：%s", self._settings.tapo_host)
            try:
                self._hub = await Discover.discover_single(
                    host=self._settings.tapo_host,
                    credentials=self._credentials,
                )
                await self._hub.update()
                logger.info(
                    "已連接網關：%s（型號：%s）",
                    self._hub.alias,
                    self._hub.model,
                )
            except Exception as e:
                logger.error("連接網關失敗：%s", e)
                raise TapoClientError(f"連接網關失敗：{e}") from e

    async def disconnect(self) -> None:
        """中斷與網關的連線。"""
        async with self._lock:
            if self._hub is not None:
                logger.info("正在中斷 Tapo 網關連線")
                self._hub = None

    async def get_sensor_readings(self) -> list[SensorReading]:
        """從所有 T315 溫溼度感測器讀取資料。

        回傳:
            所有已連接 T315 感測器的讀取資料清單。

        例外:
            TapoClientError: 網關未連接或讀取失敗時。
        """
        if self._hub is None:
            raise TapoClientError("網關未連接。請先呼叫 connect()。")

        readings: list[SensorReading] = []

        try:
            # 更新網關狀態以取得最新感測器資料
            await self._hub.update()

            # 遍歷子設備（連接至網關的感測器）
            for child in self._hub.children:
                # 篩選 T315 溫溼度感測器
                if not self._is_temperature_sensor(child):
                    continue

                reading = await self._read_sensor(child)
                if reading:
                    readings.append(reading)
                    logger.debug(
                        "讀取感測器 %s：溫度=%.1f°C，濕度=%.1f%%",
                        reading.device_name,
                        reading.temperature,
                        reading.humidity,
                    )

        except Exception as e:
            logger.error("讀取感測器失敗：%s", e)
            raise TapoClientError(f"讀取感測器失敗：{e}") from e

        logger.info("已蒐集 %d 筆感測器資料", len(readings))
        return readings

    def _is_temperature_sensor(self, device: Device) -> bool:
        """檢查設備是否為 T315 溫溼度感測器。"""
        # T315 感測器具有 temperature 和 humidity 功能
        features = device.features
        return "temperature" in features and "humidity" in features

    async def _read_sensor(self, device: Device) -> SensorReading | None:
        """從單一感測器設備讀取資料。

        參數:
            device: 要讀取的感測器設備。

        回傳:
            成功時回傳 SensorReading，否則回傳 None。
        """
        try:
            features = device.features

            # 擷取溫度
            temp_feature = features.get("temperature")
            temperature = float(temp_feature.value) if temp_feature else 0.0

            # 擷取濕度
            humidity_feature = features.get("humidity")
            humidity = float(humidity_feature.value) if humidity_feature else 0.0

            # 擷取電池電量
            battery_feature = features.get("battery_level")
            battery_level = int(battery_feature.value) if battery_feature else 0

            # 擷取 RSSI（訊號強度）
            rssi_feature = features.get("rssi")
            rssi = int(rssi_feature.value) if rssi_feature else 0

            # 擷取回報間隔
            report_interval_feature = features.get("report_interval")
            report_interval = (
                int(report_interval_feature.value) if report_interval_feature else 0
            )

            # 擷取裝置時間
            device_time_feature = features.get("device_time")
            device_time = str(device_time_feature.value) if device_time_feature else ""

            return SensorReading.create(
                device_id=device.device_id,
                device_name=device.alias or device.model,
                temperature=temperature,
                humidity=humidity,
                battery_level=battery_level,
                rssi=rssi,
                report_interval=report_interval,
                device_time=device_time,
            )

        except Exception as e:
            logger.warning("讀取感測器 %s 失敗：%s", device.alias, e)
            return None

    async def list_sensors(self) -> list[dict]:
        """列出所有已連接的感測器及其資訊。

        回傳:
            感測器資訊字典清單。
        """
        if self._hub is None:
            raise TapoClientError("網關未連接。請先呼叫 connect()。")

        await self._hub.update()

        sensors = []
        for child in self._hub.children:
            if self._is_temperature_sensor(child):
                sensors.append({
                    "device_id": child.device_id,
                    "alias": child.alias,
                    "model": child.model,
                })

        return sensors
