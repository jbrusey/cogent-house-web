from __future__ import annotations

_CONTENT_TEXT = "text/plain"
_CONTENT_PNG = "image/png"
_SAVEFIG_ARGS = {"format": "png"}
_CONTENT_PLOT = _CONTENT_PNG

thresholds: dict[int, float] = {0: 0.5, 2: 2.0, 8: 100.0, 6: 0.1, 40: 10.0}

sensor_types: dict[int, int] = {0: 0, 2: 2, 8: 8, 6: 6}

# mapping from reading type to delta type for spline reconstruction
# (subset only)
type_delta: dict[int, int] = {0: 1, 2: 3, 8: 20, 6: 7, 40: 44}

_periods: dict[str, int] = {
    "hour": 60,
    "12-hours": 60 * 12,
    "day": 1440,
    "3-days": 1440 * 3,
    "week": 1440 * 7,
    "month": 1440 * 7 * 52 // 12,
    "3-months": 3 * 1440 * 7 * 52 // 12,
    "6-months": 6 * 1440 * 7 * 52 // 12,
    "year": 12 * 1440 * 7 * 52 // 12,
    "2-years": 24 * 1440 * 7 * 52 // 12,
}

__all__ = [
    "_CONTENT_TEXT",
    "_CONTENT_PNG",
    "_SAVEFIG_ARGS",
    "_CONTENT_PLOT",
    "thresholds",
    "sensor_types",
    "type_delta",
    "_periods",
]
