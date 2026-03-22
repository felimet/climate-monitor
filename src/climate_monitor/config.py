"""設定管理模組，使用 Pydantic Settings 載入環境變數。"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """應用程式設定，從環境變數載入。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Tapo H200 網關設定
    tapo_host: str = Field(
        default="192.168.1.100",
        description="Tapo H200 網關 IP 位址",
    )
    tapo_username: str = Field(
        default="your_email@example.com",
        description="TP-Link 帳號電子郵件",
    )
    tapo_password: str = Field(
        default="your_password",
        description="TP-Link 帳號密碼",
    )

    # CrateDB 資料庫設定
    cratedb_host: str = Field(
        default="cratedb",
        description="CrateDB 主機名稱",
    )
    cratedb_port: int = Field(
        default=4200,
        description="CrateDB HTTP 連接埠",
    )

    # 資料收集設定
    collection_interval: int = Field(
        default=60,       # 預設 60 秒
        ge=10,            # 最小值 10 秒（防止過度頻繁請求）
        description="資料收集間隔（秒）",
    )

    # 連線狀態驗證設定（共 4 項檢查：RSSI 弱、RSSI 凍結、溫溼度凍結、device_time 凍結）
    validator_rssi_threshold: int = Field(
        default=-85,      # 預設 -85 dBm（半開放牧場環境建議值）
        description="RSSI 門檻（dBm），低於此值視為訊號過弱",
    )
    validator_frozen_window: int = Field(
        default=600,      # 預設 600 秒（10 分鐘，半開放牧場環境建議值）
        ge=60,            # 最小值 60 秒（防止誤判）
        description="凍結判定時間窗口（秒），連續此時間內資料不變即視為過時",
    )
    validator_history_window: int = Field(
        default=1800,     # 預設 1800 秒（30 分鐘）
        ge=300,           # 最小值 300 秒（5 分鐘）
        description="驗證器每裝置歷史記錄時間窗口（秒）",
    )
    validator_time_frozen_threshold: int = Field(
        default=3,        # 預設 3 次（device_time 停止遞增即為強斷線訊號）
        ge=2,             # 最小值 2 次（至少觀察 2 次才判定）
        le=10,            # 最大值 10 次
        description="device_time 連續相同幾次即判定凍結",
    )
    validator_min_failed_checks: int = Field(
        default=3,        # 預設 3 項（4 項中至少 3 項失敗才判定 stale）
        ge=1,             # 最小值 1（至少 1 項失敗）
        le=4,             # 最大值 4（不超過檢查項目總數）
        description="至少幾項檢查同時失敗才判定為 stale",
    )

    @property
    def validator_max_frozen_count(self) -> int:
        """根據取樣間隔計算凍結判定連續次數（最少 2 次）。"""
        return max(2, self.validator_frozen_window // self.collection_interval)

    @property
    def validator_history_size(self) -> int:
        """根據取樣間隔計算歷史記錄大小（最少 5 筆）。"""
        return max(5, self.validator_history_window // self.collection_interval)

    # 日誌設定
    log_level: str = Field(
        default="INFO",
        description="日誌等級（DEBUG、INFO、WARNING、ERROR）",
    )

    @property
    def cratedb_url(self) -> str:
        """建構 CrateDB 連線 URL。"""
        return f"http://{self.cratedb_host}:{self.cratedb_port}"


def get_settings() -> Settings:
    """取得應用程式設定單例。"""
    return Settings()
