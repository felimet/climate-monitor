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
        default=60,
        ge=10,
        description="資料收集間隔（秒）",
    )

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
