from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine

from cogent import create_app
from cogent.base.model import (
    Base,
    House,
    Location,
    Node,
    Reading,
    Room,
    SensorType,
    Session,
    init_data,
    init_model,
)


class _FixedDateTime(datetime):
    """Helper to stub datetime.now in the electricity usage view."""

    fixed_now = datetime(2023, 1, 7, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return cls.fixed_now.replace(tzinfo=None)
        return cls.fixed_now.astimezone(tz)


def _make_reading(session, node_id, location_id, when, value):
    session.add(
        Reading(
            time=when,
            nodeId=node_id,
            typeId=40,
            locationId=location_id,
            value=value,
        )
    )


def test_electricity_usage_view(monkeypatch, tmp_path):
    db_path = tmp_path / "test.db"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)
    init_model(engine)
    Base.metadata.create_all(engine)
    init_data()

    start = datetime(2023, 1, 1, tzinfo=timezone.utc)

    with Session(engine) as session:
        house = House(id=200, address="House 1")
        room = Room(id=200, name="Living room")
        location = Location(id=200, houseId=house.id, roomId=room.id)
        node = Node(id=200, locationId=location.id)
        session.add_all([house, room, location, node])
        session.commit()

        sensor_type = session.get(SensorType, 40)
        sensor_type.active = True
        session.commit()

        _make_reading(session, node.id, location.id, start, 100.0)
        _make_reading(session, node.id, location.id, start + timedelta(hours=23), 150.0)
        _make_reading(session, node.id, location.id, start + timedelta(days=1), 150.0)
        _make_reading(
            session,
            node.id,
            location.id,
            start + timedelta(days=1, hours=23),
            210.0,
        )
        session.commit()

    monkeypatch.setenv("CH_DBURL", db_url)
    monkeypatch.setattr("cogent.views.main.datetime", _FixedDateTime)

    app = create_app()
    client = app.test_client()
    response = client.get("/electricity-usage?period=week")

    assert response.status_code == 200
    assert b"Opti Smart Count usage" in response.data
    assert b"Total usage: <strong>110.00</strong>" in response.data
    assert b"2023-01-01" in response.data
    assert b"2023-01-02" in response.data


def test_electricity_usage_handles_reset(monkeypatch, tmp_path):
    db_path = tmp_path / "test.db"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)
    init_model(engine)
    Base.metadata.create_all(engine)
    init_data()

    start = datetime(2023, 1, 1, tzinfo=timezone.utc)

    with Session(engine) as session:
        house = House(id=300, address="House 2")
        room = Room(id=300, name="Kitchen")
        location = Location(id=300, houseId=house.id, roomId=room.id)
        node = Node(id=300, locationId=location.id)
        session.add_all([house, room, location, node])
        session.commit()

        sensor_type = session.get(SensorType, 40)
        sensor_type.active = True
        session.commit()

        _make_reading(session, node.id, location.id, start, 200000.0)
        _make_reading(session, node.id, location.id, start + timedelta(hours=12), 0.0)
        _make_reading(session, node.id, location.id, start + timedelta(hours=23, minutes=59), 10000.0)
        session.commit()

    monkeypatch.setenv("CH_DBURL", db_url)
    monkeypatch.setattr("cogent.views.main.datetime", _FixedDateTime)

    app = create_app()
    client = app.test_client()
    response = client.get("/electricity-usage?period=week")

    assert response.status_code == 200
    assert b"Opti Smart Count usage" in response.data
    assert b"Total usage: <strong>10000.00</strong>" in response.data
    assert b"2023-01-01" in response.data
