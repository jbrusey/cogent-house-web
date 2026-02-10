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


def test_export_page_and_download(monkeypatch, tmp_path):
    db_path = tmp_path / "test.db"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)
    init_model(engine)
    Base.metadata.create_all(engine)
    init_data()

    now = datetime.now(timezone.utc).replace(microsecond=0)
    later = now + timedelta(days=1)

    with Session(engine) as session:
        house = House(id=100, address="House 1")
        room1 = Room(id=100, name="Kitchen")
        room2 = Room(id=101, name="Bedroom")
        loc1 = Location(id=100, houseId=house.id, roomId=room1.id)
        loc2 = Location(id=101, houseId=house.id, roomId=room2.id)
        node1 = Node(id=100, locationId=loc1.id)
        node2 = Node(id=101, locationId=loc2.id)
        session.add_all([house, room1, room2, loc1, loc2, node1, node2])
        session.commit()

        for st_id in (0, 1):
            st = session.get(SensorType, st_id)
            st.active = True
        session.commit()

        session.add_all(
            [
                Reading(time=now, nodeId=node1.id, typeId=0, locationId=loc1.id, value=10.0),
                Reading(time=later, nodeId=node2.id, typeId=1, locationId=loc2.id, value=99.0),
            ]
        )
        session.commit()

    monkeypatch.setenv("CH_DBURL", db_url)
    app = create_app()
    client = app.test_client()

    page = client.get("/export")
    assert page.status_code == 200
    assert b"Download CSV" in page.data
    assert b"Sensor types" in page.data
    assert b"Rooms" in page.data

    day = now.date().isoformat()
    response = client.get(
        f"/export/download?sensor_type=0&room=100&start_date={day}&end_date={day}"
    )
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("text/csv")
    assert "attachment; filename=" in response.headers["Content-Disposition"]

    body = response.data.decode("utf-8")
    assert "time,nodeId,typeId,locationId,value" in body
    assert f"{now.replace(tzinfo=None).isoformat()},100,0,100,10.0" in body
    assert "99.0" not in body
