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


def test_fixed_graph_window():
    from flask import Flask

    from cogent.views.graph.graph import _graph_window

    app = Flask(__name__)
    for at in ('2024-01-02T12:00:00Z', '2024-01-02T14:00:00+02:00',
               '2024-01-02T12:00:00'):
        with app.test_request_context(query_string={'at': at}):
            assert _graph_window(1440) == (
                datetime(2024, 1, 2), datetime(2024, 1, 3)
            )
            assert _graph_window(60, 1) == (
                datetime(2024, 1, 2, 10, 30), datetime(2024, 1, 2, 11, 30)
            )
            assert _graph_window(60, -1) == (
                datetime(2024, 1, 2, 12, 30), datetime(2024, 1, 2, 13, 30)
            )


def test_graph_permalink_queries_historical_data_and_preserves_navigation(monkeypatch, tmp_path):
    import re
    from html import unescape
    from urllib.parse import parse_qs, urlsplit

    from sqlalchemy import create_engine

    from cogent import create_app
    from cogent.base.model import Base, House, Location, Node, Reading, Room, Session

    monkeypatch.setenv('CH_DBURL', f'sqlite:///{tmp_path}/graph.db')
    app = create_app()
    engine = create_engine(f'sqlite:///{tmp_path}/graph.db')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        house = House(address='Historical house')
        room = Room(name='fridge')
        node = Node(id=999, location=Location(house=house, room=room))
        session.add(node)
        for when, value in [(datetime(2024, 1, 1, 23), 99),
                            (datetime(2024, 1, 2, 12), 12),
                            (datetime(2024, 1, 3, 1), 99)]:
            session.add(Reading(node=node, typeId=99, time=when, value=value))
        session.commit()
    client = app.test_client()
    query = {'node': 999, 'typ': 99, 'at': '2024-01-02T12:00:00Z'}
    response = client.get('/nodeGraph', query_string={**query, 'debug': 'y'})
    assert response.status_code == 200
    assert b'12.0' in response.data
    assert b'99.0' not in response.data
    response = client.get('/nodeGraph', query_string=query)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'name="at" value="2024-01-02T12:00:00Z"' in html
    links = [parse_qs(urlsplit(unescape(link)).query)
             for link in re.findall(r'href="([^"]*nodeGraph[^"]*)"', html)]
    assert links
    assert all(link['at'] == [query['at']] for link in links)
    assert any(link.get('ago') == ['-1'] for link in links)
    assert '1704153600000' in html  # midnight UTC, twelve hours before centre
    assert '1704240000000' in html  # midnight UTC, twelve hours after centre
    assert client.get('/nodeGraph', query_string={**query, 'at': 'invalid'}).status_code == 400
    assert client.get('/plot', query_string={**query, 'at': 'invalid'}).status_code == 400



def test_relative_graph_window_still_ends_now():
    from datetime import timezone

    from flask import Flask

    from cogent.views.graph.graph import _graph_window

    with Flask(__name__).test_request_context():
        before = datetime.now(timezone.utc).replace(tzinfo=None)
        start, end = _graph_window(1440)
        after = datetime.now(timezone.utc).replace(tzinfo=None)
        assert before <= end <= after
        assert end - start == timedelta(days=1)
        start, end = _graph_window(1440, 1)
        after = datetime.now(timezone.utc).replace(tzinfo=None)
        assert before - timedelta(days=1) <= end <= after - timedelta(days=1)
        assert end - start == timedelta(days=1)
