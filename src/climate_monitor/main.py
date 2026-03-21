"""應用程式入口點，支援優雅關機。"""

import asyncio
import signal
import sys

from climate_monitor.config import get_settings
from climate_monitor.core.collector import SensorCollector
from climate_monitor.core.tapo_client import TapoClient
from climate_monitor.infra.database import CrateDBClient
from climate_monitor.utils.logging import get_logger, setup_logging


def create_collector() -> tuple[SensorCollector, CrateDBClient]:
    """建立並設定收集器及其依賴項。

    回傳:
        (收集器, 資料庫客戶端) 元組。
    """
    settings = get_settings()
    tapo_client = TapoClient(settings)
    db_client = CrateDBClient(settings)

    # 連接資料庫並初始化 Schema
    db_client.connect()
    db_client.initialize_schema()

    collector = SensorCollector(settings, tapo_client, db_client)
    return collector, db_client


async def run_collector() -> None:
    """執行感測器收集器，支援安全關機處理。"""
    logger = get_logger(__name__)

    collector, db_client = create_collector()
    shutdown_event = asyncio.Event()

    def signal_handler(sig: signal.Signals) -> None:
        logger.info("收到訊號 %s，正在啟動關機程序...", sig.name)
        shutdown_event.set()

    # 註冊訊號處理器
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))
        except NotImplementedError:
            # Windows 不支援 add_signal_handler
            signal.signal(sig, lambda s, f, sig=sig: signal_handler(sig))

    # 在背景啟動收集器
    collector_task = asyncio.create_task(collector.start())

    # 等待關機訊號
    await shutdown_event.wait()

    # 優雅關機
    logger.info("正在關機...")
    await collector.stop()
    collector_task.cancel()

    try:
        await collector_task
    except asyncio.CancelledError:
        pass

    db_client.disconnect()
    logger.info("關機完成")


def main() -> None:
    """主程式入口點。"""
    settings = get_settings()
    setup_logging(settings.log_level)
    logger = get_logger(__name__)

    logger.info("Climate Monitor 啟動中...")
    logger.info("Tapo 網關：%s", settings.tapo_host)
    logger.info("CrateDB：%s:%d", settings.cratedb_host, settings.cratedb_port)
    logger.info("蒐集間隔：%d 秒", settings.collection_interval)
    logger.info(
        "連線驗證：RSSI 門檻=%d dBm、凍結窗口=%d 秒（=%d 次）、"
        "歷史窗口=%d 秒（=%d 筆）、交叉確認門檻=%d 項",
        settings.validator_rssi_threshold,
        settings.validator_frozen_window,
        settings.validator_max_frozen_count,
        settings.validator_history_window,
        settings.validator_history_size,
        settings.validator_min_failed_checks,
    )

    try:
        asyncio.run(run_collector())
    except KeyboardInterrupt:
        logger.info("使用者中斷")
    except Exception as e:
        logger.exception("嚴重錯誤：%s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
