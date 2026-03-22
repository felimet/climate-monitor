"""感測器資料蒐集服務。"""

import asyncio
from dataclasses import replace
from datetime import datetime, timezone

from climate_monitor.config import Settings
from climate_monitor.core.tapo_client import TapoClient, TapoClientError
from climate_monitor.core.validator import (
    SensorSnapshot,
    T315ConnectionValidator,
)
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
        self._validator = T315ConnectionValidator(
            rssi_threshold=settings.validator_rssi_threshold,
            max_frozen_count=settings.validator_max_frozen_count,
            history_size=settings.validator_history_size,
            min_failed_checks=settings.validator_min_failed_checks,
            time_frozen_threshold=settings.validator_time_frozen_threshold,
        )

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

        # 驗證並記錄讀取資料
        validated_readings = []
        for reading in readings:
            snapshot = SensorSnapshot(
                temperature=reading.temperature,
                humidity=reading.humidity,
                rssi=reading.rssi,
                report_interval=reading.report_interval,
                device_time=reading.device_time,
            )
            result = self._validator.validate(reading.device_id, snapshot)

            # 所有讀數都寫入驗證檢查結果欄位
            check_fields = dict(
                failed_checks=result.failed_checks,
                check_rssi_weak=result.check_rssi_weak,
                check_rssi_frozen=result.check_rssi_frozen,
                check_temp_frozen=result.check_temp_frozen,
                check_time_frozen=result.check_time_frozen,
            )

            if result.is_valid:
                logger.info(
                    "感測器 %s：%.1f°C、%.1f%% 濕度、電池=%d%%、訊號=%ddBm",
                    reading.device_name,
                    reading.temperature,
                    reading.humidity,
                    reading.battery_level,
                    reading.rssi,
                )
                validated_readings.append(
                    replace(reading, **check_fields)
                )
            else:
                stale_reasons = "; ".join(result.reasons)
                logger.warning(
                    "感測器 %s 資料不可信（%d/%d 項失敗）：訊號=%ddBm | %s",
                    reading.device_name,
                    result.failed_checks,
                    self._settings.validator_min_failed_checks,
                    reading.rssi,
                    stale_reasons,
                )
                validated_readings.append(
                    replace(
                        reading,
                        temperature=None,
                        humidity=None,
                        is_valid=False,
                        stale_reasons=stale_reasons,
                        **check_fields,
                    )
                )

        # 儲存至資料庫（stale 資料的 temperature/humidity 為 NULL）
        try:
            count = self._db.insert_readings(validated_readings)
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
