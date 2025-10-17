from datetime import UTC, datetime, timedelta

from cogent.base.model import House, Location, Node, Reading, Room
from cogent.report.fridgeopen import fridge_open

from . import base


class TestFridgeOpenReport(base.BaseTestCase):
    def test_returns_latest_fridge_reading(self):
        now = datetime.now(UTC).replace(microsecond=0)
        earlier = now - timedelta(minutes=10)
        latest = now - timedelta(minutes=5)

        house = House(address="Test house")
        fridge_room = Room(name="fridge")
        other_room = Room(name="pantry")

        fridge_location = Location(house=house, room=fridge_room)
        other_location = Location(house=house, room=other_room)

        fridge_node = Node(id=100, location=fridge_location)
        other_node = Node(id=200, location=other_location)

        self.session.add_all(
            [
                house,
                fridge_room,
                other_room,
                fridge_location,
                other_location,
                fridge_node,
                other_node,
            ]
        )

        self.session.add_all(
            [
                Reading(node=fridge_node, typeId=0, time=earlier, value=8.0),
                Reading(node=fridge_node, typeId=0, time=latest, value=12.0),
                Reading(node=other_node, typeId=0, time=latest, value=5.0),
            ]
        )

        result = fridge_open(self.session, start_t=now - timedelta(hours=1), end_t=now)

        self.assertEqual(len(result), 1)
        self.assertIn("Fridge temperature is 12.0", result[0])
        self.assertIn(latest.strftime("%Y-%m-%d %H:%M:%S"), result[0])
