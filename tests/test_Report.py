import datetime
import unittest

# from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, func, text

from cogent.base.model import (
    Base,
    House,
    LastReport,
    Location,
    Node,
    NodeState,
    Reading,
    Room,
    RoomType,
    Session,
    init_model,
)
from cogent.report import ccYield, lowBat, packetYield

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

    def test_packet_yield_reports_lost_nodes(self):
        expected_nodes = {22, 23, 24, 4098, 4099}
        try:
            s = Session()
            html_first = packetYield(s)
            html_second = packetYield(s)

            html_first_str = "\n".join(html_first)
            html_second_str = "\n".join(html_second)

            self.assertIn("<h3>Nodes recently lost</h3>", html_first_str)
            self.assertIn("<h3>These nodes are still lost</h3>", html_second_str)
            self.assertNotIn("<h3>Nodes recently lost</h3>", html_second_str)

            for node_id in expected_nodes:
                node_cell = f"<td>{node_id}</td>"
                self.assertIn(node_cell, html_first_str)
                self.assertIn(node_cell, html_second_str)

            last_report = (
                s.query(LastReport).filter(LastReport.name == "lost-nodes").one()
            )
            self.assertEqual(eval(last_report.value), expected_nodes)
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

    def test_ccyield(self):
        try:
            s = Session()
            s.execute(text("DELETE FROM LastReport"))
            s.commit()

            start_time = s.query(func.min(Reading.time)).scalar()
            self.assertIsNotNone(start_time)
            # Keep the reporting window within a day so the existing
            # expected yield calculation remains non-zero in tests.
            end_time = start_time + datetime.timedelta(minutes=287 * 5, seconds=299)

            first_report = ccYield(s, start_t=start_time, end_t=end_time)
            first_html = "".join(first_report)

            self.assertIn("Low yield current-cost nodes", first_html)
            self.assertIn("<td>4099</td>", first_html)
            self.assertNotIn("<td>4098</td>", first_html)

            last_report = (
                s.query(LastReport).filter(LastReport.name == "lost-cc-nodes").one()
            )
            self.assertEqual(last_report.value, "set()")

            second_report = ccYield(s, start_t=start_time, end_t=end_time)
            second_html = "".join(second_report)
            self.assertIn("<td>4099</td>", second_html)

        finally:
            s.execute(text("DELETE FROM LastReport"))
            s.commit()
            s.close()


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
