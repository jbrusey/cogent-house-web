from datetime import UTC, datetime, timedelta

import pytest
from cogent.base.model import (Base, Bitset, Deployment, DeploymentMetadata,
                               House, Location, Node, NodeState, NodeType,
                               Occupier, Reading, Room, RoomType, SensorType)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def db_session(tmp_path):
    """Create a temporary in-memory database session for testing."""
    engine = create_engine(f"sqlite:///{(tmp_path / 'test.db')}")
    Base.metadata.create_all(engine)

    connection = engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def test_node_type_bitset(db_session):
    b = Bitset(value=[0] * ((20 + 7) // 8))
    b.a[3 // 8] |= 1 << (3 % 8)
    b.a[13 // 8] |= 1 << (13 % 8)

    nt = NodeType(
        time=datetime.now(UTC),
        id=0,
        name="base",
        seq=1,
        updated_seq=1,
        period=1024 * 300,
        configured=b,
    )

    db_session.add(nt)
    db_session.commit()

    configured = nt.configured
    assert (configured.a[3 // 8] & (1 << (3 % 8))) and (
        configured.a[13 // 8] & (1 << (13 % 8))
    )


def test_node_type_query(db_session):
    b = Bitset(value=[0] * ((20 + 7) // 8))
    b.a[3 // 8] |= 1 << (3 % 8)
    b.a[13 // 8] |= 1 << (13 % 8)

    nt = NodeType(
        time=datetime.now(UTC),
        id=0,
        name="base",
        seq=1,
        updated_seq=1,
        period=1024 * 300,
        configured=b,
    )

    db_session.add(nt)
    db_session.commit()

    result = db_session.get(NodeType, 0)
    assert result.name == "base"
    config = result.configured
    assert (config.a[3 // 8] & (1 << (3 % 8))) and (config.a[13 // 8] & (1 << (13 % 8)))


def test_node_type_empty(db_session):
    assert db_session.get(NodeType, 0) is None


def test_schema_localtime_wrap(db_session):
    dep = Deployment(
        name="TestDep",
        description="Does this work",
        startDate=datetime.now(UTC),
        endDate=None,
    )
    db_session.add(dep)
    db_session.commit()
    depid = dep.id

    rt = RoomType(name="Bedroom")
    db_session.add(rt)
    db_session.commit()

    dm = DeploymentMetadata(
        deploymentId=depid,
        name="Manual Reading",
        description="Read something",
        units="kwh",
        value="99999",
    )
    db_session.add(dm)
    db_session.commit()

    h = House(deploymentId=1, address="1 Sampson", startDate=datetime.now(UTC))
    db_session.add(h)
    db_session.commit()

    occ = Occupier(
        houseId=1,
        name="Mr Man",
        contactNumber="01212342345",
        startDate=datetime.now(UTC),
    )
    db_session.add(occ)
    db_session.commit()

    rt_bedroom = RoomType(name="Bedroom")
    db_session.add(rt_bedroom)
    db_session.commit()

    room = Room(roomTypeId=rt_bedroom.id, name="BedroomA")
    db_session.add(room)
    db_session.commit()

    loc = Location(houseId=h.id, roomId=room.id)
    db_session.add(loc)

    node = Node(id=63, locationId=loc.id, nodeTypeId=0)
    db_session.add(node)

    st = SensorType(id=0, name="Temperature", code="Tmp", units="deg.C")
    db_session.add(st)
    db_session.commit()

    tt = datetime.now(UTC) - timedelta(minutes=500)

    for i in range(100):
        loc_id = db_session.query(Node).filter(Node.id == 63).one().locationId
        db_session.add(
            Reading(time=tt, nodeId=63, typeId=0, locationId=loc_id, value=i / 1000.0)
        )
        db_session.add(
            NodeState(
                time=tt, nodeId=63, parent=64, localtime=((1 << 32) - 50 + i), seq_num=1
            )
        )
        tt += timedelta(minutes=5)

    db_session.commit()

    loctimes = [x[0] for x in db_session.query(NodeState.localtime).all()]
    assert max(loctimes) - min(loctimes) == 99
