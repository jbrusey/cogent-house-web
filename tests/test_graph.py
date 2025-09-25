from datetime import datetime, timedelta

from cogent.views.graph.constants import _periods
from cogent.views.graph.utils import _mins, _select_downsample_indices


def test_mins():
    for period in _periods:
        assert isinstance(_mins(period), int)


def test_select_downsample_indices_returns_full_range_when_under_limit():
    times = [datetime(2023, 1, 1) + timedelta(minutes=i) for i in range(5)]
    assert _select_downsample_indices(times, 10) == list(range(5))


def test_select_downsample_indices_respects_priority_and_bounds():
    times = [datetime(2023, 1, 1) + timedelta(minutes=i) for i in range(10)]
    result = _select_downsample_indices(times, 4, [5, 20, -1])
    assert 0 in result
    assert 9 in result
    assert 5 in result
    assert len(result) == 4


def test_select_downsample_indices_downsamples_priority_overflow():
    times = [datetime(2023, 1, 1) + timedelta(minutes=i) for i in range(50)]
    result = _select_downsample_indices(times, 5, [5, 10, 15, 20, 25])
    assert 0 in result
    assert 49 in result
    assert len(result) == 5


def test_select_downsample_indices_without_priority_even_distribution():
    times = [datetime(2023, 1, 1) + timedelta(minutes=i) for i in range(100)]
    result = _select_downsample_indices(times, 10)
    assert result[0] == 0
    assert result[-1] == 99
    assert len(result) == 10


def test_select_downsample_indices_balances_time_distribution():
    start = datetime(2023, 1, 1)
    day_one = [start + timedelta(minutes=i * (24 * 60) / 100) for i in range(100)]
    day_two_start = start + timedelta(days=1)
    day_two = [
        day_two_start + timedelta(minutes=i * (24 * 60) / 900) for i in range(900)
    ]
    times = day_one + day_two
    indices = _select_downsample_indices(times, 10)
    day_one_count = sum(1 for idx in indices if times[idx] < day_two_start)
    assert 4 <= day_one_count <= 6
