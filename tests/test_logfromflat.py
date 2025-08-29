""" test LogFromFlat

author: J. Brusey, November 2019

"""

import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import mock_open, patch

from cogent.base.logfromflat import LogFromFlat
from cogent.base.model import (
    Bitset,
    Deployment,
    House,
    Location,
    Node,
    NodeState,
    NodeType,
    Reading,
    Room,
    RoomType,
    SensorType,
    meta,
)
from sqlalchemy import and_

DBURL = "sqlite:///:memory:"


@patch("cogent.base.logfromflat.LogFromFlat.create_tables")
@patch("cogent.base.logfromflat.create_engine")
@patch("cogent.base.logfromflat.models")
def test_process_file(models, create_engine, create_tables):
    """mock store_state and check that process file reads from a json
    file and passes each line to store_state"""

    with patch("cogent.base.logfromflat.LogFromFlat.store_state") as ss:
        with patch(
            "cogent.base.logfromflat.open",
            mock_open(
                read_data="""{"0": 18, "1": -5, "sender": 235}
        {"0": 7, "1": 0, "sender": 236}"""
            ),
        ):
            lff = LogFromFlat(dbfile=DBURL)
            lff.process_file("x")

        ss.assert_any_call({"0": 18, "1": -5, "sender": 235})
        ss.assert_any_call({"0": 7, "1": 0, "sender": 236})


def dummy_deployment(session):
    """set up the basics for a the database"""

    dep = Deployment(
        name="TestDep", description="", startDate=datetime.now(timezone.utc), endDate=None
    )
    session.add(dep)
    session.commit()

    # Add a room type

    rt = RoomType(name="Bedroom")
    session.add(rt)
    session.commit()

    # Add a house
    h = House(deploymentId=1, address="unknown", startDate=datetime.now(timezone.utc))

    session.add(h)
    session.commit()

    r = Room(roomTypeId=rt.id, name="BedroomA")

    session.add(r)
    session.commit()

    ll = Location(house=h, room=r)
    session.add(ll)
    session.commit()
    assert ll.id is not None

    nt = session.get(NodeType, 14)
    if not nt:
        nt = NodeType(
            time=datetime.now(timezone.utc),
            id=14,
            name="base",
            seq=2,
            updated_seq=0,
            period=15 * 1024,
            configured=Bitset(size=14),
        )

        session.add(nt)
        session.commit()
    assert nt.id is not None

    n = Node(id=28710, location=ll, nodeType=nt)
    session.add(n)

    # session.add_all([SensorType(id=x,
    #                             name="Sensor"+str(x),
    #                             code="x",
    #                             units="none") for x in range(44)])
    session.commit()


def test_store_state():
    """test that store_state correctly stores incoming data"""

    lff = LogFromFlat(dbfile=DBURL)

    with meta.Session() as session:
        # set up database with some basic data.
        dummy_deployment(session)

        res = lff.store_state(
            {
                "0": 10.1361722946167,
                "1": -1.933643397933338e-05,
                "2": 95.4524154663086,
                "3": 0.00018446370086167008,
                "server_time": 1581266093.331143,
                "sender": 28710,
                "6": 2.999267578125,
                "7": 0.0,
                "43": 3698.0,
                "13": 510.0,
                "parent": 40969,
                "rssi": -91,
                "seq": 22,
                "localtime": 643594668,
            }
        )

        assert res

        # duplicate should return false
        res = lff.store_state(
            {
                "0": 10.1361722946167,
                "1": -1.933643397933338e-05,
                "2": 95.4524154663086,
                "3": 0.00018446370086167008,
                "server_time": 1581266093.331143,
                "sender": 28710,
                "6": 2.999267578125,
                "7": 0.0,
                "43": 3698.0,
                "13": 510.0,
                "parent": 40969,
                "rssi": -91,
                "seq": 22,
                "localtime": 643594668,
            }
        )

        assert not res

        reading = (
            session.query(Reading)
            .filter(and_(Reading.nodeId == 28710, Reading.typeId == 0))
            .one()
        )

        assert reading.locationId is not None

        assert reading.value == 10.1361722946167

        reading = (
            session.query(Reading)
            .filter(and_(Reading.nodeId == 28710, Reading.typeId == 1))
            .one()
        )

        assert reading.locationId is not None

        assert reading.value == -1.933643397933338e-05

        nodestate = session.query(NodeState).filter(NodeState.nodeId == 28710).one()

        assert nodestate.localtime == 643594668

        # test add_node by supplying data for a node not seen yet.

        res = lff.store_state(
            {
                "0": 1,
                "server_time": time.time(),
                "sender": 236,
                "parent": 28710,
                "rssi": -90,
                "seq": 22,
                "localtime": 1000,
            }
        )
        assert res
        reading = (
            session.query(Reading)
            .filter(and_(Reading.nodeId == 236, Reading.typeId == 0))
            .one()
        )
        assert reading.value == 1

        # an inactive SensorType should be activated when used
        st = SensorType(id=123, name="Test", active=False)
        session.add(st)
        session.commit()

        res = lff.store_state(
            {
                "123": 5,
                "server_time": time.time(),
                "sender": 236,
                "parent": 28710,
                "rssi": -90,
                "seq": 23,
                "localtime": 1002,
            }
        )
        assert res
        assert session.get(SensorType, 123).active


@patch("cogent.base.logfromflat.LogFromFlat.process_file")
def test_process_dir(process_file):
    import tempfile

    with tempfile.TemporaryDirectory() as tempdir:
        temppath = Path(tempdir)
        with open(str(temppath / "a.log"), "w") as f:
            f.write('{"0": 1}')
        with open(str(temppath / "b.log"), "w") as f:
            f.write('{"0": 1}')
        lff = LogFromFlat(dbfile=DBURL)
        lff.process_dir(temppath)
        process_file.assert_any_call(temppath / "a.log")
        process_file.assert_any_call(temppath / "b.log")

        with open(str(temppath / "processed_files.txt")) as processed_files:
            fileset = []
            for row in processed_files:
                fileset.append(row.rstrip())

            assert len(fileset) == 2
            assert "a.log" in fileset
            assert "b.log" in fileset

    # check what happens if we don't have write access to processed_files.txt
    with tempfile.TemporaryDirectory() as tempdir:
        temppath = Path(tempdir)
        pf = temppath / "processed_files.txt"
        with open(str(pf), "w") as pfhandle:
            pfhandle.write("b.log")

        pf.chmod(0o444)  # remove write access

        with open(str(temppath / "a.log"), "w") as f:
            f.write('{"0": 1}')
        lff = LogFromFlat(dbfile=DBURL)
        lff.process_dir(temppath)
