from cogent.views.graph.constants import _periods
from cogent.views.graph.utils import _mins, _select_downsample_indices


def test_mins():
    for period in _periods:
        assert isinstance(_mins(period), int)


def test_select_downsample_indices_returns_full_range_when_under_limit():
    assert _select_downsample_indices(5, 10) == list(range(5))


def test_select_downsample_indices_respects_priority_and_bounds():
    result = _select_downsample_indices(10, 4, [5, 20, -1])
    assert result[0] == 0
    assert result[-1] == 9
    assert 5 in result
    assert len(result) <= 4


def test_select_downsample_indices_downsamples_priority_overflow():
    result = _select_downsample_indices(50, 5, [5, 10, 15, 20, 25])
    assert result == [0, 5, 10, 20, 49]


def test_select_downsample_indices_without_priority_even_distribution():
    result = _select_downsample_indices(100, 10)
    assert result[0] == 0
    assert result[-1] == 99
    assert len(result) == 10
