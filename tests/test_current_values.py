from datetime import datetime

from sqlalchemy import create_engine

from flaskapp import create_app
from cogent.base.model import (
    Base,
    Session,
    House,
    Location,
    Node,
    Reading,
    Room,
    SensorType,
    init_data,
    init_model,
)


def test_current_values(monkeypatch, tmp_path):
    db_path = tmp_path / "test.db"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)
    init_model(engine)
    Base.metadata.create_all(engine)
    init_data()

    with Session(engine) as session:
        house = House(id=100, address="House 1")
        room = Room(id=100, name="Room 1")
        loc = Location(id=100, houseId=house.id, roomId=room.id)
        node = Node(id=100, locationId=loc.id)
        session.add_all([house, room, loc, node])
        session.commit()
        # mark temperature and delta temperature sensor types as active
        for st_id in (0, 1):
            st = session.get(SensorType, st_id)
            st.active = True
        session.commit()
        now = datetime.utcnow()
        readings = [
            Reading(
                time=now,
                nodeId=node.id,
                typeId=0,
                locationId=loc.id,
                value=25.0,
            ),
            Reading(
                time=now,
                nodeId=node.id,
                typeId=1,
                locationId=loc.id,
                value=42.0,
            ),
        ]
        session.add_all(readings)
        session.commit()

    monkeypatch.setenv("CH_DBURL", db_url)
    app = create_app()
    client = app.test_client()
    resp = client.get("/currentValues?typ=0")
    assert resp.status_code == 200
    assert b"Current Temperature" in resp.data
    assert b"25.0" in resp.data
    assert b"42.0" not in resp.data
    assert b'value="1"' in resp.data

    resp = client.get("/currentValues?typ=1")
    assert resp.status_code == 200
    assert b"42.0" in resp.data
    assert b"25.0" not in resp.data
