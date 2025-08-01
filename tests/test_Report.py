import datetime
import unittest

# from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, text

from cogent.base.model import (
    Base,
    House,
    Location,
    Node,
    NodeState,
    Reading,
    Room,
    RoomType,
    Session,
    init_model,
)
from cogent.report import lowBat

from . import base

# try:
# except ImportError:
#     #Assume we are running from the test directory
#     print "Unable to Import Cogent Module Appending Path"
#     import sys
#     sys.path.append("../")


class TestReport(base.BaseTestCase):
    @classmethod
    def setUpClass(cls):
        # Inherit from Base
        super(TestReport, cls).setUpClass()

        session = cls.Session()
        session.execute(text("DELETE FROM Node"))
        session.execute(text("DELETE FROM NodeState"))
        session.execute(text("DELETE FROM House"))
        session.execute(text("DELETE FROM Room"))
        session.execute(text("DELETE FROM Location"))
        session.execute(text("DELETE FROM Reading"))
        session.execute(text("DELETE FROM LastReport"))
        session.commit()
        initDb()

    @classmethod
    def tearDownClass(cls):
        # Inherit from Base
        session = cls.Session()
        session.execute(text("DELETE FROM Node"))
        session.execute(text("DELETE FROM NodeState"))
        session.execute(text("DELETE FROM House"))
        session.execute(text("DELETE FROM Room"))
        session.execute(text("DELETE FROM Location"))
        session.execute(text("DELETE FROM Reading"))
        session.execute(text("DELETE FROM LastReport"))
        session.commit()

    def test_lowbat(self):
        try:
            s = Session()
            x = lowBat(s)
            self.assertTrue(len(x) == 5)
            y = lowBat(s)
            self.assertTrue(len(y) == 0)
        finally:
            s.close()

    # def test_packetyield(self):
    #     try:
    #         s = Session()
    #         _ = packetYield(s)
    #         # print x
    #         _ = packetYield(s)
    #         # self.assertTrue(len(y) == 0)
    #         # print y
    #     finally:
    #         s.close()

    # def test_ccyield(self):
    #     try:
    #         s = Session()
    #         x = ccYield(s)
    #         # print x
    #         y = ccYield(s)
    #         # print y
    #         # self.assertTrue(len(y) == 0)
    #     finally:
    #         s.close()


def initDb():
    """Create some initial items in our database"""
    # print "Creating Database Objects"
    try:
        s = Session()
        h = House(address="Test house")
        s.add(h)
        rt = RoomType(name="Test")
        s.add(rt)
        r = Room(name="Example room", roomType=rt)
        s.add(r)
        ll = Location(house=h, room=r)
        s.add(ll)
        n = Node(id=22, location=ll)
        s.add(n)
        s.add(Node(id=23, location=ll))
        s.add(Node(id=24, location=ll))
        s.add(Node(id=4098, nodeTypeId=1, location=ll))
        s.add(Node(id=4099, nodeTypeId=1, location=ll))

        t = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1)
        for i in range(288):
            ns = NodeState(time=t, nodeId=23, parent=0, localtime=0, seq_num=i)
            s.add(ns)

            s.add(Reading(typeId=6, time=t, value=3.0 - i / 288.0, nodeId=22))

            s.add(Reading(typeId=11, time=t, value=300.0, nodeId=4098))
            if i < 200:
                s.add(Reading(typeId=11, time=t, value=300.0, nodeId=4099))

            if i > 6:
                s.add(NodeState(time=t, nodeId=24, parent=0, localtime=0, seq_num=i))
            t = t + datetime.timedelta(minutes=5)

        s.commit()
        # print "Object Creation Successfull"
    finally:
        s.close()


if __name__ == "__main__":
    # initDb()
    engine = create_engine("sqlite:///", echo=False)
    Base.metadata.create_all(engine)
    init_model(engine)
    # try:
    #     s = Session()
    #     h = House(address="Test house")
    #     s.add(h)
    #     rt = RoomType(name="Test")
    #     s.add(rt)
    #     r = Room(name="Example room", roomType=rt)
    #     s.add(r)
    #     ll = Location(house=h, room=r)
    #     s.add(ll)
    #     n = Node(id=22, location=ll)
    #     s.add(n)
    #     s.add(Node(id=23, location=ll))
    #     s.add(Node(id=24, location=ll))
    #     s.add(Node(id=4098, nodeTypeId=1, location=ll))
    #     s.add(Node(id=4099, nodeTypeId=1, location=ll))

    #     t = datetime.utcnow() - timedelta(days=1)
    #     for i in range(288):
    #         ns = NodeState(time=t,
    #                        nodeId=23,
    #                        parent=0,
    #                        localtime=0)
    #         s.add(ns)

    #         s.add(Reading(typeId=6,
    #                     time=t,
    #                     value=3.0 - i / 288.,
    #                     nodeId=22))

    #         s.add(Reading(typeId=11,
    #                       time=t,
    #                       value=300.0,
    #                       nodeId=4098))
    #         if i < 200:
    #             s.add(Reading(typeId=11,
    #                           time=t,
    #                           value=300.0,
    #                 nodeId=4099))

    #         if i > 6:
    #             s.add(NodeState(time=t,
    #                             nodeId=24,
    #                             parent=0,
    #                             localtime=0))
    #         t = t + timedelta(minutes=5)

    #     s.commit()
    # finally:
    #     s.close()
    unittest.main()
