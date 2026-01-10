import datetime

from cogent.base.model import (
    House,
    LastReport,
    Location,
    Node,
    Reading,
    Room,
    RoomType,
)
from cogent.report.pantryhumid import THRESHOLD, pantry_humid

from . import base


class TestPantryHumidityReport(base.BaseTestCase):
    def test_latest_pantry_reading_controls_alert(self):
        base_time = datetime.datetime.now(datetime.UTC).replace(microsecond=0)

        house = House(address="Pantry House")
        room_type = RoomType(name="Pantry Type")
        pantry_room = Room(name="pantry", roomType=room_type)
        other_room = Room(name="kitchen", roomType=room_type)

        pantry_location = Location(house=house, room=pantry_room)
        other_location = Location(house=house, room=other_room)

        pantry_node = Node(id=1001, location=pantry_location)
        other_node = Node(id=1002, location=other_location)

        older_time = base_time - datetime.timedelta(hours=1)
        newer_time = base_time

        older_pantry_reading = Reading(
            time=older_time,
            typeId=2,
            value=THRESHOLD + 5,
            node=pantry_node,
            location=pantry_location,
        )
        latest_pantry_reading = Reading(
            time=newer_time,
            typeId=2,
            value=THRESHOLD - 5,
            node=pantry_node,
            location=pantry_location,
        )
        other_room_reading = Reading(
            time=newer_time,
            typeId=2,
            value=THRESHOLD + 10,
            node=other_node,
            location=other_location,
        )

        self.session.add_all(
            [
                house,
                room_type,
                pantry_room,
                other_room,
                pantry_location,
                other_location,
                pantry_node,
                other_node,
                older_pantry_reading,
                latest_pantry_reading,
                other_room_reading,
            ]
        )
        self.session.flush()

        result = pantry_humid(
            self.session,
            start_t=base_time - datetime.timedelta(hours=2),
            end_t=base_time + datetime.timedelta(minutes=1),
        )

        self.assertEqual(result, [])

    def test_high_humidity_updates_last_report_once(self):
        base_time = datetime.datetime.now(datetime.UTC).replace(microsecond=0)

        house = House(address="Pantry House")
        room_type = RoomType(name="Pantry Type")
        pantry_room = Room(name="pantry", roomType=room_type)
        pantry_location = Location(house=house, room=pantry_room)
        pantry_node = Node(id=1001, location=pantry_location)

        pantry_reading = Reading(
            time=base_time,
            typeId=2,
            value=THRESHOLD + 5,
            node=pantry_node,
            location=pantry_location,
        )

        self.session.add_all(
            [house, room_type, pantry_room, pantry_location, pantry_node, pantry_reading]
        )
        self.session.flush()

        result = pantry_humid(
            self.session,
            start_t=base_time - datetime.timedelta(hours=2),
            end_t=base_time + datetime.timedelta(minutes=1),
        )

        self.assertEqual(len(result), 1)
        last_report = (
            self.session.query(LastReport)
            .filter(LastReport.name == "PantryHumidityHigh")
            .one()
        )
        self.assertEqual(last_report.value, "True")

        result = pantry_humid(
            self.session,
            start_t=base_time - datetime.timedelta(hours=2),
            end_t=base_time + datetime.timedelta(minutes=1),
        )

        self.assertEqual(result, [])

    def test_reports_recovery_after_high_humidity(self):
        base_time = datetime.datetime.now(datetime.UTC).replace(microsecond=0)

        house = House(address="Pantry House")
        room_type = RoomType(name="Pantry Type")
        pantry_room = Room(name="pantry", roomType=room_type)
        pantry_location = Location(house=house, room=pantry_room)
        pantry_node = Node(id=1001, location=pantry_location)

        pantry_reading = Reading(
            time=base_time,
            typeId=2,
            value=THRESHOLD - 5,
            node=pantry_node,
            location=pantry_location,
        )

        self.session.add_all(
            [
                house,
                room_type,
                pantry_room,
                pantry_location,
                pantry_node,
                pantry_reading,
                LastReport(name="PantryHumidityHigh", value="True"),
            ]
        )
        self.session.flush()

        result = pantry_humid(
            self.session,
            start_t=base_time - datetime.timedelta(hours=2),
            end_t=base_time + datetime.timedelta(minutes=1),
        )

        self.assertEqual(len(result), 1)
        self.assertIn("Pantry humidity has recovered", result[0])
        last_report = (
            self.session.query(LastReport)
            .filter(LastReport.name == "PantryHumidityHigh")
            .one()
        )
        self.assertEqual(last_report.value, "False")
