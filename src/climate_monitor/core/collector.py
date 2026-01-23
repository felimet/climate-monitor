"""感測器資料蒐集服務。"""

import asyncio
from datetime import datetime, timezone

from climate_monitor.config import Settings
from climate_monitor.core.tapo_client import TapoClient, TapoClientError
from climate_monitor.infra.database import CrateDBClient, DatabaseError
from climate_monitor.models import CollectorStats
from climate_monitor.utils.logging import get_logger

logger = get_logger(__name__)


class SensorCollector:
    """蒐集感測器資料並儲存至資料庫的服務。

    定期從 Tapo T315 感測器（透過 H200 網關）讀取資料，
    並將讀取結果插入 CrateDB。
    """

    def __init__(
        self,
        settings: Settings,
        tapo_client: TapoClient,
        db_client: CrateDBClient,
    ) -> None:
        """初始化蒐集器服務。

        參數:
            settings: 應用程式設定。
            tapo_client: Tapo 設備通訊客戶端。
            db_client: 資料庫操作客戶端。
        """
        self._settings = settings
        self._tapo = tapo_client
        self._db = db_client
        self._running = False
        self._stats = CollectorStats()

    @property
    def stats(self) -> CollectorStats:
        """取得蒐集器統計資訊。"""
        return self._stats

    async def start(self) -> None:
        """啟動資料蒐集迴圈。"""
        logger.info(
            "啟動感測器蒐集器（間隔：%d 秒）",
            self._settings.collection_interval,
        )

        # 連接至 Tapo 網關
        await self._tapo.connect()

        # 列出已發現的感測器
        sensors = await self._tapo.list_sensors()
        self._stats.sensors_discovered = [s["alias"] for s in sensors]
        logger.info(
            "發現 %d 個感測器：%s",
            len(sensors),
            "、".join(self._stats.sensors_discovered),
        )

        self._running = True
        await self._collection_loop()

    async def stop(self) -> None:
        """停止資料蒐集迴圈。"""
        logger.info("正在停止感測器蒐集器")
        self._running = False
        await self._tapo.disconnect()

    async def _collection_loop(self) -> None:
        """主要蒐集迴圈。"""
        while self._running:
            try:
                await self._collect_and_store()
            except Exception as e:
                logger.error("蒐集週期失敗：%s", e)
                self._stats.errors += 1

            # 等待下一個蒐集間隔
            await asyncio.sleep(self._settings.collection_interval)

    async def _collect_and_store(self) -> None:
        """蒐集感測器讀取資料並儲存至資料庫。"""
        # 從所有感測器蒐集資料
        try:
            readings = await self._tapo.get_sensor_readings()
            self._stats.readings_collected += len(readings)
        except TapoClientError as e:
            logger.error("蒐集資料失敗：%s", e)
            raise

        if not readings:
            logger.warning("未蒐集到感測器資料")
            return

        # 記錄讀取資料
        for reading in readings:
            logger.info(
                "感測器 %s：%.1f°C、%.1f%% 濕度、電池=%d%%、訊號=%ddBm",
                reading.device_name,
                reading.temperature,
                reading.humidity,
                reading.battery_level,
                reading.rssi,
            )

        # 儲存至資料庫
        try:
            count = self._db.insert_readings(readings)
            self._stats.readings_saved += count
            self._stats.last_collection = datetime.now(timezone.utc)
            logger.debug("已儲存 %d 筆資料至資料庫", count)
        except DatabaseError as e:
            logger.error("儲存資料失敗：%s", e)
            raise

    async def collect_once(self) -> list:
        """執行單次蒐集週期。

        適用於測試或一次性蒐集。

        回傳:
            已蒐集的讀取資料清單。
        """
        await self._tapo.connect()

        try:
            readings = await self._tapo.get_sensor_readings()
            if readings:
                self._db.insert_readings(readings)
            return readings
        finally:
            await self._tapo.disconnect()
