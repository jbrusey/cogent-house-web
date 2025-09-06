from cogent.views.graph.constants import _periods
from cogent.views.graph.utils import _mins


def test_mins():
    for period in _periods:
        assert isinstance(_mins(period), int)
