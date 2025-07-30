from flaskapp.views.legacy_graph import _mins, _periods


def test_mins():
    for period in _periods:
        assert isinstance(_mins(period), int)
