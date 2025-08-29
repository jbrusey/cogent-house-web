from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine

from cogent.base.model import (
    Base,
    House,
    Location,
    Node,
    Reading,
    Room,
    Session,
    init_data,
    init_model,
)
from flaskapp import create_app


def test_lowbat(monkeypatch, tmp_path):
    db_path = tmp_path / "test.db"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)
    init_model(engine)
    Base.metadata.create_all(engine)
    init_data()

    now = datetime.now(UTC) - timedelta(days=2)
    with Session(engine) as session:
        house = House(id=100, address="House 1")
        room = Room(id=100, name="Room 1")
        loc = Location(id=100, houseId=house.id, roomId=room.id)
        low_node = Node(id=100, locationId=loc.id)
        ok_node = Node(id=101, locationId=loc.id)
        session.add_all([house, room, loc, low_node, ok_node])
        session.commit()
        readings = [
            Reading(time=now, nodeId=100, typeId=6, locationId=loc.id, value=2.5),
            Reading(time=now, nodeId=101, typeId=6, locationId=loc.id, value=2.7),
        ]
        session.add_all(readings)
        session.commit()

    monkeypatch.setenv("CH_DBURL", db_url)
    app = create_app()
    client = app.test_client()
    resp = client.get("/lowbat?bat=2.6")
    assert resp.status_code == 200
    assert b"Low batteries" in resp.data
    assert b"100" in resp.data
    assert b"2.5" in resp.data
    assert b"House 1" in resp.data
    assert b"Room 1" in resp.data
    assert b"2.7" not in resp.data
    assert b"101" not in resp.data
