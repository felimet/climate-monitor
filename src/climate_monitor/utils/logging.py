"""結構化日誌設定模組。"""

import logging
import sys
from datetime import datetime, timezone


class UTCFormatter(logging.Formatter):
    """格式化器，輸出 UTC ISO 格式時間戳記。"""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def setup_logging(level: str = "INFO") -> logging.Logger:
    """設定應用程式結構化日誌。

    參數:
        level: 日誌等級（DEBUG、INFO、WARNING、ERROR）。

    回傳:
        已設定的根日誌記錄器。
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # 建立格式化器
    formatter = UTCFormatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    # 控制台處理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)

    # 設定根日誌記錄器
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)

    # 降低第三方函式庫的日誌雜訊
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """取得模組的日誌記錄器實例。

    參數:
        name: 日誌記錄器名稱（通常是 __name__）。

    回傳:
        日誌記錄器實例。
    """
    return logging.getLogger(name)
