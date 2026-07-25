import pandas as pd

from backend.app.services.market_data import rebuild_partial_candle_from_1m


def test_rebuild_partial_candle_uses_only_minutes_before_cutoff():
    frame = pd.DataFrame(
        [{"Open": 100.0, "High": 999.0, "Low": 1.0, "Close": 500.0, "Volume": 9999.0}],
        index=pd.DatetimeIndex(["2026-01-01 04:00:00"], name="Date"),
    )
    minute_frame = pd.DataFrame(
        [
            {"Open": 100.0, "High": 102.0, "Low": 99.0, "Close": 101.0, "Volume": 10.0},
            {"Open": 101.0, "High": 103.0, "Low": 100.0, "Close": 102.0, "Volume": 20.0},
            # This minute starts at the cutoff and must not be visible.
            {"Open": 102.0, "High": 900.0, "Low": 2.0, "Close": 800.0, "Volume": 9000.0},
        ],
        index=pd.DatetimeIndex(
            ["2026-01-01 04:00:00", "2026-01-01 04:01:00", "2026-01-01 04:02:00"],
            name="Date",
        ),
    )

    rebuilt = rebuild_partial_candle_from_1m(
        frame, minute_frame, pd.Timestamp("2026-01-01 04:02:00"), "4h"
    )

    candle = rebuilt.iloc[-1]
    assert candle["Open"] == 100.0
    assert candle["High"] == 103.0
    assert candle["Low"] == 99.0
    assert candle["Close"] == 102.0
    assert candle["Volume"] == 30.0
