"""T315 連線狀態驗證器。

透過多重訊號交叉比對，偵測 H200 Hub 回傳的資料是否為過時快取。
需至少 min_failed_checks 項檢查同時失敗才判定為 stale。

四項檢查：
1. RSSI 門檻：低於閾值視為訊號過弱
2. RSSI 凍結：連續 N 次 RSSI 完全不變，代表 Hub 在回傳快取
3. 溫溼度凍結：溫溼度連續 N 次完全相同（含小數位）
4. device_time 凍結：裝置時間停止遞增
"""

from collections import deque
from dataclasses import dataclass

from climate_monitor.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class SensorSnapshot:
    """單次 poll 的原始訊號快照。"""

    temperature: float
    humidity: float
    rssi: int
    report_interval: int
    device_time: str


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """驗證結果。"""

    is_valid: bool
    failed_checks: int
    reasons: tuple[str, ...]
    rssi: int
    frozen_count: int
    check_rssi_weak: bool = False
    check_rssi_frozen: bool = False
    check_temp_frozen: bool = False
    check_time_frozen: bool = False


class T315ConnectionValidator:
    """多重訊號驗證 T315 是否仍與 Hub 保持連線。

    每個 device_id 維護獨立的歷史紀錄。
    至少 min_failed_checks 項檢查同時失敗才判定資料不可信。
    """

    def __init__(
        self,
        rssi_threshold: int = -70,
        max_frozen_count: int = 5,
        history_size: int = 20,
        min_failed_checks: int = 2,
        time_frozen_threshold: int = 3,
    ) -> None:
        self._rssi_threshold = rssi_threshold
        self._max_frozen_count = max_frozen_count
        self._history_size = history_size
        self._min_failed_checks = min_failed_checks
        self._time_frozen_threshold = time_frozen_threshold
        self._histories: dict[str, deque[SensorSnapshot]] = {}

    def _get_history(self, device_id: str) -> deque[SensorSnapshot]:
        """取得或建立指定裝置的歷史紀錄。"""
        if device_id not in self._histories:
            self._histories[device_id] = deque(maxlen=self._history_size)
        return self._histories[device_id]

    def validate(self, device_id: str, snapshot: SensorSnapshot) -> ValidationResult:
        """驗證本次讀數的可信度。

        參數:
            device_id: 裝置唯一識別碼。
            snapshot: 本次 poll 的原始訊號快照。

        回傳:
            ValidationResult，至少 min_failed_checks 項失敗時 is_valid=False。
        """
        history = self._get_history(device_id)
        history.append(snapshot)
        reasons: list[str] = []
        chk_rssi_weak = False
        chk_rssi_frozen = False
        chk_temp_frozen = False
        chk_time_frozen = False

        # --- 檢查 1: RSSI 絕對門檻 ---
        if snapshot.rssi <= self._rssi_threshold:
            chk_rssi_weak = True
            reasons.append(
                f"RSSI {snapshot.rssi} dBm <= threshold {self._rssi_threshold} dBm"
            )

        if len(history) >= 2:
            tail = list(history)[-min(len(history), self._max_frozen_count) :]

            # --- 檢查 2: RSSI 凍結 ---
            if len(tail) >= self._max_frozen_count:
                rssi_values = {s.rssi for s in tail}
                if len(rssi_values) == 1:
                    chk_rssi_frozen = True
                    reasons.append(
                        f"RSSI frozen at {snapshot.rssi} dBm "
                        f"for {len(tail)} consecutive polls"
                    )

            # --- 檢查 3: 溫溼度凍結 ---
            if len(tail) >= self._max_frozen_count:
                temp_values = {s.temperature for s in tail}
                humid_values = {s.humidity for s in tail}
                if len(temp_values) == 1 and len(humid_values) == 1:
                    chk_temp_frozen = True
                    reasons.append(
                        f"Temperature ({snapshot.temperature}) and "
                        f"humidity ({snapshot.humidity}) frozen "
                        f"for {len(tail)} consecutive polls"
                    )

            # --- 檢查 4: device_time 凍結 ---
            same_time_count = 0
            for s in reversed(list(history)):
                if s.device_time == snapshot.device_time:
                    same_time_count += 1
                else:
                    break
            if same_time_count >= self._time_frozen_threshold:
                chk_time_frozen = True
                reasons.append(
                    f"device_time stuck at {snapshot.device_time} "
                    f"for {same_time_count} polls"
                )

        # 計算溫溼度連續凍結次數
        frozen_count = 0
        for s in reversed(list(history)):
            if s.temperature == snapshot.temperature and s.humidity == snapshot.humidity:
                frozen_count += 1
            else:
                break

        failed_checks = len(reasons)
        is_valid = failed_checks < self._min_failed_checks

        return ValidationResult(
            is_valid=is_valid,
            failed_checks=failed_checks,
            reasons=tuple(reasons),
            rssi=snapshot.rssi,
            frozen_count=frozen_count,
            check_rssi_weak=chk_rssi_weak,
            check_rssi_frozen=chk_rssi_frozen,
            check_temp_frozen=chk_temp_frozen,
            check_time_frozen=chk_time_frozen,
        )
